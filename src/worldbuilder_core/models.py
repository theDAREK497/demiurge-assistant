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
