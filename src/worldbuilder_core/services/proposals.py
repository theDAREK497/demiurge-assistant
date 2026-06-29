from sqlalchemy import select
from sqlalchemy.orm import Session

from worldbuilder_core.models import (
    Entity,
    ExtractionProposal,
    ProposalStatus,
    Relationship,
    VerificationStatus,
    World,
    WorldRule,
)
from worldbuilder_core.schemas import ExtractionPayload, ExtractionProposalCreate, ProposalApplyResult, ProposalItemSelection


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
) -> ExtractionProposal:
    if session.get(World, world_id) is None:
        raise ProposalWorldNotFoundError(f"World {world_id!r} not found")

    validate_payload_references(session, world_id, payload.payload)
    proposal = ExtractionProposal(
        world_id=world_id,
        source_text=payload.source_text,
        payload=payload.payload.model_dump(mode="json"),
        status=ProposalStatus.pending,
    )
    session.add(proposal)
    session.commit()
    session.refresh(proposal)
    return proposal


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


def _apply_payload(
    session: Session,
    proposal: ExtractionProposal,
    payload: ExtractionPayload,
) -> ProposalApplyResult:
    result = ProposalApplyResult(proposal_id=proposal.id)
    client_entity_ids: dict[str, str] = {}

    for draft in payload.entities:
        entity = None
        if draft.match_entity_id is not None:
            entity = _ensure_entity_in_world(session, proposal.world_id, draft.match_entity_id)
            _merge_entity(entity, draft.model_dump(exclude={"client_id", "match_entity_id"}))
            result.updated_entities += 1
        else:
            entity = _find_entity_by_type_and_name(session, proposal.world_id, draft.type, draft.name)
            if entity is None:
                entity = Entity(
                    world_id=proposal.world_id,
                    **draft.model_dump(exclude={"client_id", "match_entity_id"}),
                )
                session.add(entity)
                session.flush()
                result.created_entities += 1
            else:
                _merge_entity(entity, draft.model_dump(exclude={"client_id", "match_entity_id"}))
                result.updated_entities += 1

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
            is_secret=draft.is_secret,
            status=draft.status,
            attributes=draft.attributes,
        )
        session.add(relationship)
        result.created_relationships += 1

    for draft in payload.world_rules:
        rule = WorldRule(world_id=proposal.world_id, **draft.model_dump())
        session.add(rule)
        result.created_world_rules += 1

    return result


def _select_payload_items(payload: ExtractionPayload, selection: ProposalItemSelection) -> ExtractionPayload:
    return ExtractionPayload(
        entities=_select_by_indices(payload.entities, selection.entity_indices),
        relationships=_select_by_indices(payload.relationships, selection.relationship_indices),
        world_rules=_select_by_indices(payload.world_rules, selection.world_rule_indices),
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


def _ensure_entity_in_world(session: Session, world_id: str, entity_id: str) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None or entity.world_id != world_id:
        raise ProposalValidationError(f"Entity {entity_id!r} does not belong to world {world_id!r}")
    return entity
