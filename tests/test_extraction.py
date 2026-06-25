import pytest

from worldbuilder_core.services.extraction import ExtractionParseError, build_extraction_request, parse_extraction_payload


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


def test_build_extraction_request_contains_context_and_limit() -> None:
    request = build_extraction_request(
        source_text="Mira founded the Brass Guild.",
        context_text="World: Asterion",
        max_entities=12,
    )

    assert request.temperature == 0
    assert "at most 12 entities" in request.messages[0].content
    assert "World: Asterion" in request.messages[1].content
    assert "Mira founded the Brass Guild." in request.messages[1].content
