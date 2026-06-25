from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import Entity, EntityType, ViewerRole, World
from worldbuilder_core.schemas import EntityCreate, EntityRead, EntityUpdate

router = APIRouter(tags=["entities"])


def ensure_world(session: DbSession, world_id: str) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


def ensure_visible(entity: Entity | None, role: ViewerRole) -> Entity:
    if entity is None or (role == ViewerRole.player and entity.is_secret):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    return entity


@router.post("/worlds/{world_id}/entities", response_model=EntityRead, status_code=status.HTTP_201_CREATED)
def create_entity(world_id: str, payload: EntityCreate, session: DbSession) -> Entity:
    ensure_world(session, world_id)
    entity = Entity(world_id=world_id, **payload.model_dump())
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


@router.get("/worlds/{world_id}/entities", response_model=list[EntityRead])
def list_entities(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
    type: EntityType | None = None,
    q: str | None = None,
    tag: str | None = Query(default=None),
) -> list[Entity]:
    ensure_world(session, world_id)
    stmt: Select[tuple[Entity]] = select(Entity).where(Entity.world_id == world_id)
    if role == ViewerRole.player:
        stmt = stmt.where(Entity.is_secret.is_(False))
    if type is not None:
        stmt = stmt.where(Entity.type == type)
    if q:
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))

    entities = list(session.scalars(stmt.order_by(Entity.name.asc())))
    if tag:
        entities = [entity for entity in entities if tag in entity.tags]
    return entities


@router.get("/entities/{entity_id}", response_model=EntityRead)
def get_entity(entity_id: str, session: DbSession, role: ViewerRole = ViewerRole.master) -> Entity:
    return ensure_visible(session.get(Entity, entity_id), role)


@router.patch("/entities/{entity_id}", response_model=EntityRead)
def update_entity(entity_id: str, payload: EntityUpdate, session: DbSession) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, key, value)

    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(entity_id: str, session: DbSession) -> None:
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    session.delete(entity)
    session.commit()

