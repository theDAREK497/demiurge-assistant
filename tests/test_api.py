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


def test_map_pins_respect_visibility_and_round_trip_in_exports() -> None:
    client = build_client()

    world_response = client.post("/api/worlds", json={"name": "Pinned Coast"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    map_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "location",
            "name": "Harbor Map",
            "attributes": {"image_url": "/assets/harbor.png"},
        },
    )
    assert map_response.status_code == 201
    map_id = map_response.json()["id"]

    public_entity_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "Old Lighthouse"},
    )
    assert public_entity_response.status_code == 201
    public_entity_id = public_entity_response.json()["id"]

    secret_entity_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "faction", "name": "Hidden Admiralty", "is_secret": True},
    )
    assert secret_entity_response.status_code == 201
    secret_entity_id = secret_entity_response.json()["id"]

    visible_pin_response = client.post(
        f"/api/worlds/{world_id}/map-pins",
        json={
            "map_entity_id": map_id,
            "linked_entity_id": public_entity_id,
            "title": "Lighthouse",
            "note": "Visible from the docks.",
            "x": 0.25,
            "y": 0.6,
        },
    )
    assert visible_pin_response.status_code == 201
    visible_pin_id = visible_pin_response.json()["id"]

    secret_pin_response = client.post(
        f"/api/worlds/{world_id}/map-pins",
        json={"map_entity_id": map_id, "title": "Smuggler cache", "x": 0.5, "y": 0.5, "is_secret": True},
    )
    assert secret_pin_response.status_code == 201
    secret_pin_id = secret_pin_response.json()["id"]

    linked_secret_pin_response = client.post(
        f"/api/worlds/{world_id}/map-pins",
        json={
            "map_entity_id": map_id,
            "linked_entity_id": secret_entity_id,
            "title": "Admiralty dock",
            "x": 0.8,
            "y": 0.2,
        },
    )
    assert linked_secret_pin_response.status_code == 201

    master_pins = client.get(f"/api/worlds/{world_id}/map-pins")
    assert master_pins.status_code == 200
    assert [pin["title"] for pin in master_pins.json()] == ["Lighthouse", "Smuggler cache", "Admiralty dock"]

    player_pins = client.get(f"/api/worlds/{world_id}/map-pins?role=player")
    assert player_pins.status_code == 200
    assert [pin["title"] for pin in player_pins.json()] == ["Lighthouse"]

    hidden_pin = client.get(f"/api/map-pins/{secret_pin_id}?role=player")
    assert hidden_pin.status_code == 404

    update_response = client.patch(f"/api/map-pins/{visible_pin_id}", json={"x": 0.3, "title": "North Lighthouse"})
    assert update_response.status_code == 200
    assert update_response.json()["x"] == 0.3
    assert update_response.json()["title"] == "North Lighthouse"

    exported_world = client.get(f"/api/worlds/{world_id}/export")
    assert exported_world.status_code == 200
    snapshot = exported_world.json()
    assert len(snapshot["map_pins"]) == 3

    imported_client = build_client()
    import_response = imported_client.post("/api/worlds/import", json=snapshot)
    assert import_response.status_code == 201
    assert import_response.json()["imported_map_pins"] == 3

    imported_pins = imported_client.get(f"/api/worlds/{world_id}/map-pins")
    assert imported_pins.status_code == 200
    assert [pin["title"] for pin in imported_pins.json()] == ["North Lighthouse", "Smuggler cache", "Admiralty dock"]


