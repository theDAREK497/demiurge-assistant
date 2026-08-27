import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from worldbuilder_core.models import (
    DocumentExtractionJob,
    Entity,
    ExtractionProposal,
    ProposalStatus,
    RandomTable,
    RandomTableRow,
    Relationship,
    VerificationStatus,
    World,
    WorldRule,
)
from worldbuilder_core.services.world_configuration import ensure_entity_type
from worldbuilder_core.services.relationship_history import build_relationship_revision
from worldbuilder_core.services.change_history import (
    entity_snapshot,
    record_entity_change,
    record_relationship_change,
    record_world_change,
)
from worldbuilder_core.schemas import (
    ExtractionPayload,
    ExtractionProposalCreate,
    ExtractionProposalUpdate,
    ProposalApplyResult,
    ProposalItemSelection,
)


MAX_PROPOSAL_SOURCE_CHARS = 200_000
SOURCE_SEPARATOR = "\n\n--- SOURCE ---\n\n"


class ProposalError(Exception):
    """Base error for proposal operations."""


class ProposalWorldNotFoundError(ProposalError):
    pass


class ProposalNotFoundError(ProposalError):
    pass


class ProposalInvalidStateError(ProposalError):
    pass


class ProposalValidationError(ProposalError):
    pass


def create_extraction_proposal(
    session: Session,
    world_id: str,
    payload: ExtractionProposalCreate,
    *,
    commit: bool = True,
    merge_pending: bool = True,
) -> ExtractionProposal:
    if session.get(World, world_id) is None:
        raise ProposalWorldNotFoundError(f"World {world_id!r} not found")

    clean_payload = dedupe_extraction_payload(payload.payload)
    validate_payload_references(session, world_id, clean_payload)
    if merge_pending:
        return _merge_pending_proposals(
            session,
            world_id,
            source_text=payload.source_text,
            incoming=clean_payload,
            commit=commit,
        )

    proposal = ExtractionProposal(
        world_id=world_id,
        source_text=payload.source_text,
        payload=clean_payload.model_dump(mode="json"),
        status=ProposalStatus.pending,
    )
    session.add(proposal)
    if commit:
        session.commit()
        session.refresh(proposal)
    else:
        session.flush()
    return proposal


def update_extraction_proposal(
    session: Session,
    proposal_id: str,
    payload: ExtractionProposalUpdate,
) -> ExtractionProposal:
    proposal = session.get(ExtractionProposal, proposal_id)
    if proposal is None:
        raise ProposalNotFoundError(f"Proposal {proposal_id!r} not found")
    if proposal.status != ProposalStatus.pending:
        raise ProposalInvalidStateError(f"Proposal {proposal_id!r} is {proposal.status.value}")

    clean_payload = _prepare_payload_for_review(session, proposal.world_id, payload.payload)
    proposal.source_text = payload.source_text or proposal.source_text
    proposal.payload = clean_payload.model_dump(mode="json")
    proposal.error = None
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def consolidate_pending_proposals(session: Session, world_id: str) -> ExtractionProposal | None:
    if session.get(World, world_id) is None:
        raise ProposalWorldNotFoundError(f"World {world_id!r} not found")
    pending = _pending_proposals(session, world_id)
    if not pending:
        return None
    return _merge_pending_proposals(
        session,
        world_id,
        source_text=None,
        incoming=None,
        commit=True,
    )


def apply_extraction_proposal(session: Session, proposal_id: str) -> ProposalApplyResult:
    return _apply_extraction_proposal(session, proposal_id, selection=None)


def apply_selected_extraction_proposal(
    session: Session,
    proposal_id: str,
    selection: ProposalItemSelection,
) -> ProposalApplyResult:
    return _apply_extraction_proposal(session, proposal_id, selection=selection)


def _apply_extraction_proposal(
    session: Session,
    proposal_id: str,
    *,
    selection: ProposalItemSelection | None,
) -> ProposalApplyResult:
    proposal = session.get(ExtractionProposal, proposal_id)
    if proposal is None:
        raise ProposalNotFoundError(f"Proposal {proposal_id!r} not found")
    if proposal.status != ProposalStatus.pending:
        raise ProposalInvalidStateError(f"Proposal {proposal_id!r} is {proposal.status.value}")

    payload = ExtractionPayload.model_validate(proposal.payload)
    if selection is not None:
        payload = _select_payload_items(payload, selection)
    payload = sanitize_extraction_payload_for_world(session, proposal.world_id, payload)
    payload = dedupe_extraction_payload(payload)
    try:
        validate_payload_references(session, proposal.world_id, payload)
        result = _apply_payload(session, proposal, payload)
        proposal.status = ProposalStatus.applied
        proposal.error = None
        session.add(proposal)
        session.commit()
        return result
    except ProposalError as exc:
        proposal.error = str(exc)
        session.add(proposal)
        session.commit()
        raise


def reject_extraction_proposal(session: Session, proposal_id: str) -> ExtractionProposal:
    proposal = session.get(ExtractionProposal, proposal_id)
    if proposal is None:
        raise ProposalNotFoundError(f"Proposal {proposal_id!r} not found")
    if proposal.status != ProposalStatus.pending:
        raise ProposalInvalidStateError(f"Proposal {proposal_id!r} is {proposal.status.value}")

    proposal.status = ProposalStatus.rejected
    proposal.error = None
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


def delete_extraction_proposal(session: Session, proposal_id: str) -> None:
    proposal = session.get(ExtractionProposal, proposal_id)
    if proposal is None:
        raise ProposalNotFoundError(f"Proposal {proposal_id!r} not found")
    session.delete(proposal)
    session.commit()


def _prepare_payload_for_review(
    session: Session,
    world_id: str,
    payload: ExtractionPayload,
) -> ExtractionPayload:
    try:
        clean = dedupe_extraction_payload(payload)
        clean = sanitize_extraction_payload_for_world(session, world_id, clean)
        clean = dedupe_extraction_payload(clean)
        clean = ExtractionPayload.model_validate(clean.model_dump(mode="json"))
        validate_payload_references(session, world_id, clean)
        return clean
    except ProposalValidationError:
        raise
    except (TypeError, ValueError) as exc:
        raise ProposalValidationError(str(exc)) from exc


def _pending_proposals(session: Session, world_id: str) -> list[ExtractionProposal]:
    return list(
        session.scalars(
            select(ExtractionProposal)
            .where(
                ExtractionProposal.world_id == world_id,
                ExtractionProposal.status == ProposalStatus.pending,
            )
            .order_by(ExtractionProposal.created_at.asc(), ExtractionProposal.id.asc())
        )
    )


def _merge_pending_proposals(
    session: Session,
    world_id: str,
    *,
    source_text: str | None,
    incoming: ExtractionPayload | None,
    commit: bool,
) -> ExtractionProposal:
    pending = _pending_proposals(session, world_id)
    payloads = [ExtractionPayload.model_validate(proposal.payload) for proposal in pending]
    if incoming is not None:
        payloads.append(incoming)
    merged = _prepare_payload_for_review(session, world_id, merge_extraction_payloads(payloads))

    sources = [proposal.source_text for proposal in pending]
    if source_text:
        sources.append(source_text)
    merged_source = merge_proposal_sources(sources)

    if pending:
        active = pending[0]
        active.source_text = merged_source
        active.payload = merged.model_dump(mode="json")
        active.error = None
        session.add(active)
        duplicate_ids = {proposal.id for proposal in pending[1:]}
        if duplicate_ids:
            for job in session.scalars(
                select(DocumentExtractionJob).where(DocumentExtractionJob.proposal_id.in_(duplicate_ids))
            ):
                job.proposal_id = active.id
                session.add(job)
            for proposal in pending[1:]:
                session.delete(proposal)
    else:
        if not merged_source:
            raise ProposalValidationError("Proposal source text is empty")
        active = ExtractionProposal(
            world_id=world_id,
            source_text=merged_source,
            payload=merged.model_dump(mode="json"),
            status=ProposalStatus.pending,
        )
        session.add(active)

    if commit:
        session.commit()
        session.refresh(active)
    else:
        session.flush()
    return active


def merge_extraction_payloads(payloads: list[ExtractionPayload]) -> ExtractionPayload:
    if not payloads:
        return ExtractionPayload()

    entities = []
    relationships = []
    world_rules = []
    random_tables = []
    random_table_rows = []
    notes = []
    used_entity_ids: set[str] = set()
    used_table_ids: set[str] = set()

    for index, payload in enumerate(payloads, start=1):
        remapped = _remap_payload_client_id_collisions(
            payload,
            used_entity_ids=used_entity_ids,
            used_table_ids=used_table_ids,
            prefix=f"d{index}-",
        )
        entities.extend(remapped.entities)
        relationships.extend(remapped.relationships)
        world_rules.extend(remapped.world_rules)
        random_tables.extend(remapped.random_tables)
        random_table_rows.extend(remapped.random_table_rows)
        notes.extend(remapped.notes)
        used_entity_ids.update(item.client_id for item in remapped.entities if item.client_id)
        used_table_ids.update(item.client_id for item in remapped.random_tables)

    combined = ExtractionPayload.model_construct(
        entities=entities,
        relationships=relationships,
        world_rules=world_rules,
        random_tables=random_tables,
        random_table_rows=random_table_rows,
        notes=notes,
    )
    merged = dedupe_extraction_payload(combined)
    return ExtractionPayload.model_validate(merged.model_dump(mode="json"))


def _remap_payload_client_id_collisions(
    payload: ExtractionPayload,
    *,
    used_entity_ids: set[str],
    used_table_ids: set[str],
    prefix: str,
) -> ExtractionPayload:
    entity_ids = _collision_free_ids(
        [item.client_id for item in payload.entities if item.client_id],
        used_entity_ids,
        prefix,
    )
    table_ids = _collision_free_ids(
        [item.client_id for item in payload.random_tables],
        used_table_ids,
        prefix,
    )
    return payload.model_copy(
        update={
            "entities": [
                item.model_copy(update={"client_id": entity_ids[item.client_id]})
                if item.client_id
                else item
                for item in payload.entities
            ],
            "relationships": [
                item.model_copy(
                    update={
                        "source_client_id": entity_ids.get(item.source_client_id, item.source_client_id),
                        "target_client_id": entity_ids.get(item.target_client_id, item.target_client_id),
                    }
                )
                for item in payload.relationships
            ],
            "random_tables": [
                item.model_copy(update={"client_id": table_ids[item.client_id]})
                for item in payload.random_tables
            ],
            "random_table_rows": [
                item.model_copy(
                    update={"table_client_id": table_ids.get(item.table_client_id, item.table_client_id)}
                )
                if item.table_client_id
                else item
                for item in payload.random_table_rows
            ],
        }
    )


def _collision_free_ids(values: list[str], used: set[str], prefix: str) -> dict[str, str]:
    result: dict[str, str] = {}
    reserved = set(used)
    for value in values:
        if value in result:
            continue
        candidate = value
        if candidate in reserved:
            base = f"{prefix}{value}"
            candidate = base[:80]
            suffix = 2
            while candidate in reserved:
                marker = f"-{suffix}"
                candidate = f"{base[: 80 - len(marker)]}{marker}"
                suffix += 1
        result[value] = candidate
        reserved.add(candidate)
    return result


def merge_proposal_sources(sources: list[str]) -> str:
    merged = ""
    for source in sources:
        candidate = str(source or "").strip()
        if not candidate or candidate == merged or candidate in merged:
            continue
        merged = f"{merged}{SOURCE_SEPARATOR if merged else ''}{candidate}"
    if len(merged) <= MAX_PROPOSAL_SOURCE_CHARS:
        return merged
    marker = "\n\n--- SOURCE TEXT COMPACTED ---\n\n"
    head_length = MAX_PROPOSAL_SOURCE_CHARS // 2
    tail_length = MAX_PROPOSAL_SOURCE_CHARS - head_length - len(marker)
    return f"{merged[:head_length]}{marker}{merged[-tail_length:]}"


def sanitize_extraction_payload_for_world(
    session: Session,
    world_id: str,
    payload: ExtractionPayload,
) -> ExtractionPayload:
    """Keep useful LLM output when individual references are invalid."""
    existing_entities = list(session.scalars(select(Entity).where(Entity.world_id == world_id)))
    valid_entity_ids = {entity.id for entity in existing_entities}
    valid_table_ids = set(session.scalars(select(RandomTable.id).where(RandomTable.world_id == world_id)))
    used_client_ids = {entity.client_id for entity in payload.entities if entity.client_id}
    recovered_match_ids: dict[str, str] = {}
    matched_client_ids: dict[str, str] = {}
    entities = []

    for index, entity in enumerate(payload.entities):
        if entity.match_entity_id and entity.match_entity_id not in valid_entity_ids:
            client_id = _unique_recovered_client_id(index, used_client_ids)
            recovered_match_ids[entity.match_entity_id] = client_id
            entities.append(
                entity.model_copy(
                    update={
                        "client_id": client_id,
                        "match_entity_id": None,
                    }
                )
            )
            continue
        if entity.match_entity_id is None:
            existing_match = _find_single_similar_entity(existing_entities, entity)
            if existing_match is not None:
                aliases = _merge_list(entity.aliases, [entity.name]) if entity.name != existing_match.name else entity.aliases
                if entity.client_id:
                    matched_client_ids[entity.client_id] = existing_match.id
                entity = entity.model_copy(
                    update={
                        "client_id": None,
                        "match_entity_id": existing_match.id,
                        "name": existing_match.name,
                        "aliases": aliases,
                    }
                )
        entities.append(entity)

    client_ids = {entity.client_id for entity in entities if entity.client_id}
    relationships = []
    for relationship in payload.relationships:
        updates = {}
        if relationship.source_entity_id in recovered_match_ids:
            updates.update(
                source_entity_id=None,
                source_client_id=recovered_match_ids[relationship.source_entity_id],
            )
        if relationship.target_entity_id in recovered_match_ids:
            updates.update(
                target_entity_id=None,
                target_client_id=recovered_match_ids[relationship.target_entity_id],
            )
        if relationship.source_client_id in matched_client_ids:
            updates.update(
                source_client_id=None,
                source_entity_id=matched_client_ids[relationship.source_client_id],
            )
        if relationship.target_client_id in matched_client_ids:
            updates.update(
                target_client_id=None,
                target_entity_id=matched_client_ids[relationship.target_client_id],
            )
        candidate = relationship.model_copy(update=updates) if updates else relationship
        source_valid = (
            candidate.source_entity_id in valid_entity_ids
            if candidate.source_entity_id
            else candidate.source_client_id in client_ids
        )
        target_valid = (
            candidate.target_entity_id in valid_entity_ids
            if candidate.target_entity_id
            else candidate.target_client_id in client_ids
        )
        if source_valid and target_valid:
            relationships.append(candidate)

    table_client_ids = {table.client_id for table in payload.random_tables}
    return payload.model_copy(
        update={
            "entities": entities,
            "relationships": relationships,
            "random_table_rows": [
                row
                for row in payload.random_table_rows
                if (row.table_id and row.table_id in valid_table_ids)
                or (row.table_client_id and row.table_client_id in table_client_ids)
            ],
        }
    )


