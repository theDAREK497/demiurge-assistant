import pytest

from worldbuilder_core.services.extraction import (
    ExtractionParseError,
    annotate_payload_with_source_excerpts,
    build_extraction_request,
    parse_extraction_payload,
)


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
    assert payload.entities[1].type.value == "faction"
    assert payload.entities[2].type.value == "item"
    assert payload.entities[3].type.value == "concept"
    assert payload.entities[1].client_id != payload.entities[2].client_id
    assert len(payload.relationships) == 1
    assert payload.relationships[0].source_client_id == payload.entities[1].client_id
    assert payload.relationships[0].target_client_id == payload.entities[2].client_id
    assert payload.relationships[0].type == "controls"
    assert payload.world_rules[0].condition == "The Extraction Mandate"
    assert payload.world_rules[0].effect == "Corporate output overrides everything."
    assert payload.notes == ["Industrial island."]


def test_build_extraction_request_contains_context_and_limit() -> None:
    request = build_extraction_request(
        source_text="Mira founded the Brass Guild.",
        context_text="World: Asterion",
        max_entities=12,
    )

    assert request.temperature == 0
    assert "at most 12 entities" in request.messages[0].content
    assert "in Russian" in request.messages[0].content
    assert "World: Asterion" in request.messages[1].content
    assert "Mira founded the Brass Guild." in request.messages[1].content


def test_build_extraction_request_can_request_english_output() -> None:
    request = build_extraction_request(
        source_text="Mira founded the Brass Guild.",
        context_text="World: Asterion",
        max_entities=12,
        output_language="en",
    )

    assert "in English" in request.messages[0].content


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
          ]
        }
        """,
        max_entities=12,
    )

    annotated = annotate_payload_with_source_excerpts(
        payload,
        (
            "Mira founded the Brass Guild in the lower ward. "
            "When the river floods, all bridges close until dawn."
        ),
    )

    assert annotated.entities[0].source_excerpt == "Mira founded the Brass Guild in the lower ward."
    assert annotated.relationships[0].source_excerpt == "Mira founded the Brass Guild in the lower ward."
    assert annotated.world_rules[0].source_excerpt == "When the river floods, all bridges close until dawn."
