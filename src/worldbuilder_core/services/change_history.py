from copy import deepcopy

from sqlalchemy.orm import Session

from worldbuilder_core.models import Entity, EntityRevision, Relationship, WorldChange


def entity_snapshot(entity: Entity) -> dict:
    return {
        "id": entity.id,
        "world_id": entity.world_id,
        "type": entity.type,
        "name": entity.name,
        "summary": entity.summary,
        "description": entity.description,
        "aliases": deepcopy(entity.aliases),
        "tags": deepcopy(entity.tags),
        "is_secret": entity.is_secret,
        "status": entity.status.value,
        "attributes": deepcopy(entity.attributes),
    }


def relationship_snapshot(relationship: Relationship) -> dict:
    return {
        "id": relationship.id,
        "world_id": relationship.world_id,
        "source_entity_id": relationship.source_entity_id,
        "target_entity_id": relationship.target_entity_id,
        "type": relationship.type,
        "label": relationship.label,
        "description": relationship.description,
        "confidence": relationship.confidence,
        "weight": relationship.weight,
        "valid_from": relationship.valid_from,
        "valid_to": relationship.valid_to,
        "evidence": relationship.evidence,
        "is_secret": relationship.is_secret,
        "status": relationship.status.value,
        "attributes": deepcopy(relationship.attributes),
    }


def record_entity_change(
    session: Session,
    entity: Entity,
    change_kind: str,
    *,
    before_state: dict | None = None,
    source_type: str = "user_action",
    source_id: str | None = None,
    effective_at: str | None = None,
    summary: str | None = None,
    evidence: str | None = None,
    confidence: float = 1.0,
    causal_change_ids: list[str] | None = None,
    change_note: str | None = None,
) -> WorldChange:
    after_state = None if change_kind == "deleted" else entity_snapshot(entity)
    before_state = deepcopy(before_state)
    causal_ids = list(causal_change_ids or [])
    change = WorldChange(
        world_id=entity.world_id,
        subject_type="entity",
        subject_id=entity.id,
        subject_name=entity.name,
        change_kind=change_kind,
        source_type=source_type,
        source_id=source_id,
        summary=summary or _default_entity_summary(entity.name, change_kind),
        effective_at=effective_at,
        before_state=before_state,
        after_state=after_state,
        evidence=evidence,
        confidence=confidence,
        causal_change_ids=causal_ids,
        is_secret=entity.is_secret,
    )
    revision = EntityRevision(
        world_id=entity.world_id,
        entity_id=entity.id,
        change_kind=change_kind,
        source_type=source_type,
        source_id=source_id,
        effective_at=effective_at,
        before_state=before_state,
        after_state=after_state,
        change_note=change_note,
        evidence=evidence,
        confidence=confidence,
        causal_change_ids=causal_ids,
        is_secret=entity.is_secret,
    )
    session.add_all([change, revision])
    return change


def record_relationship_change(
    session: Session,
    relationship: Relationship,
    change_kind: str,
    *,
    before_state: dict | None = None,
    source_type: str = "user_action",
    source_id: str | None = None,
    summary: str | None = None,
    evidence: str | None = None,
) -> WorldChange:
    after_state = None if change_kind == "deleted" else relationship_snapshot(relationship)
    source_name = _entity_name(relationship.source_entity, relationship.source_entity_id)
    target_name = _entity_name(relationship.target_entity, relationship.target_entity_id)
    label = relationship.label or relationship.type
    return _record_change(
        session,
        world_id=relationship.world_id,
        subject_type="relationship",
        subject_id=relationship.id,
        subject_name=f"{source_name} -> {target_name}",
        change_kind=change_kind,
        source_type=source_type,
        source_id=source_id,
        summary=summary or f"Relationship {change_kind}: {source_name} --{label}--> {target_name}",
        effective_at=relationship.valid_from,
        before_state=before_state,
        after_state=after_state,
        evidence=evidence or relationship.evidence,
        confidence=relationship.confidence,
        is_secret=relationship.is_secret,
    )


def record_world_change(
    session: Session,
    *,
    world_id: str,
    subject_type: str,
    subject_id: str | None,
    subject_name: str | None,
    change_kind: str,
    source_type: str,
    source_id: str | None,
    summary: str,
    effective_at: str | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    evidence: str | None = None,
    confidence: float = 1.0,
    causal_change_ids: list[str] | None = None,
    supersedes_change_id: str | None = None,
    is_secret: bool = False,
) -> WorldChange:
    return _record_change(
        session,
        world_id=world_id,
        subject_type=subject_type,
        subject_id=subject_id,
        subject_name=subject_name,
        change_kind=change_kind,
        source_type=source_type,
        source_id=source_id,
        summary=summary,
        effective_at=effective_at,
        before_state=before_state,
        after_state=after_state,
        evidence=evidence,
        confidence=confidence,
        causal_change_ids=causal_change_ids,
        supersedes_change_id=supersedes_change_id,
        is_secret=is_secret,
    )


def _record_change(session: Session, **values) -> WorldChange:
    values["before_state"] = deepcopy(values.get("before_state"))
    values["after_state"] = deepcopy(values.get("after_state"))
    values["causal_change_ids"] = list(values.get("causal_change_ids") or [])
    change = WorldChange(**values)
    session.add(change)
    return change


def _default_entity_summary(name: str, change_kind: str) -> str:
    labels = {"created": "Entity created", "updated": "Entity updated", "deleted": "Entity deleted"}
    return f"{labels.get(change_kind, 'Entity changed')}: {name}"


def _entity_name(entity: Entity | None, fallback: str) -> str:
    return entity.name if entity is not None else fallback
