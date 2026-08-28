from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from worldbuilder_core.models import DetectiveBoardNode, Entity, MapPin, Relationship
from worldbuilder_core.schemas import EntityMergeRequest
from worldbuilder_core.services.assets import cleanup_unreferenced_assets
from worldbuilder_core.services.change_history import (
    entity_snapshot,
    record_entity_change,
    record_relationship_change,
    relationship_snapshot,
)
from worldbuilder_core.services.relationship_history import build_relationship_revision

WORD_RE = re.compile(r"[\w\-]+", re.UNICODE)
STOP_WORDS = {
    "and",
    "the",
    "with",
    "from",
    "that",
    "this",
    "для",
    "его",
    "или",
    "как",
    "она",
    "они",
    "при",
    "что",
    "это",
}


class EntityMergeConflict(ValueError):
    pass


@dataclass(slots=True)
class EntityMergeOutcome:
    entity: Entity
    deleted_entity_id: str
    rewired_relationships: int
    merged_relationships: int
    removed_self_relationships: int
    updated_references: int


def find_duplicate_candidates(session: Session, world_id: str) -> list[dict[str, Any]]:
    entities = list(session.scalars(select(Entity).where(Entity.world_id == world_id).order_by(Entity.name)))
    relationships = list(session.scalars(select(Relationship).where(Relationship.world_id == world_id)))
    entity_by_id = {entity.id: entity for entity in entities}
    neighbor_names: dict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        source = entity_by_id.get(relationship.source_entity_id)
        target = entity_by_id.get(relationship.target_entity_id)
        if source is None or target is None:
            continue
        neighbor_names[source.id].add(_normalize(target.name))
        neighbor_names[target.id].add(_normalize(source.name))

    raw_candidates: list[dict[str, Any]] = []
    short_name_matches: dict[str, list[int]] = defaultdict(list)
    for index, left in enumerate(entities):
        for right in entities[index + 1 :]:
            if left.type != right.type:
                continue
            candidate = _compare_entities(left, right, neighbor_names)
            if candidate is None:
                continue
            candidate_index = len(raw_candidates)
            raw_candidates.append(candidate)
            if candidate["short_entity_id"]:
                short_name_matches[candidate["short_entity_id"]].append(candidate_index)

    for candidate_indexes in short_name_matches.values():
        if len(candidate_indexes) < 2:
            continue
        for candidate_index in candidate_indexes:
            candidate = raw_candidates[candidate_index]
            candidate["confidence"] = "ambiguous"
            candidate["score"] = min(candidate["score"], 0.59)
            candidate["reasons"].append("ambiguous_short_name")

    for candidate in raw_candidates:
        candidate.pop("short_entity_id", None)
    return sorted(raw_candidates, key=lambda item: (-item["score"], item["left"].name, item["right"].name))


