from datetime import UTC, datetime

from worldbuilder_core.models import Relationship, RelationshipRevision


def build_relationship_revision(
    relationship: Relationship,
    *,
    effective_at: str | None = None,
    change_note: str | None = None,
) -> RelationshipRevision:
    return RelationshipRevision(
        relationship_id=relationship.id,
        source_entity_id=relationship.source_entity_id,
        target_entity_id=relationship.target_entity_id,
        type=relationship.type,
        effective_at=effective_at or relationship.valid_from or datetime.now(UTC).isoformat(),
        weight=relationship.weight,
        confidence=relationship.confidence,
        valid_from=relationship.valid_from,
        valid_to=relationship.valid_to,
        label=relationship.label,
        description=relationship.description,
        evidence=relationship.evidence,
        change_note=change_note,
    )
