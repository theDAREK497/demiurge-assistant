from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from worldbuilder_core.db import Base


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


class Entity(TimestampMixin, Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("world_id", "type", "name", name="uq_entity_world_type_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True, nullable=False)
    type: Mapped[EntityType] = mapped_column(SAEnum(EntityType), index=True, nullable=False)
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


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
