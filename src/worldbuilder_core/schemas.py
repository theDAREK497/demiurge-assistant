from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from worldbuilder_core.models import EntityType, ProposalStatus, VerificationStatus, ViewerRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class WorldUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class WorldRead(ORMModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class WorldSnapshot(WorldRead):
    pass


class EntityBase(BaseModel):
    type: EntityType
    name: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.verified
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntityCreate(EntityBase):
    pass


class EntityUpdate(BaseModel):
    type: EntityType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = None
    aliases: list[str] | None = None
    tags: list[str] | None = None
    is_secret: bool | None = None
    status: VerificationStatus | None = None
    attributes: dict[str, Any] | None = None


class EntityRead(EntityBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class EntitySnapshot(EntityRead):
    pass


class RelationshipBase(BaseModel):
    source_entity_id: str
    target_entity_id: str
    type: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    description: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.verified
    attributes: dict[str, Any] = Field(default_factory=dict)


class RelationshipCreate(RelationshipBase):
    pass


class RelationshipUpdate(BaseModel):
    source_entity_id: str | None = None
    target_entity_id: str | None = None
    type: str | None = Field(default=None, min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    description: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    is_secret: bool | None = None
    status: VerificationStatus | None = None
    attributes: dict[str, Any] | None = None


class RelationshipRead(RelationshipBase, ORMModel):
    id: str
    world_id: str
    created_at: datetime
    updated_at: datetime


class RelationshipSnapshot(RelationshipRead):
    pass


class WorldRuleBase(BaseModel):
    priority: int = Field(default=3, ge=1, le=5)
    condition: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.verified


class WorldRuleCreate(WorldRuleBase):
    pass


class WorldRuleUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=1, le=5)
    condition: str | None = Field(default=None, min_length=1)
    effect: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
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
    proposals: list[ExtractionProposalSnapshot] = Field(default_factory=list)


class WorldImportResult(BaseModel):
    world_id: str
    imported_entities: int
    imported_relationships: int
    imported_world_rules: int
    imported_proposals: int = 0


LLMMessageRole = Literal["system", "user", "assistant"]


class LLMMessage(BaseModel):
    role: LLMMessageRole
    content: str = Field(min_length=1)


class LLMChatRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1)
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)


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
    has_api_key: bool
    timeout_seconds: float
    max_entities_per_extract: int
    persisted: bool = False


class LLMConfigUpdate(BaseModel):
    base_url: str = Field(min_length=1)
    default_model: str = Field(min_length=1)
    chat_model: str | None = None
    extractor_model: str | None = None
    summarizer_model: str | None = None
    critic_model: str | None = None
    api_key: str | None = None
    clear_api_key: bool = False
    timeout_seconds: float = Field(gt=0)
    max_entities_per_extract: int = Field(ge=1, le=50)


class WorldContextRead(BaseModel):
    world: WorldRead
    role: ViewerRole
    query: str | None
    entities: list[EntityRead] = Field(default_factory=list)
    relationships: list[RelationshipRead] = Field(default_factory=list)
    world_rules: list[WorldRuleRead] = Field(default_factory=list)
    context_text: str


class WorldLLMChatRequest(BaseModel):
    messages: list[LLMMessage] = Field(min_length=1)
    role: ViewerRole = ViewerRole.master
    query: str | None = None
    max_entities: int = Field(default=12, ge=1, le=50)
    max_rules: int = Field(default=8, ge=0, le=25)
    max_relationships: int = Field(default=24, ge=0, le=100)
    save_to_wiki: bool = False
    max_extract_entities: int | None = Field(default=None, ge=1, le=50)
    model: str | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, gt=0)


class WorldLLMChatResponse(BaseModel):
    context: WorldContextRead
    completion: LLMChatResponse
    proposal: ExtractionProposalRead | None = None
    wiki_save_error: str | None = None


class ExtractedEntityDraft(BaseModel):
    client_id: str | None = Field(default=None, min_length=1, max_length=80)
    match_entity_id: str | None = None
    type: EntityType
    name: str = Field(min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.proposed
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExtractedRelationshipDraft(BaseModel):
    source_entity_id: str | None = None
    source_client_id: str | None = Field(default=None, min_length=1, max_length=80)
    target_entity_id: str | None = None
    target_client_id: str | None = Field(default=None, min_length=1, max_length=80)
    type: str = Field(min_length=1, max_length=80)
    label: str | None = Field(default=None, max_length=200)
    description: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
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
    condition: str = Field(min_length=1)
    effect: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    is_secret: bool = False
    status: VerificationStatus = VerificationStatus.proposed


class ExtractionPayload(BaseModel):
    entities: list[ExtractedEntityDraft] = Field(default_factory=list, max_length=50)
    relationships: list[ExtractedRelationshipDraft] = Field(default_factory=list, max_length=100)
    world_rules: list[ExtractedWorldRuleDraft] = Field(default_factory=list, max_length=25)
    notes: list[str] = Field(default_factory=list, max_length=25)

    @model_validator(mode="after")
    def validate_client_ids(self) -> "ExtractionPayload":
        client_ids = [entity.client_id for entity in self.entities if entity.client_id]
        if len(client_ids) != len(set(client_ids)):
            raise ValueError("Entity client_id values must be unique")
        return self


class ExtractionProposalCreate(BaseModel):
    source_text: str = Field(min_length=1)
    payload: ExtractionPayload


class ExtractionFromTextRequest(BaseModel):
    source_text: str = Field(min_length=1)
    role: ViewerRole = ViewerRole.master
    query: str | None = None
    model: str | None = None
    max_entities: int | None = Field(default=None, ge=1, le=50)


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


class ProposalItemSelection(BaseModel):
    entity_indices: list[int] | None = None
    relationship_indices: list[int] | None = None
    world_rule_indices: list[int] | None = None


class HealthRead(BaseModel):
    status: str = "ok"


class RoleQuery(BaseModel):
    role: ViewerRole = ViewerRole.master


class AssetUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=240)
    content_base64: str = Field(min_length=1)
    content_type: str = Field(min_length=1, max_length=120)


class AssetUploadResponse(BaseModel):
    url: str
    filename: str
    size_bytes: int
