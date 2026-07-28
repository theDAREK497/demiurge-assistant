from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from worldbuilder_core import __version__
from worldbuilder_core.models import (
    DetectiveBoardConnection,
    DetectiveBoardNode,
    Entity,
    EntityTypeDefinition,
    ExtractionProposal,
    MapPin,
    RandomTable,
    RandomTableRow,
    QuestStatusDefinition,
    Relationship,
    World,
    WorldRule,
)
from worldbuilder_core.schemas import (
    DetectiveBoardConnectionSnapshot,
    DetectiveBoardNodeSnapshot,
    EntitySnapshot,
    EntityTypeDefinitionSnapshot,
    ExtractionProposalSnapshot,
    ExportMetadata,
    MapPinSnapshot,
    RandomTableRowSnapshot,
    RandomTableSnapshot,
    QuestStatusDefinitionSnapshot,
    RelationshipSnapshot,
    WorldExport,
    WorldImportResult,
    WorldRuleSnapshot,
    WorldSnapshot,
)
from worldbuilder_core.services.world_configuration import ensure_world_configuration

EXPORT_SCHEMA_VERSION = "worldbuilder.snapshot.v1"


class ImportExportError(Exception):
    """Base error for snapshot import/export operations."""


class WorldNotFoundError(ImportExportError):
    pass


class WorldAlreadyExistsError(ImportExportError):
    pass


class InvalidSnapshotError(ImportExportError):
    pass


def export_world(session: Session, world_id: str) -> WorldExport:
    world = session.get(World, world_id)
    if world is None:
        raise WorldNotFoundError(f"World {world_id!r} not found")

    ensure_world_configuration(session, world_id)
    entity_types = list(
        session.scalars(
            select(EntityTypeDefinition)
            .where(EntityTypeDefinition.world_id == world_id)
            .order_by(EntityTypeDefinition.position, EntityTypeDefinition.id)
        )
    )
    quest_statuses = list(
        session.scalars(
            select(QuestStatusDefinition)
            .where(QuestStatusDefinition.world_id == world_id)
            .order_by(QuestStatusDefinition.position, QuestStatusDefinition.id)
        )
    )
    entities = list(
        session.scalars(select(Entity).where(Entity.world_id == world_id).order_by(Entity.created_at.asc(), Entity.id.asc()))
    )
    relationships = list(
        session.scalars(
            select(Relationship)
            .where(Relationship.world_id == world_id)
            .order_by(Relationship.created_at.asc(), Relationship.id.asc())
        )
    )
    rules = list(
        session.scalars(
            select(WorldRule).where(WorldRule.world_id == world_id).order_by(WorldRule.created_at.asc(), WorldRule.id.asc())
        )
    )
    proposals = list(
        session.scalars(
            select(ExtractionProposal)
            .where(ExtractionProposal.world_id == world_id)
            .order_by(ExtractionProposal.created_at.asc(), ExtractionProposal.id.asc())
        )
    )
    map_pins = list(
        session.scalars(
            select(MapPin).where(MapPin.world_id == world_id).order_by(MapPin.created_at.asc(), MapPin.id.asc())
        )
    )
    random_tables = list(
        session.scalars(
            select(RandomTable)
            .where(RandomTable.world_id == world_id)
            .order_by(RandomTable.created_at.asc(), RandomTable.id.asc())
        )
    )
    table_ids = [table.id for table in random_tables]
    random_table_rows = (
        list(
            session.scalars(
                select(RandomTableRow)
                .where(RandomTableRow.table_id.in_(table_ids))
                .order_by(RandomTableRow.created_at.asc(), RandomTableRow.id.asc())
            )
        )
        if table_ids
        else []
    )
    detective_nodes = list(
        session.scalars(
            select(DetectiveBoardNode)
            .where(DetectiveBoardNode.world_id == world_id)
            .order_by(DetectiveBoardNode.created_at.asc(), DetectiveBoardNode.id.asc())
        )
    )
    detective_connections = list(
        session.scalars(
            select(DetectiveBoardConnection)
            .where(DetectiveBoardConnection.world_id == world_id)
            .order_by(DetectiveBoardConnection.created_at.asc(), DetectiveBoardConnection.id.asc())
        )
    )

    return WorldExport(
        metadata=ExportMetadata(
            schema_version=EXPORT_SCHEMA_VERSION,
            app_version=__version__,
            exported_at=datetime.now(UTC),
        ),
        world=WorldSnapshot.model_validate(world),
        entity_types=[EntityTypeDefinitionSnapshot.model_validate(item) for item in entity_types],
        quest_statuses=[QuestStatusDefinitionSnapshot.model_validate(item) for item in quest_statuses],
        entities=[EntitySnapshot.model_validate(entity) for entity in entities],
        relationships=[RelationshipSnapshot.model_validate(relationship) for relationship in relationships],
        world_rules=[WorldRuleSnapshot.model_validate(rule) for rule in rules],
        map_pins=[MapPinSnapshot.model_validate(pin) for pin in map_pins],
        random_tables=[RandomTableSnapshot.model_validate(table) for table in random_tables],
        random_table_rows=[RandomTableRowSnapshot.model_validate(row) for row in random_table_rows],
        detective_board_nodes=[DetectiveBoardNodeSnapshot.model_validate(node) for node in detective_nodes],
        detective_board_connections=[
            DetectiveBoardConnectionSnapshot.model_validate(connection) for connection in detective_connections
        ],
        proposals=[ExtractionProposalSnapshot.model_validate(proposal) for proposal in proposals],
    )


