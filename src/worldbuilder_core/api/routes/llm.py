from fastapi import APIRouter, HTTPException, status

from worldbuilder_core.config import get_settings
from worldbuilder_core.schemas import LLMChatRequest, LLMChatResponse, LLMConfigRead
from worldbuilder_core.services.llm import LLMProviderError, build_llm_client

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/config", response_model=LLMConfigRead)
def get_llm_config() -> LLMConfigRead:
    settings = get_settings()
    return LLMConfigRead(
        base_url=settings.llm_base_url,
        default_model=settings.llm_model,
        has_api_key=bool(settings.llm_api_key),
        timeout_seconds=settings.llm_timeout_seconds,
    )


@router.post("/chat", response_model=LLMChatResponse)
async def chat_with_llm(payload: LLMChatRequest) -> LLMChatResponse:
    client = build_llm_client()
    try:
        return await client.chat(payload)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
