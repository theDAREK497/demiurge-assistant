import json
import re
from typing import Protocol

from json_repair import repair_json
from pydantic import ValidationError

from worldbuilder_core.models import EntityType, VerificationStatus
from worldbuilder_core.schemas import (
    ExtractedEntityDraft,
    ExtractionPayload,
    LLMChatRequest,
    LLMMessage,
)
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
    "world": "concept",
    "universe": "concept",
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
TECHNICAL_NAME_PATTERN = re.compile(
    r"(?iu)^(?:(?:c|s)\d+[ _-]+)*(?:c|cl|clnt|char|character|fac|faction|loc|location|ent|entity|"
    r"item|event|concept)[ _-]*\d+$"
)
GENERIC_SUBJECTS = {
    "artifact",
    "contains",
    "character",
    "concept",
    "entity",
    "event",
    "faction",
    "group",
    "item",
    "location",
    "material",
    "object",
    "organization",
    "person",
    "place",
    "region",
    "артефакт",
    "группа",
    "концепт",
    "локация",
    "материал",
    "место",
    "объект",
    "организация",
    "персонаж",
    "регион",
    "событие",
    "сущность",
    "фракция",
    "включает",
    "это",
}


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
    structured_output: bool = True,
    max_output_tokens: int | None = None,
) -> ExtractionPayload:
    extraction_request = build_extraction_request(
        source_text=source_text,
        context_text=context_text,
        max_entities=max_entities,
        output_language=output_language,
        model=model,
        intent_text=intent_text,
        structured_output=structured_output,
        max_output_tokens=max_output_tokens,
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
    payload = prefer_source_language_names(payload, source_text, output_language)
    payload = compact_extracted_entity_text(payload, source_text)
    return annotate_payload_with_source_excerpts(payload, source_text)


async def generate_adventure_payload_with_llm(
    *,
    llm_client: SupportsLLMChat,
    premise: str,
    context_text: str,
    scale: str,
    tone: str | None,
    enabled_modules: list[str],
    max_entities: int,
    output_language: str = "ru",
    model: str | None = None,
) -> ExtractionPayload:
    request = build_adventure_request(
        premise=premise,
        context_text=context_text,
        scale=scale,
        tone=tone,
        enabled_modules=enabled_modules,
        max_entities=max_entities,
        output_language=output_language,
        model=model,
    )
    completion = await llm_client.chat(request)
    try:
        payload = parse_adventure_package(completion.message.content, max_entities=max_entities)
        validate_adventure_payload(payload, enabled_modules)
    except ExtractionParseError as first_error:
        repair_request = build_repair_request(
            original_request=request,
            broken_content=completion.message.content,
            error=str(first_error),
        )
        repaired_completion = await llm_client.chat(repair_request)
        payload = parse_adventure_package(repaired_completion.message.content, max_entities=max_entities)
        validate_adventure_payload(payload, enabled_modules)
    return payload


def build_adventure_request(
    *,
    premise: str,
    context_text: str,
    scale: str,
    tone: str | None,
    enabled_modules: list[str],
    max_entities: int,
    output_language: str = "ru",
    model: str | None = None,
) -> LLMChatRequest:
    language_name = "English" if output_language == "en" else "Russian"
    modules = ", ".join(enabled_modules) or "graph, timeline, quests, randomTables, detectiveBoard"
    return LLMChatRequest(
        model=model,
        temperature=0.65,
        max_tokens=1_536,
        reasoning_effort="none",
        response_format=_adventure_response_format(max_entities),
        messages=[
            LLMMessage(
                role="system",
                content=(
                    "You create a playable adventure directly as structured Worldbuilder JSON. "
                    "This is creative generation, not extraction or a prose answer. Return JSON only. "
                    "Use the supplied world context as authoritative lore and reuse existing entities with "
                    "match_entity_id. Never make renamed copies of existing entities. "
                    "Fill the required quest, clue, timeline_event, random_table, and supporting_entities fields. "
                    "The quest description must contain hook, goal, stakes, stages, obstacles, and outcome. "
                    "Use the fixed client references quest, clue, and timeline_event in relationships. "
                    "Connect these and supporting entities with at least two relationships. "
                    "Every relationship needs a readable label, confidence from the evidence rubric, weight from "
                    "0 to 10, and short evidence. Create one useful random table and at least three rows linked by "
                    "table_client_id. Do not represent a table as an entity or relationship. "
                    "Use only concise names, one-sentence summaries, and focused descriptions. "
                    "Do not use Markdown, LaTeX, or dollar-delimited math inside JSON strings. "
                    f"Write all generated content in {language_name}. At most {max_entities} entities."
                ),
            ),
            LLMMessage(
                role="user",
                content=(
                    f"Authoritative world context:\n{context_text}\n\n"
                    f"Adventure premise:\n{premise}\n\n"
                    f"Scale: {scale}\nTone: {tone or 'match the world'}\nEnabled modules: {modules}\n"
                    "Create one coherent package that can be reviewed and applied as a draft."
                ),
            ),
        ],
    )


def _adventure_response_format(max_entities: int) -> dict:
    string = {"type": "string", "maxLength": 500}
    long_string = {"type": "string", "maxLength": 1_200}
    entity = {
        "type": "object",
        "properties": {
            "client_id": string,
            "type": string,
            "name": string,
            "summary": string,
            "description": long_string,
        },
        "required": ["client_id", "type", "name", "summary", "description"],
        "additionalProperties": False,
    }
    relationship = {
        "type": "object",
        "properties": {
            "source_client_id": string,
            "target_client_id": string,
            "type": string,
            "label": string,
            "confidence": {"type": "number"},
            "weight": {"type": "number"},
            "evidence": long_string,
        },
        "required": [
            "source_client_id",
            "target_client_id",
            "type",
            "label",
            "confidence",
            "weight",
            "evidence",
        ],
        "additionalProperties": False,
    }
    named_content = {
        "type": "object",
        "properties": {"name": string, "summary": string, "description": long_string},
        "required": ["name", "summary", "description"],
        "additionalProperties": False,
    }
    quest = {
        "type": "object",
        "properties": {
            **named_content["properties"],
            "quest_status": string,
            "timeline_date": string,
        },
        "required": ["name", "summary", "description", "quest_status", "timeline_date"],
        "additionalProperties": False,
    }
    timeline_event = {
        "type": "object",
        "properties": {**named_content["properties"], "timeline_date": string},
        "required": ["name", "summary", "description", "timeline_date"],
        "additionalProperties": False,
    }
    random_table = {
        "type": "object",
        "properties": {
            "name": string,
            "description": long_string,
            "rows": {"type": "array", "minItems": 3, "maxItems": 3, "items": long_string},
        },
        "required": ["name", "description", "rows"],
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "worldbuilder_adventure",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "quest": quest,
                    "clue": named_content,
                    "timeline_event": timeline_event,
                    "supporting_entities": {
                        "type": "array",
                        "maxItems": min(max(max_entities - 3, 1), 5),
                        "items": entity,
                    },
                    "relationships": {"type": "array", "maxItems": 6, "items": relationship},
                    "random_table": random_table,
                },
                "required": [
                    "quest",
                    "clue",
                    "timeline_event",
                    "supporting_entities",
                    "relationships",
                    "random_table",
                ],
                "additionalProperties": False,
            },
        },
    }


def parse_adventure_package(content: str, *, max_entities: int) -> ExtractionPayload:
    try:
        raw = _load_extraction_json(_extract_json_text(content))
        quest = raw["quest"]
        clue = raw["clue"]
        timeline_event = raw["timeline_event"]
        random_table = raw["random_table"]
        relationships = list(raw.get("relationships", []))
        if len(relationships) < 2:
            relationships.extend(
                [
                    {
                        "source_client_id": "clue",
                        "target_client_id": "quest",
                        "type": "reveals",
                        "label": "reveals",
                        "confidence": 0.85,
                        "weight": 7,
                        "evidence": clue["summary"],
                    },
                    {
                        "source_client_id": "timeline_event",
                        "target_client_id": "quest",
                        "type": "complicates",
                        "label": "complicates",
                        "confidence": 0.85,
                        "weight": 6,
                        "evidence": timeline_event["summary"],
                    },
                ][len(relationships) :]
            )
        normalized = {
            "entities": [
                {
                    "client_id": "quest",
                    "type": "event",
                    "name": quest["name"],
                    "summary": quest["summary"],
                    "description": quest["description"],
                    "tags": ["quest"],
                    "attributes": {
                        "module": "quest",
                        "quest_status": quest["quest_status"],
                        "timeline_date": quest["timeline_date"],
                    },
                },
                {
                    "client_id": "clue",
                    "type": "clue",
                    "name": clue["name"],
                    "summary": clue["summary"],
                    "description": clue["description"],
                },
                {
                    "client_id": "timeline_event",
                    "type": "event",
                    "name": timeline_event["name"],
                    "summary": timeline_event["summary"],
                    "description": timeline_event["description"],
                    "attributes": {"timeline_date": timeline_event["timeline_date"]},
                },
                *raw.get("supporting_entities", []),
            ],
            "relationships": relationships,
            "world_rules": [],
            "random_tables": [
                {
                    "client_id": "adventure_table",
                    "name": random_table["name"],
                    "description": random_table["description"],
                }
            ],
            "random_table_rows": [
                {
                    "table_client_id": "adventure_table",
                    "label": str(index),
                    "result": result,
                    "weight": 1,
                }
                for index, result in enumerate(random_table["rows"], start=1)
            ],
            "notes": [],
        }
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ExtractionParseError(f"Invalid adventure package: {exc}") from exc
    return parse_extraction_payload(json.dumps(normalized), max_entities=max_entities)


