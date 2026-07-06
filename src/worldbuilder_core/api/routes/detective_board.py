from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import DetectiveBoardConnection, DetectiveBoardNode, Entity, ViewerRole, World
from worldbuilder_core.schemas import (
    DetectiveBoardConnectionCreate,
    DetectiveBoardConnectionRead,
    DetectiveBoardConnectionUpdate,
    DetectiveBoardNodeCreate,
    DetectiveBoardNodeRead,
    DetectiveBoardNodeUpdate,
    DetectiveBoardRead,
)

router = APIRouter(tags=["detective board"])


def ensure_world(session: DbSession, world_id: str) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


def ensure_entity_in_world(session: DbSession, entity_id: str, world_id: str) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None or entity.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Entity does not belong to world")
    return entity


def ensure_node_in_world(session: DbSession, node_id: str, world_id: str) -> DetectiveBoardNode:
    node = session.get(DetectiveBoardNode, node_id)
    if node is None or node.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Detective board node does not belong to world")
    return node


@router.get("/worlds/{world_id}/detective-board", response_model=DetectiveBoardRead)
def get_detective_board(world_id: str, session: DbSession, role: ViewerRole = ViewerRole.master) -> DetectiveBoardRead:
    ensure_world(session, world_id)
    nodes = list(
        session.scalars(
            select(DetectiveBoardNode)
            .where(DetectiveBoardNode.world_id == world_id)
            .order_by(DetectiveBoardNode.created_at.asc(), DetectiveBoardNode.id.asc())
        )
    )
    visible_nodes = _visible_nodes(nodes, role)
    visible_node_ids = {node.id for node in visible_nodes}

    connections = list(
        session.scalars(
            select(DetectiveBoardConnection)
            .where(DetectiveBoardConnection.world_id == world_id)
            .order_by(DetectiveBoardConnection.created_at.asc(), DetectiveBoardConnection.id.asc())
        )
    )
    visible_connections = [
        connection
        for connection in connections
        if connection.source_node_id in visible_node_ids
        and connection.target_node_id in visible_node_ids
        and (role == ViewerRole.master or not connection.is_secret)
    ]
    return DetectiveBoardRead(
        nodes=[DetectiveBoardNodeRead.model_validate(node) for node in visible_nodes],
        connections=[DetectiveBoardConnectionRead.model_validate(connection) for connection in visible_connections],
    )


@router.post(
    "/worlds/{world_id}/detective-board/nodes",
    response_model=DetectiveBoardNodeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_detective_node(world_id: str, payload: DetectiveBoardNodeCreate, session: DbSession) -> DetectiveBoardNode:
    ensure_world(session, world_id)
    if payload.entity_id:
        ensure_entity_in_world(session, payload.entity_id, world_id)

    node = DetectiveBoardNode(world_id=world_id, **payload.model_dump())
    session.add(node)
    session.commit()
    session.refresh(node)
    return node


@router.patch("/detective-board/nodes/{node_id}", response_model=DetectiveBoardNodeRead)
def update_detective_node(node_id: str, payload: DetectiveBoardNodeUpdate, session: DbSession) -> DetectiveBoardNode:
    node = session.get(DetectiveBoardNode, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detective board node not found")

    data = payload.model_dump(exclude_unset=True)
    entity_id = data.get("entity_id", node.entity_id)
    if entity_id:
        ensure_entity_in_world(session, entity_id, node.world_id)

    for key, value in data.items():
        setattr(node, key, value)

    session.add(node)
    session.commit()
    session.refresh(node)
    return node


@router.delete("/detective-board/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_detective_node(node_id: str, session: DbSession) -> None:
    node = session.get(DetectiveBoardNode, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detective board node not found")
    session.delete(node)
    session.commit()


@router.post(
    "/worlds/{world_id}/detective-board/connections",
    response_model=DetectiveBoardConnectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_detective_connection(
    world_id: str,
    payload: DetectiveBoardConnectionCreate,
    session: DbSession,
) -> DetectiveBoardConnection:
    ensure_world(session, world_id)
    ensure_node_in_world(session, payload.source_node_id, world_id)
    ensure_node_in_world(session, payload.target_node_id, world_id)
    if payload.source_node_id == payload.target_node_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Connection endpoints must differ")

    connection = DetectiveBoardConnection(world_id=world_id, **payload.model_dump())
    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


@router.patch("/detective-board/connections/{connection_id}", response_model=DetectiveBoardConnectionRead)
def update_detective_connection(
    connection_id: str,
    payload: DetectiveBoardConnectionUpdate,
    session: DbSession,
) -> DetectiveBoardConnection:
    connection = session.get(DetectiveBoardConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detective board connection not found")

    data = payload.model_dump(exclude_unset=True)
    source_node_id = data.get("source_node_id", connection.source_node_id)
    target_node_id = data.get("target_node_id", connection.target_node_id)
    ensure_node_in_world(session, source_node_id, connection.world_id)
    ensure_node_in_world(session, target_node_id, connection.world_id)
    if source_node_id == target_node_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Connection endpoints must differ")

    for key, value in data.items():
        setattr(connection, key, value)

    session.add(connection)
    session.commit()
    session.refresh(connection)
    return connection


@router.delete("/detective-board/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_detective_connection(connection_id: str, session: DbSession) -> None:
    connection = session.get(DetectiveBoardConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detective board connection not found")
    session.delete(connection)
    session.commit()


def _visible_nodes(nodes: list[DetectiveBoardNode], role: ViewerRole) -> list[DetectiveBoardNode]:
    if role == ViewerRole.master:
        return nodes
    return [node for node in nodes if not node.is_secret and (not node.entity or not node.entity.is_secret)]
