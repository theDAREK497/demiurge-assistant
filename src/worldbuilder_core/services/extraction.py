import json
import re
from typing import Protocol

from pydantic import ValidationError

from worldbuilder_core.schemas import ExtractionPayload, LLMChatRequest, LLMMessage


class ExtractionParseError(Exception):
    """Raised when LLM extraction output cannot be parsed as the expected schema."""


class SupportsLLMChat(Protocol):
    async def chat(self, request: LLMChatRequest): ...


ENTITY_TYPE_ALIASES = {
    "character": "character",
    "npc": "character",
    "person": "character",
    "location": "location",
    "place": "location",
    "region": "location",
    "faction": "faction",
    "organization": "faction",
    "organisation": "faction",
    "org": "faction",
    "guild": "faction",
    "group": "faction",
    "item": "item",
    "resource": "item",
    "artifact": "item",
    "event": "event",
    "incident": "event",
    "clue": "clue",
    "hint": "clue",
    "concept": "concept",
    "setting_element": "concept",
    "setting": "concept",
    "world_concept": "concept",
    "worldbuilding_concept": "concept",
    "theme": "concept",
    "lore": "concept",
}

GENERIC_REFERENCE_VALUES = {"", "id", "entity", "entity_id", "client_id", "new", "new_entity"}
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


async def extract_payload_with_llm(
    *,
    llm_client: SupportsLLMChat,
    source_text: str,
    context_text: str,
    max_entities: int,
    output_language: str = "ru",
    model: str | None = None,
) -> ExtractionPayload:
    extraction_request = build_extraction_request(
        source_text=source_text,
        context_text=context_text,
        max_entities=max_entities,
        output_language=output_language,
        model=model,
    )
    completion = await llm_client.chat(extraction_request)
    try:
        payload = parse_extraction_payload(completion.message.content, max_entities=max_entities)
    except ExtractionParseError as first_error:
        repair_request = build_repair_request(
            original_request=extraction_request,
            broken_content=completion.message.content,
            error=str(first_error),
        )
        repaired_completion = await llm_client.chat(repair_request)
        payload = parse_extraction_payload(repaired_completion.message.content, max_entities=max_entities)
    return annotate_payload_with_source_excerpts(payload, source_text)


def build_extraction_request(
    *,
    source_text: str,
    context_text: str,
    max_entities: int,
    output_language: str = "ru",
    model: str | None = None,
) -> LLMChatRequest:
    language_name = "English" if output_language == "en" else "Russian"
    return LLMChatRequest(
        model=model,
        temperature=0.0,
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You extract structured wiki updates for Worldbuilder Core. "
                    "Return only valid JSON matching this shape: "
                    '{"entities":[],"relationships":[],"world_rules":[],"random_table_rows":[],"notes":[]}. '
                    "Entity types must be one of: character, location, faction, item, event, clue, concept. "
                    "Never invent stable UUIDs. Use client_id for new entities, and use match_entity_id only "
                    "when the context gives an existing entity UUID. "
                    "Relationships must use source_client_id or source_entity_id, and target_client_id or "
                    "target_entity_id, plus type. "
                    "World rules must use condition and effect strings. "
                    "Random table rows must use table_id only from the context, plus result, optional label, "
                    "weight, and is_secret. "
                    f"Write all names, summaries, descriptions, world rule conditions/effects, and notes in {language_name}. "
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
                    f"Validation error: {error}. "
                    "Correct field names to the required schema and return corrected JSON only. "
                    "Use client_id instead of id for new entities. "
                    "Use source_client_id/target_client_id or source_entity_id/target_entity_id for relationships. "
                    "Use condition/effect for world rules. "
                    "Use random_table_rows for proposed random table entries, and use only table_id values "
                    "that appeared in the provided context."
                ),
            ),
        ],
    )


def parse_extraction_payload(content: str, *, max_entities: int) -> ExtractionPayload:
    try:
        raw = json.loads(_extract_json_text(content))
        payload = ExtractionPayload.model_validate(_normalize_extraction_payload(raw))
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise ExtractionParseError(str(exc)) from exc

    if len(payload.entities) > max_entities:
        raise ExtractionParseError(f"Extracted {len(payload.entities)} entities; maximum is {max_entities}")
    return payload


