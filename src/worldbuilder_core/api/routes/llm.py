from fastapi import APIRouter, HTTPException, status

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.schemas import LLMChatRequest, LLMChatResponse, LLMConfigRead, LLMConfigUpdate
from worldbuilder_core.services.llm import LLMProviderError, build_llm_client
from worldbuilder_core.services.llm_settings import get_llm_runtime_settings, llm_config_read, save_llm_runtime_settings

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/config", response_model=LLMConfigRead)
def get_llm_config(session: DbSession) -> LLMConfigRead:
    return llm_config_read(get_llm_runtime_settings(session))


@router.put("/config", response_model=LLMConfigRead)
def update_llm_config(payload: LLMConfigUpdate, session: DbSession) -> LLMConfigRead:
    return llm_config_read(save_llm_runtime_settings(session, payload))


@router.post("/chat", response_model=LLMChatResponse)
async def chat_with_llm(payload: LLMChatRequest, session: DbSession) -> LLMChatResponse:
    runtime_settings = get_llm_runtime_settings(session)
    client = build_llm_client(runtime_settings, default_model=runtime_settings.model_for("chat"))
    try:
        return await client.chat(payload)
    except LLMProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
