from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from worldbuilder_core.models import ProposalStatus, VerificationStatus, ViewerRole
from worldbuilder_core.services.world_configuration import normalize_key

ChangeKind = Literal["created", "updated", "deleted", "published", "world_event", "correction", "retcon"]
ChangeSubjectType = Literal["world", "entity", "relationship", "proposal"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20_000)


class WorldUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20_000)


class WorldRead(ORMModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class WorldSnapshot(WorldRead):
    pass


class EntityBase(BaseModel):
    type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=100_000)
    aliases: list[str] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=100)
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.verified
    attributes: dict[str, Any] = Field(default_factory=dict, max_length=100)

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return normalize_key(value)


class EntityCreate(EntityBase):
    pass


class EntityUpdate(BaseModel):
    type: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=100_000)
    aliases: list[str] | None = Field(default=None, max_length=100)
    tags: list[str] | None = Field(default=None, max_length=100)
    is_secret: bool | None = None
    status: VerificationStatus | None = None
    attributes: dict[str, Any] | None = Field(default=None, max_length=100)

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        return normalize_key(value) if value is not None else None


class EntityRead(EntityBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class EntityDuplicateCandidate(BaseModel):
    left: EntityRead
    right: EntityRead
    score: float = Field(ge=0.0, le=1.0)
    confidence: Literal["strong", "possible", "ambiguous"]
    reasons: list[str]
    shared_relationship_names: list[str]


class EntityMergeRequest(EntityBase):
    primary_entity_id: str = Field(min_length=1, max_length=36)
    duplicate_entity_id: str = Field(min_length=1, max_length=36)


class EntityMergeResult(BaseModel):
    entity: EntityRead
    deleted_entity_id: str
    rewired_relationships: int = Field(ge=0)
    merged_relationships: int = Field(ge=0)
    removed_self_relationships: int = Field(ge=0)
    updated_references: int = Field(ge=0)


class EntitySnapshot(EntityRead):
    pass


class EntityRevisionRead(ORMModel):
    id: str
    world_id: str
    entity_id: str
    change_kind: str
    source_type: str
    source_id: str | None
    effective_at: str | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    change_note: str | None
    evidence: str | None
    confidence: float
    causal_change_ids: list[str]
    supersedes_revision_id: str | None
    is_secret: bool
    created_at: datetime
    updated_at: datetime


class EntityRevisionSnapshot(EntityRevisionRead):
    pass


class WorldChangeCreate(BaseModel):
    subject_type: ChangeSubjectType = "world"
    subject_id: str | None = Field(default=None, max_length=36)
    subject_name: str | None = Field(default=None, max_length=200)
    change_kind: ChangeKind = "world_event"
    summary: str = Field(min_length=1, max_length=10_000)
    effective_at: str | None = Field(default=None, max_length=120)
    evidence: str | None = Field(default=None, max_length=10_000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    causal_change_ids: list[str] = Field(default_factory=list, max_length=100)
    supersedes_change_id: str | None = Field(default=None, max_length=36)
    is_secret: bool = False

    @field_validator("causal_change_ids")
    @classmethod
    def validate_unique_causes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("causal_change_ids must be unique")
        return value


class WorldChangeUpdate(BaseModel):
    subject_type: ChangeSubjectType | None = None
    subject_id: str | None = Field(default=None, max_length=36)
    subject_name: str | None = Field(default=None, max_length=200)
    change_kind: ChangeKind | None = None
    summary: str | None = Field(default=None, min_length=1, max_length=10_000)
    effective_at: str | None = Field(default=None, max_length=120)
    evidence: str | None = Field(default=None, max_length=10_000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    causal_change_ids: list[str] | None = Field(default=None, max_length=100)
    supersedes_change_id: str | None = Field(default=None, max_length=36)
    is_secret: bool | None = None

    @field_validator("causal_change_ids")
    @classmethod
    def validate_unique_causes(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and len(value) != len(set(value)):
            raise ValueError("causal_change_ids must be unique")
        return value


class WorldChangeRead(ORMModel):
    id: str
    world_id: str
    subject_type: str
    subject_id: str | None
    subject_name: str | None
    change_kind: str
    source_type: str
    source_id: str | None
    summary: str
    effective_at: str | None
    evidence: str | None
    confidence: float
    causal_change_ids: list[str]
    supersedes_change_id: str | None
    is_secret: bool
    created_at: datetime
    updated_at: datetime


class WorldChangeSnapshot(WorldChangeRead):
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None


class EntityTypeDefinitionBase(BaseModel):
    key: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str | None = Field(default=None, max_length=500)

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        return normalize_key(value) if value else None


class EntityTypeDefinitionCreate(EntityTypeDefinitionBase):
    pass


class EntityTypeDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str | None = Field(default=None, max_length=500)
    position: int | None = Field(default=None, ge=0)


class EntityTypeDefinitionRead(ORMModel):
    id: str
    world_id: str
    key: str
    name: str
    color: str
    description: str | None
    is_builtin: bool
    position: int
    created_at: datetime
    updated_at: datetime


class EntityTypeDefinitionSnapshot(EntityTypeDefinitionRead):
    pass


class QuestStatusDefinitionBase(BaseModel):
    key: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str | None) -> str | None:
        return normalize_key(value) if value else None


class QuestStatusDefinitionCreate(QuestStatusDefinitionBase):
    pass


class QuestStatusDefinitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    position: int | None = Field(default=None, ge=0)


class QuestStatusDefinitionRead(ORMModel):
    id: str
    world_id: str
    key: str
    name: str
    color: str
    position: int
    created_at: datetime
    updated_at: datetime


class QuestStatusDefinitionSnapshot(QuestStatusDefinitionRead):
    pass


class RelationshipBase(BaseModel):
    source_entity_id: str
    target_entity_id: str
    type: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    valid_from: str | None = Field(default=None, max_length=120)
    valid_to: str | None = Field(default=None, max_length=120)
    evidence: str | None = Field(default=None, max_length=5_000)
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.verified
    attributes: dict[str, Any] = Field(default_factory=dict, max_length=100)


class RelationshipCreate(RelationshipBase):
    pass


class RelationshipUpdate(BaseModel):
    source_entity_id: str | None = None
    target_entity_id: str | None = None
    type: str | None = Field(default=None, min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    weight: float | None = Field(default=None, ge=0.0, le=10.0)
    valid_from: str | None = Field(default=None, max_length=120)
    valid_to: str | None = Field(default=None, max_length=120)
    evidence: str | None = Field(default=None, max_length=5_000)
    effective_at: str | None = Field(default=None, max_length=120)
    change_note: str | None = Field(default=None, max_length=500)
    is_secret: bool | None = None
    status: VerificationStatus | None = None
    attributes: dict[str, Any] | None = Field(default=None, max_length=100)


class RelationshipRead(RelationshipBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class RelationshipSnapshot(RelationshipRead):
    pass


class RelationshipRevisionRead(ORMModel):
    id: str
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    type: str
    effective_at: str | None
    weight: float
    confidence: float
    valid_from: str | None
    valid_to: str | None
    label: str | None
    description: str | None
    evidence: str | None
    change_note: str | None
    created_at: datetime


class WorldRuleBase(BaseModel):
    priority: int = Field(default=3, ge=1, le=5)
    condition: str = Field(min_length=1, max_length=50_000)
    effect: str = Field(min_length=1, max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    is_active: bool = True
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.verified


class WorldRuleCreate(WorldRuleBase):
    pass


class WorldRuleUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=1, le=5)
    condition: str | None = Field(default=None, min_length=1, max_length=50_000)
    effect: str | None = Field(default=None, min_length=1, max_length=50_000)
    tags: list[str] | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    is_secret: bool | None = None
    status: VerificationStatus | None = None


class WorldRuleRead(WorldRuleBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class WorldRuleSnapshot(WorldRuleRead):
    pass


class MapPinBase(BaseModel):
    map_entity_id: str
    linked_entity_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=50_000)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    is_secret: bool = False


class MapPinCreate(MapPinBase):
    pass


class MapPinUpdate(BaseModel):
    map_entity_id: str | None = None
    linked_entity_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=50_000)
    x: float | None = Field(default=None, ge=0.0, le=1.0)
    y: float | None = Field(default=None, ge=0.0, le=1.0)
    is_secret: bool | None = None


class MapPinRead(MapPinBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class MapPinSnapshot(MapPinRead):
    pass


class RandomTableRowBase(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    result: str = Field(min_length=1, max_length=50_000)
    weight: int = Field(default=1, ge=1, le=1000)
    is_secret: bool = False


class RandomTableRowCreate(RandomTableRowBase):
    pass


class RandomTableRowUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    result: str | None = Field(default=None, min_length=1, max_length=50_000)
    weight: int | None = Field(default=None, ge=1, le=1000)
    is_secret: bool | None = None


class RandomTableRowRead(RandomTableRowBase, ORMModel):
    id: str
    table_id: str
    created_at: datetime
    updated_at: datetime


class RandomTableRowSnapshot(RandomTableRowRead):
    pass


class RandomTableBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    is_secret: bool = False


class RandomTableCreate(RandomTableBase):
    pass


class RandomTableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    is_secret: bool | None = None


class RandomTableRead(RandomTableBase, ORMModel):
    id: str
    world_id: str
    rows: list[RandomTableRowRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RandomTableSnapshot(RandomTableRead):
    pass


class RandomTableRollRead(BaseModel):
    table_id: str
    row: RandomTableRowRead


class DetectiveBoardNodeBase(BaseModel):
    entity_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=50_000)
    evidence_url: str | None = Field(default=None, max_length=2_048)
    x: float = Field(default=0.5, ge=0.0, le=1.0)
    y: float = Field(default=0.5, ge=0.0, le=1.0)
    is_secret: bool = False


class DetectiveBoardNodeCreate(DetectiveBoardNodeBase):
    pass


class DetectiveBoardNodeUpdate(BaseModel):
    entity_id: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=50_000)
    evidence_url: str | None = Field(default=None, max_length=2_048)
    x: float | None = Field(default=None, ge=0.0, le=1.0)
    y: float | None = Field(default=None, ge=0.0, le=1.0)
    is_secret: bool | None = None


class DetectiveBoardNodeRead(DetectiveBoardNodeBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class DetectiveBoardNodeSnapshot(DetectiveBoardNodeRead):
    pass


class DetectiveBoardConnectionBase(BaseModel):
    source_node_id: str
    target_node_id: str
    label: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=50_000)
    is_secret: bool = False


class DetectiveBoardConnectionCreate(DetectiveBoardConnectionBase):
    pass


class DetectiveBoardConnectionUpdate(BaseModel):
    source_node_id: str | None = None
    target_node_id: str | None = None
    label: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=50_000)
    is_secret: bool | None = None


class DetectiveBoardConnectionRead(DetectiveBoardConnectionBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class DetectiveBoardConnectionSnapshot(DetectiveBoardConnectionRead):
    pass


class DetectiveBoardRead(BaseModel):
    nodes: list[DetectiveBoardNodeRead] = Field(default_factory=list)
    connections: list[DetectiveBoardConnectionRead] = Field(default_factory=list)


class DetectiveBoardGenerateRequest(BaseModel):
    output_language: Literal["ru", "en"] = "ru"
    model: str | None = None
    max_nodes: int = Field(default=12, ge=3, le=24)


class ExportMetadata(BaseModel):
    schema_version: str
    app_version: str
    exported_at: datetime


class WorldExport(BaseModel):
    metadata: ExportMetadata
    world: WorldSnapshot
    entities: list[EntitySnapshot] = Field(default_factory=list)
    relationships: list[RelationshipSnapshot] = Field(default_factory=list)
    world_rules: list[WorldRuleSnapshot] = Field(default_factory=list)
    map_pins: list[MapPinSnapshot] = Field(default_factory=list)
    random_tables: list[RandomTableSnapshot] = Field(default_factory=list)
    random_table_rows: list[RandomTableRowSnapshot] = Field(default_factory=list)
    detective_board_nodes: list[DetectiveBoardNodeSnapshot] = Field(default_factory=list)
    detective_board_connections: list[DetectiveBoardConnectionSnapshot] = Field(default_factory=list)
    proposals: list[ExtractionProposalSnapshot] = Field(default_factory=list)
    entity_types: list[EntityTypeDefinitionSnapshot] = Field(default_factory=list)
    quest_statuses: list[QuestStatusDefinitionSnapshot] = Field(default_factory=list)
    entity_revisions: list[EntityRevisionSnapshot] = Field(default_factory=list)
    world_changes: list[WorldChangeSnapshot] = Field(default_factory=list)


class WorldImportResult(BaseModel):
    world_id: str
    imported_entities: int
    imported_relationships: int
    imported_world_rules: int
    imported_map_pins: int = 0
    imported_random_tables: int = 0
    imported_random_table_rows: int = 0
    imported_detective_board_nodes: int = 0
    imported_detective_board_connections: int = 0
    imported_proposals: int = 0
    imported_entity_revisions: int = 0
    imported_world_changes: int = 0


LLMMessageRole = Literal["system", "user", "assistant"]
OutputLanguage = Literal["ru", "en"]


class LLMMessage(BaseModel):
    role: LLMMessageRole
    content: str = Field(min_length=1, max_length=100_000)


class LLMChatRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1, max_length=50)
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=1_000_000)
    reasoning_effort: Literal["none", "low", "medium", "high"] | None = None
    response_format: dict[str, Any] | None = None


class LLMUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMChatResponse(BaseModel):
    model: str
    message: LLMMessage
    finish_reason: str | None = None
    usage: LLMUsage | None = None


class LLMConfigRead(BaseModel):
    base_url: str
    default_model: str
    chat_model: str | None = None
    extractor_model: str | None = None
    summarizer_model: str | None = None
    critic_model: str | None = None
    embedding_model: str | None = None
    has_api_key: bool
    timeout_seconds: float
    max_entities_per_extract: int
    persisted: bool = False


class LLMConfigUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=2_048)
    default_model: str = Field(default="", max_length=200)
    chat_model: str | None = Field(default=None, max_length=200)
    extractor_model: str | None = Field(default=None, max_length=200)
    summarizer_model: str | None = Field(default=None, max_length=200)
    critic_model: str | None = Field(default=None, max_length=200)
    embedding_model: str | None = Field(default=None, max_length=200)
    api_key: str | None = Field(default=None, max_length=4_096)
    clear_api_key: bool = False
    timeout_seconds: float = Field(gt=0, le=600)
    max_entities_per_extract: int = Field(ge=1, le=50)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("base_url must be an HTTP or HTTPS URL")
        if parsed.username or parsed.password:
            raise ValueError("base_url must not contain credentials")
        return normalized


class WorldContextRead(BaseModel):
    world: WorldRead
    role: ViewerRole
    query: str | None
    entities: list[EntityRead] = Field(default_factory=list)
    relationships: list[RelationshipRead] = Field(default_factory=list)
    world_rules: list[WorldRuleRead] = Field(default_factory=list)
    random_tables: list[RandomTableRead] = Field(default_factory=list)
    document_chunks: list["KnowledgeChunkExcerpt"] = Field(default_factory=list)
    experience_changes: list[WorldChangeRead] = Field(default_factory=list)
    context_text: str


class KnowledgeDocumentRead(ORMModel):
    id: str
    world_id: str
    filename: str
    media_type: str
    sha256: str
    status: str
    is_secret: bool
    total_chars: int
    total_chunks: int
    processed_chunks: int
    duplicate_chunks: int
    error: str | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentProcessResult(BaseModel):
    document: KnowledgeDocumentRead
    processed_in_batch: int
    created_in_batch: int
    duplicates_in_batch: int


class KnowledgeChunkExcerpt(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    position: int
    heading: str | None = None
    content: str


class EmbeddingIndexStatus(BaseModel):
    world_id: str
    model: str | None
    total_chunks: int
    embedded_chunks: int
    pending_chunks: int
    dimensions: int | None = None


class EmbeddingBatchResult(BaseModel):
    status: EmbeddingIndexStatus
    processed_in_batch: int


class EmbeddingJobRead(ORMModel):
    id: str
    world_id: str
    model: str
    status: str
    batch_size: int
    total_chunks: int
    processed_chunks: int
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    retry_at: datetime | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class DocumentExtractionJobRead(ORMModel):
    id: str
    world_id: str
    document_id: str
    proposal_id: str | None
    status: str
    next_position: int
    total_chunks: int
    processed_chunks: int
    current_segment: int
    total_segments: int
    proposal_count: int
    output_language: str
    attempts: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    heartbeat_at: datetime | None
    retry_at: datetime | None
    pause_requested: bool
    error: str | None
    created_at: datetime
    updated_at: datetime


class WorldLLMChatRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1, max_length=50)
    role: ViewerRole = ViewerRole.master
    output_language: OutputLanguage = "ru"
    query: str | None = Field(default=None, max_length=2_000)
    max_entities: int = Field(default=12, ge=1, le=50)
    max_rules: int = Field(default=8, ge=0, le=25)
    max_relationships: int = Field(default=24, ge=0, le=100)
    save_to_wiki: bool = False
    max_extract_entities: int | None = Field(default=None, ge=1, le=50)
    model: str | None = Field(default=None, max_length=200)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0, le=1_000_000)


class WorldLLMChatResponse(BaseModel):
    context: WorldContextRead
    completion: LLMChatResponse
    proposal: ExtractionProposalRead | None = None
    wiki_save_error: str | None = None


class ExtractedEntityDraft(BaseModel):
    client_id: str | None = Field(default=None, min_length=1, max_length=80)
    match_entity_id: str | None = None
    source_excerpt: str | None = Field(default=None, max_length=240)
    type: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.proposed
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value: str) -> str:
        return normalize_key(value)