def _extract_json_text(content: str) -> str:
    stripped = content.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    candidate = match.group(1).strip() if match else stripped
    if candidate.startswith("{") or candidate.startswith("["):
        return candidate

    first_object = candidate.find("{")
    last_object = candidate.rfind("}")
    if first_object != -1 and last_object != -1 and first_object < last_object:
        return candidate[first_object : last_object + 1]

    first_array = candidate.find("[")
    last_array = candidate.rfind("]")
    if first_array != -1 and last_array != -1 and first_array < last_array:
        return candidate[first_array : last_array + 1]

    return candidate


def _normalize_extraction_payload(raw: object) -> dict:
    if isinstance(raw, dict) and isinstance(raw.get("payload"), dict):
        raw = raw["payload"]
    if not isinstance(raw, dict):
        raise TypeError("Extraction payload must be a JSON object")

    entity_aliases: dict[str, str] = {}
    entities = _normalize_entities(raw.get("entities"), entity_aliases)
    relationships = _normalize_relationships(raw.get("relationships"), entity_aliases)
    world_rules = _normalize_world_rules(raw.get("world_rules"))
    random_table_rows = _normalize_random_table_rows(
        raw.get("random_table_rows") or raw.get("random_table_entries") or raw.get("table_rows")
    )
    notes = _normalize_notes(raw.get("notes"))
    return {
        "entities": entities,
        "relationships": relationships,
        "world_rules": world_rules,
        "random_table_rows": random_table_rows,
        "notes": notes,
    }


def _normalize_entities(raw_entities: object, entity_aliases: dict[str, str]) -> list[dict]:
    entities: list[dict] = []
    used_client_ids: set[str] = set()

    for index, raw_entity in enumerate(_as_list(raw_entities)):
        if not isinstance(raw_entity, dict):
            continue

        name = _clean_string(raw_entity.get("name"))
        if not name:
            continue

        entity_type = _normalize_entity_type(raw_entity.get("type"))
        description = _clean_string(raw_entity.get("description"))
        summary = _clean_string(raw_entity.get("summary"))
        if summary is None and description:
            summary = description[:500]

        match_entity_id = _clean_string(raw_entity.get("match_entity_id"))
        client_id = None if match_entity_id else _build_client_id(raw_entity, name, used_client_ids, index)

        entity = {
            "client_id": client_id,
            "match_entity_id": match_entity_id,
            "type": entity_type,
            "name": name,
            "summary": summary,
            "description": description,
            "aliases": _normalize_string_list(raw_entity.get("aliases")),
            "tags": _normalize_string_list(raw_entity.get("tags")),
            "is_secret": bool(raw_entity.get("is_secret", False)),
            "status": _normalize_status(raw_entity.get("status")),
            "attributes": _normalize_attributes(raw_entity.get("attributes")),
        }
        entities.append(entity)

        if client_id:
            for alias in _collect_entity_aliases(raw_entity, name):
                entity_aliases[alias] = client_id

    return entities


def _normalize_relationships(raw_relationships: object, entity_aliases: dict[str, str]) -> list[dict]:
    relationships: list[dict] = []

    for raw_relationship in _as_list(raw_relationships):
        if not isinstance(raw_relationship, dict):
            continue

        source_ref = _clean_string(
            raw_relationship.get("source_client_id")
            or raw_relationship.get("source_entity_id")
            or raw_relationship.get("source_id")
            or raw_relationship.get("source")
        )
        target_ref = _clean_string(
            raw_relationship.get("target_client_id")
            or raw_relationship.get("target_entity_id")
            or raw_relationship.get("target_id")
            or raw_relationship.get("target")
        )
        if not source_ref or not target_ref:
            continue

        relationship_type = _clean_string(
            raw_relationship.get("type") or raw_relationship.get("relationship_type") or raw_relationship.get("label")
        )
        if not relationship_type:
            relationship_type = "related_to"

        source_client_id, source_entity_id = _normalize_reference(source_ref, entity_aliases)
        target_client_id, target_entity_id = _normalize_reference(target_ref, entity_aliases)
        if (not source_client_id and not source_entity_id) or (not target_client_id and not target_entity_id):
            continue

        relationships.append(
            {
                "source_client_id": source_client_id,
                "source_entity_id": source_entity_id,
                "target_client_id": target_client_id,
                "target_entity_id": target_entity_id,
                "type": relationship_type[:80],
                "label": _clean_string(raw_relationship.get("label")),
                "description": _clean_string(raw_relationship.get("description")),
                "confidence": _normalize_confidence(raw_relationship.get("confidence")),
                "is_secret": bool(raw_relationship.get("is_secret", False)),
                "status": _normalize_status(raw_relationship.get("status")),
                "attributes": _normalize_attributes(raw_relationship.get("attributes")),
            }
        )

    return relationships


