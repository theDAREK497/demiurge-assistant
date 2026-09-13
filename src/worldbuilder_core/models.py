from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from worldbuilder_core.config import get_settings
from worldbuilder_core.db import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # Local source check before optional production dependencies are installed.
    Vector = None


def embedding_column_type():
    if get_settings().database_url.startswith("postgresql"):
        if Vector is None:
            raise RuntimeError("PostgreSQL mode requires the pgvector package")
        return Vector(get_settings().embedding_dimensions)
    return JSON


def uuid_str() -> str:
    return str(uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class EntityType(StrEnum):
    character = "character"
    location = "location"
    faction = "faction"
    item = "item"
    event = "event"
    clue = "clue"
    concept = "concept"


class VerificationStatus(StrEnum):
    verified = "verified"
    proposed = "proposed"
    unknown = "unknown"
    rejected = "rejected"


class ViewerRole(StrEnum):
    master = "master"
    player = "player"


class ProposalStatus(StrEnum):
    pending = "pending"
    applied = "applied"
    rejected = "rejected"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


class World(TimestampMixin, Base):
    __tablename__ = "worlds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    entities: Mapped[list["Entity"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    relationships: Mapped[list["Relationship"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    rules: Mapped[list["WorldRule"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    map_pins: Mapped[list["MapPin"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    random_tables: Mapped[list["RandomTable"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    detective_nodes: Mapped[list["DetectiveBoardNode"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    detective_connections: Mapped[list["DetectiveBoardConnection"]] = relationship(
        back_populates="world",
        cascade="all, delete-orphan",
    )
    proposals: Mapped[list["ExtractionProposal"]] = relationship(back_populates="world", cascade="all, delete-orphan")
    entity_types: Mapped[list["EntityTypeDefinition"]] = relationship(
        back_populates="world",
        cascade="all, delete-orphan",
    )
    quest_statuses: Mapped[list["QuestStatusDefinition"]] = relationship(
        back_populates="world",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="world",
        cascade="all, delete-orphan",
    )
    knowledge_chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="world",
        cascade="all, delete-orphan",
    )
    entity_revisions: Mapped[list["EntityRevision"]] = relationship(
        back_populates="world",
        cascade="all, delete-orphan",
    )
    changes: Mapped[list["WorldChange"]] = relationship(
        back_populates="world",
        cascade="all, delete-orphan",
    )