def validate_adventure_payload(payload: ExtractionPayload, enabled_modules: list[str]) -> None:
    modules = set(enabled_modules)
    errors: list[str] = []
    if "quests" in modules and not any("quest" in entity.tags for entity in payload.entities):
        errors.append("missing quest entity tagged quest")
    if "detectiveBoard" in modules and not any(entity.type == "clue" for entity in payload.entities):
        errors.append("missing clue entity")
    if "timeline" in modules and not any(
        entity.type == "event" and entity.attributes.get("timeline_date") for entity in payload.entities
    ):
        errors.append("missing timeline event with attributes.timeline_date")
    if "graph" in modules and len(payload.relationships) < 2:
        errors.append("at least two relationships are required")
    if "randomTables" in modules:
        if not payload.random_tables:
            errors.append("missing random table")
        if len(payload.random_table_rows) < 3:
            errors.append("random table needs at least three rows")
    if errors:
        raise ExtractionParseError("Adventure package incomplete: " + "; ".join(errors))


def build_extraction_request(
    *,
    source_text: str,
    context_text: str,
    max_entities: int,
    output_language: str = "ru",
    model: str | None = None,
    intent_text: str | None = None,
    structured_output: bool = True,
    max_output_tokens: int | None = None,
) -> LLMChatRequest:
    language_name = "English" if output_language == "en" else "Russian"
    return LLMChatRequest(
        model=model,
        temperature=0.0,
        max_tokens=max_output_tokens or max(1_536, min(4_096, max_entities * 240)),
        reasoning_effort="none",
        response_format=_extraction_response_format(max_entities) if structured_output else None,
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
                    "Every entity must include a short name. Keep summaries to one sentence and descriptions under "
                    "800 characters. Omit optional fields that add no information. "
                    "The name field is a display title, never a client ID and never a sentence: use the exact proper "
                    "name from the source, normally one to six words. Values such as Cl 001, Fac 002, Faction 003, "
                    "entity_1, or a descriptive sentence are forbidden. If the source does not name an object, do "
                    "not create an entity for it. "
                    "Extract reusable canon facts, not pieces of prose. Ignore tables of contents, chapter lists, "
                    "page numbers, headers, footers, copyright text, publisher metadata, decorative headings, "
                    "epigraphs, author notes, and navigation text. Do not turn metaphors, comparisons, dreams, "
                    "internal monologue, rhetorical examples, unnamed background people or props, or ordinary "
                    "moment-to-moment scene actions into entities. Narrative prose may still contain canon facts: "
                    "extract a named or otherwise stable world object only when the text makes a concrete assertion "
                    "about it. Create an event only for a distinct world-significant occurrence, not for every action. "
                    "Never treat a truncated word at the beginning or end of the source, a grammatical fragment, or "
                    "a status word such as alive/dead as an entity name. A short name must appear with its complete "
                    "spelling as an explicit subject in the source. "
                    "An entirely empty payload is correct when the passage contains no reusable world facts. "
                    "Never merge several events or quests into one entity and never copy the whole source text into "
                    "an entity description. Keep each summary under 500 characters and each description focused only "
                    "on that entity. "
                    "When the text describes a quest or mission, always create one primary event entity tagged 'quest'; "
                    "supporting locations, characters, and items do not replace the quest entity. "
                    "For every event and quest, copy its explicit date, era, sequence marker, or order into "
                    "attributes.timeline_date. Do not invent a date when none is stated. "
                    "Every relationship must include confidence and weight. Confidence rubric: 1.0 only for an "
                    "explicitly confirmed statement, 0.85 for a direct but contextual statement, 0.65 for a strong "
                    "inference, 0.4 for a weak hypothesis. Weight is semantic importance, not confidence: 1-2 means "
                    "incidental, 3-4 minor, 5-6 meaningful, 7-8 strong, 9 defining, and 10 inseparable. Most ordinary "
                    "relationships should be 3-6; use 7-10 only when the connection defines both entities. Use the "
                    "full scale instead of defaulting every relationship to a high value. Include "
                    "valid_from, valid_to, and evidence when the text provides them. "
                    "For a new random table use random_tables with client_id, name, description, and is_secret. "
                    "Its rows must use table_client_id. For an existing table use table_id from context. "
                    "Create a random table only when the source explicitly describes a roll/dice/random table or "
                    "rollable alternatives. Copy at least two actual rows. Do not convert ordinary reference, matrix, "
                    "comparison, chronology, or statistics tables into random tables. Never create an empty table. "
                    "Imported Word tables are enclosed in [DOCUMENT TABLE] markers. Preserve their row boundaries. "
                    "Treat such a table as rollable when a column contains a die, roll, chance, percent, or result "
                    "heading and its cells contain outcome ranges such as 1-4, d20, or percentages, even if the prose "
                    "does not call it a random table. Use the range as row label and the outcome as row result. "
                    "Never represent random tables or their rows as entities or relationships. "
                    "Do not use LaTeX or dollar-delimited math. Write coordinates and symbols as plain text. "
                    f"Write all names, summaries, descriptions, labels, world rule conditions/effects, and notes in {language_name}. "
                    "For proper names, use the spelling present in the source in that language. If both Cyrillic and "
                    "Latin variants occur, choose the requested-language variant and put the other spelling in aliases. "
                    "Keep a foreign spelling only when the source contains no requested-language spelling. "
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
            "strict": True,
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
        max_tokens=original_request.max_tokens,
        reasoning_effort=original_request.reasoning_effort,
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
                    "Remove empty random tables and ordinary non-random reference tables. "
                    "A quest must be an event entity with the tag 'quest'."
                    " Split distinct quests, events, and clues into separate entities. Put explicit event dates in "
                    "attributes.timeline_date. Relationship confidence must follow the 1.0/0.85/0.65/0.4 rubric. "
                    "Relationship weight is independent from confidence and must use the full 1-10 importance scale."
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
        raw = _load_extraction_json(_extract_json_text(content))
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


def _load_extraction_json(candidate: str) -> object:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = repair_json(candidate, return_objects=True)
        if not isinstance(repaired, (dict, list)):
            return json.loads(candidate)
        return repaired


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
        attributes = {**candidate.attributes, "module": "quest"}
        timeline_date = _extract_timeline_date(source_text)
        if timeline_date and "timeline_date" not in attributes:
            attributes["timeline_date"] = timeline_date
        entities[candidate_index] = candidate.model_copy(
            update={
                "type": EntityType.event,
                "tags": _merge_unique_strings(candidate.tags, ["quest"]),
                "attributes": attributes,
            }
        )
        return payload.model_copy(update={"entities": entities})

    title = quest_title or ("New quest" if _looks_english(intent_text or source_text) else "Новый квест")
    used_client_ids = {entity.client_id for entity in entities if entity.client_id}
    client_id = _unique_quest_client_id(title, used_client_ids)
    attributes = {"module": "quest"}
    timeline_date = _extract_timeline_date(source_text)
    if timeline_date:
        attributes["timeline_date"] = timeline_date
    entities.append(
        ExtractedEntityDraft(
            client_id=client_id,
            type=EntityType.event,
            name=title[:200],
            summary=_extract_quest_summary(source_text),
            description=_extract_quest_description(source_text),
            tags=["quest"],
            status=VerificationStatus.proposed,
            attributes=attributes,
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
        inline = re.match(
            r"(?iu)^(?:quest(?:\s+hook)?|mission|adventure\s+hook)\s+([^:.!?]{1,120})\s*:",
            clean_line,
        )
        if inline:
            title = _clean_quest_title(inline.group(1))
            if title:
                return title
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


def _extract_timeline_date(source_text: str) -> str | None:
    patterns = (
        r"(?iu)\bYear\s+\d{1,6}\b",
        r"(?iu)\b(?:\d{1,4})\s*(?:year|г(?:од(?:а|у|ом|е)?|\.)?)\b",
        r"(?iu)\b(?:spring|summer|autumn|fall|winter)\s+(?:of\s+)?\d{1,4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, source_text)
        if match:
            return match.group(0).strip(" .,:;-")[:120]
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


def prefer_source_language_names(
    payload: ExtractionPayload,
    source_text: str,
    output_language: str,
) -> ExtractionPayload:
    if output_language == "ru":
        pattern = r"\b[А-ЯЁ][а-яё]+(?:[-'][А-ЯЁа-яё]+)?(?:\s+[А-ЯЁ][а-яё]+(?:[-'][А-ЯЁа-яё]+)?){0,3}\b"
        target_pattern = re.compile(r"[А-Яа-яЁё]")
    elif output_language == "en":
        pattern = r"\b[A-Z][a-z]+(?:[-'][A-Za-z]+)?(?:\s+[A-Z][a-z]+(?:[-'][A-Za-z]+)?){0,3}\b"
        target_pattern = re.compile(r"[A-Za-z]")
    else:
        return payload

    candidates_by_key: dict[str, list[str]] = {}
    for candidate in re.findall(pattern, source_text):
        key = _phonetic_name_key(candidate)
        if len(key.replace(" ", "")) >= 4:
            candidates_by_key.setdefault(key, []).append(candidate)

    entities = []
    for entity in payload.entities:
        if target_pattern.search(entity.name):
            entities.append(entity)
            continue
        matches = candidates_by_key.get(_phonetic_name_key(entity.name), [])
        if not matches:
            entities.append(entity)
            continue
        localized_name = min(matches, key=lambda value: (len(value.split()), len(value)))
        aliases = _merge_unique_strings(entity.aliases, [entity.name])
        entities.append(entity.model_copy(update={"name": localized_name, "aliases": aliases}))
    return payload.model_copy(update={"entities": entities})


CYRILLIC_TRANSLITERATION = str.maketrans(
    {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
        "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
)


def _phonetic_name_key(value: str) -> str:
    normalized = value.casefold().translate(CYRILLIC_TRANSLITERATION)
    normalized = normalized.replace("x", "ks").replace("ph", "f").replace("w", "v")
    words = re.findall(r"[a-z]+", normalized)
    return " ".join(re.sub(r"[aeiouy]", "", word) for word in words)


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
    if candidate.startswith(("{", "[")):
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
    random_tables, random_table_rows = _prune_unusable_random_tables(random_tables, random_table_rows)
    relationships = _calibrate_relationship_weights(relationships)
    relationships = _calibrate_relationship_confidence(relationships)
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
        summary_name = _clean_string(raw_entity.get("summary"))
        identifier_name = _name_from_client_id(raw_entity.get("client_id") or raw_entity.get("id"))
        if identifier_name and (not name or _looks_like_descriptive_name(name) or _is_technical_name(name)):
            name = identifier_name
        if not name or _looks_like_descriptive_name(name) or _is_technical_name(name):
            name = _recover_entity_name(raw_entity, fallback=name or summary_name)
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


def _name_from_client_id(raw_value: object) -> str | None:
    value = _clean_string(raw_value)
    if not value:
        return None
    parts = [part for part in re.split(r"[-_\s]+", value) if part]
    prefixes = {
        "char",
        "character",
        "cl",
        "clue",
        "concept",
        "entity",
        "event",
        "fac",
        "faction",
        "item",
        "clnt",
        "loc",
        "location",
        "quest",
        "rt",
        "table",
    }
    while parts and (
        parts[0].casefold() in prefixes
        or re.fullmatch(r"(?i)[cs]\d+", parts[0])
    ):
        parts.pop(0)
    if not parts or all(part.isdigit() for part in parts):
        return None
    return " ".join(parts)[:200].replace("-", " ").title()


def _looks_like_descriptive_name(value: str) -> bool:
    words = value.split()
    return len(words) > 8 or "," in value or (len(words) >= 5 and value.rstrip().endswith((".", "!", "?")))


def _is_technical_name(value: str) -> bool:
    return bool(TECHNICAL_NAME_PATTERN.fullmatch(value.strip()))


def _recover_entity_name(raw_entity: dict, *, fallback: str | None) -> str | None:
    values = [
        _clean_string(raw_entity.get("description")),
        _clean_string(raw_entity.get("summary")),
        _clean_string(raw_entity.get("source_excerpt")),
    ]
    for value in values:
        candidate = _subject_from_text(value)
        if candidate:
            return candidate[:200]
    if fallback and not _is_technical_name(fallback):
        candidate = _subject_from_text(fallback)
        if candidate:
            return candidate[:200]
    return None


def _subject_from_text(value: str | None) -> str | None:
    if not value:
        return None
    sentence = re.sub(r"\s+", " ", value).strip().strip("*#`_ ")
    if not sentence:
        return None

    dash_match = re.match(r"^[\"'«“]?(.{2,100}?)[\"'»”]?\s+[—–-]\s+", sentence)
    if dash_match:
        candidate = _clean_subject(dash_match.group(1))
        if candidate:
            return candidate

    verb_match = re.match(
        r"(?iu)^[\"'«“]?(.{2,100}?)[\"'»”]?\s+(?:является|представляет\s+собой|находится|"
        r"служит|считается|указывает|ведет|ведёт|раскрывает|was|is|are|represents|serves|points|leads|reveals)\b",
        sentence,
    )
    if verb_match:
        candidate = _clean_subject(verb_match.group(1))
        if candidate:
            return candidate

    proper_match = re.match(
        r"^((?:[A-ZА-ЯЁ][\wЁёА-Яа-я'-]*(?:\s+|$)){2,4})",
        sentence,
    )
    if proper_match:
        candidate = _clean_subject(proper_match.group(1))
        if candidate:
            return candidate

    clause = re.split(r"[,;.!?]", sentence, maxsplit=1)[0].strip()
    if 1 <= len(clause.split()) <= 6 and (
        any(character.isdigit() for character in clause)
        or len(re.findall(r"\b[A-ZА-ЯЁ][\wЁёА-Яа-я'-]+", clause)) >= 2
    ):
        return _clean_subject(clause)
    return None


def _clean_subject(value: str) -> str | None:
    candidate = re.sub(r"\s+", " ", value).strip(" \"'«»“”.,:;()[]")
    words = candidate.split()
    if not words or len(words) > 6 or len(candidate) > 100 or "," in candidate:
        return None
    if words[0].casefold() in GENERIC_SUBJECTS:
        return None
    if any(
        word.casefold() in {"где", "который", "которая", "которого", "котором", "которую", "which", "that"}
        for word in words
    ):
        return None
    if not any(character.isalpha() for character in candidate):
        return None
    return candidate


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


def _prune_unusable_random_tables(tables: list[dict], rows: list[dict]) -> tuple[list[dict], list[dict]]:
    row_counts: dict[str, int] = {}
    for row in rows:
        client_id = row.get("table_client_id")
        if client_id:
            row_counts[client_id] = row_counts.get(client_id, 0) + 1
    usable_ids = {table["client_id"] for table in tables if row_counts.get(table["client_id"], 0) >= 2}
    return (
        [table for table in tables if table["client_id"] in usable_ids],
        [row for row in rows if row.get("table_id") or row.get("table_client_id") in usable_ids],
    )


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


def _calibrate_relationship_weights(relationships: list[dict]) -> list[dict]:
    if len(relationships) < 4:
        return relationships
    weights = [float(relationship["weight"]) for relationship in relationships]
    minimum = min(weights)
    maximum = max(weights)
    if minimum < 7:
        return relationships
    if maximum == minimum:
        return [{**relationship, "weight": 5.0} for relationship in relationships]
    return [
        {
            **relationship,
            "weight": float(round(1 + ((float(relationship["weight"]) - minimum) / (maximum - minimum)) * 9)),
        }
        for relationship in relationships
    ]


def _calibrate_relationship_confidence(relationships: list[dict]) -> list[dict]:
    generic_types = {
        "related_to",
        "associated_with",
        "connected_to",
        "linked_to",
        "связан_с",
    }
    calibrated = []
    for relationship in relationships:
        relation_type = str(relationship.get("type") or "").casefold().replace(" ", "_")
        label = str(relationship.get("label") or "").casefold()
        is_ambiguous = (
            relation_type in generic_types
            or "связан с" in label
            or "related to" in label
            or "associated with" in label
            or "/" in label
        )
        calibrated.append(
            {
                **relationship,
                "confidence": min(float(relationship.get("confidence", 0.65)), 0.65)
                if is_ambiguous
                else relationship.get("confidence", 0.65),
            }
        )
    return calibrated


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

    return _make_bounded_unique_id(candidate, used_client_ids)


def _build_named_client_id(
    raw_item: dict,
    name: str,
    used_client_ids: set[str],
    index: int,
    fallback_prefix: str,
) -> str:
    preferred = _clean_string(raw_item.get("client_id")) or _clean_string(raw_item.get("id"))
    candidate = _slugify(preferred or name) or f"{fallback_prefix}-{index + 1}"
    return _make_bounded_unique_id(candidate, used_client_ids)


def _make_bounded_unique_id(candidate: str, used_client_ids: set[str]) -> str:
    unique_candidate = candidate[:80]
    suffix = 2
    while unique_candidate in used_client_ids:
        marker = f"-{suffix}"
        unique_candidate = f"{candidate[: 80 - len(marker)]}{marker}"
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
