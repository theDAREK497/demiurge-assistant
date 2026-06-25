from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from worldbuilder_core.models import Entity, Relationship, ViewerRole, World, WorldRule
from worldbuilder_core.schemas import EntityRead, RelationshipRead, WorldContextRead, WorldRead, WorldRuleRead


class RetrievalError(Exception):
    """Base error for retrieval operations."""


class RetrievalWorldNotFoundError(RetrievalError):
    pass


def build_world_context(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole = ViewerRole.master,
    query: str | None = None,
    max_entities: int = 12,
    max_rules: int = 8,
    max_relationships: int = 24,
) -> WorldContextRead:
    world = session.get(World, world_id)
    if world is None:
        raise RetrievalWorldNotFoundError(f"World {world_id!r} not found")

    rules = _select_rules(session, world_id, role=role, max_rules=max_rules)
    entities = _select_entities(session, world_id, role=role, query=query, max_entities=max_entities)
    relationships = _select_relationships(
        session,
        world_id,
        role=role,
        entity_ids=[entity.id for entity in entities],
        max_relationships=max_relationships,
    )

    return WorldContextRead(
        world=WorldRead.model_validate(world),
        role=role,
        query=query,
        entities=[EntityRead.model_validate(entity) for entity in entities],
        relationships=[RelationshipRead.model_validate(relationship) for relationship in relationships],
        world_rules=[WorldRuleRead.model_validate(rule) for rule in rules],
        context_text=render_context_text(world, rules=rules, entities=entities, relationships=relationships),
    )


def _select_rules(session: Session, world_id: str, *, role: ViewerRole, max_rules: int) -> list[WorldRule]:
    stmt: Select[tuple[WorldRule]] = (
        select(WorldRule)
        .where(WorldRule.world_id == world_id, WorldRule.is_active.is_(True))
        .order_by(WorldRule.priority.desc(), WorldRule.created_at.asc())
        .limit(max_rules)
    )
    if role == ViewerRole.player:
        stmt = stmt.where(WorldRule.is_secret.is_(False))
    return list(session.scalars(stmt))


def _select_entities(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole,
    query: str | None,
    max_entities: int,
) -> list[Entity]:
    stmt: Select[tuple[Entity]] = select(Entity).where(Entity.world_id == world_id)
    if role == ViewerRole.player:
        stmt = stmt.where(Entity.is_secret.is_(False))
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(or_(Entity.name.ilike(pattern), Entity.summary.ilike(pattern), Entity.description.ilike(pattern)))
    stmt = stmt.order_by(Entity.updated_at.desc(), Entity.name.asc()).limit(max_entities)
    return list(session.scalars(stmt))


def _select_relationships(
    session: Session,
    world_id: str,
    *,
    role: ViewerRole,
    entity_ids: list[str],
    max_relationships: int,
) -> list[Relationship]:
    if not entity_ids:
        return []

    stmt: Select[tuple[Relationship]] = (
        select(Relationship)
        .where(
            Relationship.world_id == world_id,
            (Relationship.source_entity_id.in_(entity_ids)) | (Relationship.target_entity_id.in_(entity_ids)),
        )
        .order_by(Relationship.updated_at.desc(), Relationship.created_at.desc())
        .limit(max_relationships)
    )
    if role == ViewerRole.player:
        stmt = stmt.where(Relationship.is_secret.is_(False))

    relationships = list(session.scalars(stmt))
    if role == ViewerRole.player:
        relationships = [
            relationship
            for relationship in relationships
            if not relationship.source_entity.is_secret and not relationship.target_entity.is_secret
        ]
    return relationships


def render_context_text(
    world: World,
    *,
    rules: list[WorldRule],
    entities: list[Entity],
    relationships: list[Relationship],
) -> str:
    lines = [f"World: {world.name}"]
    if world.description:
        lines.append(f"Description: {world.description}")

    if rules:
        lines.append("")
        lines.append("World rules:")
        for rule in rules:
            lines.append(f"- P{rule.priority}: if {rule.condition} then {rule.effect}")

    if entities:
        lines.append("")
        lines.append("Relevant entities:")
        for entity in entities:
            detail = entity.summary or entity.description or "No summary."
            lines.append(f"- {entity.type.value}: {entity.name} [{entity.id}] - {detail}")

    if relationships:
        lines.append("")
        lines.append("Relevant relationships:")
        for relationship in relationships:
            source = relationship.source_entity.name
            target = relationship.target_entity.name
            label = relationship.label or relationship.type
            lines.append(f"- {source} --{label}--> {target}")

    return "\n".join(lines)

