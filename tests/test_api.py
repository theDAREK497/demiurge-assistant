import base64
from collections.abc import Generator
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from worldbuilder_core.db import Base, get_session
from worldbuilder_core.main import create_app
from worldbuilder_core.schemas import LLMChatResponse, LLMMessage


def build_client(*, client_address: tuple[str, int] = ("testclient", 50000)) -> TestClient:
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
    return TestClient(app, client=client_address)


def process_uploaded_document(client: TestClient, document_id: str) -> dict:
    for _ in range(20):
        response = client.post(f"/api/documents/{document_id}/process?batch_size=2")
        assert response.status_code == 200, response.text
        document = response.json()["document"]
        if document["status"] == "ready":
            return document
    raise AssertionError("Document did not finish processing")


def test_duplicate_candidates_keep_ambiguous_short_names_separate() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Names"}).json()["id"]
    for name in ("Александр", "Александр Тимофеев", "Александр Петров"):
        response = client.post(
            f"/api/worlds/{world_id}/entities",
            json={"type": "character", "name": name},
        )
        assert response.status_code == 201, response.text

    response = client.get(f"/api/worlds/{world_id}/entities/duplicate-candidates")

    assert response.status_code == 200, response.text
    candidates = response.json()
    assert len(candidates) == 2
    assert {candidate["confidence"] for candidate in candidates} == {"ambiguous"}
    assert all("ambiguous_short_name" in candidate["reasons"] for candidate in candidates)


def test_proposal_matching_never_changes_an_entity_of_another_type() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Type Guard"}).json()["id"]
    location = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "Аврора", "summary": "Полярная станция."},
    ).json()
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Аврора является руководителем экспедиции.",
            "payload": {
                "entities": [
                    {
                        "client_id": "aurora-character",
                        "type": "character",
                        "name": "Аврора",
                        "summary": "Руководитель экспедиции.",
                    }
                ]
            },
        },
    ).json()

    response = client.post(f"/api/proposals/{proposal['id']}/apply")

    assert response.status_code == 200, response.text
    entities = client.get(f"/api/worlds/{world_id}/entities").json()
    assert {(entity["name"], entity["type"]) for entity in entities} == {
        ("Аврора", "location"),
        ("Аврора", "character"),
    }
    assert next(entity for entity in entities if entity["type"] == "location")["id"] == location["id"]


def test_repeated_proposal_publish_upserts_canonical_objects_and_keeps_secrets() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Canonical Guard"}).json()["id"]
    source = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "character", "name": "Мира", "is_secret": True},
    ).json()
    target = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "Башня"},
    ).json()
    relationship = client.post(
        f"/api/worlds/{world_id}/relationships",
        json={
            "source_entity_id": source["id"],
            "target_entity_id": target["id"],
            "type": "guards",
            "label": "тайно охраняет",
            "weight": 9,
            "is_secret": True,
        },
    ).json()
    client.post(
        f"/api/worlds/{world_id}/world-rules",
        json={
            "condition": "Башня открыта.",
            "effect": "Звон слышен во всем городе.",
            "is_secret": True,
        },
    )
    table = client.post(
        f"/api/worlds/{world_id}/random-tables",
        json={"name": "Шепот башни"},
    ).json()
    client.post(
        f"/api/random-tables/{table['id']}/rows",
        json={"label": "1", "result": "Мира проходит по стене.", "weight": 8, "is_secret": True},
    )
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Мира охраняет Башню. Таблица и правило подтверждены.",
            "payload": {
                "entities": [
                    {
                        "match_entity_id": source["id"],
                        "type": "character",
                        "name": "Мира",
                        "summary": "Хранительница Башни.",
                        "is_secret": False,
                    }
                ],
                "relationships": [
                    {
                        "source_entity_id": source["id"],
                        "target_entity_id": target["id"],
                        "type": "guards",
                        "label": "охраняет Башню",
                        "weight": 3,
                        "is_secret": False,
                    }
                ],
                "world_rules": [
                    {
                        "condition": "Башня открыта.",
                        "effect": "Звон слышен во всем городе.",
                        "is_secret": False,
                    }
                ],
                "random_tables": [
                    {"client_id": "tower-whispers", "name": "Шепот башни", "is_secret": False}
                ],
                "random_table_rows": [
                    {
                        "table_client_id": "tower-whispers",
                        "label": "1",
                        "result": "Мира проходит по стене.",
                        "weight": 2,
                        "is_secret": False,
                    }
                ],
            },
        },
    ).json()

    response = client.post(f"/api/proposals/{proposal['id']}/apply")

    assert response.status_code == 200, response.text
    stored_source = client.get(f"/api/entities/{source['id']}").json()
    assert stored_source["is_secret"] is True
    relationships = client.get(f"/api/worlds/{world_id}/relationships").json()
    assert len(relationships) == 1
    assert relationships[0]["id"] == relationship["id"]
    assert relationships[0]["weight"] == 3
    assert relationships[0]["is_secret"] is True
    assert len(client.get(f"/api/worlds/{world_id}/relationship-revisions").json()) == 2
    rules = client.get(f"/api/worlds/{world_id}/world-rules?active_only=false").json()
    assert len(rules) == 1
    assert rules[0]["is_secret"] is True
    tables = client.get(f"/api/worlds/{world_id}/random-tables").json()
    assert len(tables) == 1
    assert len(tables[0]["rows"]) == 1
    assert tables[0]["rows"][0]["weight"] == 2
    assert tables[0]["rows"][0]["is_secret"] is True