def validate_payload_references(session: Session, world_id: str, payload: ExtractionPayload) -> None:
    client_ids = {entity.client_id for entity in payload.entities if entity.client_id}

    for entity in payload.entities:
        if entity.match_entity_id is not None:
            _ensure_entity_in_world(session, world_id, entity.match_entity_id)

    for relationship in payload.relationships:
        if relationship.source_entity_id is not None:
            _ensure_entity_in_world(session, world_id, relationship.source_entity_id)
        elif relationship.source_client_id not in client_ids:
            raise ProposalValidationError(f"Unknown source_client_id {relationship.source_client_id!r}")

        if relationship.target_entity_id is not None:
            _ensure_entity_in_world(session, world_id, relationship.target_entity_id)
        elif relationship.target_client_id not in client_ids:
            raise ProposalValidationError(f"Unknown target_client_id {relationship.target_client_id!r}")

    table_client_ids = {table.client_id for table in payload.random_tables}
    for row in payload.random_table_rows:
        if row.table_id:
            _ensure_random_table_in_world(session, world_id, row.table_id)
        elif row.table_client_id not in table_client_ids:
            raise ProposalValidationError(f"Unknown table_client_id {row.table_client_id!r}")


def dedupe_extraction_payload(payload: ExtractionPayload) -> ExtractionPayload:
    entities, client_id_aliases = _dedupe_entities(payload.entities)
    relationships = _dedupe_relationships(payload.relationships, client_id_aliases)
    random_tables, table_client_id_aliases = _dedupe_random_tables(payload.random_tables)
    random_table_rows = _dedupe_random_table_rows(payload.random_table_rows, table_client_id_aliases)
    return ExtractionPayload(
        entities=entities,
        relationships=relationships,
        world_rules=_dedupe_by_key(payload.world_rules, _world_rule_key, _merge_world_rule_draft),
        random_tables=random_tables,
        random_table_rows=random_table_rows,
        notes=_dedupe_notes(payload.notes),
    )


def _dedupe_entities(entities: list) -> tuple[list, dict[str, str]]:
    deduped = []
    by_key: dict[tuple, int] = {}
    client_id_aliases: dict[str, str] = {}

    for draft in entities:
        key = _entity_key(draft)
        existing_index = by_key.get(key)
        if existing_index is None:
            existing_index = next(
                (
                    index
                    for index, existing in enumerate(deduped)
                    if _entities_likely_same(existing, draft)
                ),
                None,
            )
        if existing_index is None:
            by_key[key] = len(deduped)
            deduped.append(draft)
            continue

        existing = deduped[existing_index]
        merged = _merge_entity_draft(existing, draft)
        deduped[existing_index] = merged
        if draft.client_id and merged.client_id and draft.client_id != merged.client_id:
            client_id_aliases[draft.client_id] = merged.client_id
        if existing.client_id and merged.client_id and existing.client_id != merged.client_id:
            client_id_aliases[existing.client_id] = merged.client_id

    return deduped, client_id_aliases


def _dedupe_relationships(relationships: list, client_id_aliases: dict[str, str]) -> list:
    remapped = []
    for draft in relationships:
        updates = {}
        if draft.source_client_id in client_id_aliases:
            updates["source_client_id"] = client_id_aliases[draft.source_client_id]
        if draft.target_client_id in client_id_aliases:
            updates["target_client_id"] = client_id_aliases[draft.target_client_id]
        remapped.append(draft.model_copy(update=updates) if updates else draft)
    return _dedupe_by_key(remapped, _relationship_key, _merge_relationship_draft)


