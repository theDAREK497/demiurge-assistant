from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import Entity, Relationship, ViewerRole, World
from worldbuilder_core.schemas import (
    EntityCreate,
    EntityDuplicateCandidate,
    EntityMergeRequest,
    EntityMergeResult,
    EntityRead,
    EntityUpdate,
)
from worldbuilder_core.services.assets import (
    cleanup_unreferenced_assets,
    entity_asset_url,
)
from worldbuilder_core.services.change_history import (
    entity_snapshot,
    record_entity_change,
    record_relationship_change,
    relationship_snapshot,
)
from worldbuilder_core.services.entity_duplicates import (
    EntityMergeConflict,
    find_duplicate_candidates,
    merge_entities,
)
from worldbuilder_core.services.world_configuration import ensure_entity_type

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
    ensure_entity_type(session, world_id, payload.type)
    entity = Entity(world_id=world_id, **payload.model_dump())
    session.add(entity)
    session.flush()
    record_entity_change(session, entity, "created")
    session.commit()
    session.refresh(entity)
    return entity


@router.get("/worlds/{world_id}/entities", response_model=list[EntityRead])
def list_entities(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
    type: str | None = None,
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


@router.get(
    "/worlds/{world_id}/entities/duplicate-candidates",
    response_model=list[EntityDuplicateCandidate],
)
def list_entity_duplicate_candidates(world_id: str, session: DbSession) -> list[dict]:
    ensure_world(session, world_id)
    return find_duplicate_candidates(session, world_id)


@router.post("/worlds/{world_id}/entities/merge", response_model=EntityMergeResult)
def merge_world_entities(world_id: str, payload: EntityMergeRequest, session: DbSession) -> EntityMergeResult:
    ensure_world(session, world_id)
    try:
        outcome = merge_entities(session, world_id, payload)
    except EntityMergeConflict as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entities could not be merged") from exc
    return EntityMergeResult(
        entity=EntityRead.model_validate(outcome.entity),
        deleted_entity_id=outcome.deleted_entity_id,
        rewired_relationships=outcome.rewired_relationships,
        merged_relationships=outcome.merged_relationships,
        removed_self_relationships=outcome.removed_self_relationships,
        updated_references=outcome.updated_references,
    )


@router.get("/entities/{entity_id}", response_model=EntityRead)
def get_entity(entity_id: str, session: DbSession, role: ViewerRole = ViewerRole.master) -> Entity:
    return ensure_visible(session.get(Entity, entity_id), role)


@router.patch("/entities/{entity_id}", response_model=EntityRead)
def update_entity(entity_id: str, payload: EntityUpdate, session: DbSession) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    previous_asset_url = entity_asset_url(entity.attributes)
    previous_state = entity_snapshot(entity)
    if payload.type is not None:
        ensure_entity_type(session, entity.world_id, payload.type)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, key, value)

    session.add(entity)
    session.flush()
    record_entity_change(session, entity, "updated", before_state=previous_state)
    session.commit()
    session.refresh(entity)
    cleanup_unreferenced_assets(session, {previous_asset_url})
    return entity


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(entity_id: str, session: DbSession) -> None:
    entity = session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    previous_asset_url = entity_asset_url(entity.attributes)
    previous_state = entity_snapshot(entity)
    record_entity_change(session, entity, "deleted", before_state=previous_state)
    relationships = list(
        session.scalars(
            select(Relationship).where(
                (Relationship.source_entity_id == entity.id) | (Relationship.target_entity_id == entity.id)
            )
        )
    )
    for relationship in relationships:
        record_relationship_change(
            session,
            relationship,
            "deleted",
            before_state=relationship_snapshot(relationship),
            summary=f"Relationship deleted with entity: {entity.name}",
        )
    session.delete(entity)
    session.commit()
    cleanup_unreferenced_assets(session, {previous_asset_url})
