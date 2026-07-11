import json
import re
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError, model_validator

from worldbuilder_core.schemas import LLMChatRequest, LLMMessage


class DetectiveGenerationParseError(Exception):
    pass


class SupportsLLMChat(Protocol):
    async def chat(self, request: LLMChatRequest): ...


class GeneratedDetectiveNode(BaseModel):
    client_id: str = Field(min_length=1, max_length=80)
    entity_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    note: str | None = None
    evidence_url: str | None = None
    is_secret: bool = False


class GeneratedDetectiveConnection(BaseModel):
    source_client_id: str = Field(min_length=1, max_length=80)
    target_client_id: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    note: str | None = None
    is_secret: bool = False

    @model_validator(mode="after")
    def endpoints_differ(self) -> "GeneratedDetectiveConnection":
        if self.source_client_id == self.target_client_id:
            raise ValueError("Connection endpoints must differ")
        return self


class GeneratedDetectiveBoard(BaseModel):
    nodes: list[GeneratedDetectiveNode] = Field(default_factory=list, max_length=24)
    connections: list[GeneratedDetectiveConnection] = Field(default_factory=list, max_length=60)


async def generate_detective_board_with_llm(
    *,
    llm_client: SupportsLLMChat,
    context_text: str,
    output_language: str,
    max_nodes: int,
    model: str | None,
) -> GeneratedDetectiveBoard:
    request = build_detective_generation_request(
        context_text=context_text,
        output_language=output_language,
        max_nodes=max_nodes,
        model=model,
    )
    completion = await llm_client.chat(request)
    try:
        return parse_detective_board(completion.message.content, max_nodes=max_nodes)
    except DetectiveGenerationParseError as first_error:
        repair = LLMChatRequest(
            model=model,
            temperature=0.0,
            messages=[
                *request.messages,
                LLMMessage(role="assistant", content=completion.message.content),
                LLMMessage(
                    role="user",
                    content=(
                        f"The JSON was invalid: {first_error}. Return corrected JSON only. "
                        "Use nodes with unique client_id values and connections that reference those client IDs."
                    ),
                ),
            ],
        )
        repaired = await llm_client.chat(repair)
        return parse_detective_board(repaired.message.content, max_nodes=max_nodes)


def build_detective_generation_request(
    *,
    context_text: str,
    output_language: str,
    max_nodes: int,
    model: str | None,
) -> LLMChatRequest:
    language_name = "English" if output_language == "en" else "Russian"
    return LLMChatRequest(
        model=model,
        temperature=0.2,
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "Build a concise detective board from world context. Return JSON only: "
                    '{"nodes":[{"client_id":"clue-1","entity_id":null,"title":"...","note":"...",'
                    '"evidence_url":null,"is_secret":false}],"connections":[{"source_client_id":"clue-1",'
                    '"target_client_id":"suspect-1","label":"...","note":"...","is_secret":false}]}. '
                    f"Create 5 to {max_nodes} useful nodes and only meaningful connections. "
                    "Use an entity_id only when the context provides that exact UUID; otherwise use null. "
                    f"Write titles, notes, and labels in {language_name}. Include public clues and secret conclusions."
                ),
            ),
            LLMMessage(role="user", content=f"World context:\n{context_text}"),
        ],
    )


def parse_detective_board(content: str, *, max_nodes: int) -> GeneratedDetectiveBoard:
    try:
        raw = json.loads(_extract_json_object(content))
        normalized = _normalize_board(raw)
        board = GeneratedDetectiveBoard.model_validate(normalized)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise DetectiveGenerationParseError(str(exc)) from exc
    if len(board.nodes) > max_nodes:
        raise DetectiveGenerationParseError(f"Generated {len(board.nodes)} nodes; maximum is {max_nodes}")
    return board


def _normalize_board(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise TypeError("Detective board must be a JSON object")
    nodes = []
    aliases: dict[str, str] = {}
    used_ids: set[str] = set()
    for index, item in enumerate(raw.get("nodes") if isinstance(raw.get("nodes"), list) else []):
        if not isinstance(item, dict):
            continue
        title = _text(item.get("title") or item.get("name"))
        if not title:
            continue
        client_id = _unique_slug(_text(item.get("client_id") or item.get("id")) or title, used_ids, index)
        nodes.append(
            {
                "client_id": client_id,
                "entity_id": _text(item.get("entity_id")),
                "title": title,
                "note": _text(item.get("note") or item.get("description") or item.get("summary")),
                "evidence_url": _text(item.get("evidence_url") or item.get("image_url")),
                "is_secret": bool(item.get("is_secret", False)),
            }
        )
        for alias in (client_id, title, _text(item.get("id")), _text(item.get("client_id"))):
            if alias:
                aliases[alias.casefold()] = client_id

    connections = []
    for item in raw.get("connections") if isinstance(raw.get("connections"), list) else []:
        if not isinstance(item, dict):
            continue
        source = _resolve_alias(item.get("source_client_id") or item.get("source_id") or item.get("source"), aliases)
        target = _resolve_alias(item.get("target_client_id") or item.get("target_id") or item.get("target"), aliases)
        if not source or not target or source == target:
            continue
        connections.append(
            {
                "source_client_id": source,
                "target_client_id": target,
                "label": _text(item.get("label") or item.get("type")),
                "note": _text(item.get("note") or item.get("description")),
                "is_secret": bool(item.get("is_secret", False)),
            }
        )
    return {"nodes": nodes, "connections": connections}


def _extract_json_object(content: str) -> str:
    stripped = content.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else stripped
    start = candidate.find("{")
    end = candidate.rfind("}")
    return candidate[start : end + 1] if start != -1 and end > start else candidate


def _unique_slug(value: str, used: set[str], index: int) -> str:
    base = re.sub(r"[^0-9a-zA-Z_-]+", "-", value.lower()).strip("-_")[:70] or f"node-{index + 1}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _resolve_alias(value: object, aliases: dict[str, str]) -> str | None:
    text = _text(value)
    return aliases.get(text.casefold()) if text else None


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