def test_random_tables_crud_roll_visibility_and_export_import() -> None:
    client = build_client()

    world_response = client.post("/api/worlds", json={"name": "Dice Vale"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    table_response = client.post(
        f"/api/worlds/{world_id}/random-tables",
        json={"name": "Road encounters", "description": "Things found on the old road."},
    )
    assert table_response.status_code == 201
    table_id = table_response.json()["id"]

    public_row_response = client.post(
        f"/api/random-tables/{table_id}/rows",
        json={"label": "Merchant", "result": "A tired merchant asks for directions.", "weight": 2},
    )
    assert public_row_response.status_code == 201
    public_row_id = public_row_response.json()["id"]

    secret_row_response = client.post(
        f"/api/random-tables/{table_id}/rows",
        json={"label": "Assassin", "result": "A hidden assassin follows the party.", "is_secret": True},
    )
    assert secret_row_response.status_code == 201
    secret_row_id = secret_row_response.json()["id"]

    secret_table_response = client.post(
        f"/api/worlds/{world_id}/random-tables",
        json={"name": "GM secrets", "is_secret": True},
    )
    assert secret_table_response.status_code == 201

    master_tables = client.get(f"/api/worlds/{world_id}/random-tables")
    assert master_tables.status_code == 200
    assert [table["name"] for table in master_tables.json()] == ["GM secrets", "Road encounters"]
    road_table = next(table for table in master_tables.json() if table["id"] == table_id)
    assert [row["label"] for row in road_table["rows"]] == ["Merchant", "Assassin"]

    player_tables = client.get(f"/api/worlds/{world_id}/random-tables?role=player")
    assert player_tables.status_code == 200
    assert [table["name"] for table in player_tables.json()] == ["Road encounters"]
    assert [row["label"] for row in player_tables.json()[0]["rows"]] == ["Merchant"]

    player_roll = client.post(f"/api/random-tables/{table_id}/roll?role=player")
    assert player_roll.status_code == 200
    assert player_roll.json()["row"]["id"] == public_row_id

    update_table_response = client.patch(f"/api/random-tables/{table_id}", json={"name": "Road signs"})
    assert update_table_response.status_code == 200
    assert update_table_response.json()["name"] == "Road signs"

    update_row_response = client.patch(f"/api/random-table-rows/{public_row_id}", json={"weight": 3})
    assert update_row_response.status_code == 200
    assert update_row_response.json()["weight"] == 3

    exported_world = client.get(f"/api/worlds/{world_id}/export")
    assert exported_world.status_code == 200
    snapshot = exported_world.json()
    assert len(snapshot["random_tables"]) == 2
    assert len(snapshot["random_table_rows"]) == 2

    imported_client = build_client()
    import_response = imported_client.post("/api/worlds/import", json=snapshot)
    assert import_response.status_code == 201
    assert import_response.json()["imported_random_tables"] == 2
    assert import_response.json()["imported_random_table_rows"] == 2

    imported_tables = imported_client.get(f"/api/worlds/{world_id}/random-tables")
    assert imported_tables.status_code == 200
    assert [table["name"] for table in imported_tables.json()] == ["GM secrets", "Road signs"]

    delete_secret_row = imported_client.delete(f"/api/random-table-rows/{secret_row_id}")
    assert delete_secret_row.status_code == 204


def test_detective_board_crud_visibility_and_export_import() -> None:
    client = build_client()

    world_response = client.post("/api/worlds", json={"name": "Casebook"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    public_entity_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "character", "name": "Inspector Vale"},
    )
    assert public_entity_response.status_code == 201
    public_entity_id = public_entity_response.json()["id"]

    secret_entity_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "faction", "name": "Glass Hand", "is_secret": True},
    )
    assert secret_entity_response.status_code == 201
    secret_entity_id = secret_entity_response.json()["id"]

    inspector_node = client.post(
        f"/api/worlds/{world_id}/detective-board/nodes",
        json={
            "entity_id": public_entity_id,
            "title": "Inspector",
            "note": "Owns the casebook.",
            "evidence_url": "https://example.invalid/case",
            "x": 0.25,
            "y": 0.4,
        },
    )
    assert inspector_node.status_code == 201
    inspector_node_id = inspector_node.json()["id"]

    clue_node = client.post(
        f"/api/worlds/{world_id}/detective-board/nodes",
        json={"title": "Blue wax seal", "x": 0.65, "y": 0.45},
    )
    assert clue_node.status_code == 201
    clue_node_id = clue_node.json()["id"]

    secret_node = client.post(
        f"/api/worlds/{world_id}/detective-board/nodes",
        json={"title": "Hidden patron", "x": 0.5, "y": 0.8, "is_secret": True},
    )
    assert secret_node.status_code == 201
    secret_node_id = secret_node.json()["id"]

    linked_secret_node = client.post(
        f"/api/worlds/{world_id}/detective-board/nodes",
        json={"entity_id": secret_entity_id, "title": "Glass Hand", "x": 0.8, "y": 0.2},
    )
    assert linked_secret_node.status_code == 201

    visible_connection = client.post(
        f"/api/worlds/{world_id}/detective-board/connections",
        json={
            "source_node_id": inspector_node_id,
            "target_node_id": clue_node_id,
            "label": "found",
            "note": "Found near the archive.",
        },
    )
    assert visible_connection.status_code == 201
    visible_connection_id = visible_connection.json()["id"]

    secret_connection = client.post(
        f"/api/worlds/{world_id}/detective-board/connections",
        json={
            "source_node_id": inspector_node_id,
            "target_node_id": secret_node_id,
            "label": "suspects",
            "is_secret": True,
        },
    )
    assert secret_connection.status_code == 201

    master_board = client.get(f"/api/worlds/{world_id}/detective-board")
    assert master_board.status_code == 200
    assert [node["title"] for node in master_board.json()["nodes"]] == [
        "Inspector",
        "Blue wax seal",
        "Hidden patron",
        "Glass Hand",
    ]
    assert [connection["label"] for connection in master_board.json()["connections"]] == ["found", "suspects"]

    player_board = client.get(f"/api/worlds/{world_id}/detective-board?role=player")
    assert player_board.status_code == 200
    assert [node["title"] for node in player_board.json()["nodes"]] == ["Inspector", "Blue wax seal"]
    assert [connection["label"] for connection in player_board.json()["connections"]] == ["found"]

    update_node = client.patch(f"/api/detective-board/nodes/{clue_node_id}", json={"title": "Blue seal"})
    assert update_node.status_code == 200
    assert update_node.json()["title"] == "Blue seal"

    update_connection = client.patch(f"/api/detective-board/connections/{visible_connection_id}", json={"label": "confirms"})
    assert update_connection.status_code == 200
    assert update_connection.json()["label"] == "confirms"

    exported_world = client.get(f"/api/worlds/{world_id}/export")
    assert exported_world.status_code == 200
    snapshot = exported_world.json()
    assert len(snapshot["detective_board_nodes"]) == 4
    assert len(snapshot["detective_board_connections"]) == 2

    imported_client = build_client()
    import_response = imported_client.post("/api/worlds/import", json=snapshot)
    assert import_response.status_code == 201
    assert import_response.json()["imported_detective_board_nodes"] == 4
    assert import_response.json()["imported_detective_board_connections"] == 2

    imported_board = imported_client.get(f"/api/worlds/{world_id}/detective-board")
    assert imported_board.status_code == 200
    assert [node["title"] for node in imported_board.json()["nodes"]] == [
        "Inspector",
        "Blue seal",
        "Hidden patron",
        "Glass Hand",
    ]


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
    assert 'id="chatThreadList"' in app_response.text
    assert 'id="saveToWiki"' not in app_response.text
    assert 'id="llmSettingsForm"' in app_response.text
    assert 'id="roleGate"' in app_response.text
    assert 'id="entityDrawerBackdrop"' in app_response.text
    assert 'id="entityReader"' in app_response.text
    assert 'id="mapPinForm"' in app_response.text
    assert 'id="randomTableForm"' in app_response.text
    assert 'data-module-toggle="randomTables"' in app_response.text
    assert 'id="detectiveNodeForm"' in app_response.text
    assert 'data-module-toggle="detectiveBoard"' in app_response.text

    ru_response = client.get("/app/i18n/ru.json")
    assert ru_response.status_code == 200
    assert ru_response.json()["tabs.wiki"] == "Энциклопедия"
    assert ru_response.json()["tabs.rules"] == "Законы мира"
    assert ru_response.json()["tabs.proposals"] == "Черновики"
    assert ru_response.json()["rule.condition"] == "Когда это важно"
    assert ru_response.json()["entity.open"] == "Открыть"
    assert ru_response.json()["chat.saveThis"] == "Сохранить в черновик"
    assert ru_response.json()["proposal.status.applied"] == "Применен"
    assert ru_response.json()["proposal.status.rejected"] == "Отклонен"

    module_response = client.get("/app/js/main.js")
    assert module_response.status_code == 200
    assert "export async function boot" in module_response.text
    assert "worldbuilder.modules" in module_response.text

    render_response = client.get("/app/js/render.js")
    assert render_response.status_code == 200
    assert "data-save-message" in render_response.text
    assert "entityReviewChanges" in render_response.text
    assert "data-map-image" in render_response.text
    assert "data-roll-random-table" in render_response.text
    assert "detectiveBoardView" in render_response.text
    assert "entityReviewChangeDetails" in render_response.text
    assert "proposal-change-summary" in render_response.text
    assert "proposal-change-detail" in render_response.text
    assert "data-delete-proposal" in render_response.text
    assert "#{1,6}" in render_response.text
    assert 'output.push("<hr>")' in render_response.text

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
            "imported_map_pins": 0,
            "imported_random_tables": 0,
            "imported_random_table_rows": 0,
            "imported_detective_board_nodes": 0,
            "imported_detective_board_connections": 0,
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

    public_table = client.post(
        f"/api/worlds/{world_id}/random-tables",
        json={"name": "Gate rumors"},
    )
    assert public_table.status_code == 201
    public_table_id = public_table.json()["id"]
    public_row = client.post(
        f"/api/random-tables/{public_table_id}/rows",
        json={"label": "Bell", "result": "A mirror bell rings at dusk."},
    )
    assert public_row.status_code == 201

    secret_table = client.post(
        f"/api/worlds/{world_id}/random-tables",
        json={"name": "Choir secrets", "is_secret": True},
    )
    assert secret_table.status_code == 201

    master_context = client.get(f"/api/worlds/{world_id}/context?role=master")
    assert master_context.status_code == 200
    assert "Silver Choir" in master_context.json()["context_text"]
    assert "Choir secrets" in master_context.json()["context_text"]
    assert len(master_context.json()["relationships"]) == 1
    assert len(master_context.json()["world_rules"]) == 2
    assert [table["name"] for table in master_context.json()["random_tables"]] == ["Choir secrets", "Gate rumors"]

    player_context = client.get(f"/api/worlds/{world_id}/context?role=player")
    assert player_context.status_code == 200
    player_payload = player_context.json()
    assert [entity["name"] for entity in player_payload["entities"]] == ["Mirror Gate"]
    assert player_payload["relationships"] == []
    assert len(player_payload["world_rules"]) == 1
    assert [table["name"] for table in player_payload["random_tables"]] == ["Gate rumors"]
    assert "Silver Choir" not in player_payload["context_text"]
    assert "Choir secrets" not in player_payload["context_text"]


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
        "created_random_tables": 0,
        "created_random_table_rows": 0,
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


def test_extraction_endpoint_keeps_valid_items_when_llm_references_are_noisy(monkeypatch) -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Recovered Vale"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]
    invented_match_id = "11111111-1111-4111-8111-111111111111"

    class FakeExtractionLLMClient:
        async def chat(self, request):
            return LLMChatResponse(
                model="fake-extractor",
                message=LLMMessage(
                    role="assistant",
                    content=f"""
                    {{
                      "entities": [
                        {{"match_entity_id": "{invented_match_id}", "type": "character", "name": "Mira"}},
                        {{"client_id": "north-gate", "type": "location", "name": "North Gate"}}
                      ],
                      "relationships": [
                        {{"source_entity_id": "{invented_match_id}", "target_client_id": "north-gate", "type": "guards"}},
                        {{"source_client_id": "missing", "target_client_id": "north-gate", "type": "haunts"}}
                      ],
                      "random_table_rows": [
                        {{"table_id": "invented-table", "result": "Broken row"}}
                      ]
                    }}
                    """,
                ),
                finish_reason="stop",
            )

    import worldbuilder_core.api.routes.proposals as proposals_route

    monkeypatch.setattr(proposals_route, "build_llm_client", lambda *_, **__: FakeExtractionLLMClient())

    response = client.post(
        f"/api/worlds/{world_id}/proposals/extract",
        json={"source_text": "Mira guards the North Gate."},
    )

    assert response.status_code == 201
    payload = response.json()["payload"]
    assert [entity["name"] for entity in payload["entities"]] == ["Mira", "North Gate"]
    assert payload["entities"][0]["match_entity_id"] is None
    assert payload["entities"][0]["client_id"].startswith("recovered-entity-")
    assert len(payload["relationships"]) == 1
    assert payload["relationships"][0]["source_client_id"] == payload["entities"][0]["client_id"]
    assert payload["random_table_rows"] == []


