from worldbuilder_core.schemas import LLMChatRequest, LLMMessage, WorldContextRead, WorldLLMChatRequest


def build_world_llm_request(context: WorldContextRead, request: WorldLLMChatRequest) -> LLMChatRequest:
    system_message = LLMMessage(
        role="system",
        content=(
            "You are the Worldbuilder assistant. Use the authoritative world context below. "
            f"The current viewer role is {context.role.value}; do not reveal information absent from this context.\n\n"
            f"{context.context_text}"
        ),
    )
    return LLMChatRequest(
        messages=[system_message, *request.messages],
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
