import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from worldbuilder_core.models import EntityTypeDefinition, QuestStatusDefinition

DEFAULT_ENTITY_TYPES = (
    ("character", "Character", "#C85D5D"),
    ("location", "Location", "#4F8B6D"),
    ("faction", "Faction", "#6C6FB3"),
    ("item", "Item", "#C28B3C"),
    ("event", "Event", "#B45F8D"),
    ("clue", "Clue", "#4D91A8"),
    ("concept", "Concept", "#7C6A58"),
)

DEFAULT_QUEST_STATUSES = (
    ("backlog", "Backlog", "#6B7280"),
    ("active", "Active", "#3B82F6"),
    ("blocked", "Blocked", "#D97706"),
    ("done", "Done", "#2E8B57"),
)

FALLBACK_ENTITY_COLOR = "#6B7280"


def normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = re.sub(r"[\s/]+", "_", normalized)
    normalized = "".join(char for char in normalized if char.isalnum() or char in "_-")
    normalized = re.sub(r"[_-]{2,}", "_", normalized).strip("_-")
    if not normalized:
        raise ValueError("Key must contain letters or numbers")
    return normalized[:80]


def humanize_key(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").strip().title()


def ensure_entity_types(session: Session, world_id: str) -> None:
    existing_types = set(
        session.scalars(select(EntityTypeDefinition.key).where(EntityTypeDefinition.world_id == world_id))
    )
    for position, (key, name, color) in enumerate(DEFAULT_ENTITY_TYPES):
        if key not in existing_types:
            session.add(
                EntityTypeDefinition(
                    world_id=world_id,
                    key=key,
                    name=name,
                    color=color,
                    is_builtin=True,
                    position=position,
                )
            )
    session.flush()


def ensure_quest_statuses(session: Session, world_id: str) -> None:
    existing_statuses = set(
        session.scalars(select(QuestStatusDefinition.key).where(QuestStatusDefinition.world_id == world_id))
    )
    for position, (key, name, color) in enumerate(DEFAULT_QUEST_STATUSES):
        if key not in existing_statuses:
            session.add(
                QuestStatusDefinition(
                    world_id=world_id,
                    key=key,
                    name=name,
                    color=color,
                    position=position,
                )
            )
    session.flush()


def ensure_world_configuration(session: Session, world_id: str) -> None:
    ensure_entity_types(session, world_id)
    ensure_quest_statuses(session, world_id)


def ensure_entity_type(
    session: Session,
    world_id: str,
    raw_key: str,
    *,
    name: str | None = None,
    color: str = FALLBACK_ENTITY_COLOR,
) -> EntityTypeDefinition:
    ensure_entity_types(session, world_id)
    key = normalize_key(raw_key)
    definition = session.scalar(
        select(EntityTypeDefinition).where(
            EntityTypeDefinition.world_id == world_id,
            EntityTypeDefinition.key == key,
        )
    )
    if definition is not None:
        return definition

    position = session.scalar(
        select(func.coalesce(func.max(EntityTypeDefinition.position), -1)).where(
            EntityTypeDefinition.world_id == world_id
        )
    )
    definition = EntityTypeDefinition(
        world_id=world_id,
        key=key,
        name=(name or humanize_key(key))[:120],
        color=color,
        position=int(position if position is not None else -1) + 1,
    )
    session.add(definition)
    session.flush()
    return definition
