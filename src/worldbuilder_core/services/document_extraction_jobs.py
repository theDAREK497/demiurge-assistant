from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from worldbuilder_core.models import (
    DocumentChunkLink,
    DocumentExtractionJob,
    ExtractionProposal,
    KnowledgeChunk,
    KnowledgeDocument,
    ProposalStatus,
)
from worldbuilder_core.schemas import ExtractionPayload, ExtractionProposalCreate
from worldbuilder_core.services.embedding_jobs import LEASE_SECONDS
from worldbuilder_core.services.extraction import ExtractionParseError, extract_payload_with_llm
from worldbuilder_core.services.llm import LLMProviderError, build_llm_client
from worldbuilder_core.services.llm_settings import get_llm_runtime_settings
from worldbuilder_core.services.proposals import (
    ProposalValidationError,
    create_extraction_proposal,
    dedupe_extraction_payload,
    sanitize_extraction_payload_for_world,
)
from worldbuilder_core.services.retrieval import build_world_context

EXTRACTION_SEGMENT_CHARS = 2_200
DOCUMENT_SEGMENT_MAX_ENTITIES = 4
RETRY_BASE_SECONDS = 15
RETRY_MAX_SECONDS = 120


def enqueue_document_extraction(
    session: Session,
    document: KnowledgeDocument,
    *,
    output_language: str = "ru",
) -> DocumentExtractionJob:
    if document.status != "ready":
        raise ValueError("Document must finish chunking before AI extraction")
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:document_id))"),
            {"document_id": document.id},
        )
    existing = session.scalar(
        select(DocumentExtractionJob)
        .where(
            DocumentExtractionJob.document_id == document.id,
            DocumentExtractionJob.status.in_(("queued", "running")),
        )
        .order_by(DocumentExtractionJob.created_at.desc())
    )
    if existing is not None:
        return existing
    resumable = session.scalar(
        select(DocumentExtractionJob)
        .where(
            DocumentExtractionJob.document_id == document.id,
            DocumentExtractionJob.status == "failed",
            DocumentExtractionJob.processed_chunks < DocumentExtractionJob.total_chunks,
        )
        .order_by(DocumentExtractionJob.updated_at.desc())
    )
    if resumable is not None:
        resumable.status = "queued"
        resumable.attempts = 0
        resumable.error = None
        resumable.retry_at = None
        resumable.lease_owner = None
        resumable.lease_expires_at = None
        resumable.total_chunks = document.total_chunks
        session.commit()
        session.refresh(resumable)
        return resumable
    job = DocumentExtractionJob(
        world_id=document.world_id,
        document_id=document.id,
        total_chunks=document.total_chunks,
        output_language=output_language,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def claim_document_extraction_job(session: Session, worker_id: str) -> DocumentExtractionJob | None:
    now = datetime.now(UTC)
    stmt = (
        select(DocumentExtractionJob)
        .where(
            or_(
                DocumentExtractionJob.status == "queued",
                (DocumentExtractionJob.status == "running")
                & (DocumentExtractionJob.lease_expires_at < now),
            ),
            DocumentExtractionJob.attempts < DocumentExtractionJob.max_attempts,
            or_(
                DocumentExtractionJob.retry_at.is_(None),
                DocumentExtractionJob.retry_at <= now,
            ),
        )
        .order_by(DocumentExtractionJob.updated_at.asc())
        .limit(1)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    job = session.scalar(stmt)
    if job is None:
        return None
    job.status = "running"
    job.lease_owner = worker_id
    job.heartbeat_at = now
    job.retry_at = None
    job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    session.commit()
    session.refresh(job)
    return job


def pause_document_extraction_job(session: Session, job_id: str) -> DocumentExtractionJob:
    job = session.get(DocumentExtractionJob, job_id)
    if job is None:
        raise LookupError("Document extraction job not found")
    if job.status not in {"queued", "running", "paused"}:
        raise ValueError("Only an active extraction job can be paused")
    job.pause_requested = True
    if job.status == "queued":
        job.status = "paused"
        job.retry_at = None
    session.commit()
    session.refresh(job)
    return job


def resume_document_extraction_job(session: Session, job_id: str) -> DocumentExtractionJob:
    job = session.get(DocumentExtractionJob, job_id)
    if job is None:
        raise LookupError("Document extraction job not found")
    if job.status != "paused":
        raise ValueError("Only a paused extraction job can be resumed")
    job.pause_requested = False
    job.status = "queued"
    job.attempts = 0
    job.error = None
    job.retry_at = None
    session.commit()
    session.refresh(job)
    return job


async def run_document_extraction_batch(
    session: Session,
    job_id: str,
    worker_id: str,
) -> DocumentExtractionJob:
    job = session.get(DocumentExtractionJob, job_id)
    if job is None or job.status != "running" or job.lease_owner != worker_id:
        raise LookupError("Document extraction job lease is not owned by this worker")
    try:
        row = session.execute(
            select(DocumentChunkLink, KnowledgeChunk)
            .join(KnowledgeChunk, KnowledgeChunk.id == DocumentChunkLink.chunk_id)
            .where(
                DocumentChunkLink.document_id == job.document_id,
                DocumentChunkLink.position == job.next_position,
            )
        ).first()
        if row is None:
            return _finish_job(session, job)
        _, chunk = row
        document = session.get(KnowledgeDocument, job.document_id)
        if document is None:
            raise ValueError("Source document no longer exists")
        runtime = get_llm_runtime_settings(session)
        context = build_world_context(
            session,
            job.world_id,
            query=chunk.content[:1_000],
            max_entities=runtime.max_entities_per_extract,
            max_document_chunks=0,
        )
        client = build_llm_client(runtime, default_model=runtime.model_for("extractor"))
        segments = _split_for_extraction(chunk.content)
        segment_payloads, completed_segments = _restore_segment_progress(job, len(segments))
        _save_segment_progress(
            session,
            job,
            current=completed_segments,
            total=len(segments),
            partial_payloads=segment_payloads,
        )
        for segment_index in range(completed_segments, len(segments)):
            segment_payloads.append(
                await extract_payload_with_llm(
                    llm_client=client,
                    source_text=segments[segment_index],
                    context_text=context.context_text,
                    max_entities=min(runtime.max_entities_per_extract, DOCUMENT_SEGMENT_MAX_ENTITIES),
                    output_language=job.output_language,
                    model=runtime.model_for("extractor"),
                    truncate_excess_entities=True,
                    structured_output=True,
                    max_output_tokens=1_280,
                    intent_text=(
                        "Extract only explicit world objects and structures present in this source segment. "
                        "Do not invent missing content."
                    ),
                )
            )
            _save_segment_progress(
                session,
                job,
                current=segment_index + 1,
                total=len(segments),
                partial_payloads=segment_payloads,
            )
            if _pause_requested(session, job.id):
                job.status = "paused"
                job.lease_owner = None
                job.lease_expires_at = None
                session.commit()
                session.refresh(job)
                return job
        payload = _merge_segment_payloads(segment_payloads)
        payload = sanitize_extraction_payload_for_world(session, job.world_id, payload)
        if document.is_secret:
            payload = _apply_source_secrecy(payload)
        if _has_payload(payload):
            job.proposal_id, created = _merge_into_proposal(session, job, chunk.content, payload)
            if created:
                job.proposal_count += 1
        job.next_position += 1
        job.processed_chunks += 1
        job.current_segment = 0
        job.total_segments = 0
        job.partial_payloads = []
        job.attempts = 0
        job.error = None
        job.retry_at = None
        job.heartbeat_at = datetime.now(UTC)
        job.lease_owner = None
        job.lease_expires_at = None
        pause_requested = _pause_requested(session, job.id)
        if job.processed_chunks >= job.total_chunks:
            job.status = "completed"
            job.pause_requested = False
        else:
            job.status = "paused" if pause_requested else "queued"
        session.commit()
        session.refresh(job)
        return job
    except (LLMProviderError, ExtractionParseError, ProposalValidationError, ValueError) as exc:
        session.rollback()
        job = session.get(DocumentExtractionJob, job_id)
        job.attempts += 1
        job.status = (
            "paused"
            if job.pause_requested
            else "failed" if job.attempts >= job.max_attempts else "queued"
        )
        job.error = str(exc)[:2_000]
        if job.status == "queued":
            retry_seconds = min(RETRY_BASE_SECONDS * (2 ** (job.attempts - 1)), RETRY_MAX_SECONDS)
            job.retry_at = datetime.now(UTC) + timedelta(seconds=retry_seconds)
        else:
            job.retry_at = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = datetime.now(UTC)
        session.commit()
        session.refresh(job)
        return job


def _pause_requested(session: Session, job_id: str) -> bool:
    return bool(
        session.scalar(
            select(DocumentExtractionJob.pause_requested).where(DocumentExtractionJob.id == job_id)
        )
    )


def _save_segment_progress(
    session: Session,
    job: DocumentExtractionJob,
    *,
    current: int,
    total: int,
    partial_payloads: list[ExtractionPayload],
) -> None:
    now = datetime.now(UTC)
    job.current_segment = current
    job.total_segments = total
    job.partial_payloads = [payload.model_dump(mode="json") for payload in partial_payloads]
    job.heartbeat_at = now
    job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    session.commit()


def _restore_segment_progress(
    job: DocumentExtractionJob,
    total_segments: int,
) -> tuple[list[ExtractionPayload], int]:
    if job.total_segments != total_segments or job.current_segment != len(job.partial_payloads or []):
        return [], 0
    try:
        payloads = [ExtractionPayload.model_validate(payload) for payload in job.partial_payloads]
    except (TypeError, ValueError):
        return [], 0
    return payloads, min(job.current_segment, total_segments)


def _merge_into_proposal(
    session: Session,
    job: DocumentExtractionJob,
    source_text: str,
    incoming: ExtractionPayload,
) -> tuple[str, bool]:
    proposal = session.get(ExtractionProposal, job.proposal_id) if job.proposal_id else None
    if proposal is not None and proposal.status == ProposalStatus.pending:
        current = ExtractionPayload.model_validate(proposal.payload)
        combined_source = f"{proposal.source_text}\n\n--- SOURCE CHUNK ---\n\n{source_text}"
        combined_data = {
            "entities": [*current.entities, *incoming.entities],
            "relationships": [*current.relationships, *incoming.relationships],
            "world_rules": [*current.world_rules, *incoming.world_rules],
            "random_tables": [*current.random_tables, *incoming.random_tables],
            "random_table_rows": [*current.random_table_rows, *incoming.random_table_rows],
            "notes": [*current.notes, *incoming.notes],
        }
        if len(combined_source) <= 200_000 and all(
            len(combined_data[key]) <= limit
            for key, limit in {
                "entities": 50,
                "relationships": 100,
                "world_rules": 25,
                "random_tables": 25,
                "random_table_rows": 100,
                "notes": 25,
            }.items()
        ):
            merged = dedupe_extraction_payload(ExtractionPayload.model_construct(**combined_data))
            merged = ExtractionPayload.model_validate(merged.model_dump(mode="json"))
            proposal.source_text = combined_source
            proposal.payload = merged.model_dump(mode="json")
            session.flush()
            return proposal.id, False
    proposal = create_extraction_proposal(
        session,
        job.world_id,
        ExtractionProposalCreate(source_text=source_text, payload=incoming),
        commit=False,
    )
    return proposal.id, True


def _finish_job(session: Session, job: DocumentExtractionJob) -> DocumentExtractionJob:
    job.status = "completed"
    job.retry_at = None
    job.lease_owner = None
    job.lease_expires_at = None
    session.commit()
    session.refresh(job)
    return job


def _has_payload(payload: ExtractionPayload) -> bool:
    return any(
        (
            payload.entities,
            payload.relationships,
            payload.world_rules,
            payload.random_tables,
            payload.random_table_rows,
            payload.notes,
        )
    )


def _split_for_extraction(text_value: str, limit: int = EXTRACTION_SEGMENT_CHARS) -> list[str]:
    if len(text_value) <= limit:
        return [text_value]
    segments = []
    remaining = text_value.strip()
    while len(remaining) > limit:
        split_at = max(
            remaining.rfind("\n\n", 0, limit),
            remaining.rfind(". ", 0, limit),
            remaining.rfind(" ", 0, limit),
        )
        if split_at < limit // 2:
            split_at = limit
        elif remaining[split_at : split_at + 2] == ". ":
            split_at += 1
        segment = remaining[:split_at].strip()
        if segment:
            segments.append(segment)
        remaining = remaining[split_at:].strip()
    if remaining:
        segments.append(remaining)
    return segments


def _merge_segment_payloads(payloads: list[ExtractionPayload]) -> ExtractionPayload:
    if not payloads:
        return ExtractionPayload()
    namespaced = [
        _namespace_segment_references(payload, segment_index)
        for segment_index, payload in enumerate(payloads)
    ]
    combined = ExtractionPayload.model_construct(
        entities=[item for payload in namespaced for item in payload.entities][:50],
        relationships=[item for payload in namespaced for item in payload.relationships][:100],
        world_rules=[item for payload in namespaced for item in payload.world_rules][:25],
        random_tables=[item for payload in namespaced for item in payload.random_tables][:25],
        random_table_rows=[item for payload in namespaced for item in payload.random_table_rows][:100],
        notes=[item for payload in namespaced for item in payload.notes][:25],
    )
    return dedupe_extraction_payload(combined)


def _namespace_segment_references(payload: ExtractionPayload, segment_index: int) -> ExtractionPayload:
    prefix = f"s{segment_index + 1}-"
    entity_ids = {
        entity.client_id: f"{prefix}{entity.client_id}"[:80]
        for entity in payload.entities
        if entity.client_id
    }
    table_ids = {
        table.client_id: f"{prefix}{table.client_id}"[:80]
        for table in payload.random_tables
    }
    return payload.model_copy(
        update={
            "entities": [
                entity.model_copy(update={"client_id": entity_ids[entity.client_id]})
                if entity.client_id
                else entity
                for entity in payload.entities
            ],
            "relationships": [
                relationship.model_copy(
                    update={
                        "source_client_id": entity_ids.get(
                            relationship.source_client_id,
                            relationship.source_client_id,
                        ),
                        "target_client_id": entity_ids.get(
                            relationship.target_client_id,
                            relationship.target_client_id,
                        ),
                    }
                )
                for relationship in payload.relationships
            ],
            "random_tables": [
                table.model_copy(update={"client_id": table_ids[table.client_id]})
                for table in payload.random_tables
            ],
            "random_table_rows": [
                row.model_copy(
                    update={
                        "table_client_id": table_ids.get(row.table_client_id, row.table_client_id),
                    }
                )
                if row.table_client_id
                else row
                for row in payload.random_table_rows
            ],
        }
    )


def _apply_source_secrecy(payload: ExtractionPayload) -> ExtractionPayload:
    return payload.model_copy(
        update={
            "entities": [item.model_copy(update={"is_secret": True}) for item in payload.entities],
            "relationships": [
                item.model_copy(update={"is_secret": True}) for item in payload.relationships
            ],
            "world_rules": [
                item.model_copy(update={"is_secret": True}) for item in payload.world_rules
            ],
            "random_tables": [
                item.model_copy(update={"is_secret": True}) for item in payload.random_tables
            ],
            "random_table_rows": [
                item.model_copy(update={"is_secret": True}) for item in payload.random_table_rows
            ],
        }
    )