def import_world(session: Session, snapshot: WorldExport, *, replace_existing: bool = False) -> WorldImportResult:
    validate_snapshot(snapshot)

    existing_world = session.get(World, snapshot.world.id)
    if existing_world is not None:
        if not replace_existing:
            raise WorldAlreadyExistsError(f"World {snapshot.world.id!r} already exists")
        session.delete(existing_world)
        session.flush()

    world = World(**snapshot.world.model_dump())
    session.add(world)
    session.flush()

    for definition in snapshot.entity_types:
        session.add(EntityTypeDefinition(**definition.model_dump()))
    for definition in snapshot.quest_statuses:
        session.add(QuestStatusDefinition(**definition.model_dump()))
    if not snapshot.entity_types or not snapshot.quest_statuses:
        ensure_world_configuration(session, world.id)

    for entity_data in snapshot.entities:
        session.add(Entity(**entity_data.model_dump()))
    session.flush()

    for relationship_data in snapshot.relationships:
        session.add(Relationship(**relationship_data.model_dump()))

    for rule_data in snapshot.world_rules:
        session.add(WorldRule(**rule_data.model_dump()))

    for pin_data in snapshot.map_pins:
        session.add(MapPin(**pin_data.model_dump()))

    for table_data in snapshot.random_tables:
        data = table_data.model_dump(exclude={"rows"})
        session.add(RandomTable(**data))
    session.flush()

    for row_data in snapshot.random_table_rows:
        session.add(RandomTableRow(**row_data.model_dump()))

    for node_data in snapshot.detective_board_nodes:
        session.add(DetectiveBoardNode(**node_data.model_dump()))
    session.flush()

    for connection_data in snapshot.detective_board_connections:
        session.add(DetectiveBoardConnection(**connection_data.model_dump()))

    for proposal_data in snapshot.proposals:
        data = proposal_data.model_dump()
        data["payload"] = proposal_data.payload.model_dump(mode="json")
        session.add(ExtractionProposal(**data))

    session.commit()

    return WorldImportResult(
        world_id=snapshot.world.id,
        imported_entities=len(snapshot.entities),
        imported_relationships=len(snapshot.relationships),
        imported_world_rules=len(snapshot.world_rules),
        imported_map_pins=len(snapshot.map_pins),
        imported_random_tables=len(snapshot.random_tables),
        imported_random_table_rows=len(snapshot.random_table_rows),
        imported_detective_board_nodes=len(snapshot.detective_board_nodes),
        imported_detective_board_connections=len(snapshot.detective_board_connections),
        imported_proposals=len(snapshot.proposals),
    )


