import json
import re
from typing import Protocol

from pydantic import ValidationError

from worldbuilder_core.schemas import ExtractionPayload, LLMChatRequest, LLMMessage


class ExtractionParseError(Exception):
    """Raised when LLM extraction output cannot be parsed as the expected schema."""


class SupportsLLMChat(Protocol):
    async def chat(self, request: LLMChatRequest): ...


async def extract_payload_with_llm(
    *,
    llm_client: SupportsLLMChat,
    source_text: str,
    context_text: str,
    max_entities: int,
    model: str | None = None,
) -> ExtractionPayload:
    extraction_request = build_extraction_request(
        source_text=source_text,
        context_text=context_text,
        max_entities=max_entities,
        model=model,
    )
    completion = await llm_client.chat(extraction_request)
    try:
        return parse_extraction_payload(completion.message.content, max_entities=max_entities)
    except ExtractionParseError as first_error:
        repair_request = build_repair_request(
            original_request=extraction_request,
            broken_content=completion.message.content,
            error=str(first_error),
        )
        repaired_completion = await llm_client.chat(repair_request)
        return parse_extraction_payload(repaired_completion.message.content, max_entities=max_entities)


def build_extraction_request(
    *,
    source_text: str,
    context_text: str,
    max_entities: int,
    model: str | None = None,
) -> LLMChatRequest:
    return LLMChatRequest(
        model=model,
        temperature=0.0,
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You extract structured wiki updates for Worldbuilder Core. "
                    "Return only valid JSON matching this shape: "
                    '{"entities":[],"relationships":[],"world_rules":[],"notes":[]}. '
                    "Never invent stable UUIDs. Use client_id for new entities, and use match_entity_id only "
                    "when the context gives an existing entity UUID. "
                    f"Extract at most {max_entities} entities. "
                    "Use status 'unknown' when uncertain, otherwise use 'proposed'."
                ),
            ),
            LLMMessage(role="user", content=f"Authoritative world context:\n{context_text}\n\nText to extract:\n{source_text}"),
        ],
    )


def build_repair_request(
    *,
    original_request: LLMChatRequest,
    broken_content: str,
    error: str,
) -> LLMChatRequest:
    return LLMChatRequest(
        model=original_request.model,
        temperature=0.0,
        messages=[
            *original_request.messages,
            LLMMessage(role="assistant", content=broken_content),
            LLMMessage(
                role="user",
                content=(
                    "The previous response was not valid for the required JSON schema. "
                    f"Validation error: {error}. Return corrected JSON only."
                ),
            ),
        ],
    )


def parse_extraction_payload(content: str, *, max_entities: int) -> ExtractionPayload:
    try:
        raw = json.loads(_strip_json_fence(content))
        payload = ExtractionPayload.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ExtractionParseError(str(exc)) from exc

    if len(payload.entities) > max_entities:
        raise ExtractionParseError(f"Extracted {len(payload.entities)} entities; maximum is {max_entities}")
    return payload


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped
