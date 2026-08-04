import json

import pytest

from worldbuilder_core.services.extraction import (
    ExtractionParseError,
    annotate_payload_with_source_excerpts,
    build_extraction_request,
    compact_extracted_entity_text,
    ensure_requested_quest_entity,
    parse_extraction_payload,
)
from worldbuilder_core.schemas import ExtractionPayload


def test_parse_extraction_payload_accepts_plain_json() -> None:
    payload = parse_extraction_payload(
        """
        {
          "entities": [
            {"client_id": "mira", "type": "character", "name": "Mira"}
          ],
          "relationships": [],
          "world_rules": [],
          "notes": ["clean"]
        }
        """,
        max_entities=12,
    )

    assert payload.entities[0].client_id == "mira"
    assert payload.entities[0].status == "proposed"
    assert payload.notes == ["clean"]


def test_parse_extraction_payload_recovers_missing_entity_name() -> None:
    payload = parse_extraction_payload(
        json.dumps(
            {
                "entities": [
                    {
                        "type": "clue",
                        "summary": "Blue seal points to Mira. It was found in the archive.",
                    }
                ]
            }
        ),
        max_entities=12,
    )

    assert payload.entities[0].name == "Blue seal points to Mira."
    assert payload.entities[0].type == "clue"


def test_parse_extraction_payload_prefers_meaningful_client_id_over_long_summary() -> None:
    payload = parse_extraction_payload(
        json.dumps(
            {
                "entities": [
                    {
                        "client_id": "loc_tunguska",
                        "type": "location",
                        "summary": "The primary network core, associated with the arrival of the original material.",
                    }
                ]
            }
        ),
        max_entities=12,
    )

    assert payload.entities[0].name == "Tunguska"


def test_parse_extraction_payload_replaces_descriptive_name_from_client_id() -> None:
    payload = parse_extraction_payload(
        json.dumps(
            {
                "entities": [
                    {
                        "client_id": "loc_tomsk",
                        "type": "location",
                        "name": "The controlling terminal and relay for the whole crystal network.",
                    }
                ]
            }
        ),
        max_entities=12,
    )

    assert payload.entities[0].name == "Tomsk"


def test_world_entity_type_is_normalized_to_concept() -> None:
    payload = parse_extraction_payload(
        '{"entities":[{"client_id":"world-eon","type":"world","name":"Eon"}]}',
        max_entities=12,
    )

    assert payload.entities[0].type == "concept"


def test_parse_extraction_payload_accepts_json_fence() -> None:
    payload = parse_extraction_payload(
        """
        ```json
        {
          "entities": [],
          "relationships": [],
          "world_rules": [
            {
              "priority": 5,
              "condition": "Magic is proposed.",
              "effect": "Replace it with clockwork."
            }
          ]
        }
        ```
        """,
        max_entities=12,
    )

    assert payload.world_rules[0].priority == 5


def test_parse_extraction_payload_rejects_invalid_json() -> None:
    with pytest.raises(ExtractionParseError):
        parse_extraction_payload("not json", max_entities=12)


def test_parse_extraction_payload_enforces_entity_limit() -> None:
    content = {
        "entities": [
            {"client_id": "one", "type": "concept", "name": "One"},
            {"client_id": "two", "type": "concept", "name": "Two"},
        ]
    }

    with pytest.raises(ExtractionParseError):
        parse_extraction_payload(str(content).replace("'", '"'), max_entities=1)


def test_parse_extraction_payload_can_truncate_excess_entities() -> None:
    payload = parse_extraction_payload(
        """
        {
          "entities": [
            {"client_id": "kept", "type": "clue", "name": "Kept clue"},
            {"client_id": "removed", "type": "clue", "name": "Removed clue"}
          ],
          "relationships": [
            {"source_client_id": "kept", "target_client_id": "removed", "type": "points_to"}
          ]
        }
        """,
        max_entities=1,
        truncate_excess_entities=True,
    )

    assert [entity.client_id for entity in payload.entities] == ["kept"]
    assert payload.relationships == []


def test_parse_extraction_payload_normalizes_llm_styled_output() -> None:
    payload = parse_extraction_payload(
        """
        ```json
        {
          "entities": [
            {"id": "e60758c3-a1f9-435a-bd2a-c5fd76180735", "type": "character", "name": "Shish", "description": "Mine technician."},
            {"id": "client_id", "type": "organization", "name": "Aurora Minerals", "description": "Owns the island."},
            {"id": "client_id", "type": "resource", "name": "Copper", "description": "Critical export."},
            {"id": "client_id", "type": "world_concept", "name": "Extraction Mandate", "description": "Everything serves output."}
          ],
          "relationships": [
            {"source_id": "e60758c3-a1f9-435a-bd2a-c5fd76180735", "target_id": "client_id", "type": "works_for"},
            {"source_id": "Aurora Minerals", "target_id": "Copper", "label": "controls"}
          ],
          "world_rules": [
            {"rule_name": "The Extraction Mandate", "description": "Corporate output overrides everything.", "priority": 1}
          ],
          "notes": ["Industrial island."]
        }
        ```
        """,
        max_entities=12,
    )

    assert len(payload.entities) == 4
    assert payload.entities[1].type == "faction"
    assert payload.entities[2].type == "item"
    assert payload.entities[3].type == "concept"
    assert payload.entities[1].client_id != payload.entities[2].client_id
    assert len(payload.relationships) == 1
    assert payload.relationships[0].source_client_id == payload.entities[1].client_id
    assert payload.relationships[0].target_client_id == payload.entities[2].client_id
    assert payload.relationships[0].type == "controls"
    assert payload.world_rules[0].condition == "The Extraction Mandate"
    assert payload.world_rules[0].effect == "Corporate output overrides everything."
    assert payload.notes == ["Industrial island."]


