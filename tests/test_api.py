import base64
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from worldbuilder_core.schemas import LLMChatResponse, LLMMessage
from worldbuilder_core.db import Base, get_session
from worldbuilder_core.main import create_app


def build_client() -> TestClient:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_session() -> Generator[Session, None, None]:
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app = create_app(create_tables_on_startup=False)
    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_world_entity_relationship_and_rule_flow() -> None:
    client = build_client()

    world_response = client.post("/api/worlds", json={"name": "Asterion", "description": "Clockwork fantasy."})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    character_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "character",
            "name": "Mira",
            "summary": "A cartographer.",
            "tags": ["guild"],
            "is_secret": True,
        },
    )
    assert character_response.status_code == 201
    character_id = character_response.json()["id"]

    faction_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "faction", "name": "Brass Guild"},
    )
    assert faction_response.status_code == 201
    faction_id = faction_response.json()["id"]

    player_entities = client.get(f"/api/worlds/{world_id}/entities?role=player")
    assert player_entities.status_code == 200
    assert [entity["name"] for entity in player_entities.json()] == ["Brass Guild"]

    relationship_response = client.post(
        f"/api/worlds/{world_id}/relationships",
        json={
            "source_entity_id": character_id,
            "target_entity_id": faction_id,
            "type": "member_of",
            "label": "member of",
        },
    )
    assert relationship_response.status_code == 201
    relationship_id = relationship_response.json()["id"]

    player_relationships = client.get(f"/api/worlds/{world_id}/relationships?role=player")
    assert player_relationships.status_code == 200
    assert player_relationships.json() == []

    hidden_relationship = client.get(f"/api/relationships/{relationship_id}?role=player")
    assert hidden_relationship.status_code == 404

    rule_response = client.post(
        f"/api/worlds/{world_id}/world-rules",
        json={
            "priority": 5,
            "condition": "Any magic explanation appears.",
            "effect": "Use clockwork science instead.",
            "tags": ["technology"],
        },
    )
    assert rule_response.status_code == 201
    assert rule_response.json()["priority"] == 5


def test_visual_app_is_served() -> None:
    client = build_client()

    root_response = client.get("/", follow_redirects=False)
    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/app/"

    app_response = client.get("/app/")
    assert app_response.status_code == 200
    assert "Worldbuilder Core" in app_response.text
    assert "/app/app.js" in app_response.text
    assert 'data-tab="settings"' in app_response.text
    assert 'data-tab="graph"' in app_response.text
    assert 'data-tab="timeline"' in app_response.text
    assert 'data-tab="modules"' in app_response.text
    assert 'data-module-toggle="quests"' in app_response.text
    assert 'data-i18n="chat.saveHint"' in app_response.text
    assert 'id="llmSettingsForm"' in app_response.text
    assert 'id="roleGate"' in app_response.text

    ru_response = client.get("/app/i18n/ru.json")
    assert ru_response.status_code == 200
    assert ru_response.json()["tabs.wiki"] == "Вики"
    assert ru_response.json()["tabs.settings"] == "Настройки"
    assert ru_response.json()["tabs.graph"] == "Граф"
    assert ru_response.json()["chat.saveThis"] == "Сохранить в мир"
    assert ru_response.json()["modules.title"] == "Разделы мира"

    module_response = client.get("/app/js/main.js")
    assert module_response.status_code == 200
    assert "export async function boot" in module_response.text
    assert "worldbuilder.modules" in module_response.text

    render_response = client.get("/app/js/render.js")
    assert render_response.status_code == 200
    assert "data-save-message" in render_response.text

    theme_response = client.get("/app/js/theme.js")
    assert theme_response.status_code == 200
    assert "setTheme" in theme_response.text