def merge_entities(
    session: Session,
    world_id: str,
    payload: EntityMergeRequest,
) -> EntityMergeOutcome:
    primary = session.get(Entity, payload.primary_entity_id)
    duplicate = session.get(Entity, payload.duplicate_entity_id)
    if primary is None or primary.world_id != world_id or duplicate is None or duplicate.world_id != world_id:
        raise EntityMergeConflict("Entity not found in this world")
    if primary.id == duplicate.id:
        raise EntityMergeConflict("Choose two different entities")
    if primary.type != duplicate.type or payload.type != primary.type:
        raise EntityMergeConflict("Only entities of the same type can be merged")

    collision = session.scalar(
        select(Entity).where(
            Entity.world_id == world_id,
            Entity.type == payload.type,
            Entity.name == payload.name,
            Entity.id.not_in([primary.id, duplicate.id]),
        )
    )
    if collision is not None:
        raise EntityMergeConflict("Another entity already uses the selected name")

    primary_before = entity_snapshot(primary)
    duplicate_before = entity_snapshot(duplicate)
    previous_asset_urls = {
        _asset_url(primary.attributes),
        _asset_url(duplicate.attributes),
    }
    primary.name = payload.name.strip()
    primary.summary = payload.summary or _prefer_richer(primary.summary, duplicate.summary, limit=500)
    primary.description = _merge_distinct_text(payload.description or primary.description, duplicate.description, 100_000)
    primary.aliases = _unique_text(
        [
            *payload.aliases,
            *primary.aliases,
            *duplicate.aliases,
            primary_before["name"],
            duplicate.name,
        ],
        exclude={_normalize(primary.name)},
        limit=100,
    )
    primary.tags = _unique_text([*payload.tags, *primary.tags, *duplicate.tags], limit=100)
    primary.is_secret = bool(payload.is_secret or primary.is_secret or duplicate.is_secret)
    primary.status = payload.status
    primary.attributes = {**duplicate.attributes, **primary.attributes, **payload.attributes}
    session.add(primary)

    relationships = list(session.scalars(select(Relationship).where(Relationship.world_id == world_id)))
    untouched = [
        relationship
        for relationship in relationships
        if duplicate.id not in {relationship.source_entity_id, relationship.target_entity_id}
    ]
    relationship_index = {_relationship_key(relationship): relationship for relationship in untouched}
    rewired_relationships = 0
    merged_relationships = 0
    removed_self_relationships = 0
    for relationship in relationships:
        if duplicate.id not in {relationship.source_entity_id, relationship.target_entity_id}:
            continue
        before_state = relationship_snapshot(relationship)
        source_id = primary.id if relationship.source_entity_id == duplicate.id else relationship.source_entity_id
        target_id = primary.id if relationship.target_entity_id == duplicate.id else relationship.target_entity_id
        if source_id == target_id:
            record_relationship_change(
                session,
                relationship,
                "deleted",
                before_state=before_state,
                source_type="entity_merge",
                source_id=primary.id,
                summary=f"Self-relationship removed while merging {duplicate.name} into {primary.name}",
            )
            session.delete(relationship)
            removed_self_relationships += 1
            continue

        key = _relationship_key(relationship, source_id=source_id, target_id=target_id)
        existing = relationship_index.get(key)
        if existing is not None and existing.id != relationship.id:
            existing_before = relationship_snapshot(existing)
            _merge_relationship(existing, relationship)
            session.add(
                build_relationship_revision(
                    existing,
                    effective_at=existing.valid_from,
                    change_note=f"Merged duplicate entity {duplicate.name} into {primary.name}",
                )
            )
            record_relationship_change(
                session,
                existing,
                "updated",
                before_state=existing_before,
                source_type="entity_merge",
                source_id=primary.id,
                summary=f"Duplicate relationship merged after combining {duplicate.name} with {primary.name}",
            )
            record_relationship_change(
                session,
                relationship,
                "deleted",
                before_state=before_state,
                source_type="entity_merge",
                source_id=primary.id,
                summary=f"Duplicate relationship removed after combining {duplicate.name} with {primary.name}",
            )
            session.delete(relationship)
            merged_relationships += 1
            continue

        relationship.source_entity_id = source_id
        relationship.target_entity_id = target_id
        if source_id == primary.id:
            relationship.source_entity = primary
        if target_id == primary.id:
            relationship.target_entity = primary
        relationship_index[key] = relationship
        session.add(
            build_relationship_revision(
                relationship,
                effective_at=relationship.valid_from,
                change_note=f"Moved relationship from {duplicate.name} to {primary.name}",
            )
        )
        record_relationship_change(
            session,
            relationship,
            "updated",
            before_state=before_state,
            source_type="entity_merge",
            source_id=primary.id,
            summary=f"Relationship moved from {duplicate.name} to {primary.name}",
        )
        rewired_relationships += 1

    updated_references = 0
    for pin in session.scalars(
        select(MapPin).where(
            MapPin.world_id == world_id,
            (MapPin.map_entity_id == duplicate.id) | (MapPin.linked_entity_id == duplicate.id),
        )
    ):
        if pin.map_entity_id == duplicate.id:
            pin.map_entity_id = primary.id
            pin.map_entity = primary
        if pin.linked_entity_id == duplicate.id:
            pin.linked_entity_id = primary.id
            pin.linked_entity = primary
        updated_references += 1
    for node in session.scalars(
        select(DetectiveBoardNode).where(
            DetectiveBoardNode.world_id == world_id,
            DetectiveBoardNode.entity_id == duplicate.id,
        )
    ):
        node.entity_id = primary.id
        node.entity = primary
        updated_references += 1

    record_entity_change(
        session,
        primary,
        "updated",
        before_state=primary_before,
        source_type="entity_merge",
        source_id=duplicate.id,
        summary=f"Entity merged: {duplicate.name} -> {primary.name}",
        evidence="Confirmed manually in duplicate resolver",
        change_note="Merged duplicate data, aliases, relationships, and references",
    )
    record_entity_change(
        session,
        duplicate,
        "deleted",
        before_state=duplicate_before,
        source_type="entity_merge",
        source_id=primary.id,
        summary=f"Duplicate entity removed after merge: {duplicate.name}",
        evidence=f"Merged into {primary.name}",
        change_note=f"Merged into entity {primary.id}",
    )
    deleted_entity_id = duplicate.id
    session.delete(duplicate)
    session.commit()
    session.refresh(primary)
    previous_asset_urls.discard(_asset_url(primary.attributes))
    cleanup_unreferenced_assets(session, previous_asset_urls)
    return EntityMergeOutcome(
        entity=primary,
        deleted_entity_id=deleted_entity_id,
        rewired_relationships=rewired_relationships,
        merged_relationships=merged_relationships,
        removed_self_relationships=removed_self_relationships,
        updated_references=updated_references,
    )