def test_proposal_apply_rolls_back_partial_writes(monkeypatch) -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Atomic Publish"}).json()["id"]
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={"source_text": "Failure fixture.", "payload": {}},
    ).json()

    import worldbuilder_core.services.proposals as proposal_service
    from worldbuilder_core.models import Entity

    def fail_after_write(session, stored_proposal, _payload):
        session.add(Entity(world_id=stored_proposal.world_id, type="concept", name="Partial write"))
        session.flush()
        raise proposal_service.ProposalValidationError("forced failure")

    monkeypatch.setattr(proposal_service, "_apply_payload", fail_after_write)

    response = client.post(f"/api/proposals/{proposal['id']}/apply")

    assert response.status_code == 422
    assert client.get(f"/api/worlds/{world_id}/entities").json() == []
    stored_proposal = client.get(f"/api/proposals/{proposal['id']}").json()
    assert stored_proposal["status"] == "pending"
    assert stored_proposal["error"] == "forced failure"


def test_merge_entities_preserves_data_and_rewires_references() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Merge"}).json()["id"]
    primary = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "character",
            "name": "Александр Тимофеев",
            "summary": "Исследователь",
            "tags": ["ученый"],
        },
    ).json()
    duplicate = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "character",
            "name": "Александр",
            "description": "Работал в северной лаборатории.",
            "aliases": ["Саша"],
            "tags": ["экспедиция"],
        },
    ).json()
    target = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "Северная лаборатория"},
    ).json()
    for source_id in (primary["id"], duplicate["id"]):
        response = client.post(
            f"/api/worlds/{world_id}/relationships",
            json={
                "source_entity_id": source_id,
                "target_entity_id": target["id"],
                "type": "works_at",
                "label": "Работает в",
                "weight": 6,
            },
        )
        assert response.status_code == 201, response.text
    pin = client.post(
        f"/api/worlds/{world_id}/map-pins",
        json={
            "map_entity_id": target["id"],
            "linked_entity_id": duplicate["id"],
            "title": "Рабочее место",
            "x": 0.2,
            "y": 0.3,
        },
    )
    assert pin.status_code == 201, pin.text
    node = client.post(
        f"/api/worlds/{world_id}/detective-board/nodes",
        json={"entity_id": duplicate["id"], "title": "Подозреваемый"},
    )
    assert node.status_code == 201, node.text

    response = client.post(
        f"/api/worlds/{world_id}/entities/merge",
        json={
            "primary_entity_id": primary["id"],
            "duplicate_entity_id": duplicate["id"],
            "type": "character",
            "name": "Александр Тимофеев",
            "summary": "Исследователь",
            "description": None,
            "aliases": [],
            "tags": [],
            "is_secret": False,
            "status": "verified",
            "attributes": {},
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["deleted_entity_id"] == duplicate["id"]
    assert result["merged_relationships"] == 1
    assert result["updated_references"] == 2
    assert "Александр" in result["entity"]["aliases"]
    assert "Саша" in result["entity"]["aliases"]
    assert set(result["entity"]["tags"]) == {"ученый", "экспедиция"}
    assert "северной лаборатории" in result["entity"]["description"]
    assert client.get(f"/api/entities/{duplicate['id']}").status_code == 404
    relationships = client.get(f"/api/worlds/{world_id}/relationships").json()
    assert len(relationships) == 1
    assert relationships[0]["source_entity_id"] == primary["id"]
    revisions = client.get(f"/api/worlds/{world_id}/relationship-revisions").json()
    assert len(revisions) == 2
    assert {revision["relationship_id"] for revision in revisions} == {relationships[0]["id"]}
    assert any("Merged duplicate entity" in (revision["change_note"] or "") for revision in revisions)
    assert client.get(f"/api/worlds/{world_id}/map-pins").json()[0]["linked_entity_id"] == primary["id"]
    assert client.get(f"/api/worlds/{world_id}/detective-board").json()["nodes"][0]["entity_id"] == primary["id"]


def test_remote_player_cannot_escalate_to_master_api(monkeypatch) -> None:
    trusted_client = build_client()
    world_id = trusted_client.post("/api/worlds", json={"name": "Guarded Vale"}).json()["id"]
    trusted_client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "concept", "name": "Public lore", "is_secret": False},
    )
    trusted_client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "concept", "name": "Master secret", "is_secret": True},
    )
    table_id = trusted_client.post(
        f"/api/worlds/{world_id}/random-tables",
        json={"name": "Public roll"},
    ).json()["id"]
    trusted_client.post(
        f"/api/random-tables/{table_id}/rows",
        json={"result": "Visible result"},
    )

    remote_player = TestClient(trusted_client.app, client=("192.0.2.20", 50000))
    assert remote_player.get("/api/worlds", headers={"Host": "rebind.example"}).status_code == 400
    assert remote_player.get("/api/worlds").status_code == 200
    player_entities = remote_player.get(f"/api/worlds/{world_id}/entities?role=player")
    assert player_entities.status_code == 200
    assert [entity["name"] for entity in player_entities.json()] == ["Public lore"]
    assert remote_player.post(f"/api/random-tables/{table_id}/roll?role=player").status_code == 200

    assert remote_player.get(f"/api/worlds/{world_id}/entities?role=master").status_code == 403
    assert remote_player.get(f"/api/worlds/{world_id}/entities").status_code == 403
    assert remote_player.get("/api/llm/config").status_code == 403
    assert remote_player.post("/api/worlds", json={"name": "Forbidden"}).status_code == 403

    monkeypatch.setattr(trusted_client.app.state.worldbuilder_settings, "master_token", "correct-master-key")
    remote_master = TestClient(
        trusted_client.app,
        client=("192.0.2.21", 50000),
        headers={"X-Worldbuilder-Master-Token": "correct-master-key"},
    )
    master_entities = remote_master.get(f"/api/worlds/{world_id}/entities?role=master")
    assert master_entities.status_code == 200
    assert {entity["name"] for entity in master_entities.json()} == {"Public lore", "Master secret"}

    app_response = trusted_client.get("/app/")
    assert app_response.headers["x-content-type-options"] == "nosniff"
    assert app_response.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in app_response.headers["content-security-policy"]

    monkeypatch.setattr(trusted_client.app.state.worldbuilder_settings, "max_request_bytes", 128)
    oversized = trusted_client.post(
        "/api/worlds",
        content=b"x" * 129,
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 413


def test_dynamic_entity_types_and_quest_statuses() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Configurable World"}).json()["id"]

    types = client.get(f"/api/worlds/{world_id}/entity-types").json()
    assert {item["key"] for item in types} >= {"character", "location", "event"}

    custom_type = client.post(
        f"/api/worlds/{world_id}/entity-types",
        json={"name": "Era artifact", "color": "#123ABC"},
    )
    assert custom_type.status_code == 201
    custom_type_payload = custom_type.json()
    assert custom_type_payload["key"] == "era_artifact"

    entity = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "creature_kind", "name": "Ash Drake"},
    )
    assert entity.status_code == 201
    assert any(
        item["key"] == "creature_kind"
        for item in client.get(f"/api/worlds/{world_id}/entity-types").json()
    )

    statuses = client.get(f"/api/worlds/{world_id}/quest-statuses").json()
    assert [item["key"] for item in statuses][:2] == ["backlog", "active"]
    custom_status = client.post(
        f"/api/worlds/{world_id}/quest-statuses",
        json={"name": "Review", "color": "#ABCDEF"},
    )
    assert custom_status.status_code == 201
    assert custom_status.json()["key"] == "review"

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
    assert 'data-tab="assistant"' in app_response.text
    assert 'data-tab="experience"' in app_response.text
    assert 'id="experienceForm"' in app_response.text
    assert 'id="experienceCauses"' in app_response.text
    assert 'id="assistantForm"' in app_response.text
    assert 'id="assistantAuditResolverBackdrop"' in app_response.text
    assert 'id="assistantAuditResolverContent"' in app_response.text
    assert app_response.text.count("data-assistant-scenario=") == 3
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
    assert ru_response.json()["tabs.assistant"] == "Помощник"
    assert ru_response.json()["tabs.experience"] == "Опыт"
    assert ru_response.json()["assistant.adventure.title"] == "Подготовить приключение"
    assert ru_response.json()["assistant.audit.resolve"] == "Разобрать конфликты"
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
    assert "openProposalEditor" in render_response.text
    assert "weightedCoseLayoutOptions" in render_response.text
    assert "relationshipIdealLength" in render_response.text
    assert 'label: String(Number(relationship.weight ?? 1))' in render_response.text
    assert 't("relationship.type")' in render_response.text
    assert "data-extraction-created-at" in render_response.text
    assert "documents.extractionTiming" in render_response.text
    assert "data-proposal-secret" in render_response.text
    assert "proposal.visibilitySecret" in render_response.text
    assert "#{1,6}" in render_response.text
    assert 'output.push("<hr>")' in render_response.text
    assert "export function renderAssistant" in render_response.text
    assert "parseApiDateTime" in render_response.text
    assert "`${normalized}Z`" in render_response.text
    assert "proposalRelationshipEndpointName(relationship, \"source\", proposal.payload)" in render_response.text

    actions_response = client.get("/app/js/actions.js")
    assert actions_response.status_code == 200
    assert "export function parseAssistantAuditFindings" in actions_response.text
    assert "export async function createAssistantAuditDraft" in actions_response.text
    assert "A shared location, group membership" in actions_response.text

    theme_response = client.get("/app/js/theme.js")
    assert theme_response.status_code == 200
    assert "setTheme" in theme_response.text