def _dedupe_random_tables(random_tables: list) -> tuple[list, dict[str, str]]:
    deduped = []
    by_name: dict[str, int] = {}
    client_id_aliases: dict[str, str] = {}
    for draft in random_tables:
        key = _normalized_text(draft.name)
        existing_index = by_name.get(key)
        if existing_index is None:
            by_name[key] = len(deduped)
            deduped.append(draft)
            continue
        existing = deduped[existing_index]
        deduped[existing_index] = existing.model_copy(
            update={
                "source_excerpt": existing.source_excerpt or draft.source_excerpt,
                "description": existing.description or draft.description,
                "is_secret": existing.is_secret or draft.is_secret,
            }
        )
        client_id_aliases[draft.client_id] = existing.client_id
    return deduped, client_id_aliases


def _dedupe_random_table_rows(rows: list, client_id_aliases: dict[str, str]) -> list:
    remapped = []
    for row in rows:
        if row.table_client_id in client_id_aliases:
            row = row.model_copy(update={"table_client_id": client_id_aliases[row.table_client_id]})
        remapped.append(row)
    return _dedupe_by_key(remapped, _random_table_row_key, _merge_random_table_row_draft)


def _dedupe_by_key(items: list, key_factory, merge_factory) -> list:
    deduped = []
    by_key: dict[tuple, int] = {}
    for item in items:
        key = key_factory(item)
        existing_index = by_key.get(key)
        if existing_index is None:
            by_key[key] = len(deduped)
            deduped.append(item)
            continue
        deduped[existing_index] = merge_factory(deduped[existing_index], item)
    return deduped


def _dedupe_notes(notes: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for note in notes:
        key = _normalized_text(note)
        if key and key not in seen:
            deduped.append(note)
            seen.add(key)
    return deduped


def _unique_recovered_client_id(index: int, used_client_ids: set[str]) -> str:
    base = f"recovered-entity-{index + 1}"
    candidate = base
    suffix = 2
    while candidate in used_client_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used_client_ids.add(candidate)
    return candidate


def _entity_key(draft) -> tuple:
    if draft.match_entity_id:
        return ("match", draft.match_entity_id)
    return ("new", str(draft.type), _normalized_text(draft.name))


def _relationship_key(draft) -> tuple:
    return (
        draft.source_entity_id or f"client:{draft.source_client_id}",
        draft.target_entity_id or f"client:{draft.target_client_id}",
        _normalized_text(draft.type),
    )


def _world_rule_key(draft) -> tuple:
    return (_normalized_text(draft.condition), _normalized_text(draft.effect))


def _random_table_row_key(draft) -> tuple:
    table_ref = draft.table_id or f"client:{draft.table_client_id}"
    return (table_ref, _normalized_text(draft.label or ""), _normalized_text(draft.result))


def _merge_entity_draft(current, incoming):
    aliases = _merge_list(current.aliases, incoming.aliases)
    if _normalized_entity_name(current.name) != _normalized_entity_name(incoming.name):
        aliases = _merge_list(aliases, [incoming.name])
    return current.model_copy(
        update={
            "client_id": current.client_id or incoming.client_id,
            "match_entity_id": current.match_entity_id or incoming.match_entity_id,
            "source_excerpt": _prefer_richer_text(current.source_excerpt, incoming.source_excerpt),
            "summary": _prefer_richer_text(current.summary, incoming.summary),
            "description": _prefer_richer_text(current.description, incoming.description),
            "aliases": aliases,
            "tags": _merge_list(current.tags, incoming.tags),
            "is_secret": current.is_secret or incoming.is_secret,
            "attributes": _merge_attributes(current.attributes, incoming.attributes),
        }
    )


def _merge_relationship_draft(current, incoming):
    return current.model_copy(
        update={
            "source_excerpt": _prefer_richer_text(current.source_excerpt, incoming.source_excerpt),
            "label": _prefer_richer_text(current.label, incoming.label),
            "description": _prefer_richer_text(current.description, incoming.description),
            "confidence": max(current.confidence, incoming.confidence),
            "weight": max(current.weight, incoming.weight),
            "valid_from": current.valid_from or incoming.valid_from,
            "valid_to": current.valid_to or incoming.valid_to,
            "evidence": _prefer_richer_text(current.evidence, incoming.evidence),
            "is_secret": current.is_secret or incoming.is_secret,
            "attributes": _merge_attributes(current.attributes, incoming.attributes),
        }
    )


def _merge_world_rule_draft(current, incoming):
    return current.model_copy(
        update={
            "source_excerpt": _prefer_richer_text(current.source_excerpt, incoming.source_excerpt),
            "priority": max(current.priority, incoming.priority),
            "tags": _merge_list(current.tags, incoming.tags),
            "is_active": current.is_active or incoming.is_active,
            "is_secret": current.is_secret or incoming.is_secret,
        }
    )


def _merge_random_table_row_draft(current, incoming):
    return current.model_copy(
        update={
            "source_excerpt": _prefer_richer_text(current.source_excerpt, incoming.source_excerpt),
            "label": _prefer_richer_text(current.label, incoming.label),
            "weight": max(current.weight, incoming.weight),
            "is_secret": current.is_secret or incoming.is_secret,
        }
    )


def _prefer_richer_text(current: str | None, incoming: str | None) -> str | None:
    current_value = str(current or "").strip()
    incoming_value = str(incoming or "").strip()
    if not current_value:
        return incoming_value or None
    if not incoming_value:
        return current_value
    return incoming_value if len(incoming_value) > len(current_value) else current_value


def _merge_attributes(current: dict, incoming: dict) -> dict:
    merged = dict(current or {})
    for key, value in (incoming or {}).items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
        elif isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = _merge_list(merged[key], value)
    return merged


def _normalized_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


ROLE_NAME_TOKENS = {
    "старейшин",
    "глава",
    "вожд",
    "правител",
    "хранител",
    "elder",
    "leader",
    "chief",
    "keeper",
    "ruler",
}
GENERIC_NAME_TOKENS = {
    "поселк",
    "деревн",
    "город",
    "общин",
    "местн",
    "безымянн",
    "village",
    "settlement",
    "town",
    "community",
    "local",
    "unnamed",
}
DIRECTION_NAME_TOKENS = {
    "north",
    "south",
    "east",
    "west",
    "northern",
    "southern",
    "eastern",
    "western",
    "северн",
    "южн",
    "восточн",
    "западн",
}
DETAIL_STOPWORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "into",
    "для",
    "как",
    "что",
    "это",
    "его",
    "она",
    "они",
    "явля",
    "котор",
    "сво",
    "при",
    "или",
    "без",
}


