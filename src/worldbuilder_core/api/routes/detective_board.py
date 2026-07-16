from math import ceil, sqrt

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import DetectiveBoardConnection, DetectiveBoardNode, Entity, ViewerRole, World
from worldbuilder_core.schemas import (
    DetectiveBoardConnectionCreate,
    DetectiveBoardConnectionRead,
    DetectiveBoardConnectionUpdate,
    DetectiveBoardGenerateRequest,
    DetectiveBoardNodeCreate,
    DetectiveBoardNodeRead,
    DetectiveBoardNodeUpdate,
    DetectiveBoardRead,
)
from worldbuilder_core.services.detective_generation import DetectiveGenerationParseError, generate_detective_board_with_llm
from worldbuilder_core.services.llm import LLMProviderError, build_llm_client
from worldbuilder_core.services.llm_settings import get_llm_runtime_settings
from worldbuilder_core.services.retrieval import build_world_context

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
            .options(joinedload(DetectiveBoardNode.entity))
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
    "/worlds/{world_id}/detective-board/generate",
    response_model=DetectiveBoardRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_detective_board(
    world_id: str,
    payload: DetectiveBoardGenerateRequest,
    session: DbSession,
) -> DetectiveBoardRead:
    ensure_world(session, world_id)
    existing_node = session.scalar(
        select(DetectiveBoardNode.id).where(DetectiveBoardNode.world_id == world_id).limit(1)
    )
    if existing_node:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Detective board is not empty")

    runtime_settings = get_llm_runtime_settings(session)
    model = payload.model or runtime_settings.model_for("extractor")
    context = build_world_context(
        session,
        world_id,
        role=ViewerRole.master,
        query="detective board clues suspects motives locations",
        max_entities=payload.max_nodes,
    )
    client = build_llm_client(runtime_settings, default_model=model)
    try:
        generated = await generate_detective_board_with_llm(
            llm_client=client,
            context_text=context.context_text,
            output_language=payload.output_language,
            max_nodes=payload.max_nodes,
            model=model,
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except DetectiveGenerationParseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Board generation failed: {exc}") from exc

    valid_entity_ids = set(session.scalars(select(Entity.id).where(Entity.world_id == world_id)))
    columns = max(2, ceil(sqrt(max(len(generated.nodes), 1) * 1.6)))
    rows = max(1, ceil(len(generated.nodes) / columns))
    node_ids: dict[str, str] = {}
    for index, draft in enumerate(generated.nodes):
        column = index % columns
        row = index // columns
        node = DetectiveBoardNode(
            world_id=world_id,
            entity_id=draft.entity_id if draft.entity_id in valid_entity_ids else None,
            title=draft.title,
            note=draft.note,
            evidence_url=draft.evidence_url,
            x=(column + 1) / (columns + 1),
            y=(row + 1) / (rows + 1),
            is_secret=draft.is_secret,
        )
        session.add(node)
        session.flush()
        node_ids[draft.client_id] = node.id

    for draft in generated.connections:
        source_id = node_ids.get(draft.source_client_id)
        target_id = node_ids.get(draft.target_client_id)
        if not source_id or not target_id or source_id == target_id:
            continue
        session.add(
            DetectiveBoardConnection(
                world_id=world_id,
                source_node_id=source_id,
                target_node_id=target_id,
                label=draft.label,
                note=draft.note,
                is_secret=draft.is_secret,
            )
        )
    session.commit()
    return get_detective_board(world_id, session, ViewerRole.master)


@router.delete("/worlds/{world_id}/detective-board", status_code=status.HTTP_204_NO_CONTENT)
def delete_detective_board(world_id: str, session: DbSession) -> None:
    ensure_world(session, world_id)
    session.execute(delete(DetectiveBoardConnection).where(DetectiveBoardConnection.world_id == world_id))
    session.execute(delete(DetectiveBoardNode).where(DetectiveBoardNode.world_id == world_id))
    session.commit()


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