class EntityTypeDefinition(TimestampMixin, Base):
    __tablename__ = "entity_type_definitions"
    __table_args__ = (UniqueConstraint("world_id", "key", name="uq_entity_type_world_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    world: Mapped[World] = relationship(back_populates="entity_types")


class QuestStatusDefinition(TimestampMixin, Base):
    __tablename__ = "quest_status_definitions"
    __table_args__ = (UniqueConstraint("world_id", "key", name="uq_quest_status_world_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    world: Mapped[World] = relationship(back_populates="quest_statuses")


class Entity(TimestampMixin, Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("world_id", "type", "name", name="uq_entity_world_type_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus),
        default=VerificationStatus.verified,
        index=True,
        nullable=False,
    )
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    world: Mapped[World] = relationship(back_populates="entities")


class EntityRevision(TimestampMixin, Base):
    __tablename__ = "entity_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    change_kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    effective_at: Mapped[str | None] = mapped_column(String(120), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    causal_change_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    supersedes_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    world: Mapped[World] = relationship(back_populates="entity_revisions")


class WorldChange(TimestampMixin, Base):
    __tablename__ = "world_changes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    subject_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    change_kind: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    effective_at: Mapped[str | None] = mapped_column(String(120), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    causal_change_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    supersedes_change_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    world: Mapped[World] = relationship(back_populates="changes")


class Relationship(TimestampMixin, Base):
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False)
    target_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    valid_from: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valid_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus),
        default=VerificationStatus.verified,
        index=True,
        nullable=False,
    )
    attributes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    world: Mapped[World] = relationship(back_populates="relationships")
    source_entity: Mapped[Entity] = relationship(foreign_keys=[source_entity_id])
    target_entity: Mapped[Entity] = relationship(foreign_keys=[target_entity_id])
    revisions: Mapped[list["RelationshipRevision"]] = relationship(
        back_populates="relationship",
        cascade="all, delete-orphan",
        order_by="RelationshipRevision.created_at.desc()",
    )


class RelationshipRevision(TimestampMixin, Base):
    __tablename__ = "relationship_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("relationships.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    effective_at: Mapped[str | None] = mapped_column(String(120), nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    valid_from: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valid_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    relationship: Mapped[Relationship] = relationship(back_populates="revisions")


class WorldRule(TimestampMixin, Base):
    __tablename__ = "world_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    effect: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus),
        default=VerificationStatus.verified,
        index=True,
        nullable=False,
    )

    world: Mapped[World] = relationship(back_populates="rules")


class MapPin(TimestampMixin, Base):
    __tablename__ = "map_pins"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    map_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True, nullable=False)
    linked_entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    world: Mapped[World] = relationship(back_populates="map_pins")
    map_entity: Mapped[Entity] = relationship(foreign_keys=[map_entity_id])
    linked_entity: Mapped[Entity | None] = relationship(foreign_keys=[linked_entity_id])


class RandomTable(TimestampMixin, Base):
    __tablename__ = "random_tables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    world: Mapped[World] = relationship(back_populates="random_tables")
    rows: Mapped[list["RandomTableRow"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="RandomTableRow.created_at",
    )


class RandomTableRow(TimestampMixin, Base):
    __tablename__ = "random_table_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    table_id: Mapped[str] = mapped_column(ForeignKey("random_tables.id", ondelete="CASCADE"), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    table: Mapped[RandomTable] = relationship(back_populates="rows")


class DetectiveBoardNode(TimestampMixin, Base):
    __tablename__ = "detective_board_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id", ondelete="SET NULL"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    x: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    y: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    world: Mapped[World] = relationship(back_populates="detective_nodes")
    entity: Mapped[Entity | None] = relationship(foreign_keys=[entity_id])


class DetectiveBoardConnection(TimestampMixin, Base):
    __tablename__ = "detective_board_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("detective_board_nodes.id", ondelete="CASCADE"), index=True, nullable=False)
    target_node_id: Mapped[str] = mapped_column(ForeignKey("detective_board_nodes.id", ondelete="CASCADE"), index=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    world: Mapped[World] = relationship(back_populates="detective_connections")
    source_node: Mapped[DetectiveBoardNode] = relationship(foreign_keys=[source_node_id])
    target_node: Mapped[DetectiveBoardNode] = relationship(foreign_keys=[target_node_id])


class ExtractionProposal(TimestampMixin, Base):
    __tablename__ = "extraction_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus),
        default=ProposalStatus.pending,
        index=True,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    world: Mapped[World] = relationship(back_populates="proposals")


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (UniqueConstraint("world_id", "sha256", name="uq_knowledge_document_world_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_chars: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    world: Mapped[World] = relationship(back_populates="documents")
    chunk_links: Mapped[list["DocumentChunkLink"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunkLink.position",
    )


class KnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("world_id", "content_hash", name="uq_knowledge_chunk_world_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(16), nullable=False)
    fingerprint_band_0: Mapped[str] = mapped_column(String(4), index=True, nullable=False)
    fingerprint_band_1: Mapped[str] = mapped_column(String(4), index=True, nullable=False)
    fingerprint_band_2: Mapped[str] = mapped_column(String(4), index=True, nullable=False)
    fingerprint_band_3: Mapped[str] = mapped_column(String(4), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(embedding_column_type(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)

    world: Mapped[World] = relationship(back_populates="knowledge_chunks")
    document_links: Mapped[list["DocumentChunkLink"]] = relationship(back_populates="chunk")


class DocumentChunkLink(TimestampMixin, Base):
    __tablename__ = "document_chunk_links"
    __table_args__ = (UniqueConstraint("document_id", "position", name="uq_document_chunk_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str | None] = mapped_column(String(500), nullable=True)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunk_links")
    chunk: Mapped[KnowledgeChunk] = relationship(back_populates="document_links")


class EmbeddingJob(TimestampMixin, Base):
    __tablename__ = "embedding_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True, nullable=False)
    batch_size: Mapped[int] = mapped_column(Integer, default=16, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentExtractionJob(TimestampMixin, Base):
    __tablename__ = "document_extraction_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    proposal_id: Mapped[str | None] = mapped_column(
        ForeignKey("extraction_proposals.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True, nullable=False)
    next_position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_segment: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_segments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    partial_payloads: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    proposal_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_language: Mapped[str] = mapped_column(String(8), default="ru", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    pause_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