def _normalize_world_rules(raw_world_rules: object) -> list[dict]:
    rules: list[dict] = []

    for raw_rule in _as_list(raw_world_rules):
        if isinstance(raw_rule, str):
            text = _clean_string(raw_rule)
            if not text:
                continue
            rules.append(
                {
                    "priority": 3,
                    "condition": text,
                    "effect": text,
                    "tags": [],
                    "is_active": True,
                    "is_secret": False,
                    "status": "proposed",
                }
            )
            continue

        if not isinstance(raw_rule, dict):
            continue

        condition = _clean_string(
            raw_rule.get("condition")
            or raw_rule.get("when")
            or raw_rule.get("rule_name")
            or raw_rule.get("name")
            or raw_rule.get("title")
        )
        effect = _clean_string(
            raw_rule.get("effect") or raw_rule.get("then") or raw_rule.get("description") or raw_rule.get("details")
        )

        if not condition and effect:
            condition = effect
        if not effect and condition:
            effect = _clean_string(raw_rule.get("description")) or condition
        if not condition or not effect:
            continue

        rules.append(
            {
                "priority": _normalize_priority(raw_rule.get("priority")),
                "condition": condition,
                "effect": effect,
                "tags": _normalize_string_list(raw_rule.get("tags")),
                "is_active": bool(raw_rule.get("is_active", True)),
                "is_secret": bool(raw_rule.get("is_secret", False)),
                "status": _normalize_status(raw_rule.get("status")),
            }
        )

    return rules


def _normalize_random_table_rows(raw_rows: object) -> list[dict]:
    rows: list[dict] = []

    for raw_row in _as_list(raw_rows):
        if not isinstance(raw_row, dict):
            continue

        table_id = _clean_string(
            raw_row.get("table_id")
            or raw_row.get("random_table_id")
            or raw_row.get("table")
            or raw_row.get("target_table_id")
        )
        result = _clean_string(
            raw_row.get("result")
            or raw_row.get("text")
            or raw_row.get("entry")
            or raw_row.get("outcome")
            or raw_row.get("description")
        )
        if not table_id or not result:
            continue

        rows.append(
            {
                "table_id": table_id,
                "source_excerpt": _clean_string(raw_row.get("source_excerpt")),
                "label": _clean_string(raw_row.get("label") or raw_row.get("name") or raw_row.get("title")),
                "result": result,
                "weight": _normalize_weight(raw_row.get("weight")),
                "is_secret": bool(raw_row.get("is_secret", False)),
            }
        )

    return rows


def _normalize_notes(raw_notes: object) -> list[str]:
    notes: list[str] = []
    for raw_note in _as_list(raw_notes):
        note = _clean_string(raw_note)
        if note:
            notes.append(note)
    return notes


def annotate_payload_with_source_excerpts(payload: ExtractionPayload, source_text: str) -> ExtractionPayload:
    sentences = _split_source_sentences(source_text)
    if not sentences:
        return payload

    entity_labels = {entity.client_id: entity.name for entity in payload.entities if entity.client_id}
    fallback_excerpt = _trim_excerpt(sentences[0])

    entities = [
        entity.model_copy(
            update={
                "source_excerpt": entity.source_excerpt
                or _find_best_excerpt(sentences, [entity.name, *entity.aliases, entity.summary or "", entity.description or ""])
                or fallback_excerpt,
            }
        )
        for entity in payload.entities
    ]

    relationships = []
    for relationship in payload.relationships:
        source_label = entity_labels.get(relationship.source_client_id or "", relationship.source_entity_id or "")
        target_label = entity_labels.get(relationship.target_client_id or "", relationship.target_entity_id or "")
        relationships.append(
            relationship.model_copy(
                update={
                    "source_excerpt": relationship.source_excerpt
                    or _find_best_excerpt(
                        sentences,
                        [source_label, target_label, relationship.label or "", relationship.type, relationship.description or ""],
                    )
                    or fallback_excerpt,
                }
            )
        )

    rules = [
        rule.model_copy(
            update={
                "source_excerpt": rule.source_excerpt
                or _find_best_excerpt(sentences, [rule.condition, rule.effect])
                or fallback_excerpt,
            }
        )
        for rule in payload.world_rules
    ]

    random_table_rows = [
        row.model_copy(
            update={
                "source_excerpt": row.source_excerpt
                or _find_best_excerpt(sentences, [row.label or "", row.result])
                or fallback_excerpt,
            }
        )
        for row in payload.random_table_rows
    ]

    return payload.model_copy(
        update={
            "entities": entities,
            "relationships": relationships,
            "world_rules": rules,
            "random_table_rows": random_table_rows,
        }
    )


