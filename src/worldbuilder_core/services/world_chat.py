from worldbuilder_core.schemas import LLMChatRequest, LLMMessage, WorldContextRead, WorldLLMChatRequest


LANGUAGE_NAMES = {
    "ru": "Russian",
    "en": "English",
}

MAX_CONTEXT_CHARS = 14_000
MAX_HISTORY_CHARS = 8_000
MAX_MESSAGE_CHARS = 4_000


def build_world_llm_request(context: WorldContextRead, request: WorldLLMChatRequest) -> LLMChatRequest:
    language_name = LANGUAGE_NAMES.get(request.output_language, "Russian")
    system_message = LLMMessage(
        role="system",
        content=(
            "You are the Worldbuilder assistant. Use the authoritative world context below. "
            f"The current viewer role is {context.role.value}; do not reveal information absent from this context. "
            f"Write all user-facing prose, world rules, names you invent, and draftable lore in {language_name}. "
            "When the context contains both Cyrillic and Latin spellings of the same proper name, use the spelling "
            "that matches the requested language. Preserve a foreign spelling only when no requested-language "
            "version exists in the context. Do not invent translated names. Never expose internal UUIDs, client IDs, "
            "database keys, or unnamed technical codes to the user; say that the exact name is not specified.\n\n"
            f"{_compact_text(context.context_text, MAX_CONTEXT_CHARS)}"
        ),
    )
    return LLMChatRequest(
        messages=[system_message, *_compact_messages(request.messages)],
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        reasoning_effort="none",
    )


def _compact_messages(messages: list[LLMMessage]) -> list[LLMMessage]:
    selected: list[LLMMessage] = []
    used_chars = 0
    for message in reversed(messages):
        content = _compact_text(message.content, MAX_MESSAGE_CHARS)
        remaining = MAX_HISTORY_CHARS - used_chars
        if remaining <= 0:
            break
        content = _compact_text(content, remaining)
        selected.append(message.model_copy(update={"content": content}))
        used_chars += len(content)
    return list(reversed(selected))


def _compact_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    marker = "\n...[truncated]...\n"
    if limit <= len(marker) + 2:
        return value[:limit]
    available = max(limit - len(marker), 2)
    head = available // 2
    tail = available - head
    return f"{value[:head]}{marker}{value[-tail:]}"
