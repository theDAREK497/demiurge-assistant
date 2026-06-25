from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from worldbuilder_core import __version__
from worldbuilder_core.models import Entity, ExtractionProposal, Relationship, World, WorldRule
from worldbuilder_core.schemas import (
    EntitySnapshot,
    ExtractionProposalSnapshot,
    ExportMetadata,
    RelationshipSnapshot,
    WorldExport,
    WorldImportResult,
    WorldRuleSnapshot,
    WorldSnapshot,
)

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

    return WorldExport(
        metadata=ExportMetadata(
            schema_version=EXPORT_SCHEMA_VERSION,
            app_version=__version__,
            exported_at=datetime.now(UTC),
        ),
        world=WorldSnapshot.model_validate(world),
        entities=[EntitySnapshot.model_validate(entity) for entity in entities],
        relationships=[RelationshipSnapshot.model_validate(relationship) for relationship in relationships],
        world_rules=[WorldRuleSnapshot.model_validate(rule) for rule in rules],
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

    for entity_data in snapshot.entities:
        session.add(Entity(**entity_data.model_dump()))
    session.flush()

    for relationship_data in snapshot.relationships:
        session.add(Relationship(**relationship_data.model_dump()))

    for rule_data in snapshot.world_rules:
        session.add(WorldRule(**rule_data.model_dump()))

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
    proposal_ids = [proposal.id for proposal in snapshot.proposals]

    _ensure_unique(entity_ids, "entity ids")
    _ensure_unique(relationship_ids, "relationship ids")
    _ensure_unique(rule_ids, "world rule ids")
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

    for proposal in snapshot.proposals:
        if proposal.world_id != world_id:
            raise InvalidSnapshotError(f"Proposal {proposal.id!r} belongs to another world")


def _ensure_unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise InvalidSnapshotError(f"Snapshot contains duplicate {label}")