def _find_single_similar_entity(existing_entities: list[Entity], draft) -> Entity | None:
    exact_candidates = [
        entity
        for entity in existing_entities
        if any(
            _normalized_entity_name(existing_name) == _normalized_entity_name(draft_name)
            for existing_name in [entity.name, *(entity.aliases or [])]
            for draft_name in [draft.name, *(draft.aliases or [])]
        )
    ]
    if len(exact_candidates) == 1:
        return exact_candidates[0]
    candidates = [entity for entity in existing_entities if _entities_likely_same(entity, draft)]
    return candidates[0] if len(candidates) == 1 else None


def _entities_likely_same(left, right) -> bool:
    if str(left.type) != str(right.type):
        return False

    left_names = [left.name, *(getattr(left, "aliases", None) or [])]
    right_names = [right.name, *(getattr(right, "aliases", None) or [])]
    for left_name in left_names:
        for right_name in right_names:
            if _names_likely_same(left_name, right_name):
                return True

    left_name_tokens = set(_entity_name_tokens(left.name))
    right_name_tokens = set(_entity_name_tokens(right.name))
    shared_role_tokens = left_name_tokens & right_name_tokens & ROLE_NAME_TOKENS
    has_generic_variant = bool((left_name_tokens | right_name_tokens) & GENERIC_NAME_TOKENS)
    if not shared_role_tokens or not has_generic_variant:
        return False

    left_details = _entity_detail_tokens(left)
    right_details = _entity_detail_tokens(right)
    shared_details = left_details & right_details
    detail_overlap = len(shared_details) / max(1, min(len(left_details), len(right_details)))
    return len(shared_details) >= 3 and detail_overlap >= 0.22