def validate_snapshot(snapshot: WorldExport) -> None:
    if snapshot.metadata.schema_version != EXPORT_SCHEMA_VERSION:
        raise InvalidSnapshotError(
            f"Unsupported snapshot schema {snapshot.metadata.schema_version!r}; expected {EXPORT_SCHEMA_VERSION!r}"
        )

    world_id = snapshot.world.id
    entity_ids = [entity.id for entity in snapshot.entities]
    relationship_ids = [relationship.id for relationship in snapshot.relationships]
    rule_ids = [rule.id for rule in snapshot.world_rules]
    map_pin_ids = [pin.id for pin in snapshot.map_pins]
    random_table_ids = [table.id for table in snapshot.random_tables]
    random_table_row_ids = [row.id for row in snapshot.random_table_rows]
    detective_node_ids = [node.id for node in snapshot.detective_board_nodes]
    detective_connection_ids = [connection.id for connection in snapshot.detective_board_connections]
    proposal_ids = [proposal.id for proposal in snapshot.proposals]

    _ensure_unique(entity_ids, "entity ids")
    _ensure_unique(relationship_ids, "relationship ids")
    _ensure_unique(rule_ids, "world rule ids")
    _ensure_unique(map_pin_ids, "map pin ids")
    _ensure_unique(random_table_ids, "random table ids")
    _ensure_unique(random_table_row_ids, "random table row ids")
    _ensure_unique(detective_node_ids, "detective board node ids")
    _ensure_unique(detective_connection_ids, "detective board connection ids")
    _ensure_unique(proposal_ids, "proposal ids")

    entity_id_set = set(entity_ids)
    for entity in snapshot.entities:
        if entity.world_id != world_id:
            raise InvalidSnapshotError(f"Entity {entity.id!r} belongs to another world")

    for relationship in snapshot.relationships:
        if relationship.world_id != world_id:
            raise InvalidSnapshotError(f"Relationship {relationship.id!r} belongs to another world")
        if relationship.source_entity_id not in entity_id_set:
            raise InvalidSnapshotError(f"Relationship {relationship.id!r} has missing source entity")
        if relationship.target_entity_id not in entity_id_set:
            raise InvalidSnapshotError(f"Relationship {relationship.id!r} has missing target entity")

    for rule in snapshot.world_rules:
        if rule.world_id != world_id:
            raise InvalidSnapshotError(f"World rule {rule.id!r} belongs to another world")

    for pin in snapshot.map_pins:
        if pin.world_id != world_id:
            raise InvalidSnapshotError(f"Map pin {pin.id!r} belongs to another world")
        if pin.map_entity_id not in entity_id_set:
            raise InvalidSnapshotError(f"Map pin {pin.id!r} has missing map entity")
        if pin.linked_entity_id and pin.linked_entity_id not in entity_id_set:
            raise InvalidSnapshotError(f"Map pin {pin.id!r} has missing linked entity")

    random_table_id_set = set(random_table_ids)
    for table in snapshot.random_tables:
        if table.world_id != world_id:
            raise InvalidSnapshotError(f"Random table {table.id!r} belongs to another world")

    for row in snapshot.random_table_rows:
        if row.table_id not in random_table_id_set:
            raise InvalidSnapshotError(f"Random table row {row.id!r} has missing table")

    detective_node_id_set = set(detective_node_ids)
    for node in snapshot.detective_board_nodes:
        if node.world_id != world_id:
            raise InvalidSnapshotError(f"Detective board node {node.id!r} belongs to another world")
        if node.entity_id and node.entity_id not in entity_id_set:
            raise InvalidSnapshotError(f"Detective board node {node.id!r} has missing entity")

    for connection in snapshot.detective_board_connections:
        if connection.world_id != world_id:
            raise InvalidSnapshotError(f"Detective board connection {connection.id!r} belongs to another world")
        if connection.source_node_id not in detective_node_id_set:
            raise InvalidSnapshotError(f"Detective board connection {connection.id!r} has missing source node")
        if connection.target_node_id not in detective_node_id_set:
            raise InvalidSnapshotError(f"Detective board connection {connection.id!r} has missing target node")

    for proposal in snapshot.proposals:
        if proposal.world_id != world_id:
            raise InvalidSnapshotError(f"Proposal {proposal.id!r} belongs to another world")


def _ensure_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise InvalidSnapshotError(f"Snapshot contains duplicate {label}")