def test_llm_config_can_be_persisted() -> None:
    client = build_client()

    initial_response = client.get("/api/llm/config")
    assert initial_response.status_code == 200
    assert initial_response.json()["persisted"] is False
    assert initial_response.json()["default_model"] == ""

    update_response = client.put(
        "/api/llm/config",
        json={
            "base_url": "http://127.0.0.1:1234/v1/",
            "default_model": "local-default",
            "chat_model": "local-chat",
            "extractor_model": "local-extractor",
            "summarizer_model": "",
            "critic_model": None,
            "embedding_model": "local-embed",
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
    assert payload["embedding_model"] == "local-embed"
    assert payload["has_api_key"] is True
    assert payload["timeout_seconds"] == 45
    assert payload["max_entities_per_extract"] == 7
    assert payload["persisted"] is True

    clear_response = client.put(
        "/api/llm/config",
        json={
            "base_url": "http://127.0.0.1:1234/v1",
            "default_model": "",
            "api_key": "",
            "clear_api_key": True,
            "timeout_seconds": 45,
            "max_entities_per_extract": 7,
        },
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["has_api_key"] is False
    assert clear_response.json()["default_model"] == ""


def test_image_asset_upload_and_serving(monkeypatch, tmp_path) -> None:
    from worldbuilder_core.config import get_settings

    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path / "uploads"))
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

    world_id = client.post("/api/worlds", json={"name": "Asset cleanup"}).json()["id"]
    entity_id = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "character", "name": "Portrait owner", "attributes": {"image_url": payload["url"]}},
    ).json()["id"]
    assert client.delete(f"/api/entities/{entity_id}").status_code == 204
    assert client.get(payload["url"]).status_code == 404

    unsupported_response = client.post(
        "/api/assets",
        json={
            "filename": "note.txt",
            "content_type": "text/plain",
            "content_base64": base64.b64encode(b"hello").decode("ascii"),
        },
    )
    assert unsupported_response.status_code == 415

    mismatched_response = client.post(
        "/api/assets",
        json={
            "filename": "fake.png",
            "content_type": "image/png",
            "content_base64": base64.b64encode(b"<html>not an image</html>").decode("ascii"),
        },
    )
    assert mismatched_response.status_code == 422


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
            "imported_entity_revisions": 2,
            "imported_world_changes": 3,
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


def test_world_context_finds_entities_by_alias_and_exposes_alias_to_the_model() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Alias Search"}).json()["id"]
    entity = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "character",
            "name": "Александр Тимофеев",
            "aliases": ["Саша"],
            "summary": "Исследователь проекта Эон.",
        },
    ).json()

    response = client.get(f"/api/worlds/{world_id}/context?role=master&q=Саша")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["id"] for item in payload["entities"]] == [entity["id"]]
    assert "aliases: Саша" in payload["context_text"]


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
    changes = client.get(f"/api/worlds/{world_id}/changes").json()
    assert len(changes) == 4
    assert {change["change_kind"] for change in changes} == {"created", "published"}
    assert {change["source_id"] for change in changes} == {proposal_id}
    assert len(exported_world.json()["entity_revisions"]) == 2
    assert len(exported_world.json()["world_changes"]) == 4

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


def test_extraction_matches_semantic_role_variant_to_existing_entity(monkeypatch) -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Copper Vale"}).json()["id"]
    existing = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "character",
            "name": "Старейшина Громоздкий",
            "summary": "Заказчик миссии, лидер общины Медной долины.",
            "description": "Пожилой лидер общины требует спасения пропавших рабочих.",
        },
    ).json()

    class FakeExtractionLLMClient:
        async def chat(self, request):
            return LLMChatResponse(
                model="fake-extractor",
                message=LLMMessage(
                    role="assistant",
                    content="""
                    {
                      "entities": [
                        {
                          "client_id": "settlement-elder",
                          "type": "character",
                          "name": "Старейшина Поселка",
                          "summary": "Старейшина местной общины просит спасти пропавших рабочих.",
                          "description": "Представитель сообщества Медной долины и заказчик приключения."
                        }
                      ]
                    }
                    """,
                ),
                finish_reason="stop",
            )

    import worldbuilder_core.api.routes.proposals as proposals_route

    monkeypatch.setattr(proposals_route, "build_llm_client", lambda *_, **__: FakeExtractionLLMClient())

    proposal_response = client.post(
        f"/api/worlds/{world_id}/proposals/extract",
        json={"source_text": "Старейшина поселка просит спасти пропавших рабочих."},
    )

    assert proposal_response.status_code == 201
    draft = proposal_response.json()["payload"]["entities"][0]
    assert draft["match_entity_id"] == existing["id"]
    assert draft["client_id"] is None
    assert draft["name"] == "Старейшина Громоздкий"
    assert "Старейшина Поселка" in draft["aliases"]

    apply_response = client.post(f"/api/proposals/{proposal_response.json()['id']}/apply")
    assert apply_response.status_code == 200
    assert apply_response.json()["created_entities"] == 0
    assert apply_response.json()["updated_entities"] == 1
    entities = client.get(f"/api/worlds/{world_id}/entities").json()
    assert len(entities) == 1
    assert "Старейшина Поселка" in entities[0]["aliases"]


def test_extraction_endpoint_guarantees_requested_quest_entity(monkeypatch) -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Quest Vale"}).json()["id"]
    existing_quest = client.post(
        f"/api/worlds/{world_id}/entities",
        json={
            "type": "event",
            "name": "Эхо старой шахты: Потерянный медный колокол",
            "summary": "Приключение о пропавшем медном колоколе.",
        },
    ).json()

    class FakeExtractionLLMClient:
        async def chat(self, request):
            return LLMChatResponse(
                model="fake-extractor",
                message=LLMMessage(
                    role="assistant",
                    content="""
                    {
                      "entities": [
                        {"client_id": "elder", "type": "character", "name": "Старейшина"},
                        {"client_id": "stage", "type": "event", "name": "Набег (Этап I)"}
                      ]
                    }
                    """,
                ),
                finish_reason="stop",
            )

    import worldbuilder_core.api.routes.proposals as proposals_route

    monkeypatch.setattr(proposals_route, "build_llm_client", lambda *_, **__: FakeExtractionLLMClient())

    response = client.post(
        f"/api/worlds/{world_id}/proposals/extract",
        json={
            "intent_text": "Создай квест.",
            "source_text": (
                '# КВЕСТ: "ПОТЕРЯННЫЙ МЕДНЫЙ КОЛОКОЛ"\n\n'
                "### Цель\nВернуть колокол до рассвета."
            ),
        },
    )

    assert response.status_code == 201
    quests = [entity for entity in response.json()["payload"]["entities"] if "quest" in entity["tags"]]
    assert len(quests) == 1
    assert quests[0]["name"] == "Эхо старой шахты: Потерянный медный колокол"
    assert quests[0]["type"] == "event"
    assert quests[0]["match_entity_id"] == existing_quest["id"]
    assert "Потерянный медный колокол" in quests[0]["aliases"]


def test_adventure_generation_creates_one_complete_draft(monkeypatch) -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Ash Coast"}).json()["id"]
    existing = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "Cinder Port", "summary": "A storm-battered harbor."},
    ).json()

    class FakeAdventureLLMClient:
        async def chat(self, request):
            assert request.reasoning_effort == "none"
            assert request.response_format["json_schema"]["strict"] is True
            assert "creative generation" in request.messages[0].content
            assert "Cinder Port" in request.messages[1].content
            return LLMChatResponse(
                model="fake-adventure",
                message=LLMMessage(
                    role="assistant",
                    content=f"""
                    {{
                      "quest": {{"name":"The Drowned Bell","summary":"Recover the bell.","description":"Hook, goal, stakes, three stages, obstacles, and outcome.","quest_status":"planned","timeline_date":"Scene 1"}},
                      "clue": {{"name":"Salt-stained Ledger","summary":"Evidence points to the old pier.","description":"The ledger records the bell shipment."}},
                      "timeline_event": {{"name":"Black Tide","summary":"The tide floods the lower docks.","description":"The flood blocks the safest route.","timeline_date":"Scene 2"}},
                      "supporting_entities": [
                        {{"client_id":"cinder-port","type":"location","name":"{existing['name']}","summary":"A storm-battered harbor.","description":"The adventure starts here."}}
                      ],
                      "relationships": [
                        {{"source_client_id":"quest","target_client_id":"cinder-port","type":"takes_place_in","label":"takes place in","confidence":1.0,"weight":8,"evidence":"The premise names the port."}},
                        {{"source_client_id":"clue","target_client_id":"quest","type":"reveals","label":"reveals","confidence":0.85,"weight":7,"evidence":"The ledger reveals the route."}},
                        {{"source_client_id":"timeline_event","target_client_id":"quest","type":"complicates","label":"complicates","confidence":0.85,"weight":6,"evidence":"The tide blocks the docks."}}
                      ],
                      "random_table": {{
                        "name":"Dock Events","description":"Complications during the search.",
                        "rows": [
                          "A patrol closes the pier.",
                          "The tide exposes a tunnel.",
                          "A witness asks for protection."
                        ]
                      }}
                    }}
                    """,
                ),
                finish_reason="stop",
            )

    import worldbuilder_core.api.routes.proposals as proposals_route

    monkeypatch.setattr(proposals_route, "build_llm_client", lambda *_, **__: FakeAdventureLLMClient())

    response = client.post(
        f"/api/worlds/{world_id}/proposals/generate-adventure",
        json={
            "premise": "Build an investigation around Cinder Port.",
            "scale": "small",
            "tone": "grim",
            "output_language": "en",
            "enabled_modules": ["graph", "timeline", "quests", "randomTables", "detectiveBoard"],
            "max_entities": 8,
        },
    )

    assert response.status_code == 201, response.text
    proposal = response.json()
    assert proposal["status"] == "pending"
    assert len(proposal["payload"]["entities"]) == 4
    assert len(proposal["payload"]["relationships"]) == 3
    assert len(proposal["payload"]["random_table_rows"]) == 3
    cinder_port = next(entity for entity in proposal["payload"]["entities"] if entity["name"] == "Cinder Port")
    assert cinder_port["match_entity_id"] == existing["id"]


def test_apply_does_not_merge_distinct_directional_entities() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Twin Gates"}).json()["id"]
    client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "North Watchtower", "summary": "A gate watchtower."},
    )
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "The South Watchtower is rebuilt.",
            "payload": {
                "entities": [
                    {
                        "client_id": "south-watchtower",
                        "type": "location",
                        "name": "South Watchtower",
                        "summary": "A gate watchtower.",
                    }
                ]
            },
        },
    ).json()

    apply_response = client.post(f"/api/proposals/{proposal['id']}/apply")

    assert apply_response.status_code == 200
    assert apply_response.json()["created_entities"] == 1
    assert len(client.get(f"/api/worlds/{world_id}/entities").json()) == 2