def test_llm_config_can_be_persisted() -> None:
    client = build_client()

    initial_response = client.get("/api/llm/config")
    assert initial_response.status_code == 200
    assert initial_response.json()["persisted"] is False

    update_response = client.put(
        "/api/llm/config",
        json={
            "base_url": "http://127.0.0.1:1234/v1/",
            "default_model": "local-default",
            "chat_model": "local-chat",
            "extractor_model": "local-extractor",
            "summarizer_model": "",
            "critic_model": None,
            "api_key": "test-key",
            "timeout_seconds": 45,
            "max_entities_per_extract": 7,
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["base_url"] == "http://127.0.0.1:1234/v1"
    assert payload["default_model"] == "local-default"
    assert payload["chat_model"] == "local-chat"
    assert payload["extractor_model"] == "local-extractor"
    assert payload["has_api_key"] is True
    assert payload["timeout_seconds"] == 45
    assert payload["max_entities_per_extract"] == 7
    assert payload["persisted"] is True

    clear_response = client.put(
        "/api/llm/config",
        json={
            "base_url": "http://127.0.0.1:1234/v1",
            "default_model": "local-default",
            "api_key": "",
            "clear_api_key": True,
            "timeout_seconds": 45,
            "max_entities_per_extract": 7,
        },
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["has_api_key"] is False


def test_image_asset_upload_and_serving() -> None:
    client = build_client()
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    upload_response = client.post(
        "/api/assets",
        json={
            "filename": "../Portrait.png",
            "content_type": "image/png",
            "content_base64": base64.b64encode(image_bytes).decode("ascii"),
        },
    )
    assert upload_response.status_code == 201
    payload = upload_response.json()
    assert payload["url"].startswith("/assets/portrait-")
    assert payload["filename"].endswith(".png")
    assert payload["size_bytes"] == len(image_bytes)

    asset_response = client.get(payload["url"])
    assert asset_response.status_code == 200
    assert asset_response.content == image_bytes

    unsupported_response = client.post(
        "/api/assets",
        json={
            "filename": "note.txt",
            "content_type": "text/plain",
            "content_base64": base64.b64encode(b"hello").decode("ascii"),
        },
    )
    assert unsupported_response.status_code == 415


def test_world_export_import_preserves_stable_ids() -> None:
    source_client = build_client()
    world_response = source_client.post("/api/worlds", json={"name": "The Ashen Atlas"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    location_response = source_client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "location",
            "name": "Cinder Port",
            "description": "A harbor built on cooled lava.",
            "tags": ["coast"],
        },
    )
    assert location_response.status_code == 201
    location_id = location_response.json()["id"]

    faction_response = source_client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "faction",
            "name": "Lantern Court",
            "is_secret": True,
            "status": "proposed",
        },
    )
    assert faction_response.status_code == 201
    faction_id = faction_response.json()["id"]

    relationship_response = source_client.post(
        f"/api/worlds/{world_id}/relationships",
        json={
            "source_entity_id": faction_id,
            "target_entity_id": location_id,
            "type": "controls",
            "confidence": 0.75,
            "is_secret": True,
        },
    )
    assert relationship_response.status_code == 201
    relationship_id = relationship_response.json()["id"]

    rule_response = source_client.post(
        f"/api/worlds/{world_id}/world-rules",
        json={
            "priority": 4,
            "condition": "A ship crosses the ash sea.",
            "effect": "Navigation depends on ember beacons.",
            "tags": ["travel"],
            "is_secret": True,
        },
    )
    assert rule_response.status_code == 201
    rule_id = rule_response.json()["id"]

    export_response = source_client.get(f"/api/worlds/{world_id}/export")
    assert export_response.status_code == 200
    snapshot = export_response.json()
    assert snapshot["metadata"]["schema_version"] == "worldbuilder.snapshot.v1"

    target_client = build_client()
    import_response = target_client.post("/api/worlds/import", json=snapshot)
    assert import_response.status_code == 201
    assert import_response.json() == {
        "world_id": world_id,
        "imported_entities": 2,
        "imported_relationships": 1,
        "imported_world_rules": 1,
        "imported_proposals": 0,
    }

    imported_world = target_client.get(f"/api/worlds/{world_id}")
    assert imported_world.status_code == 200
    assert imported_world.json()["name"] == "The Ashen Atlas"

    imported_entities = target_client.get(f"/api/worlds/{world_id}/entities").json()
    assert {entity["id"] for entity in imported_entities} == {location_id, faction_id}

    imported_relationships = target_client.get(f"/api/worlds/{world_id}/relationships").json()
    assert imported_relationships[0]["id"] == relationship_id
    assert imported_relationships[0]["source_entity_id"] == faction_id
    assert imported_relationships[0]["target_entity_id"] == location_id

    imported_rules = target_client.get(f"/api/worlds/{world_id}/world-rules?active_only=false").json()
    assert imported_rules[0]["id"] == rule_id

    conflict_response = target_client.post("/api/worlds/import", json=snapshot)
    assert conflict_response.status_code == 409

    replace_response = target_client.post("/api/worlds/import?replace_existing=true", json=snapshot)
    assert replace_response.status_code == 201

    broken_snapshot = snapshot | {"metadata": snapshot["metadata"] | {"schema_version": "unknown"}}
    invalid_response = target_client.post("/api/worlds/import?replace_existing=true", json=broken_snapshot)
    assert invalid_response.status_code == 422


def test_world_context_respects_player_visibility() -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Glass Marches", "description": "A borderland of mirrors."})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    public_entity = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "Mirror Gate", "summary": "A public crossing."},
    )
    assert public_entity.status_code == 201
    public_id = public_entity.json()["id"]

    secret_entity = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "faction", "name": "Silver Choir", "summary": "Hidden rulers.", "is_secret": True},
    )
    assert secret_entity.status_code == 201
    secret_id = secret_entity.json()["id"]

    relationship = client.post(
        f"/api/worlds/{world_id}/relationships",
        json={
            "source_entity_id": secret_id,
            "target_entity_id": public_id,
            "type": "controls",
            "label": "secretly controls",
        },
    )
    assert relationship.status_code == 201

    public_rule = client.post(
        f"/api/worlds/{world_id}/world-rules",
        json={"priority": 3, "condition": "A mirror is broken.", "effect": "It rings like a bell."},
    )
    assert public_rule.status_code == 201

    secret_rule = client.post(
        f"/api/worlds/{world_id}/world-rules",
        json={
            "priority": 5,
            "condition": "The Silver Choir is named.",
            "effect": "Treat it as a hidden conspiracy.",
            "is_secret": True,
        },
    )
    assert secret_rule.status_code == 201

    master_context = client.get(f"/api/worlds/{world_id}/context?role=master")
    assert master_context.status_code == 200
    assert "Silver Choir" in master_context.json()["context_text"]
    assert len(master_context.json()["relationships"]) == 1
    assert len(master_context.json()["world_rules"]) == 2

    player_context = client.get(f"/api/worlds/{world_id}/context?role=player")
    assert player_context.status_code == 200
    player_payload = player_context.json()
    assert [entity["name"] for entity in player_payload["entities"]] == ["Mirror Gate"]
    assert player_payload["relationships"] == []
    assert len(player_payload["world_rules"]) == 1
    assert "Silver Choir" not in player_payload["context_text"]


def test_extraction_proposal_apply_and_reject_flow() -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Iron Orchard"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    proposal_response = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Mara founded the Rust Garden and forbade sky fire.",
            "payload": {
                "entities": [
                    {
                        "client_id": "mara",
                        "type": "character",
                        "name": "Mara",
                        "summary": "Founder of the Rust Garden.",
                        "tags": ["founder"],
                    },
                    {
                        "client_id": "rust-garden",
                        "type": "faction",
                        "name": "Rust Garden",
                        "summary": "A faction of iron horticulturalists.",
                        "status": "unknown",
                    },
                ],
                "relationships": [
                    {
                        "source_client_id": "mara",
                        "target_client_id": "rust-garden",
                        "type": "founded",
                        "label": "founded",
                        "confidence": 0.9,
                    }
                ],
                "world_rules": [
                    {
                        "priority": 5,
                        "condition": "Sky fire is suggested.",
                        "effect": "It is forbidden in the Iron Orchard.",
                        "tags": ["magic"],
                    }
                ],
                "notes": ["Extracted from generated narration."],
            },
        },
    )
    assert proposal_response.status_code == 201
    proposal = proposal_response.json()
    assert proposal["status"] == "pending"
    proposal_id = proposal["id"]

    apply_response = client.post(f"/api/proposals/{proposal_id}/apply")
    assert apply_response.status_code == 200
    assert apply_response.json() == {
        "proposal_id": proposal_id,
        "created_entities": 2,
        "updated_entities": 0,
        "created_relationships": 1,
        "created_world_rules": 1,
    }

    applied_proposal = client.get(f"/api/proposals/{proposal_id}")
    assert applied_proposal.status_code == 200
    assert applied_proposal.json()["status"] == "applied"

    exported_world = client.get(f"/api/worlds/{world_id}/export")
    assert exported_world.status_code == 200
    assert exported_world.json()["proposals"][0]["id"] == proposal_id
    assert exported_world.json()["proposals"][0]["status"] == "applied"

    entities = client.get(f"/api/worlds/{world_id}/entities").json()
    assert {entity["name"] for entity in entities} == {"Mara", "Rust Garden"}
    assert {entity["status"] for entity in entities} == {"proposed", "unknown"}

    relationships = client.get(f"/api/worlds/{world_id}/relationships").json()
    assert len(relationships) == 1
    assert relationships[0]["type"] == "founded"

    rules = client.get(f"/api/worlds/{world_id}/world-rules").json()
    assert len(rules) == 1
    assert rules[0]["priority"] == 5

    second_apply = client.post(f"/api/proposals/{proposal_id}/apply")
    assert second_apply.status_code == 409

    reject_candidate = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Bad rumor.",
            "payload": {
                "entities": [
                    {
                        "client_id": "rumor",
                        "type": "concept",
                        "name": "False rumor",
                    }
                ]
            },
        },
    )
    assert reject_candidate.status_code == 201
    reject_response = client.post(f"/api/proposals/{reject_candidate.json()['id']}/reject")
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"

    invalid_response = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "A dangling relation.",
            "payload": {
                "relationships": [
                    {
                        "source_client_id": "missing",
                        "target_client_id": "also-missing",
                        "type": "knows",
                    }
                ]
            },
        },
    )
    assert invalid_response.status_code == 422


