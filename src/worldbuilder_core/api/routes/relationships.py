from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import Entity, Relationship, ViewerRole, World
from worldbuilder_core.schemas import RelationshipCreate, RelationshipRead, RelationshipUpdate

router = APIRouter(tags=["relationships"])


def ensure_world(session: DbSession, world_id: str) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


def ensure_entity_in_world(session: DbSession, entity_id: str, world_id: str) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None or entity.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Relationship entity is not in this world")
    return entity


def ensure_visible(relationship: Relationship | None, role: ViewerRole) -> Relationship:
    if relationship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    if role == ViewerRole.player and (
        relationship.is_secret or relationship.source_entity.is_secret or relationship.target_entity.is_secret
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    return relationship


@router.post("/worlds/{world_id}/relationships", response_model=RelationshipRead, status_code=status.HTTP_201_CREATED)
def create_relationship(world_id: str, payload: RelationshipCreate, session: DbSession) -> Relationship:
    ensure_world(session, world_id)
    ensure_entity_in_world(session, payload.source_entity_id, world_id)
    ensure_entity_in_world(session, payload.target_entity_id, world_id)

    relationship = Relationship(world_id=world_id, **payload.model_dump())
    session.add(relationship)
    session.commit()
    session.refresh(relationship)
    return relationship


@router.get("/worlds/{world_id}/relationships", response_model=list[RelationshipRead])
def list_relationships(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
    entity_id: str | None = None,
) -> list[Relationship]:
    ensure_world(session, world_id)
    stmt: Select[tuple[Relationship]] = select(Relationship).where(Relationship.world_id == world_id)
    if role == ViewerRole.player:
        stmt = stmt.where(Relationship.is_secret.is_(False))
    if entity_id is not None:
        stmt = stmt.where(
            (Relationship.source_entity_id == entity_id) | (Relationship.target_entity_id == entity_id)
        )
    relationships = list(session.scalars(stmt.order_by(Relationship.created_at.desc())))
    if role == ViewerRole.player:
        relationships = [
            relationship
            for relationship in relationships
            if not relationship.source_entity.is_secret and not relationship.target_entity.is_secret
        ]
    return relationships


@router.get("/relationships/{relationship_id}", response_model=RelationshipRead)
def get_relationship(
    relationship_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
) -> Relationship:
    return ensure_visible(session.get(Relationship, relationship_id), role)


@router.patch("/relationships/{relationship_id}", response_model=RelationshipRead)
def update_relationship(
    relationship_id: str,
    payload: RelationshipUpdate,
    session: DbSession,
) -> Relationship:
    relationship = session.get(Relationship, relationship_id)
    if relationship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")

    data = payload.model_dump(exclude_unset=True)
    source_id = data.get("source_entity_id", relationship.source_entity_id)
    target_id = data.get("target_entity_id", relationship.target_entity_id)
    ensure_entity_in_world(session, source_id, relationship.world_id)
    ensure_entity_in_world(session, target_id, relationship.world_id)

    for key, value in data.items():
        setattr(relationship, key, value)

    session.add(relationship)
    session.commit()
    session.refresh(relationship)
    return relationship


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(relationship_id: str, session: DbSession) -> None:
    relationship = session.get(Relationship, relationship_id)
    if relationship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found")
    session.delete(relationship)
    session.commit()