def _normalize_entity_type(raw_type: object) -> str:
    value = _clean_string(raw_type)
    if not value:
        return "concept"
    return ENTITY_TYPE_ALIASES.get(value.lower(), "concept")


def _normalize_status(raw_status: object) -> str:
    value = _clean_string(raw_status)
    if value in {"verified", "proposed", "unknown", "rejected"}:
        return value
    return "proposed"


def _normalize_priority(raw_priority: object) -> int:
    try:
        priority = int(raw_priority)
    except (TypeError, ValueError):
        return 3
    return max(1, min(priority, 5))


def _normalize_weight(raw_weight: object) -> int:
    try:
        weight = int(raw_weight)
    except (TypeError, ValueError):
        return 1
    return max(1, min(weight, 1000))


def _normalize_confidence(raw_confidence: object) -> float:
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(confidence, 1.0))


def _normalize_attributes(raw_attributes: object) -> dict:
    return dict(raw_attributes) if isinstance(raw_attributes, dict) else {}


def _normalize_string_list(raw_values: object) -> list[str]:
    if isinstance(raw_values, str):
        raw_values = [part.strip() for part in raw_values.split(",")]
    if not isinstance(raw_values, list):
        return []

    values: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        value = _clean_string(raw_value)
        if value and value not in seen:
            values.append(value)
            seen.add(value)
    return values


def _normalize_reference(reference: str, entity_aliases: dict[str, str]) -> tuple[str | None, str | None]:
    if reference.lower() in GENERIC_REFERENCE_VALUES:
        return None, None
    if reference in entity_aliases:
        return entity_aliases[reference], None
    if UUID_PATTERN.fullmatch(reference):
        return None, reference
    normalized = _slugify(reference)
    return (normalized, None) if normalized else (None, None)


def _build_client_id(raw_entity: dict, name: str, used_client_ids: set[str], index: int) -> str:
    preferred = _clean_string(raw_entity.get("client_id")) or _clean_string(raw_entity.get("id"))
    if preferred and preferred.lower() not in GENERIC_REFERENCE_VALUES:
        candidate = _slugify(preferred)
    else:
        candidate = _slugify(name)
    if not candidate:
        candidate = f"entity-{index + 1}"

    unique_candidate = candidate
    suffix = 2
    while unique_candidate in used_client_ids:
        unique_candidate = f"{candidate}-{suffix}"
        suffix += 1
    used_client_ids.add(unique_candidate)
    return unique_candidate


def _collect_entity_aliases(raw_entity: dict, name: str) -> set[str]:
    aliases = {name}
    for key in ("client_id", "id", "entity_id", "name"):
        value = _clean_string(raw_entity.get(key))
        if value and value.lower() not in GENERIC_REFERENCE_VALUES:
            aliases.add(value)
    for alias in _normalize_string_list(raw_entity.get("aliases")):
        aliases.add(alias)
    return aliases


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _clean_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z_-]+", "-", value.strip().lower()).strip("-_")
    return slug[:80]


def _split_source_sentences(source_text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", source_text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _find_best_excerpt(sentences: list[str], terms: list[str]) -> str | None:
    normalized_terms = []
    for term in terms:
        normalized = _normalize_match_term(term)
        if normalized:
            normalized_terms.append(normalized)
    if not normalized_terms:
        return None

    best_sentence = None
    best_score = 0
    for sentence in sentences:
        haystack = _normalize_match_term(sentence)
        score = sum(1 for term in normalized_terms if term in haystack)
        if score > best_score:
            best_sentence = sentence
            best_score = score
    return _trim_excerpt(best_sentence) if best_sentence and best_score > 0 else None


def _normalize_match_term(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _trim_excerpt(value: str | None) -> str | None:
    if not value:
        return None
    trimmed = value.strip()
    if len(trimmed) <= 240:
        return trimmed
    return f"{trimmed[:237].rstrip()}..."