def _names_likely_same(left: str, right: str) -> bool:
    left_normalized = _normalized_entity_name(left)
    right_normalized = _normalized_entity_name(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    left_phonetic = _phonetic_name_key(left)
    right_phonetic = _phonetic_name_key(right)
    if (
        left_phonetic == right_phonetic
        and len(left_phonetic.replace(" ", "")) >= 5
    ):
        return True

    left_base = _normalized_entity_name(re.sub(r"\([^)]*\)\s*$", "", left))
    right_base = _normalized_entity_name(re.sub(r"\([^)]*\)\s*$", "", right))
    if left_base and right_base and left_base == right_base:
        return True

    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    left_stemmed_tokens = set(_entity_name_tokens(left))
    right_stemmed_tokens = set(_entity_name_tokens(right))
    if (left_stemmed_tokens ^ right_stemmed_tokens) & DIRECTION_NAME_TOKENS:
        return False
    if len(left_stemmed_tokens) >= 2 and left_stemmed_tokens == right_stemmed_tokens:
        return True
    shorter_tokens, longer_tokens = sorted((left_tokens, right_tokens), key=len)
    if (
        len(shorter_tokens) >= 3
        and shorter_tokens.issubset(longer_tokens)
        and len(longer_tokens) - len(shorter_tokens) <= 3
    ):
        return True

    ratio = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return ratio >= 0.9


def _entity_detail_tokens(entity) -> set[str]:
    values = [
        entity.name,
        *(getattr(entity, "aliases", None) or []),
        getattr(entity, "summary", None) or "",
        getattr(entity, "description", None) or "",
    ]
    tokens = {_stem_entity_token(token) for token in re.findall(r"[^\W_]+", " ".join(values).casefold())}
    return {token for token in tokens if len(token) >= 3 and token not in DETAIL_STOPWORDS}


def _entity_name_tokens(value: str) -> list[str]:
    return [_stem_entity_token(token) for token in _raw_entity_name_tokens(value)]


def _raw_entity_name_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("ё", "е")
    return re.findall(r"[^\W_]+", normalized)


def _normalized_entity_name(value: str) -> str:
    return " ".join(_raw_entity_name_tokens(value))


CYRILLIC_TRANSLITERATION = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
)


def _phonetic_name_key(value: str) -> str:
    normalized = str(value or "").casefold().translate(CYRILLIC_TRANSLITERATION)
    normalized = normalized.replace("x", "ks").replace("ph", "f").replace("w", "v")
    words = re.findall(r"[a-z]+", normalized)
    return " ".join(re.sub(r"[aeiouy]", "", word) for word in words)


def _stem_entity_token(token: str) -> str:
    if re.fullmatch(r"[а-яё]+", token):
        for suffix in (
            "иями",
            "ями",
            "ами",
            "ого",
            "ему",
            "ому",
            "ыми",
            "ими",
            "иях",
            "ах",
            "ях",
            "ой",
            "ей",
            "ий",
            "ый",
            "ая",
            "яя",
            "ое",
            "ее",
            "ые",
            "ие",
            "ов",
            "ев",
            "ам",
            "ям",
            "ом",
            "ем",
            "а",
            "я",
            "ы",
            "и",
            "е",
            "у",
            "ю",
        ):
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                return token[: -len(suffix)]
    if token.endswith("ies") and len(token) > 5:
        return f"{token[:-3]}y"
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def _apply_payload(
    session: Session,
    proposal: ExtractionProposal,
    payload: ExtractionPayload,
) -> ProposalApplyResult:
    result = ProposalApplyResult(proposal_id=proposal.id)
    client_entity_ids: dict[str, str] = {}

    for draft in payload.entities:
        ensure_entity_type(session, proposal.world_id, draft.type)
        entity = None
        previous_state = None
        change_kind = "updated"
        if draft.match_entity_id is not None:
            entity = _ensure_entity_in_world(session, proposal.world_id, draft.match_entity_id)
            previous_state = entity_snapshot(entity)
            _merge_entity(entity, draft.model_dump(exclude={"client_id", "match_entity_id", "source_excerpt"}))
            result.updated_entities += 1
        else:
            entity = _find_entity_by_type_and_name(session, proposal.world_id, draft.type, draft.name)
            if entity is None:
                entity = Entity(
                    world_id=proposal.world_id,
                    **draft.model_dump(exclude={"client_id", "match_entity_id", "source_excerpt"}),
                )
                session.add(entity)
                session.flush()
                change_kind = "created"
                result.created_entities += 1
            else:
                previous_state = entity_snapshot(entity)
                _merge_entity(entity, draft.model_dump(exclude={"client_id", "match_entity_id", "source_excerpt"}))
                result.updated_entities += 1

        record_entity_change(
            session,
            entity,
            change_kind,
            before_state=previous_state,
            source_type="proposal",
            source_id=proposal.id,
            evidence=draft.source_excerpt,
        )

        if draft.client_id:
            client_entity_ids[draft.client_id] = entity.id

    for draft in payload.relationships:
        source_entity_id = draft.source_entity_id or client_entity_ids[draft.source_client_id or ""]
        target_entity_id = draft.target_entity_id or client_entity_ids[draft.target_client_id or ""]
        relationship = Relationship(
            world_id=proposal.world_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            type=draft.type,
            label=draft.label,
            description=draft.description,
            confidence=draft.confidence,
            weight=draft.weight,
            valid_from=draft.valid_from,
            valid_to=draft.valid_to,
            evidence=draft.evidence,
            is_secret=draft.is_secret,
            status=draft.status,
            attributes=draft.attributes,
        )
        session.add(relationship)
        session.flush()
        session.add(build_relationship_revision(relationship))
        record_relationship_change(
            session,
            relationship,
            "created",
            source_type="proposal",
            source_id=proposal.id,
            evidence=draft.evidence,
        )
        result.created_relationships += 1

    for draft in payload.world_rules:
        rule = WorldRule(world_id=proposal.world_id, **draft.model_dump(exclude={"source_excerpt"}))
        session.add(rule)
        result.created_world_rules += 1

    table_client_ids: dict[str, str] = {}
    for draft in payload.random_tables:
        table = _find_random_table_by_name(session, proposal.world_id, draft.name)
        if table is None:
            table = RandomTable(
                world_id=proposal.world_id,
                name=draft.name,
                description=draft.description,
                is_secret=draft.is_secret,
            )
            session.add(table)
            session.flush()
            result.created_random_tables += 1
        else:
            table.description = table.description or draft.description
            table.is_secret = table.is_secret or draft.is_secret
        table_client_ids[draft.client_id] = table.id

    for draft in payload.random_table_rows:
        table_id = draft.table_id or table_client_ids[draft.table_client_id or ""]
        row = RandomTableRow(
            table_id=table_id,
            **draft.model_dump(exclude={"table_id", "table_client_id", "source_excerpt"}),
        )
        session.add(row)
        result.created_random_table_rows += 1

    record_world_change(
        session,
        world_id=proposal.world_id,
        subject_type="proposal",
        subject_id=proposal.id,
        subject_name=None,
        change_kind="published",
        source_type="proposal",
        source_id=proposal.id,
        summary=(
            "Draft published: "
            f"entities +{result.created_entities}/~{result.updated_entities}, "
            f"relationships +{result.created_relationships}, rules +{result.created_world_rules}, "
            f"tables +{result.created_random_tables}, rows +{result.created_random_table_rows}"
        ),
    )

    return result