def test_apply_does_not_merge_distinct_short_names_after_russian_stemming() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Short Names"}).json()["id"]
    client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "character", "name": "Мир", "summary": "Странник."},
    )
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Мира пришла в город.",
            "payload": {
                "entities": [
                    {"client_id": "mira", "type": "character", "name": "Мира", "summary": "Странница."}
                ]
            },
        },
    ).json()

    apply_response = client.post(f"/api/proposals/{proposal['id']}/apply")

    assert apply_response.status_code == 200
    assert apply_response.json()["created_entities"] == 1
    assert {entity["name"] for entity in client.get(f"/api/worlds/{world_id}/entities").json()} == {"Мир", "Мира"}


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
                    {"client_id": "mira-copy", "type": "character", "name": "Mira.", "tags": ["scout"]},
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


def test_pending_proposals_merge_into_one_review_draft() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Unified Draft"}).json()["id"]

    first = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Mira serves the Brass Guild.",
            "payload": {
                "entities": [
                    {"client_id": "mira", "type": "character", "name": "Mira", "summary": "Scout."},
                    {"client_id": "guild", "type": "faction", "name": "Brass Guild"},
                ],
                "relationships": [
                    {
                        "source_client_id": "mira",
                        "target_client_id": "guild",
                        "type": "member_of",
                        "weight": 2,
                        "evidence": "A short mention.",
                    }
                ],
            },
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Mira is the senior scout of the Brass Guild.",
            "payload": {
                "entities": [
                    {
                        "client_id": "character-1",
                        "type": "character",
                        "name": "Mira",
                        "summary": "Senior scout and pathfinder of the guild.",
                    },
                    {"client_id": "faction-1", "type": "faction", "name": "Brass Guild"},
                ],
                "relationships": [
                    {
                        "source_client_id": "character-1",
                        "target_client_id": "faction-1",
                        "type": "MEMBER_OF",
                        "weight": 8,
                        "confidence": 0.9,
                        "evidence": "The guild ledger names Mira as its senior scout.",
                    }
                ],
            },
        },
    )
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    payload = second.json()["payload"]
    assert len(payload["entities"]) == 2
    assert len(payload["relationships"]) == 1
    assert payload["entities"][0]["summary"] == "Senior scout and pathfinder of the guild."
    assert payload["relationships"][0]["weight"] == 8
    assert payload["relationships"][0]["confidence"] == 0.9
    assert "A short mention." in payload["relationships"][0]["evidence"]
    assert "The guild ledger names Mira as its senior scout." in payload["relationships"][0]["evidence"]
    assert payload["relationships"][0]["attributes"]["support_count"] == 2
    pending = client.get(f"/api/worlds/{world_id}/proposals?status_filter=pending").json()
    assert len(pending) == 1
    assert "Mira serves" in pending[0]["source_text"]
    assert "senior scout" in pending[0]["source_text"]