def test_parse_extraction_payload_keeps_new_dynamic_entity_type() -> None:
    payload = parse_extraction_payload(
        '{"entities":[{"client_id":"deity","type":"forgotten_deity","name":"The Sleeper"}]}',
        max_entities=12,
    )

    assert payload.entities[0].type == "forgotten_deity"


def test_parse_extraction_payload_normalizes_random_table_rows() -> None:
    payload = parse_extraction_payload(
        """
        {
          "random_table_entries": [
            {
              "random_table_id": "table-1",
              "title": "Moon rumor",
              "entry": "A moonlit courier offers a sealed contract.",
              "weight": "3",
              "is_secret": true
            }
          ]
        }
        """,
        max_entities=12,
    )

    assert len(payload.random_table_rows) == 1
    row = payload.random_table_rows[0]
    assert row.table_id == "table-1"
    assert row.label == "Moon rumor"
    assert row.result == "A moonlit courier offers a sealed contract."
    assert row.weight == 3
    assert row.is_secret is True


def test_build_extraction_request_contains_context_and_limit() -> None:
    request = build_extraction_request(
        source_text="Mira founded the Brass Guild.",
        context_text="World: Asterion",
        max_entities=12,
    )

    assert request.temperature == 0
    assert request.max_tokens == 2_880
    assert request.response_format is not None
    assert request.response_format["type"] == "json_schema"
    assert request.response_format["json_schema"]["strict"] is True
    assert request.reasoning_effort == "none"
    assert "at most 12 entities" in request.messages[0].content
    assert "random_table_rows" in request.messages[0].content
    assert "in Russian" in request.messages[0].content
    assert "World: Asterion" in request.messages[1].content
    assert "Mira founded the Brass Guild." in request.messages[1].content


def test_build_extraction_request_can_disable_structured_output() -> None:
    request = build_extraction_request(
        source_text="Mira founded the Brass Guild.",
        context_text="World: Asterion",
        max_entities=4,
        structured_output=False,
    )

    assert request.response_format is None


def test_build_extraction_request_can_request_english_output() -> None:
    request = build_extraction_request(
        source_text="Mira founded the Brass Guild.",
        context_text="World: Asterion",
        max_entities=12,
        output_language="en",
    )

    assert "in English" in request.messages[0].content


def test_extraction_promotes_clues_dates_and_relationship_strength() -> None:
    payload = parse_extraction_payload(
        """
        {
          "entities": [
            {"client_id":"seal","type":"evidence","name":"Blue seal"},
            {"client_id":"fire","type":"event","name":"Archive fire","date":"Year 315"}
          ],
          "relationships": [
            {"source_client_id":"seal","target_client_id":"fire","type":"points_to","weight":7}
          ]
        }
        """,
        max_entities=12,
    )

    assert payload.entities[0].type == "clue"
    assert payload.entities[1].attributes["timeline_date"] == "Year 315"
    assert payload.relationships[0].confidence == 0.65
    assert payload.relationships[0].weight == 7


def test_compact_extracted_entity_text_drops_copied_full_chat() -> None:
    source = "Quest briefing. " * 500
    payload = ExtractionPayload.model_validate(
        {
            "entities": [
                {
                    "client_id": "quest",
                    "type": "event",
                    "name": "Briefing",
                    "summary": "Recover the archive key.",
                    "description": source,
                    "tags": ["quest"],
                }
            ]
        }
    )

    compacted = compact_extracted_entity_text(payload, source)

    assert compacted.entities[0].description == "Recover the archive key."


