from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import ExtractionProposal, ProposalStatus
from worldbuilder_core.schemas import (
    AdventureGenerationRequest,
    ExtractionFromTextRequest,
    ExtractionProposalCreate,
    ExtractionProposalRead,
    ExtractionProposalUpdate,
    ProposalApplyResult,
    ProposalItemSelection,
)
from worldbuilder_core.services.extraction import (
    ExtractionParseError,
    extract_payload_with_llm,
    generate_adventure_payload_with_llm,
)
from worldbuilder_core.services.llm import LLMProviderError, build_llm_client
from worldbuilder_core.services.llm_settings import get_llm_runtime_settings
from worldbuilder_core.services.proposals import (
    ProposalInvalidStateError,
    ProposalNotFoundError,
    ProposalValidationError,
    ProposalWorldNotFoundError,
    apply_extraction_proposal,
    apply_selected_extraction_proposal,
    consolidate_pending_proposals,
    create_extraction_proposal,
    delete_extraction_proposal,
    reject_extraction_proposal,
    sanitize_extraction_payload_for_world,
    update_extraction_proposal,
)
from worldbuilder_core.services.retrieval import (
    RetrievalWorldNotFoundError,
    build_world_context,
    build_world_context_with_embeddings,
)

router = APIRouter(tags=["proposals"])


@router.post("/worlds/{world_id}/proposals", response_model=ExtractionProposalRead, status_code=status.HTTP_201_CREATED)
def create_proposal(world_id: str, payload: ExtractionProposalCreate, session: DbSession) -> ExtractionProposal:
    try:
        return create_extraction_proposal(session, world_id, payload)
    except ProposalWorldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found") from exc
    except ProposalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/worlds/{world_id}/proposals/consolidate",
    response_model=ExtractionProposalRead | None,
)
def consolidate_proposals(world_id: str, session: DbSession) -> ExtractionProposal | None:
    try:
        return consolidate_pending_proposals(session, world_id)
    except ProposalWorldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found") from exc
    except ProposalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/worlds/{world_id}/proposals/extract",
    response_model=ExtractionProposalRead,
    status_code=status.HTTP_201_CREATED,
)
async def extract_proposal_from_text(
    world_id: str,
    payload: ExtractionFromTextRequest,
    session: DbSession,
) -> ExtractionProposal:
    runtime_settings = get_llm_runtime_settings(session)
    max_entities = payload.max_entities or runtime_settings.max_entities_per_extract
    try:
        context = build_world_context(session, world_id, role=payload.role, query=payload.query, max_entities=max_entities)
    except RetrievalWorldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found") from exc

    llm_client = build_llm_client(runtime_settings, default_model=runtime_settings.model_for("extractor"))
    try:
        extraction_payload = await extract_payload_with_llm(
            llm_client=llm_client,
            source_text=payload.source_text,
            context_text=context.context_text,
            max_entities=max_entities,
            output_language=payload.output_language,
            model=payload.model or runtime_settings.model_for("extractor"),
            intent_text=payload.intent_text,
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ExtractionParseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM extraction failed: {exc}") from exc

    extraction_payload = sanitize_extraction_payload_for_world(session, world_id, extraction_payload)
    try:
        return create_extraction_proposal(
            session,
            world_id,
            ExtractionProposalCreate(source_text=payload.source_text, payload=extraction_payload),
        )
    except ProposalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/worlds/{world_id}/proposals/generate-adventure",
    response_model=ExtractionProposalRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_adventure_proposal(
    world_id: str,
    payload: AdventureGenerationRequest,
    session: DbSession,
) -> ExtractionProposal:
    try:
        context = await build_world_context_with_embeddings(
            session,
            world_id,
            role=payload.role,
            query=payload.query or payload.premise,
            max_entities=payload.max_entities,
            max_rules=12,
            max_relationships=40,
        )
    except RetrievalWorldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found") from exc

    runtime_settings = get_llm_runtime_settings(session)
    llm_client = build_llm_client(runtime_settings, default_model=runtime_settings.model_for("extractor"))
    try:
        adventure = await generate_adventure_payload_with_llm(
            llm_client=llm_client,
            premise=payload.premise,
            context_text=context.context_text,
            scale=payload.scale,
            tone=payload.tone,
            enabled_modules=payload.enabled_modules,
            max_entities=payload.max_entities,
            output_language=payload.output_language,
            model=payload.model or runtime_settings.model_for("extractor"),
        )
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except ExtractionParseError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Adventure generation failed: {exc}") from exc

    adventure = sanitize_extraction_payload_for_world(session, world_id, adventure)
    try:
        return create_extraction_proposal(
            session,
            world_id,
            ExtractionProposalCreate(source_text=payload.premise, payload=adventure),
        )
    except ProposalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/worlds/{world_id}/proposals", response_model=list[ExtractionProposalRead])
def list_proposals(
    world_id: str,
    session: DbSession,
    status_filter: ProposalStatus | None = None,
) -> list[ExtractionProposal]:
    stmt = select(ExtractionProposal).where(ExtractionProposal.world_id == world_id)
    if status_filter is not None:
        stmt = stmt.where(ExtractionProposal.status == status_filter)
    return list(session.scalars(stmt.order_by(ExtractionProposal.created_at.desc())))


@router.get("/proposals/{proposal_id}", response_model=ExtractionProposalRead)
def get_proposal(proposal_id: str, session: DbSession) -> ExtractionProposal:
    proposal = session.get(ExtractionProposal, proposal_id)
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    return proposal


@router.patch("/proposals/{proposal_id}", response_model=ExtractionProposalRead)
def update_proposal(
    proposal_id: str,
    payload: ExtractionProposalUpdate,
    session: DbSession,
) -> ExtractionProposal:
    try:
        return update_extraction_proposal(session, proposal_id, payload)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found") from exc
    except ProposalInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProposalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/apply", response_model=ProposalApplyResult)
def apply_proposal(proposal_id: str, session: DbSession) -> ProposalApplyResult:
    try:
        return apply_extraction_proposal(session, proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found") from exc
    except ProposalInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProposalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/apply-selected", response_model=ProposalApplyResult)
def apply_selected_proposal(
    proposal_id: str,
    payload: ProposalItemSelection,
    session: DbSession,
) -> ProposalApplyResult:
    try:
        return apply_selected_extraction_proposal(session, proposal_id, payload)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found") from exc
    except ProposalInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ProposalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/proposals/{proposal_id}/reject", response_model=ExtractionProposalRead)
def reject_proposal(proposal_id: str, session: DbSession) -> ExtractionProposal:
    try:
        return reject_extraction_proposal(session, proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found") from exc
    except ProposalInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/proposals/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proposal(proposal_id: str, session: DbSession) -> None:
    try:
        delete_extraction_proposal(session, proposal_id)
    except ProposalNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found") from exc