def test_pending_proposal_editor_revalidates_and_removes_dangling_links() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Draft Editor"}).json()["id"]
    proposal = client.post(
        f"/api/worlds/{world_id}/proposals",
        json={
            "source_text": "Mira knows Oren.",
            "payload": {
                "entities": [
                    {"client_id": "mira", "type": "character", "name": "Mira"},
                    {"client_id": "oren", "type": "character", "name": "Oren"},
                ],
                "relationships": [
                    {"source_client_id": "mira", "target_client_id": "oren", "type": "knows"}
                ],
            },
        },
    ).json()

    edited = client.patch(
        f"/api/proposals/{proposal['id']}",
        json={
            "source_text": "Mira the Pathfinder.",
            "payload": {
                "entities": [
                    {
                        "client_id": "mira",
                        "type": "character",
                        "name": "Mira the Pathfinder",
                        "description": "Edited before publication.",
                        "is_secret": True,
                    }
                ],
                "relationships": proposal["payload"]["relationships"],
            },
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["payload"]["entities"][0]["name"] == "Mira the Pathfinder"
    assert edited.json()["payload"]["entities"][0]["is_secret"] is True
    assert edited.json()["payload"]["relationships"] == []
    assert edited.json()["source_text"] == "Mira the Pathfinder."
    applied = client.post(f"/api/proposals/{proposal['id']}/apply")
    assert applied.status_code == 200, applied.text
    assert client.get(f"/api/worlds/{world_id}/entities?role=player").json() == []


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


def test_large_document_pipeline_deduplicates_and_retrieves_chunks(tmp_path, monkeypatch) -> None:
    client = build_client()
    monkeypatch.setattr(client.app.state.worldbuilder_settings, "upload_dir", str(tmp_path))
    world_id = client.post("/api/worlds", json={"name": "Book World"}).json()["id"]
    shared = ("obsidian sentinel guards the northern archive. " * 180).encode()

    public_upload = client.post(
        f"/api/worlds/{world_id}/documents?filename=chronicle.txt&is_secret=false",
        content=shared + b"\n\nThe silver observatory is open to every traveler.",
        headers={"Content-Type": "text/plain"},
    )
    assert public_upload.status_code == 201, public_upload.text
    public_document = process_uploaded_document(client, public_upload.json()["id"])
    assert public_document["total_chunks"] > 1

    secret_upload = client.post(
        f"/api/worlds/{world_id}/documents?filename=sealed.txt&is_secret=true",
        content=shared + b"\n\nsealedcipher belongs only to the master.",
        headers={"Content-Type": "text/plain"},
    )
    assert secret_upload.status_code == 201, secret_upload.text
    secret_document = process_uploaded_document(client, secret_upload.json()["id"])
    assert secret_document["duplicate_chunks"] >= 1

    master_context = client.get(f"/api/worlds/{world_id}/context?role=master&q=sealedcipher")
    assert master_context.status_code == 200
    assert any(chunk["filename"] == "sealed.txt" for chunk in master_context.json()["document_chunks"])
    assert "sealedcipher" in master_context.json()["context_text"]

    player_context = client.get(f"/api/worlds/{world_id}/context?role=player&q=sealedcipher")
    assert player_context.status_code == 200
    assert player_context.json()["document_chunks"] == []
    assert "sealedcipher" not in player_context.json()["context_text"]

    listed = client.get(f"/api/worlds/{world_id}/documents")
    assert {item["filename"] for item in listed.json()} == {"chronicle.txt", "sealed.txt"}
    assert client.delete(f"/api/documents/{secret_document['id']}").status_code == 204


def test_document_upload_rejects_duplicate_and_unsupported_file(tmp_path, monkeypatch) -> None:
    client = build_client()
    monkeypatch.setattr(client.app.state.worldbuilder_settings, "upload_dir", str(tmp_path))
    world_id = client.post("/api/worlds", json={"name": "Upload Guard"}).json()["id"]
    payload = b"A unique source document."

    first = client.post(f"/api/worlds/{world_id}/documents?filename=source.txt", content=payload)
    assert first.status_code == 201
    duplicate = client.post(f"/api/worlds/{world_id}/documents?filename=copy.txt", content=payload)
    assert duplicate.status_code == 409
    unsupported = client.post(f"/api/worlds/{world_id}/documents?filename=source.pdf", content=payload)
    assert unsupported.status_code == 415


def test_docx_document_is_extracted_without_optional_dependencies(tmp_path, monkeypatch) -> None:
    client = build_client()
    monkeypatch.setattr(client.app.state.worldbuilder_settings, "upload_dir", str(tmp_path))
    world_id = client.post("/api/worlds", json={"name": "DOCX World"}).json()["id"]
    document_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>The amber lighthouse watches the frozen coast.</w:t></w:r></w:p>
        <w:p><w:r><w:t>Its keeper records every passing vessel.</w:t></w:r></w:p>
      </w:body>
    </w:document>"""
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)

    upload = client.post(
        f"/api/worlds/{world_id}/documents?filename=book.docx",
        content=buffer.getvalue(),
        headers={"Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    )
    assert upload.status_code == 201, upload.text
    process_uploaded_document(client, upload.json()["id"])
    context = client.get(f"/api/worlds/{world_id}/context?q=lighthouse")
    assert "amber lighthouse" in context.json()["context_text"]


def test_deleting_world_removes_document_files(tmp_path, monkeypatch) -> None:
    client = build_client()
    monkeypatch.setattr(client.app.state.worldbuilder_settings, "upload_dir", str(tmp_path))
    world_id = client.post("/api/worlds", json={"name": "Temporary Library"}).json()["id"]
    upload = client.post(
        f"/api/worlds/{world_id}/documents?filename=temporary.txt",
        content=b"Temporary library content.",
    )
    assert upload.status_code == 201
    process_uploaded_document(client, upload.json()["id"])
    assert list(tmp_path.rglob("*"))

    assert client.delete(f"/api/worlds/{world_id}").status_code == 204
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]


def test_embedding_index_queues_and_cancels_worker_job(tmp_path, monkeypatch) -> None:
    client = build_client()
    monkeypatch.setattr(client.app.state.worldbuilder_settings, "upload_dir", str(tmp_path))
    world_id = client.post("/api/worlds", json={"name": "Vector World"}).json()["id"]
    client.put(
        "/api/llm/config",
        json={
            "base_url": "http://embedding.test/v1",
            "default_model": "chat-model",
            "embedding_model": "embed-model",
            "timeout_seconds": 10,
            "max_entities_per_extract": 12,
        },
    )
    upload = client.post(
        f"/api/worlds/{world_id}/documents?filename=vectors.txt",
        content=b"Moon harbor is guarded by glass towers.",
    )
    process_uploaded_document(client, upload.json()["id"])

    queued = client.post(f"/api/worlds/{world_id}/embeddings/process")
    assert queued.status_code == 200, queued.text
    job = queued.json()
    assert job["status"] == "queued"
    assert job["total_chunks"] == 1
    assert client.post(f"/api/worlds/{world_id}/embeddings/process").json()["id"] == job["id"]
    assert client.get(f"/api/embedding-jobs/{job['id']}").json()["status"] == "queued"

    cleared = client.delete(f"/api/worlds/{world_id}/embeddings")
    assert cleared.status_code == 200
    assert cleared.json()["embedded_chunks"] == 0
    assert client.get(f"/api/embedding-jobs/{job['id']}").json()["status"] == "cancelled"


def test_document_extraction_endpoint_queues_one_active_job(tmp_path, monkeypatch) -> None:
    client = build_client()
    monkeypatch.setattr(client.app.state.worldbuilder_settings, "upload_dir", str(tmp_path))
    world_id = client.post("/api/worlds", json={"name": "Extracted Book"}).json()["id"]
    upload = client.post(
        f"/api/worlds/{world_id}/documents?filename=quests.txt",
        content=b"Quest: return the Moon Bell to the northern archive.",
    )
    document = process_uploaded_document(client, upload.json()["id"])

    queued = client.post(f"/api/documents/{document['id']}/extract?output_language=en")
    assert queued.status_code == 202, queued.text
    job = queued.json()
    assert job["status"] == "queued"
    assert job["output_language"] == "en"
    assert job["total_chunks"] == document["total_chunks"]
    assert client.post(f"/api/documents/{document['id']}/extract").json()["id"] == job["id"]
    assert client.get(f"/api/document-extraction-jobs/{job['id']}").json()["status"] == "queued"

    paused = client.post(f"/api/document-extraction-jobs/{job['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["pause_requested"] is True

    resumed = client.post(f"/api/document-extraction-jobs/{job['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "queued"
    assert resumed.json()["pause_requested"] is False

    listed = client.get(f"/api/worlds/{world_id}/document-extraction-jobs")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [job["id"]]


def test_relationship_tracks_strength_period_and_revision_history() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Living Graph"}).json()["id"]
    source_id = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "character", "name": "Mira"},
    ).json()["id"]
    target_id = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "faction", "name": "Archive"},
    ).json()["id"]
    created = client.post(
        f"/api/worlds/{world_id}/relationships",
        json={
            "source_entity_id": source_id,
            "target_entity_id": target_id,
            "type": "member_of",
            "confidence": 0.85,
            "weight": 4.5,
            "valid_from": "Year 315",
            "evidence": "The archive register names Mira.",
        },
    )
    assert created.status_code == 201, created.text
    relationship_id = created.json()["id"]

    updated = client.patch(
        f"/api/relationships/{relationship_id}",
        json={
            "weight": 8,
            "confidence": 1,
            "valid_to": "Year 318",
            "effective_at": "Year 317",
            "change_note": "Mira became the archive keeper.",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["weight"] == 8
    assert updated.json()["valid_to"] == "Year 318"

    revisions = client.get(f"/api/worlds/{world_id}/relationship-revisions").json()
    assert len(revisions) == 2
    assert revisions[0]["effective_at"] == "Year 317"
    assert revisions[0]["change_note"] == "Mira became the archive keeper."
    assert revisions[1]["weight"] == 4.5


def test_world_experience_tracks_changes_and_retrieves_causal_history() -> None:
    client = build_client()
    world_id = client.post("/api/worlds", json={"name": "Causal Vale"}).json()["id"]
    entity = client.post(
        f"/api/worlds/{world_id}/entities",
        json={"type": "location", "name": "Old Bridge", "summary": "The only river crossing."},
    ).json()
    updated = client.patch(
        f"/api/entities/{entity['id']}",
        json={"summary": "The bridge collapsed during the flood."},
    )
    assert updated.status_code == 200, updated.text

    automatic_changes = client.get(f"/api/worlds/{world_id}/changes").json()
    assert [change["change_kind"] for change in automatic_changes] == ["updated", "created"]
    revisions = client.get(f"/api/worlds/{world_id}/entity-revisions?entity_id={entity['id']}").json()
    assert len(revisions) == 2
    assert revisions[0]["before_state"]["summary"] == "The only river crossing."
    assert revisions[0]["after_state"]["summary"] == "The bridge collapsed during the flood."

    flood = client.post(
        f"/api/worlds/{world_id}/changes",
        json={
            "change_kind": "world_event",
            "summary": "A century flood destroyed the eastern roads.",
            "effective_at": "Year 412",
            "confidence": 0.8,
            "evidence": "Harbor chronicle, volume 4.",
        },
    )
    assert flood.status_code == 201, flood.text
    flood_id = flood.json()["id"]
    consequence = client.post(
        f"/api/worlds/{world_id}/changes",
        json={
            "subject_type": "entity",
            "subject_id": entity["id"],
            "change_kind": "world_event",
            "summary": "Old Bridge collapsed and trade moved north.",
            "effective_at": "Year 412",
            "causal_change_ids": [flood_id],
        },
    )
    assert consequence.status_code == 201, consequence.text

    cycle = client.patch(
        f"/api/changes/{flood_id}",
        json={"causal_change_ids": [consequence.json()["id"]]},
    )
    assert cycle.status_code == 422

    context = client.get(f"/api/worlds/{world_id}/context?q=Old%20Bridge")
    assert context.status_code == 200, context.text
    assert "Relevant world changes and causal history" in context.json()["context_text"]
    assert "trade moved north" in context.json()["context_text"]
    assert "century flood" in context.json()["context_text"]

    secret = client.post(
        f"/api/worlds/{world_id}/changes",
        json={"change_kind": "world_event", "summary": "Hidden plot moved the royal seal.", "is_secret": True},
    )
    assert secret.status_code == 201
    player_context = client.get(f"/api/worlds/{world_id}/context?role=player&q=Hidden%20plot").json()
    assert "Hidden plot" not in player_context["context_text"]
    assert client.get(f"/api/worlds/{world_id}/changes?role=player&q=Hidden%20plot").json() == []

    deleted = client.delete(f"/api/entities/{entity['id']}")
    assert deleted.status_code == 204
    retained = client.get(f"/api/worlds/{world_id}/changes?subject_id={entity['id']}").json()
    assert retained[0]["change_kind"] == "deleted"
    deleted_revision = client.get(f"/api/worlds/{world_id}/entity-revisions?entity_id={entity['id']}").json()[0]
    assert deleted_revision["before_state"]["name"] == "Old Bridge"
