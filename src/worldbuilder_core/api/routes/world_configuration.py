from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import (
    Entity,
    EntityTypeDefinition,
    QuestStatusDefinition,
    World,
)
from worldbuilder_core.schemas import (
    EntityTypeDefinitionCreate,
    EntityTypeDefinitionRead,
    EntityTypeDefinitionUpdate,
    QuestStatusDefinitionCreate,
    QuestStatusDefinitionRead,
    QuestStatusDefinitionUpdate,
)
from worldbuilder_core.services.world_configuration import (
    ensure_entity_types,
    ensure_quest_statuses,
    humanize_key,
    normalize_key,
)

router = APIRouter(tags=["world-configuration"])


def _ensure_world(session: DbSession, world_id: str) -> None:
    if session.get(World, world_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")


@router.get("/worlds/{world_id}/entity-types", response_model=list[EntityTypeDefinitionRead])
def list_entity_types(world_id: str, session: DbSession) -> list[EntityTypeDefinition]:
    _ensure_world(session, world_id)
    ensure_entity_types(session, world_id)
    session.commit()
    return list(
        session.scalars(
            select(EntityTypeDefinition)
            .where(EntityTypeDefinition.world_id == world_id)
            .order_by(EntityTypeDefinition.position, EntityTypeDefinition.name)
        )
    )


@router.post(
    "/worlds/{world_id}/entity-types",
    response_model=EntityTypeDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_entity_type(
    world_id: str,
    payload: EntityTypeDefinitionCreate,
    session: DbSession,
) -> EntityTypeDefinition:
    _ensure_world(session, world_id)
    key = normalize_key(payload.key or payload.name)
    existing = session.scalar(
        select(EntityTypeDefinition).where(
            EntityTypeDefinition.world_id == world_id,
            EntityTypeDefinition.key == key,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entity type already exists")
    position = session.scalar(
        select(func.coalesce(func.max(EntityTypeDefinition.position), -1)).where(
            EntityTypeDefinition.world_id == world_id
        )
    )
    definition = EntityTypeDefinition(
        world_id=world_id,
        key=key,
        name=payload.name.strip() or humanize_key(key),
        color=payload.color.upper(),
        description=payload.description,
        position=int(position if position is not None else -1) + 1,
    )
    session.add(definition)
    session.commit()
    session.refresh(definition)
    return definition


@router.patch("/entity-types/{type_id}", response_model=EntityTypeDefinitionRead)
def update_entity_type(
    type_id: str,
    payload: EntityTypeDefinitionUpdate,
    session: DbSession,
) -> EntityTypeDefinition:
    definition = session.get(EntityTypeDefinition, type_id)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(definition, key, value.upper() if key == "color" else value)
    session.commit()
    session.refresh(definition)
    return definition


@router.delete("/entity-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity_type(type_id: str, session: DbSession) -> None:
    definition = session.get(EntityTypeDefinition, type_id)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity type not found")
    if definition.is_builtin:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Built-in entity types cannot be deleted")
    usage = session.scalar(
        select(func.count(Entity.id)).where(
            Entity.world_id == definition.world_id,
            Entity.type == definition.key,
        )
    )
    if usage:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entity type is in use")
    session.delete(definition)
    session.commit()


@router.get("/worlds/{world_id}/quest-statuses", response_model=list[QuestStatusDefinitionRead])
def list_quest_statuses(world_id: str, session: DbSession) -> list[QuestStatusDefinition]:
    _ensure_world(session, world_id)
    ensure_quest_statuses(session, world_id)
    session.commit()
    return list(
        session.scalars(
            select(QuestStatusDefinition)
            .where(QuestStatusDefinition.world_id == world_id)
            .order_by(QuestStatusDefinition.position, QuestStatusDefinition.name)
        )
    )


@router.post(
    "/worlds/{world_id}/quest-statuses",
    response_model=QuestStatusDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_quest_status(
    world_id: str,
    payload: QuestStatusDefinitionCreate,
    session: DbSession,
) -> QuestStatusDefinition:
    _ensure_world(session, world_id)
    key = normalize_key(payload.key or payload.name)
    existing = session.scalar(
        select(QuestStatusDefinition).where(
            QuestStatusDefinition.world_id == world_id,
            QuestStatusDefinition.key == key,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Quest status already exists")
    position = session.scalar(
        select(func.coalesce(func.max(QuestStatusDefinition.position), -1)).where(
            QuestStatusDefinition.world_id == world_id
        )
    )
    definition = QuestStatusDefinition(
        world_id=world_id,
        key=key,
        name=payload.name.strip(),
        color=payload.color.upper(),
        position=int(position if position is not None else -1) + 1,
    )
    session.add(definition)
    session.commit()
    session.refresh(definition)
    return definition


@router.patch("/quest-statuses/{status_id}", response_model=QuestStatusDefinitionRead)
def update_quest_status(
    status_id: str,
    payload: QuestStatusDefinitionUpdate,
    session: DbSession,
) -> QuestStatusDefinition:
    definition = session.get(QuestStatusDefinition, status_id)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest status not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(definition, key, value.upper() if key == "color" else value)
    session.commit()
    session.refresh(definition)
    return definition


@router.delete("/quest-statuses/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quest_status(status_id: str, session: DbSession) -> None:
    definition = session.get(QuestStatusDefinition, status_id)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest status not found")
    remaining = list(
        session.scalars(
            select(QuestStatusDefinition)
            .where(
                QuestStatusDefinition.world_id == definition.world_id,
                QuestStatusDefinition.id != definition.id,
            )
            .order_by(QuestStatusDefinition.position)
        )
    )
    if not remaining:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="At least one quest status is required")
    fallback = remaining[0].key
    quests = [
        entity
        for entity in session.scalars(select(Entity).where(Entity.world_id == definition.world_id))
        if "quest" in (entity.tags or []) or (entity.attributes or {}).get("module") == "quest"
    ]
    for quest in quests:
        attributes = dict(quest.attributes or {})
        if attributes.get("quest_status", "backlog") == definition.key:
            attributes["quest_status"] = fallback
            quest.attributes = attributes
    session.delete(definition)
    session.commit()
