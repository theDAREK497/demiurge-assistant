import json
import re
from typing import Protocol

from pydantic import ValidationError

from worldbuilder_core.models import EntityType, VerificationStatus
from worldbuilder_core.schemas import ExtractedEntityDraft, ExtractionPayload, LLMChatRequest, LLMMessage
from worldbuilder_core.services.world_configuration import normalize_key


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
    "evidence": "clue",
    "proof": "clue",
    "lead": "clue",
    "улика": "clue",
    "доказательство": "clue",
    "зацепка": "clue",
    "concept": "concept",
    "setting_element": "concept",
    "setting": "concept",
    "world_concept": "concept",
    "worldbuilding_concept": "concept",
    "theme": "concept",
    "lore": "concept",
    "quest": "event",
    "mission": "event",
    "adventure_hook": "event",
    "квест": "event",
    "задание": "event",
}

QUEST_TYPE_ALIASES = {"quest", "mission", "adventure_hook", "квест", "задание"}
QUEST_TAG_ALIASES = {
    "quest",
    "quests",
    "mission",
    "missions",
    "adventure_hook",
    "квест",
    "квесты",
    "квестовый",
    "задание",
    "задания",
    "миссия",
    "миссии",
}
RANDOM_TABLE_TYPE_ALIASES = {
    "random_table",
    "random table",
    "roll_table",
    "table",
    "случайная таблица",
    "таблица",
}

GENERIC_REFERENCE_VALUES = {"", "id", "entity", "entity_id", "client_id", "new", "new_entity"}
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
QUEST_REQUEST_PATTERN = re.compile(
    r"(?iu)\b(?:quests?|missions?|adventure[ _-]?hooks?|квест\w*|задани\w*|мисси\w*)\b"
)
QUEST_STAGE_PATTERN = re.compile(r"(?iu)\b(?:stage|act|этап|акт)\s*(?:[ivx]+|\d+)?\b")
QUEST_SECTION_PATTERN = re.compile(
    r"(?iu)^(?:objective|goal|quest giver|reward|failure|цель|заказчик|награда|последств\w*|осложнен\w*)\b"
)


async def extract_payload_with_llm(
    *,
    llm_client: SupportsLLMChat,
    source_text: str,
    context_text: str,
    max_entities: int,
    output_language: str = "ru",
    model: str | None = None,
    intent_text: str | None = None,
    truncate_excess_entities: bool = False,
) -> ExtractionPayload:
    extraction_request = build_extraction_request(
        source_text=source_text,
        context_text=context_text,
        max_entities=max_entities,
        output_language=output_language,
        model=model,
        intent_text=intent_text,
    )
    completion = await llm_client.chat(extraction_request)
    try:
        payload = parse_extraction_payload(
            completion.message.content,
            max_entities=max_entities,
            truncate_excess_entities=truncate_excess_entities,
        )
    except ExtractionParseError as first_error:
        repair_request = build_repair_request(
            original_request=extraction_request,
            broken_content=completion.message.content,
            error=str(first_error),
        )
        repaired_completion = await llm_client.chat(repair_request)
        payload = parse_extraction_payload(
            repaired_completion.message.content,
            max_entities=max_entities,
            truncate_excess_entities=truncate_excess_entities,
        )
    payload = ensure_requested_quest_entity(
        payload,
        source_text=source_text,
        intent_text=intent_text,
    )
    payload = compact_extracted_entity_text(payload, source_text)
    return annotate_payload_with_source_excerpts(payload, source_text)


def build_extraction_request(
    *,
    source_text: str,
    context_text: str,
    max_entities: int,
    output_language: str = "ru",
    model: str | None = None,
    intent_text: str | None = None,
) -> LLMChatRequest:
    language_name = "English" if output_language == "en" else "Russian"
    return LLMChatRequest(
        model=model,
        temperature=0.0,
        max_tokens=768,
        response_format=_extraction_response_format(max_entities),
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You extract structured wiki updates for Worldbuilder Core. "
                    "Return only valid JSON matching this shape: "
                    '{"entities":[],"relationships":[],"world_rules":[],"random_tables":[],"random_table_rows":[],"notes":[]}. '
                    "Prefer entity types character, location, faction, item, event, clue, concept. "
                    "When none fits, create a concise stable snake_case entity type; it will be added to the world. "
                    "Never invent stable UUIDs. Use client_id for new entities, and use match_entity_id only "
                    "when the context gives an existing entity UUID. "
                    "Relationships must use source_client_id or source_entity_id, and target_client_id or "
                    "target_entity_id, plus a stable snake_case type and a readable label in the requested language. "
                    "World rules must use condition and effect strings. "
                    "Create a separate entity for every distinct quest, event, and clue. A clue is concrete evidence, "
                    "trace, document, testimony, anomaly, or fact that can lead to a conclusion; use type 'clue'. "
                    "Never merge several events or quests into one entity and never copy the whole source text into "
                    "an entity description. Keep each summary under 500 characters and each description focused only "
                    "on that entity. "
                    "When the text describes a quest or mission, always create one primary event entity tagged 'quest'; "
                    "supporting locations, characters, and items do not replace the quest entity. "
                    "For every event and quest, copy its explicit date, era, sequence marker, or order into "
                    "attributes.timeline_date. Do not invent a date when none is stated. "
                    "Every relationship must include confidence and weight. Confidence rubric: 1.0 only for an "
                    "explicitly confirmed statement, 0.85 for a direct but contextual statement, 0.65 for a strong "
                    "inference, 0.4 for a weak hypothesis. Weight is relationship strength from 0 to 10. Include "
                    "valid_from, valid_to, and evidence when the text provides them. "
                    "For a new random table use random_tables with client_id, name, description, and is_secret. "
                    "Its rows must use table_client_id. For an existing table use table_id from context. "
                    "Never represent random tables or their rows as entities or relationships. "
                    "Do not use LaTeX or dollar-delimited math. Write coordinates and symbols as plain text. "
                    f"Write all names, summaries, descriptions, world rule conditions/effects, and notes in {language_name}. "
                    f"Extract at most {max_entities} entities. "
                    "Use status 'unknown' when uncertain, otherwise use 'proposed'."
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Authoritative world context:\n{context_text}\n\n"
                    f"Original user intent:\n{intent_text or 'Not provided.'}\n\n"
                    f"Text to extract:\n{source_text}"
                ),
            ),
        ],
    )


def _extraction_response_format(max_entities: int) -> dict:
    string = {"type": "string", "maxLength": 500}
    long_string = {"type": "string", "maxLength": 2_000}
    boolean = {"type": "boolean"}
    number = {"type": "number"}
    string_array = {"type": "array", "items": string, "maxItems": 20}

    def object_array(properties: dict, required: list[str], max_items: int) -> dict:
        return {
            "type": "array",
            "maxItems": max_items,
            "items": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        }

    entity_attributes = {
        "type": "object",
        "properties": {
            "timeline_date": string,
            "module": string,
            "quest_status": string,
        },
        "additionalProperties": False,
    }
    schema = {
        "type": "object",
        "properties": {
            "entities": object_array(
                {
                    "client_id": string,
                    "match_entity_id": string,
                    "type": string,
                    "name": string,
                    "summary": string,
                    "description": long_string,
                    "aliases": string_array,
                    "tags": string_array,
                    "is_secret": boolean,
                    "status": string,
                    "attributes": entity_attributes,
                },
                ["type", "name"],
                max_entities,
            ),
            "relationships": object_array(
                {
                    "source_client_id": string,
                    "source_entity_id": string,
                    "target_client_id": string,
                    "target_entity_id": string,
                    "type": string,
                    "label": string,
                    "description": long_string,
                    "confidence": number,
                    "weight": number,
                    "valid_from": string,
                    "valid_to": string,
                    "evidence": long_string,
                    "is_secret": boolean,
                    "status": string,
                },
                ["type"],
                12,
            ),
            "world_rules": object_array(
                {
                    "priority": {"type": "integer"},
                    "condition": long_string,
                    "effect": long_string,
                    "tags": string_array,
                    "is_active": boolean,
                    "is_secret": boolean,
                    "status": string,
                },
                ["condition", "effect"],
                6,
            ),
            "random_tables": object_array(
                {
                    "client_id": string,
                    "name": string,
                    "description": long_string,
                    "is_secret": boolean,
                },
                ["client_id", "name"],
                4,
            ),
            "random_table_rows": object_array(
                {
                    "table_id": string,
                    "table_client_id": string,
                    "label": string,
                    "result": long_string,
                    "weight": {"type": "integer"},
                    "is_secret": boolean,
                },
                ["result"],
                12,
            ),
            "notes": {"type": "array", "items": long_string, "maxItems": 5},
        },
        "required": [
            "entities",
            "relationships",
            "world_rules",
            "random_tables",
            "random_table_rows",
            "notes",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
            "json_schema": {
                "name": "worldbuilder_extraction",
                "strict": False,
                "schema": schema,
        },
    }


def build_repair_request(
    *,
    original_request: LLMChatRequest,
    broken_content: str,
    error: str,
) -> LLMChatRequest:
    return LLMChatRequest(
        model=original_request.model,
        temperature=0.0,
        response_format=original_request.response_format,
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
                    "Keep relationship type stable and machine-readable, and add a readable relationship label. "
                    "Use condition/effect for world rules. "
                    "Use random_tables for new tables and random_table_rows for entries. New rows must reference "
                    "a new table_client_id; existing rows must use only table_id values from context. "
                    "A quest must be an event entity with the tag 'quest'."
                    " Split distinct quests, events, and clues into separate entities. Put explicit event dates in "
                    "attributes.timeline_date. Relationship confidence must follow the 1.0/0.85/0.65/0.4 rubric."
                ),
            ),
        ],
    )


def parse_extraction_payload(
    content: str,
    *,
    max_entities: int,
    truncate_excess_entities: bool = False,
) -> ExtractionPayload:
    try:
        raw = json.loads(_extract_json_text(content))
        payload = ExtractionPayload.model_validate(_normalize_extraction_payload(raw))
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        raise ExtractionParseError(str(exc)) from exc

    if len(payload.entities) > max_entities:
        if truncate_excess_entities:
            original_client_ids = {entity.client_id for entity in payload.entities if entity.client_id}
            kept_entities = payload.entities[:max_entities]
            kept_client_ids = {entity.client_id for entity in kept_entities if entity.client_id}
            kept_relationships = [
                relationship
                for relationship in payload.relationships
                if not (
                    relationship.source_client_id in original_client_ids - kept_client_ids
                    or relationship.target_client_id in original_client_ids - kept_client_ids
                )
            ]
            return payload.model_copy(
                update={
                    "entities": kept_entities,
                    "relationships": kept_relationships,
                }
            )
        raise ExtractionParseError(f"Extracted {len(payload.entities)} entities; maximum is {max_entities}")
    return payload


def ensure_requested_quest_entity(
    payload: ExtractionPayload,
    *,
    source_text: str,
    intent_text: str | None = None,
) -> ExtractionPayload:
    request_text = intent_text or source_text
    if not QUEST_REQUEST_PATTERN.search(request_text):
        return payload

    entities = list(payload.entities)
    quest_title = _extract_quest_title(source_text)
    candidate_index = _find_quest_candidate_index(entities, quest_title)
    if candidate_index is not None:
        candidate = entities[candidate_index]
        entities[candidate_index] = candidate.model_copy(
            update={
                "type": EntityType.event,
                "tags": _merge_unique_strings(candidate.tags, ["quest"]),
                "attributes": {**candidate.attributes, "module": "quest"},
            }
        )
        return payload.model_copy(update={"entities": entities})

    title = quest_title or ("New quest" if _looks_english(intent_text or source_text) else "Новый квест")
    used_client_ids = {entity.client_id for entity in entities if entity.client_id}
    client_id = _unique_quest_client_id(title, used_client_ids)
    entities.append(
        ExtractedEntityDraft(
            client_id=client_id,
            type=EntityType.event,
            name=title[:200],
            summary=_extract_quest_summary(source_text),
            description=_extract_quest_description(source_text),
            tags=["quest"],
            status=VerificationStatus.proposed,
            attributes={"module": "quest"},
        )
    )
    return payload.model_copy(update={"entities": entities})


def _find_quest_candidate_index(entities: list[ExtractedEntityDraft], quest_title: str | None) -> int | None:
    for index, entity in enumerate(entities):
        if entity.type == EntityType.event and "quest" in _normalize_quest_tags(entity.tags):
            return index

    if quest_title:
        title_tokens = set(_normalize_match_term(quest_title).split())
        for index, entity in enumerate(entities):
            if entity.type != EntityType.event or QUEST_STAGE_PATTERN.search(entity.name):
                continue
            name_tokens = set(_normalize_match_term(entity.name).split())
            if title_tokens and (
                title_tokens.issubset(name_tokens)
                or name_tokens.issubset(title_tokens)
                or _normalize_match_term(quest_title) in _normalize_match_term(entity.name)
            ):
                return index

    likely_events = [
        index
        for index, entity in enumerate(entities)
        if entity.type == EntityType.event
        and not QUEST_STAGE_PATTERN.search(entity.name)
        and (
            _name_explicitly_marks_quest(entity.name)
            or re.match(r"(?iu)^\s*(?:quest|mission|квест|задание)\b", entity.summary or "")
        )
    ]
    if likely_events:
        return likely_events[0]

    non_stage_events = [
        index
        for index, entity in enumerate(entities)
        if entity.type == EntityType.event and not QUEST_STAGE_PATTERN.search(entity.name)
    ]
    return non_stage_events[0] if len(non_stage_events) == 1 else None


def _extract_quest_title(source_text: str) -> str | None:
    heading_candidates: list[str] = []
    for raw_line in source_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        clean_line = re.sub(r"^#{1,6}\s*", "", line)
        clean_line = clean_line.strip("* _`#")
        explicit = re.match(
            r"(?iu)^(?:quest(?:\s+hook)?|mission|adventure\s+hook|квест\w*(?:\s+крючок)?|задание)\s*[:\-–—]\s*(.+)$",
            clean_line,
        )
        if explicit:
            title = _clean_quest_title(explicit.group(1))
            if title:
                return title
        if line.startswith("#"):
            heading_candidates.append(clean_line)

    for heading in heading_candidates:
        title = _clean_quest_title(heading)
        if title and not QUEST_SECTION_PATTERN.match(title) and not re.fullmatch(
            r"(?iu)(?:quest(?:\s+hook)?|mission|adventure\s+hook|квест\w*(?:\s+крючок)?|задание)",
            title,
        ):
            return title
    return None


def _clean_quest_title(value: str) -> str | None:
    title = value.strip().strip("* _`#\"'«»“”")
    title = re.sub(r"\s+", " ", title).strip()
    if not title or len(title) > 200:
        return None
    if any(character.isalpha() for character in title) and title == title.upper():
        title = title.capitalize()
    return title


def _extract_quest_summary(source_text: str) -> str | None:
    lines = source_text.splitlines()
    for index, raw_line in enumerate(lines):
        heading = re.sub(r"^[#*\s]+", "", raw_line).strip()
        if not re.match(r"(?iu)^(?:objective|goal|цель(?:\s+миссии)?)\b", heading):
            continue
        for candidate in lines[index + 1 :]:
            clean = _strip_markdown(candidate)
            if clean:
                return clean[:500]

    for paragraph in re.split(r"\n\s*\n", source_text):
        clean = _strip_markdown(paragraph)
        if clean and not QUEST_REQUEST_PATTERN.fullmatch(clean) and not clean.lower().startswith(("hello", "привет")):
            return clean[:500]
    return None


def _extract_quest_description(source_text: str) -> str | None:
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", source_text):
        clean = _strip_markdown(paragraph)
        if not clean:
            continue
        paragraphs.append(clean)
        if sum(len(item) for item in paragraphs) >= 1_500:
            break
    description = "\n\n".join(paragraphs).strip()
    return description[:2_000] or None


def compact_extracted_entity_text(
    payload: ExtractionPayload,
    source_text: str,
) -> ExtractionPayload:
    source_normalized = re.sub(r"\s+", " ", source_text).strip()
    entities = []
    for entity in payload.entities:
        description = entity.description
        limit = 2_500 if entity.type in {EntityType.event, EntityType.clue} else 8_000
        if description:
            normalized = re.sub(r"\s+", " ", description).strip()
            copied_whole_source = (
                len(source_normalized) > 2_000
                and len(normalized) >= len(source_normalized) * 0.8
                and normalized[:500] == source_normalized[:500]
            )
            if copied_whole_source:
                description = entity.summary
            elif len(description) > limit:
                description = description[:limit].rsplit(" ", 1)[0].rstrip() + "..."
        entities.append(entity.model_copy(update={"description": description}))
    return payload.model_copy(update={"entities": entities})


def _strip_markdown(value: str) -> str:
    value = re.sub(r"^[#>*\-\s]+", "", value.strip())
    value = re.sub(r"[*_`]+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _unique_quest_client_id(title: str, used_client_ids: set[str]) -> str:
    base = f"quest-{_slugify(title)}"[:80].rstrip("-") or "quest"
    candidate = base
    suffix = 2
    while candidate in used_client_ids:
        suffix_text = f"-{suffix}"
        candidate = f"{base[: 80 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def _looks_english(value: str) -> bool:
    latin = len(re.findall(r"[A-Za-z]", value))
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", value))
    return latin > cyrillic


def _normalize_quest_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        marker = re.sub(r"[\s-]+", "_", tag.casefold().strip())
        value = "quest" if marker in QUEST_TAG_ALIASES or marker.startswith(("квест", "мисси")) else tag
        if value not in normalized:
            normalized.append(value)
    return normalized


def _name_explicitly_marks_quest(name: str) -> bool:
    return bool(re.search(r"(?iu)(?:^|[\s(\[:\-])(?:quest|mission|квест\w*|задание)(?:$|[\s)\]:\-])", name))


def _merge_unique_strings(current: list[str], incoming: list[str]) -> list[str]:
    merged = list(current)
    for value in incoming:
        if value not in merged:
            merged.append(value)
    return merged


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

    raw_entities = _as_list(raw.get("entities"))
    raw_table_entities = [entity for entity in raw_entities if _is_random_table_entity(entity)]
    raw_wiki_entities = [entity for entity in raw_entities if not _is_random_table_entity(entity)]
    entity_aliases: dict[str, str] = {}
    table_aliases: dict[str, str] = {}
    entities = _normalize_entities(raw_wiki_entities, entity_aliases)
    random_tables, nested_rows = _normalize_random_tables(
        [*_as_list(raw.get("random_tables") or raw.get("tables")), *raw_table_entities],
        table_aliases,
    )
    relationship_rows, wiki_relationships = _extract_table_rows_from_relationships(
        raw.get("relationships"),
        table_aliases,
        raw_entities,
    )
    relationships = _normalize_relationships(wiki_relationships, entity_aliases)
    world_rules = _normalize_world_rules(raw.get("world_rules"))
    random_table_rows = _normalize_random_table_rows(
        [
            *_as_list(raw.get("random_table_rows") or raw.get("random_table_entries") or raw.get("table_rows")),
            *nested_rows,
            *relationship_rows,
        ],
        table_aliases,
    )
    notes = _normalize_notes(raw.get("notes"))
    return {
        "entities": entities,
        "relationships": relationships,
        "world_rules": world_rules,
        "random_tables": random_tables,
        "random_table_rows": random_table_rows,
        "notes": notes,
    }


def _normalize_entities(raw_entities: object, entity_aliases: dict[str, str]) -> list[dict]:
    entities: list[dict] = []
    used_client_ids: set[str] = set()

    for index, raw_entity in enumerate(_as_list(raw_entities)):
        if not isinstance(raw_entity, dict):
            continue

        name = _clean_string(raw_entity.get("name") or raw_entity.get("title"))
        if not name:
            summary_name = _clean_string(raw_entity.get("summary"))
            if summary_name:
                name = re.split(r"(?<=[.!?])\s", summary_name, maxsplit=1)[0][:200]
        if not name:
            continue

        raw_entity_type = _clean_string(raw_entity.get("type")) or ""
        entity_type = _normalize_entity_type(raw_entity_type)
        description = _clean_string(raw_entity.get("description"))
        summary = _clean_string(raw_entity.get("summary"))
        if summary is None and description:
            summary = description[:500]

        match_entity_id = _clean_string(raw_entity.get("match_entity_id"))
        client_id = None if match_entity_id else _build_client_id(raw_entity, name, used_client_ids, index)

        tags = _normalize_quest_tags(_normalize_string_list(raw_entity.get("tags")))
        quest_marker = _clean_string(
            raw_entity.get("kind")
            or raw_entity.get("category")
            or raw_entity.get("entity_type")
            or _normalize_attributes(raw_entity.get("attributes")).get("module")
        )
        if (
            raw_entity_type.casefold() in QUEST_TYPE_ALIASES
            or (quest_marker and quest_marker.casefold() in QUEST_TAG_ALIASES)
            or _name_explicitly_marks_quest(name)
        ) and "quest" not in tags:
            tags.append("quest")

        attributes = _normalize_attributes(raw_entity.get("attributes"))
        existing_timeline_date = _clean_optional_fact(attributes.get("timeline_date"))
        if existing_timeline_date:
            attributes["timeline_date"] = existing_timeline_date[:120]
        else:
            attributes.pop("timeline_date", None)
        timeline_date = _clean_optional_fact(
            raw_entity.get("timeline_date")
            or raw_entity.get("date")
            or raw_entity.get("event_date")
            or raw_entity.get("time")
        )
        if timeline_date and "timeline_date" not in attributes:
            attributes["timeline_date"] = timeline_date[:120]

        entity = {
            "client_id": client_id,
            "match_entity_id": match_entity_id,
            "type": entity_type,
            "name": name,
            "summary": summary,
            "description": description,
            "aliases": _normalize_string_list(raw_entity.get("aliases")),
            "tags": tags,
            "is_secret": bool(raw_entity.get("is_secret", False)),
            "status": _normalize_status(raw_entity.get("status")),
            "attributes": attributes,
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

        attributes = _normalize_attributes(raw_relationship.get("attributes"))
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
                "weight": _normalize_relationship_weight(
                    raw_relationship.get("weight") or attributes.get("weight")
                ),
                "valid_from": _clean_optional_fact(
                    raw_relationship.get("valid_from") or attributes.get("valid_from")
                ),
                "valid_to": _clean_optional_fact(
                    raw_relationship.get("valid_to") or attributes.get("valid_to")
                ),
                "evidence": _clean_optional_fact(
                    raw_relationship.get("evidence")
                    or raw_relationship.get("source_excerpt")
                    or attributes.get("evidence")
                ),
                "is_secret": bool(raw_relationship.get("is_secret", False)),
                "status": _normalize_status(raw_relationship.get("status")),
                "attributes": attributes,
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


def _normalize_random_tables(raw_tables: object, table_aliases: dict[str, str]) -> tuple[list[dict], list[dict]]:
    tables: list[dict] = []
    nested_rows: list[dict] = []
    used_client_ids: set[str] = set()

    for index, raw_table in enumerate(_as_list(raw_tables)):
        if not isinstance(raw_table, dict):
            continue
        name = _clean_string(raw_table.get("name") or raw_table.get("title"))
        if not name:
            continue
        client_id = _build_named_client_id(raw_table, name, used_client_ids, index, "table")
        tables.append(
            {
                "client_id": client_id,
                "source_excerpt": _clean_string(raw_table.get("source_excerpt")),
                "name": name,
                "description": _clean_string(raw_table.get("description") or raw_table.get("summary")),
                "is_secret": bool(raw_table.get("is_secret", False)),
            }
        )
        for alias in _collect_table_aliases(raw_table, name):
            table_aliases[alias] = client_id
        for raw_row in _as_list(raw_table.get("rows") or raw_table.get("entries") or raw_table.get("results")):
            if isinstance(raw_row, str):
                raw_row = {"result": raw_row}
            if isinstance(raw_row, dict):
                nested_rows.append({**raw_row, "table_client_id": client_id})

    return tables, nested_rows


def _normalize_random_table_rows(raw_rows: object, table_aliases: dict[str, str] | None = None) -> list[dict]:
    rows: list[dict] = []
    table_aliases = table_aliases or {}

    for raw_row in _as_list(raw_rows):
        if not isinstance(raw_row, dict):
            continue

        explicit_table_id = _clean_string(
            raw_row.get("table_id") or raw_row.get("random_table_id") or raw_row.get("target_table_id")
        )
        explicit_client_id = _clean_string(raw_row.get("table_client_id"))
        generic_table_ref = _clean_string(raw_row.get("table"))
        table_client_id = explicit_client_id
        table_id = explicit_table_id
        if table_client_id:
            table_id = None
        elif table_id and _lookup_alias(table_aliases, table_id):
            table_client_id = _lookup_alias(table_aliases, table_id)
            table_id = None
        elif not table_id and generic_table_ref:
            table_client_id = _lookup_alias(table_aliases, generic_table_ref) or _slugify(generic_table_ref) or None
        result = _clean_string(
            raw_row.get("result")
            or raw_row.get("text")
            or raw_row.get("entry")
            or raw_row.get("outcome")
            or raw_row.get("description")
        )
        if (not table_id and not table_client_id) or not result:
            continue

        rows.append(
            {
                "table_id": table_id,
                "table_client_id": table_client_id,
                "source_excerpt": _clean_string(raw_row.get("source_excerpt")),
                "label": _clean_string(raw_row.get("label") or raw_row.get("name") or raw_row.get("title")),
                "result": result,
                "weight": _normalize_weight(raw_row.get("weight")),
                "is_secret": bool(raw_row.get("is_secret", False)),
            }
        )

    return rows


def _extract_table_rows_from_relationships(
    raw_relationships: object,
    table_aliases: dict[str, str],
    raw_entities: list,
) -> tuple[list[dict], list]:
    rows: list[dict] = []
    relationships: list = []
    entity_lookup: dict[str, dict] = {}
    for raw_entity in raw_entities:
        if not isinstance(raw_entity, dict):
            continue
        name = _clean_string(raw_entity.get("name"))
        if not name:
            continue
        for alias in _collect_entity_aliases(raw_entity, name):
            entity_lookup[alias.casefold()] = raw_entity

    row_relationship_types = {
        "contains",
        "includes",
        "has_entry",
        "table_entry",
        "entry",
        "result",
        "roll_result",
        "содержит",
        "результат",
        "строка_таблицы",
    }
    for raw_relationship in _as_list(raw_relationships):
        if not isinstance(raw_relationship, dict):
            continue
        source = _clean_string(
            raw_relationship.get("source_client_id")
            or raw_relationship.get("source_entity_id")
            or raw_relationship.get("source_id")
            or raw_relationship.get("source")
        )
        target = _clean_string(
            raw_relationship.get("target_client_id")
            or raw_relationship.get("target_entity_id")
            or raw_relationship.get("target_id")
            or raw_relationship.get("target")
        )
        relation_type = _clean_string(raw_relationship.get("type") or raw_relationship.get("relationship_type")) or ""
        source_table = _lookup_alias(table_aliases, source)
        target_table = _lookup_alias(table_aliases, target)
        if relation_type.casefold() in row_relationship_types and bool(source_table) != bool(target_table):
            row_ref = target if source_table else source
            raw_row_entity = entity_lookup.get((row_ref or "").casefold(), {})
            result = _clean_string(
                raw_row_entity.get("description")
                or raw_row_entity.get("summary")
                or raw_row_entity.get("name")
                or raw_relationship.get("description")
                or row_ref
            )
            if result:
                rows.append(
                    {
                        "table_client_id": source_table or target_table,
                        "label": _clean_string(raw_row_entity.get("name") or raw_relationship.get("label")),
                        "result": result,
                        "weight": raw_relationship.get("weight", 1),
                        "is_secret": bool(raw_relationship.get("is_secret", False)),
                    }
                )
            continue
        relationships.append(raw_relationship)
    return rows, relationships


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
        source_excerpt = (
            relationship.source_excerpt
            or _find_best_excerpt(
                sentences,
                [
                    source_label,
                    target_label,
                    relationship.label or "",
                    relationship.type,
                    relationship.description or "",
                ],
            )
            or fallback_excerpt
        )
        relationships.append(
            relationship.model_copy(
                update={
                    "source_excerpt": source_excerpt,
                    "evidence": relationship.evidence or source_excerpt,
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

    random_tables = [
        table.model_copy(
            update={
                "source_excerpt": table.source_excerpt
                or _find_best_excerpt(sentences, [table.name, table.description or ""])
                or fallback_excerpt,
            }
        )
        for table in payload.random_tables
    ]

    return payload.model_copy(
        update={
            "entities": entities,
            "relationships": relationships,
            "world_rules": rules,
            "random_tables": random_tables,
            "random_table_rows": random_table_rows,
        }
    )


def _normalize_entity_type(raw_type: object) -> str:
    value = _clean_string(raw_type)
    if not value:
        return "concept"
    return ENTITY_TYPE_ALIASES.get(value.lower(), normalize_key(value))


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
        return 0.65
    return max(0.0, min(confidence, 1.0))


def _normalize_relationship_weight(raw_weight: object) -> float:
    try:
        weight = float(raw_weight)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, min(weight, 10.0))


def _normalize_attributes(raw_attributes: object) -> dict:
    return dict(raw_attributes) if isinstance(raw_attributes, dict) else {}


def _clean_optional_fact(value: object) -> str | None:
    cleaned = _clean_string(value)
    if not cleaned:
        return None
    if cleaned.casefold() in {
        "-",
        "—",
        "n/a",
        "none",
        "null",
        "unknown",
        "not specified",
        "не указано",
        "неизвестно",
        "нет",
    }:
        return None
    return cleaned


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


def _build_named_client_id(
    raw_item: dict,
    name: str,
    used_client_ids: set[str],
    index: int,
    fallback_prefix: str,
) -> str:
    preferred = _clean_string(raw_item.get("client_id")) or _clean_string(raw_item.get("id"))
    candidate = _slugify(preferred or name) or f"{fallback_prefix}-{index + 1}"
    unique_candidate = candidate
    suffix = 2
    while unique_candidate in used_client_ids:
        unique_candidate = f"{candidate}-{suffix}"
        suffix += 1
    used_client_ids.add(unique_candidate)
    return unique_candidate


def _is_random_table_entity(raw_entity: object) -> bool:
    if not isinstance(raw_entity, dict):
        return False
    raw_type = _clean_string(raw_entity.get("type") or raw_entity.get("entity_type"))
    return bool(raw_type and raw_type.lower() in RANDOM_TABLE_TYPE_ALIASES)


def _collect_table_aliases(raw_table: dict, name: str) -> set[str]:
    aliases = {name}
    for key in ("client_id", "id", "table_id", "name", "title"):
        value = _clean_string(raw_table.get(key))
        if value:
            aliases.add(value)
    return aliases


def _lookup_alias(aliases: dict[str, str], value: str | None) -> str | None:
    if not value:
        return None
    if value in aliases:
        return aliases[value]
    folded = value.casefold()
    return next((target for alias, target in aliases.items() if alias.casefold() == folded), None)


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