def test_extraction_proposal_can_apply_selected_items() -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Selective Marches"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    proposal_response = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Keep only Mira for now.",
            "payload": {
                "entities": [
                    {"client_id": "mira", "type": "character", "name": "Mira"},
                    {"client_id": "gate", "type": "location", "name": "North Gate"},
                ],
                "relationships": [
                    {
                        "source_client_id": "mira",
                        "target_client_id": "gate",
                        "type": "guards",
                    }
                ],
                "world_rules": [
                    {
                        "priority": 2,
                        "condition": "A gate is named.",
                        "effect": "Mention its watch rotation.",
                    }
                ],
            },
        },
    )
    assert proposal_response.status_code == 201
    proposal_id = proposal_response.json()["id"]

    selected_response = client.post(
        f"/api/proposals/{proposal_id}/apply-selected",
        json={
            "entity_indices": [0],
            "relationship_indices": [],
            "world_rule_indices": [],
        },
    )
    assert selected_response.status_code == 200
    assert selected_response.json() == {
        "proposal_id": proposal_id,
        "created_entities": 1,
        "updated_entities": 0,
        "created_relationships": 0,
        "created_world_rules": 0,
    }

    entities = client.get(f"/api/worlds/{world_id}/entities").json()
    assert [entity["name"] for entity in entities] == ["Mira"]

    assert client.get(f"/api/worlds/{world_id}/relationships").json() == []
    assert client.get(f"/api/worlds/{world_id}/world-rules").json() == []
    assert client.get(f"/api/proposals/{proposal_id}").json()["status"] == "applied"

    second_apply = client.post(
        f"/api/proposals/{proposal_id}/apply-selected",
        json={"entity_indices": [1]},
    )
    assert second_apply.status_code == 409


def test_world_chat_can_save_completion_to_wiki_proposal(monkeypatch) -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Copper Vale"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    class FakeLLMClient:
        def __init__(self) -> None:
            self.calls = 0

        async def chat(self, request):
            self.calls += 1
            if self.calls == 1:
                assert "Worldbuilder assistant" in request.messages[0].content
                return LLMChatResponse(
                    model="fake-model",
                    message=LLMMessage(
                        role="assistant",
                        content="Nara founded the Copper Circle beneath the old aqueduct.",
                    ),
                    finish_reason="stop",
                )

            assert "extract structured wiki updates" in request.messages[0].content
            return LLMChatResponse(
                model="fake-model",
                message=LLMMessage(
                    role="assistant",
                    content="""
                    {
                      "entities": [
                        {"client_id": "nara", "type": "character", "name": "Nara"},
                        {"client_id": "copper-circle", "type": "faction", "name": "Copper Circle"}
                      ],
                      "relationships": [
                        {
                          "source_client_id": "nara",
                          "target_client_id": "copper-circle",
                          "type": "founded"
                        }
                      ],
                      "world_rules": [],
                      "notes": []
                    }
                    """,
                ),
                finish_reason="stop",
            )

    fake_client = FakeLLMClient()

    import worldbuilder_core.api.routes.retrieval as retrieval_route

    monkeypatch.setattr(retrieval_route, "build_llm_client", lambda *_, **__: fake_client)

    response = client.post(
        f"/api/worlds/{world_id}/chat",
        json={
            "save_to_wiki": True,
            "messages": [{"role": "user", "content": "Tell me a new faction rumor."}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["completion"]["message"]["content"] == "Nara founded the Copper Circle beneath the old aqueduct."
    assert payload["wiki_save_error"] is None
    assert payload["proposal"]["status"] == "pending"
    assert payload["proposal"]["source_text"] == "Nara founded the Copper Circle beneath the old aqueduct."
    assert fake_client.calls == 2

    proposals = client.get(f"/api/worlds/{world_id}/proposals").json()
    assert len(proposals) == 1
    assert proposals[0]["payload"]["entities"][0]["name"] == "Nara"