def _compare_entities(
    left: Entity,
    right: Entity,
    neighbor_names: dict[str, set[str]],
) -> dict[str, Any] | None:
    left_names = _identity_names(left)
    right_names = _identity_names(right)
    exact_names = left_names & right_names
    left_tokens = _name_tokens(left.name)
    right_tokens = _name_tokens(right.name)
    subset_match = bool(left_tokens and right_tokens and (left_tokens < right_tokens or right_tokens < left_tokens))
    shared_neighbors = sorted(neighbor_names[left.id] & neighbor_names[right.id])
    detail_overlap = _detail_tokens(left) & _detail_tokens(right)
    if not exact_names and not subset_match:
        return None

    reasons: list[str] = []
    score = 0.0
    if exact_names:
        score += 0.7
        reasons.append("exact_name_or_alias")
    if subset_match:
        score += 0.42
        reasons.append("short_name")
    if shared_neighbors:
        score += min(0.25, 0.1 + 0.04 * len(shared_neighbors))
        reasons.append(f"shared_relationships:{len(shared_neighbors)}")
    if detail_overlap:
        score += min(0.2, 0.04 * len(detail_overlap))
        reasons.append(f"shared_details:{len(detail_overlap)}")
    score = min(1.0, round(score, 2))
    has_context = bool(shared_neighbors or detail_overlap)
    confidence = "strong" if exact_names and has_context else "possible" if score >= 0.62 else "ambiguous"
    short_entity_id = None
    if subset_match:
        short_entity_id = left.id if len(left_tokens) < len(right_tokens) else right.id
    return {
        "left": left,
        "right": right,
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
        "shared_relationship_names": shared_neighbors[:12],
        "short_entity_id": short_entity_id,
    }


def _identity_names(entity: Entity) -> set[str]:
    return {_normalize(value) for value in [entity.name, *entity.aliases] if _normalize(value)}


def _name_tokens(value: str) -> frozenset[str]:
    return frozenset(token for token in WORD_RE.findall(_normalize(value)) if len(token) > 1)


def _detail_tokens(entity: Entity) -> set[str]:
    values = [entity.summary or "", entity.description or "", *entity.tags]
    values.extend(str(value) for value in entity.attributes.values() if isinstance(value, (str, int, float)))
    return {
        token
        for token in WORD_RE.findall(_normalize(" ".join(values)))
        if len(token) >= 4 and token not in STOP_WORDS
    }


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е")
    return " ".join(WORD_RE.findall(text))


def _unique_text(
    values: list[str],
    *,
    exclude: set[str] | None = None,
    limit: int,
) -> list[str]:
    excluded = exclude or set()
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        normalized = _normalize(cleaned)
        if not cleaned or not normalized or normalized in excluded or normalized in seen:
            continue
        seen.add(normalized)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _prefer_richer(first: str | None, second: str | None, *, limit: int) -> str | None:
    values = [value.strip() for value in (first, second) if value and value.strip()]
    return max(values, key=len)[:limit] if values else None


def _merge_distinct_text(first: str | None, second: str | None, limit: int) -> str | None:
    values: list[str] = []
    normalized_values: list[str] = []
    for value in (first, second):
        cleaned = str(value or "").strip()
        normalized = _normalize(cleaned)
        if not normalized or any(normalized in known or known in normalized for known in normalized_values):
            continue
        values.append(cleaned)
        normalized_values.append(normalized)
    return "\n\n".join(values)[:limit] or None


def _relationship_key(
    relationship: Relationship,
    *,
    source_id: str | None = None,
    target_id: str | None = None,
) -> tuple[str, str, str, str, str, str]:
    return (
        source_id or relationship.source_entity_id,
        target_id or relationship.target_entity_id,
        _normalize(relationship.type),
        _normalize(relationship.label),
        relationship.valid_from or "",
        relationship.valid_to or "",
    )


def _merge_relationship(target: Relationship, source: Relationship) -> None:
    target.description = _merge_distinct_text(target.description, source.description, 100_000)
    target.evidence = _merge_distinct_text(target.evidence, source.evidence, 100_000)
    target.confidence = max(target.confidence, source.confidence)
    target.weight = max(target.weight, source.weight)
    target.is_secret = target.is_secret or source.is_secret
    target.attributes = {**source.attributes, **target.attributes}


def _asset_url(attributes: dict[str, Any] | None) -> str | None:
    value = (attributes or {}).get("image_url")
    return str(value) if value else None