def test_extraction_proposal_can_be_deleted() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Brief Draft"}).json()["id"]
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Temporary note.",
            "payload": {"notes": ["Temporary note."]},
        },
    )
    assert proposal.status_code == 201
    proposal_id = proposal.json()["id"]

    delete_response = client.delete(f"/api/proposals/{proposal_id}")
    assert delete_response.status_code == 204
    assert client.get(f"/api/proposals/{proposal_id}").status_code == 404
    assert client.delete(f"/api/proposals/{proposal_id}").status_code == 404


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
            "random_table_row_indices": [],
        },
    )
    assert selected_response.status_code == 200
    assert selected_response.json() == {
        "proposal_id": proposal_id,
        "created_entities": 1,
        "updated_entities": 0,
        "created_relationships": 0,
        "created_world_rules": 0,
        "created_random_tables": 0,
        "created_random_table_rows": 0,
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


def test_extraction_proposal_deduplicates_repeated_draft_items() -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Duplicate Forge"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    table_response = client.post(f"/api/worlds/{world_id}/random-tables", json={"name": "Rumors"})
    assert table_response.status_code == 201
    table_id = table_response.json()["id"]

    proposal_response = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Mira joins the Brass Guild. A bell tolls under the river.",
            "payload": {
                "entities": [
                    {"client_id": "mira", "type": "character", "name": "Mira", "aliases": ["Cartographer"]},
                    {"client_id": "mira-copy", "type": "character", "name": "Mira", "tags": ["scout"]},
                    {"client_id": "brass-guild", "type": "faction", "name": "Brass Guild"},
                ],
                "relationships": [
                    {"source_client_id": "mira", "target_client_id": "brass-guild", "type": "member_of"},
                    {"source_client_id": "mira-copy", "target_client_id": "brass-guild", "type": "MEMBER_OF"},
                ],
                "world_rules": [
                    {"condition": "A guild is named.", "effect": "Mention its public charter.", "tags": ["guild"]},
                    {"condition": "A guild is named.", "effect": "Mention its public charter.", "tags": ["law"]},
                ],
                "random_table_rows": [
                    {"table_id": table_id, "label": "River bell", "result": "A bell tolls under the river.", "weight": 1},
                    {"table_id": table_id, "label": "River bell", "result": "A bell tolls under the river.", "weight": 3},
                ],
                "notes": ["Review duplicates.", "Review duplicates."],
            },
        },
    )
    assert proposal_response.status_code == 201
    payload = proposal_response.json()["payload"]
    assert [entity["name"] for entity in payload["entities"]] == ["Mira", "Brass Guild"]
    assert payload["entities"][0]["aliases"] == ["Cartographer"]
    assert payload["entities"][0]["tags"] == ["scout"]
    assert len(payload["relationships"]) == 1
    assert payload["relationships"][0]["source_client_id"] == "mira"
    assert len(payload["world_rules"]) == 1
    assert set(payload["world_rules"][0]["tags"]) == {"guild", "law"}
    assert len(payload["random_table_rows"]) == 1
    assert payload["random_table_rows"][0]["weight"] == 3
    assert payload["notes"] == ["Review duplicates."]