def test_parse_extraction_payload_creates_quest_and_new_random_table() -> None:
    payload = parse_extraction_payload(
        """
        {
          "entities": [
            {"id": "lost-bell", "type": "quest", "name": "The Lost Bell", "summary": "Recover the bell."},
            {
              "id": "road-rumors",
              "type": "random_table",
              "name": "Road rumors",
              "description": "What travelers whisper.",
              "rows": [
                {"label": "Bell", "result": "A bell rings beneath the road.", "weight": 2}
              ]
            }
          ],
          "relationships": [
            {"source_id": "road-rumors", "target": "A rider carries a sealed map.", "type": "contains"}
          ]
        }
        """,
        max_entities=12,
    )

    assert len(payload.entities) == 1
    assert payload.entities[0].type == "event"
    assert "quest" in payload.entities[0].tags
    assert len(payload.random_tables) == 1
    assert payload.random_tables[0].name == "Road rumors"
    assert len(payload.random_table_rows) == 2
    assert {row.table_client_id for row in payload.random_table_rows} == {payload.random_tables[0].client_id}


def test_requested_quest_is_created_when_model_only_extracts_supporting_entities() -> None:
    payload = parse_extraction_payload(
        """
        {
          "entities": [
            {"client_id": "elder", "type": "character", "name": "Старейшина"},
            {"client_id": "stage-one", "type": "event", "name": "Набег гоблинов (Этап I)"}
          ]
        }
        """,
        max_entities=12,
    )

    result = ensure_requested_quest_entity(
        payload,
        intent_text="Создай квест с целью и наградой.",
        source_text=(
            '# КВЕСТОВЫЙ КРЮЧОК: "ПУЛЬС МЕДНОГО СЕРДЦА"\n\n'
            "### Цель миссии\nНайти пропавших рабочих.\n\n"
            "### Награда\nМедный кристалл."
        ),
    )

    quests = [entity for entity in result.entities if "quest" in entity.tags]
    assert len(quests) == 1
    assert quests[0].type == "event"
    assert quests[0].name == "Пульс медного сердца"
    assert quests[0].summary == "Найти пропавших рабочих."
    assert quests[0].attributes["module"] == "quest"
    assert "quest" not in result.entities[1].tags


def test_requested_quest_promotes_matching_event_instead_of_creating_duplicate() -> None:
    payload = parse_extraction_payload(
        """
        {
          "entities": [
            {
              "client_id": "lost-bell",
              "type": "event",
              "name": "The Lost Bell",
              "summary": "Recover the bell before dawn."
            }
          ]
        }
        """,
        max_entities=12,
    )

    result = ensure_requested_quest_entity(
        payload,
        intent_text="Create a quest.",
        source_text="# The Lost Bell\n\n## Objective\nRecover the bell before dawn.",
    )

    assert len(result.entities) == 1
    assert result.entities[0].tags == ["quest"]
    assert result.entities[0].attributes["module"] == "quest"


def test_generic_document_extraction_intent_does_not_invent_quest() -> None:
    result = ensure_requested_quest_entity(
        ExtractionPayload(),
        intent_text="Extract only explicit world objects and structures present in this source segment.",
        source_text="The crystal network connects Tunguska and Tomsk.",
    )

    assert result.entities == []


def test_plain_quest_prefix_recovers_title_and_timeline_date() -> None:
    result = ensure_requested_quest_entity(
        ExtractionPayload(),
        intent_text="Create the explicitly described quest.",
        source_text="Quest Ash Bell: In Year 315 investigator Mira must recover the bell before dawn.",
    )

    assert len(result.entities) == 1
    assert result.entities[0].name == "Ash Bell"
    assert result.entities[0].tags == ["quest"]
    assert result.entities[0].attributes["timeline_date"] == "Year 315"


def test_russian_quest_tag_is_normalized() -> None:
    payload = parse_extraction_payload(
        '{"entities":[{"client_id":"bell","type":"event","name":"Колокол","tags":["Квест"]}]}',
        max_entities=12,
    )

    assert payload.entities[0].tags == ["quest"]


def test_annotate_payload_with_source_excerpts_matches_relevant_sentences() -> None:
    payload = parse_extraction_payload(
        """
        {
          "entities": [
            {"client_id": "mira", "type": "character", "name": "Mira"},
            {"client_id": "brass-guild", "type": "faction", "name": "Brass Guild"}
          ],
          "relationships": [
            {"source_client_id": "mira", "target_client_id": "brass-guild", "type": "founded"}
          ],
          "world_rules": [
            {"condition": "When the river floods", "effect": "all bridges close"}
          ],
          "random_table_rows": [
            {"table_id": "table-1", "label": "Bridge rumor", "result": "A ferryman knows a dry route through the old culverts."}
          ]
        }
        """,
        max_entities=12,
    )

    annotated = annotate_payload_with_source_excerpts(
        payload,
        (
            "Mira founded the Brass Guild in the lower ward. "
            "When the river floods, all bridges close until dawn. "
            "A ferryman knows a dry route through the old culverts."
        ),
    )

    assert annotated.entities[0].source_excerpt == "Mira founded the Brass Guild in the lower ward."
    assert annotated.relationships[0].source_excerpt == "Mira founded the Brass Guild in the lower ward."
    assert annotated.world_rules[0].source_excerpt == "When the river floods, all bridges close until dawn."
    assert annotated.random_table_rows[0].source_excerpt == "A ferryman knows a dry route through the old culverts."