class ExtractedRelationshipDraft(BaseModel):
    source_entity_id: str | None = None
    source_client_id: str | None = Field(default=None, min_length=1, max_length=80)
    target_entity_id: str | None = None
    target_client_id: str | None = Field(default=None, min_length=1, max_length=80)
    source_excerpt: str | None = Field(default=None, max_length=240)
    type: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    description: str | None = None
    confidence: float = Field(default=0.65, ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    valid_from: str | None = Field(default=None, max_length=120)
    valid_to: str | None = Field(default=None, max_length=120)
    evidence: str | None = Field(default=None, max_length=5_000)
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.proposed
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_refs(self) -> "ExtractedRelationshipDraft":
        if bool(self.source_entity_id) == bool(self.source_client_id):
            raise ValueError("Provide exactly one source reference")
        if bool(self.target_entity_id) == bool(self.target_client_id):
            raise ValueError("Provide exactly one target reference")
        return self


class ExtractedWorldRuleDraft(BaseModel):
    priority: int = Field(default=3, ge=1, le=5)
    source_excerpt: str | None = Field(default=None, max_length=240)
    condition: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.proposed


class ExtractedRandomTableDraft(BaseModel):
    client_id: str = Field(min_length=1, max_length=80)
    source_excerpt: str | None = Field(default=None, max_length=240)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    is_secret: bool = False


class ExtractedRandomTableRowDraft(BaseModel):
    table_id: str | None = None
    table_client_id: str | None = Field(default=None, min_length=1, max_length=80)
    source_excerpt: str | None = Field(default=None, max_length=240)
    label: str | None = Field(default=None, max_length=200)
    result: str = Field(min_length=1)
    weight: int = Field(default=1, ge=1, le=1000)
    is_secret: bool = False

    @model_validator(mode="after")
    def validate_table_ref(self) -> "ExtractedRandomTableRowDraft":
        if bool(self.table_id) == bool(self.table_client_id):
            raise ValueError("Provide exactly one table reference")
        return self


class ExtractionPayload(BaseModel):
    # A document job can consolidate many bounded model responses into one review draft.
    # Per-request extraction limits remain small; these limits cover the reviewed aggregate.
    entities: list[ExtractedEntityDraft] = Field(default_factory=list, max_length=2_000)
    relationships: list[ExtractedRelationshipDraft] = Field(default_factory=list, max_length=5_000)
    world_rules: list[ExtractedWorldRuleDraft] = Field(default_factory=list, max_length=1_000)
    random_tables: list[ExtractedRandomTableDraft] = Field(default_factory=list, max_length=500)
    random_table_rows: list[ExtractedRandomTableRowDraft] = Field(default_factory=list, max_length=5_000)
    notes: list[str] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_client_ids(self) -> "ExtractionPayload":
        client_ids = [entity.client_id for entity in self.entities if entity.client_id]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("Entity client_id values must be unique")
        table_client_ids = [table.client_id for table in self.random_tables]
        if len(table_client_ids) != len(set(table_client_ids)):
            raise ValueError("Random table client_id values must be unique")
        return self


class ExtractionProposalCreate(BaseModel):
    source_text: str = Field(min_length=1, max_length=200_000)
    payload: ExtractionPayload


class ExtractionProposalUpdate(BaseModel):
    source_text: str | None = Field(default=None, min_length=1, max_length=200_000)
    payload: ExtractionPayload


class ExtractionFromTextRequest(BaseModel):
    source_text: str = Field(min_length=1, max_length=200_000)
    intent_text: str | None = Field(default=None, min_length=1, max_length=20_000)
    role: ViewerRole = ViewerRole.master
    output_language: OutputLanguage = "ru"
    query: str | None = Field(default=None, max_length=2_000)
    model: str | None = Field(default=None, max_length=200)
    max_entities: int | None = Field(default=None, ge=1, le=50)


class AdventureGenerationRequest(BaseModel):
    premise: str = Field(min_length=1, max_length=4_000)
    scale: Literal["small", "medium", "large"] = "small"
    tone: str | None = Field(default=None, max_length=120)
    enabled_modules: list[str] = Field(
        default_factory=lambda: ["graph", "timeline", "quests", "randomTables", "detectiveBoard"],
        max_length=20,
    )
    role: ViewerRole = ViewerRole.master
    output_language: OutputLanguage = "ru"
    query: str | None = Field(default=None, max_length=2_000)
    model: str | None = Field(default=None, max_length=200)
    max_entities: int = Field(default=8, ge=4, le=50)


class ExtractionProposalRead(ORMModel):
    id: str
    world_id: str
    source_text: str
    payload: ExtractionPayload
    status: ProposalStatus
    error: str | None
    created_at: datetime
    updated_at: datetime


class ExtractionProposalSnapshot(ExtractionProposalRead):
    pass


class ProposalApplyResult(BaseModel):
    proposal_id: str
    created_entities: int = 0
    updated_entities: int = 0
    created_relationships: int = 0
    created_world_rules: int = 0
    created_random_tables: int = 0
    created_random_table_rows: int = 0


class ProposalItemSelection(BaseModel):
    entity_indices: list[int] | None = None
    relationship_indices: list[int] | None = None
    world_rule_indices: list[int] | None = None
    random_table_indices: list[int] | None = None
    random_table_row_indices: list[int] | None = None


class HealthRead(BaseModel):
    status: str = "ok"
    local_worker_enabled: bool = False


class RoleQuery(BaseModel):
    role: ViewerRole = ViewerRole.master


class AssetUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str = Field(min_length=1, max_length=7_000_000)
    content_type: str = Field(min_length=1, max_length=120)


class AssetUploadResponse(BaseModel):
    url: str
    filename: str
    size_bytes: int