def test_extraction_proposal_can_apply_random_table_rows() -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Oracle Dice"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    table_response = client.post(
        f"/api/worlds/{world_id}/random-tables",
        json={"name": "Moon market rumors"},
    )
    assert table_response.status_code == 201
    table_id = table_response.json()["id"]

    proposal_response = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Add rumors about the moon market: a bell tolls under the river and a masked buyer wants glass.",
            "payload": {
                "random_table_rows": [
                    {
                        "table_id": table_id,
                        "label": "River bell",
                        "result": "A bell tolls under the river when the moon market opens.",
                        "weight": 2,
                    },
                    {
                        "table_id": table_id,
                        "label": "Masked buyer",
                        "result": "A masked buyer pays double for unbroken glass.",
                        "is_secret": True,
                    },
                ]
            },
        },
    )
    assert proposal_response.status_code == 201
    proposal_id = proposal_response.json()["id"]
    assert proposal_response.json()["payload"]["random_table_rows"][0]["source_excerpt"] is None

    selected_response = client.post(
        f"/api/proposals/{proposal_id}/apply-selected",
        json={
            "entity_indices": [],
            "relationship_indices": [],
            "world_rule_indices": [],
            "random_table_row_indices": [1],
        },
    )
    assert selected_response.status_code == 200
    assert selected_response.json() == {
        "proposal_id": proposal_id,
        "created_entities": 0,
        "updated_entities": 0,
        "created_relationships": 0,
        "created_world_rules": 0,
        "created_random_tables": 0,
        "created_random_table_rows": 1,
    }

    tables = client.get(f"/api/worlds/{world_id}/random-tables").json()
    assert len(tables) == 1
    assert [row["label"] for row in tables[0]["rows"]] == ["Masked buyer"]
    assert tables[0]["rows"][0]["is_secret"] is True

    invalid_response = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Bad table.",
            "payload": {
                "random_table_rows": [
                    {
                        "table_id": "missing-table",
                        "result": "This should not validate.",
                    }
                ]
            },
        },
    )
    assert invalid_response.status_code == 422


def test_extraction_proposal_can_create_random_table_with_rows() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "New Dice"}).json()["id"]
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Create a weather table.",
            "payload": {
                "random_tables": [
                    {
                        "client_id": "weather",
                        "name": "Strange weather",
                        "description": "Weather over the glass marsh.",
                    }
                ],
                "random_table_rows": [
                    {"table_client_id": "weather", "label": "Ash", "result": "Warm ash falls.", "weight": 2},
                    {"table_client_id": "weather", "label": "Glass rain", "result": "Glass rain begins."},
                ],
            },
        },
    )
    assert proposal.status_code == 201

    apply_response = client.post(
        f"/api/proposals/{proposal.json()['id']}/apply-selected",
        json={
            "entity_indices": [],
            "relationship_indices": [],
            "world_rule_indices": [],
            "random_table_indices": [],
            "random_table_row_indices": [0, 1],
        },
    )
    assert apply_response.status_code == 200
    assert apply_response.json()["created_random_tables"] == 1
    assert apply_response.json()["created_random_table_rows"] == 2
    tables = client.get(f"/api/worlds/{world_id}/random-tables").json()
    assert [table["name"] for table in tables] == ["Strange weather"]
    assert [row["label"] for row in tables[0]["rows"]] == ["Ash", "Glass rain"]