def _select_payload_items(payload: ExtractionPayload, selection: ProposalItemSelection) -> ExtractionPayload:
    selected_rows = _select_by_indices(payload.random_table_rows, selection.random_table_row_indices)
    selected_tables = _select_by_indices(payload.random_tables, selection.random_table_indices)
    required_table_client_ids = {row.table_client_id for row in selected_rows if row.table_client_id}
    selected_table_client_ids = {table.client_id for table in selected_tables}
    selected_tables.extend(
        table
        for table in payload.random_tables
        if table.client_id in required_table_client_ids and table.client_id not in selected_table_client_ids
    )
    return ExtractionPayload(
        entities=_select_by_indices(payload.entities, selection.entity_indices),
        relationships=_select_by_indices(payload.relationships, selection.relationship_indices),
        world_rules=_select_by_indices(payload.world_rules, selection.world_rule_indices),
        random_tables=selected_tables,
        random_table_rows=selected_rows,
        notes=payload.notes,
    )


def _select_by_indices(items: list, indices: list[int] | None) -> list:
    if indices is None:
        return list(items)

    selected = []
    for index in sorted(set(indices)):
        if index < 0 or index >= len(items):
            raise ProposalValidationError(f"Selection index {index} is out of range")
        selected.append(items[index])
    return selected


def _merge_entity(entity: Entity, data: dict) -> None:
    for key in ("type", "name", "summary", "description", "is_secret", "status"):
        value = data.get(key)
        if value is not None:
            setattr(entity, key, value)

    entity.aliases = _merge_list(entity.aliases, data.get("aliases") or [])
    entity.tags = _merge_list(entity.tags, data.get("tags") or [])
    entity.attributes = {**entity.attributes, **(data.get("attributes") or {})}

    if entity.status == VerificationStatus.verified and data.get("status") in {
        VerificationStatus.proposed,
        VerificationStatus.unknown,
    }:
        entity.status = data["status"]


def _merge_list(current: list[str], incoming: list[str]) -> list[str]:
    merged = list(current)
    for item in incoming:
        if item not in merged:
            merged.append(item)
    return merged


def _find_entity_by_type_and_name(session: Session, world_id: str, entity_type: str, name: str) -> Entity | None:
    return session.scalar(
        select(Entity).where(
            Entity.world_id == world_id,
            Entity.type == entity_type,
            Entity.name == name,
        )
    )


def _find_random_table_by_name(session: Session, world_id: str, name: str) -> RandomTable | None:
    return session.scalar(select(RandomTable).where(RandomTable.world_id == world_id, RandomTable.name == name))


def _ensure_entity_in_world(session: Session, world_id: str, entity_id: str) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None or entity.world_id != world_id:
        raise ProposalValidationError(f"Entity {entity_id!r} does not belong to world {world_id!r}")
    return entity


def _ensure_random_table_in_world(session: Session, world_id: str, table_id: str) -> RandomTable:
    table = session.get(RandomTable, table_id)
    if table is None or table.world_id != world_id:
        raise ProposalValidationError(f"Random table {table_id!r} does not belong to world {world_id!r}")
    return table
