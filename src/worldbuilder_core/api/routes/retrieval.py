from fastapi import APIRouter, HTTPException, Query, status

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.config import get_settings
from worldbuilder_core.models import ViewerRole
from worldbuilder_core.schemas import ExtractionProposalCreate, ExtractionProposalRead, WorldContextRead, WorldLLMChatRequest, WorldLLMChatResponse
from worldbuilder_core.services.extraction import ExtractionParseError, extract_payload_with_llm
from worldbuilder_core.services.llm import LLMProviderError, build_llm_client
from worldbuilder_core.services.proposals import ProposalValidationError, create_extraction_proposal
from worldbuilder_core.services.retrieval import RetrievalWorldNotFoundError, build_world_context
from worldbuilder_core.services.world_chat import build_world_llm_request

router = APIRouter(tags=["retrieval"])


@router.get("/worlds/{world_id}/context", response_model=WorldContextRead)
def get_world_context(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
    q: str | None = Query(default=None),
    max_entities: int = Query(default=12, ge=1, le=50),
    max_rules: int = Query(default=8, ge=0, le=25),
    max_relationships: int = Query(default=24, ge=0, le=100),
) -> WorldContextRead:
    try:
        return build_world_context(
            session,
            world_id,
            role=role,
            query=q,
            max_entities=max_entities,
            max_rules=max_rules,
            max_relationships=max_relationships,
        )
    except RetrievalWorldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found") from exc


@router.post("/worlds/{world_id}/chat", response_model=WorldLLMChatResponse)
async def chat_with_world_context(
    world_id: str,
    payload: WorldLLMChatRequest,
    session: DbSession,
) -> WorldLLMChatResponse:
    try:
        context = build_world_context(
            session,
            world_id,
            role=payload.role,
            query=payload.query,
            max_entities=payload.max_entities,
            max_rules=payload.max_rules,
            max_relationships=payload.max_relationships,
        )
    except RetrievalWorldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found") from exc

    llm_request = build_world_llm_request(context, payload)
    llm_client = build_llm_client()
    try:
        completion = await llm_client.chat(llm_request)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    proposal = None
    wiki_save_error = None
    if payload.save_to_wiki:
        settings = get_settings()
        max_extract_entities = payload.max_extract_entities or settings.max_entities_per_extract
        try:
            extraction_payload = await extract_payload_with_llm(
                llm_client=llm_client,
                source_text=completion.message.content,
                context_text=context.context_text,
                max_entities=max_extract_entities,
                model=payload.model,
            )
            proposal = ExtractionProposalRead.model_validate(
                create_extraction_proposal(
                    session,
                    world_id,
                    ExtractionProposalCreate(source_text=completion.message.content, payload=extraction_payload),
                )
            )
        except (LLMProviderError, ExtractionParseError, ProposalValidationError) as exc:
            wiki_save_error = str(exc)

    return WorldLLMChatResponse(context=context, completion=completion, proposal=proposal, wiki_save_error=wiki_save_error)