def test_detective_board_can_be_generated_and_deleted(monkeypatch) -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Casebook"}).json()["id"]
    entity = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "character", "name": "Inspector Vale"},
    ).json()

    class FakeBoardLLMClient:
        async def chat(self, request):
            return LLMChatResponse(
                model="fake-board",
                message=LLMMessage(
                    role="assistant",
                    content=f"""
                    {{
                      "nodes": [
                        {{"client_id": "inspector", "entity_id": "{entity['id']}", "title": "Inspector Vale", "note": "Follows the wax trail."}},
                        {{"client_id": "seal", "title": "Blue wax seal", "note": "Found near the gate.", "is_secret": false}},
                        {{"client_id": "patron", "title": "Hidden patron", "note": "Paid for silence.", "is_secret": true}}
                      ],
                      "connections": [
                        {{"source_client_id": "inspector", "target_client_id": "seal", "label": "found"}},
                        {{"source_client_id": "seal", "target_client_id": "patron", "label": "points to", "is_secret": true}}
                      ]
                    }}
                    """,
                ),
                finish_reason="stop",
            )

    import worldbuilder_core.api.routes.detective_board as detective_route

    monkeypatch.setattr(detective_route, "build_llm_client", lambda *_, **__: FakeBoardLLMClient())
    generated = client.post(
        f"/api/worlds/{world_id}/detective-board/generate",
        json={"output_language": "en", "max_nodes": 8},
    )
    assert generated.status_code == 201
    assert len(generated.json()["nodes"]) == 3
    assert len(generated.json()["connections"]) == 2
    assert generated.json()["nodes"][0]["entity_id"] == entity["id"]
    assert client.post(f"/api/worlds/{world_id}/detective-board/generate", json={}).status_code == 409

    deleted = client.delete(f"/api/worlds/{world_id}/detective-board")
    assert deleted.status_code == 204
    assert client.get(f"/api/worlds/{world_id}/detective-board").json() == {"nodes": [], "connections": []}


def test_world_can_be_deleted_with_all_owned_data() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Disposable World"}).json()["id"]
    client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "concept", "name": "Temporary concept"},
    )

    response = client.delete(f"/api/worlds/{world_id}")
    assert response.status_code == 204
    assert all(world["id"] != world_id for world in client.get("/api/worlds").json())
    assert client.get(f"/api/worlds/{world_id}").status_code == 404

def test_extraction_proposal_can_update_existing_entity_by_match_id() -> None:
    client = build_client()
    world_response = client.post("/api/worlds", json={"name": "Revision Basin"})
    assert world_response.status_code == 201
    world_id = world_response.json()["id"]

    entity_response = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "character",
            "name": "Mira",
            "summary": "An old summary.",
            "tags": ["scout"],
            "status": "verified",
        },
    )
    assert entity_response.status_code == 201
    entity_id = entity_response.json()["id"]

    proposal_response = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Mira is now the master cartographer of the basin.",
            "payload": {
                "entities": [
                    {
                        "match_entity_id": entity_id,
                        "source_excerpt": "Mira is now the master cartographer of the basin.",
                        "type": "character",
                        "name": "Mira",
                        "summary": "Master cartographer of the basin.",
                        "tags": ["cartographer"],
                        "status": "proposed",
                    }
                ],
                "relationships": [],
                "world_rules": [],
                "notes": [],
            },
        },
    )
    assert proposal_response.status_code == 201
    proposal_id = proposal_response.json()["id"]

    apply_response = client.post(f"/api/proposals/{proposal_id}/apply")
    assert apply_response.status_code == 200
    assert apply_response.json() == {
        "proposal_id": proposal_id,
        "created_entities": 0,
        "updated_entities": 1,
        "created_relationships": 0,
        "created_world_rules": 0,
        "created_random_tables": 0,
        "created_random_table_rows": 0,
    }

    entities = client.get(f"/api/worlds/{world_id}/entities").json()
    assert len(entities) == 1
    assert entities[0]["id"] == entity_id
    assert entities[0]["summary"] == "Master cartographer of the basin."
    assert set(entities[0]["tags"]) == {"scout", "cartographer"}
    assert entities[0]["status"] == "proposed"


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
