from worldbuilder_core.schemas import LLMChatRequest, LLMMessage, WorldContextRead, WorldLLMChatRequest


LANGUAGE_NAMES = {
    "ru": "Russian",
    "en": "English",
}


def build_world_llm_request(context: WorldContextRead, request: WorldLLMChatRequest) -> LLMChatRequest:
    language_name = LANGUAGE_NAMES.get(request.output_language, "Russian")
    system_message = LLMMessage(
        role="system",
        content=(
            "You are the Worldbuilder assistant. Use the authoritative world context below. "
            f"The current viewer role is {context.role.value}; do not reveal information absent from this context. "
            f"Write all user-facing prose, world rules, names you invent, and draftable lore in {language_name}.\n\n"
            f"{context.context_text}"
        ),
    )
    return LLMChatRequest(
        messages=[system_message, *request.messages],
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )
