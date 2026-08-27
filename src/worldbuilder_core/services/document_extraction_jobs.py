from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from worldbuilder_core.models import (
    DocumentChunkLink,
    DocumentExtractionJob,
    KnowledgeChunk,
    KnowledgeDocument,
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
OVERLAP_SEARCH_CHARS = 2_000
MIN_REPEATED_OVERLAP_CHARS = 80


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
        previous_chunk = _document_chunk_at_position(session, job.document_id, job.next_position - 1)
        source_text, repeated_context = _split_repeated_chunk_overlap(
            previous_chunk.content if previous_chunk is not None else "",
            chunk.content,
        )
        document = session.get(KnowledgeDocument, job.document_id)
        if document is None:
            raise ValueError("Source document no longer exists")
        runtime = get_llm_runtime_settings(session)
        context = build_world_context(
            session,
            job.world_id,
            query=(source_text or chunk.content)[:1_000],
            max_entities=runtime.max_entities_per_extract,
            max_document_chunks=0,
        )
        context_text = context.context_text
        if repeated_context:
            context_text = (
                f"{context_text}\n\n"
                "Previous chunk context (reference only; do not extract it again):\n"
                f"{repeated_context[-800:]}"
            ).strip()
        client = build_llm_client(runtime, default_model=runtime.model_for("extractor"))
        segments = _split_for_extraction(source_text) if source_text else []
        segment_payloads, completed_segments = _restore_segment_progress(job, len(segments))
        _save_segment_progress(
            session,
            job,
            current=completed_segments,
            total=len(segments),
            partial_payloads=segment_payloads,
        )
        for segment_index in range(completed_segments, len(segments)):
            segment_source = segments[segment_index]
            extracted = await extract_payload_with_llm(
                llm_client=client,
                source_text=segment_source,
                context_text=context_text,
                max_entities=min(runtime.max_entities_per_extract, DOCUMENT_SEGMENT_MAX_ENTITIES),
                output_language=job.output_language,
                model=runtime.model_for("extractor"),
                truncate_excess_entities=True,
                structured_output=True,
                max_output_tokens=1_280,
                intent_text=(
                    "Extract only explicit, reusable world facts present in this source segment. "
                    "Ignore literary decoration, ordinary scene actions, and document navigation or front matter. "
                    "Return an empty payload when the segment contains no canon facts. Do not invent missing content. "
                    "Never create an entity from a truncated boundary token or a grammatical status word."
                ),
            )
            segment_payloads.append(_drop_fragmentary_boundary_entities(extracted, segment_source))
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
            job.proposal_id, created = _merge_into_proposal(session, job, source_text, payload)
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
    incoming = _namespace_payload_references(incoming, f"c{job.next_position + 1}-")
    previous_proposal_id = job.proposal_id
    proposal = create_extraction_proposal(
        session,
        job.world_id,
        ExtractionProposalCreate(source_text=source_text, payload=incoming),
        commit=False,
    )
    return proposal.id, proposal.id != previous_proposal_id


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


def _document_chunk_at_position(
    session: Session,
    document_id: str,
    position: int,
) -> KnowledgeChunk | None:
    if position < 0:
        return None
    return session.scalar(
        select(KnowledgeChunk)
        .join(DocumentChunkLink, DocumentChunkLink.chunk_id == KnowledgeChunk.id)
        .where(
            DocumentChunkLink.document_id == document_id,
            DocumentChunkLink.position == position,
        )
    )


def _split_repeated_chunk_overlap(previous: str, current: str) -> tuple[str, str]:
    previous = previous.rstrip()
    current = current.lstrip()
    if len(previous) < MIN_REPEATED_OVERLAP_CHARS or len(current) < MIN_REPEATED_OVERLAP_CHARS:
        return current, ""

    needle = current[:48]
    search_start = max(0, len(previous) - OVERLAP_SEARCH_CHARS)
    search_end = len(previous)
    while search_end > search_start:
        match_start = previous.rfind(needle, search_start, search_end)
        if match_start < 0:
            break
        repeated = previous[match_start:]
        if len(repeated) >= MIN_REPEATED_OVERLAP_CHARS and current.startswith(repeated):
            return current[len(repeated) :].lstrip(), repeated
        search_end = match_start
    return current, ""


def _drop_fragmentary_boundary_entities(
    payload: ExtractionPayload,
    source_text: str,
) -> ExtractionPayload:
    stripped_source = source_text.lstrip()
    if not stripped_source or not stripped_source[0].islower():
        return payload

    removed_client_ids = {
        entity.client_id
        for entity in payload.entities
        if entity.client_id and _entity_looks_like_boundary_fragment(entity.name, entity.source_excerpt, stripped_source)
    }
    if not removed_client_ids:
        return payload
    return payload.model_copy(
        update={
            "entities": [entity for entity in payload.entities if entity.client_id not in removed_client_ids],
            "relationships": [
                relationship
                for relationship in payload.relationships
                if relationship.source_client_id not in removed_client_ids
                and relationship.target_client_id not in removed_client_ids
            ],
        }
    )


def _entity_looks_like_boundary_fragment(
    name: str,
    source_excerpt: str | None,
    source_text: str,
) -> bool:
    normalized_name = " ".join(re.findall(r"[\w-]+", name.casefold(), flags=re.UNICODE))
    excerpt_tokens = re.findall(r"[\w-]+", (source_excerpt or "").casefold(), flags=re.UNICODE)
    if not normalized_name or len(normalized_name) > 20 or excerpt_tokens != [normalized_name]:
        return False
    matches = list(
        re.finditer(
            rf"(?<!\w){re.escape(normalized_name)}(?!\w)",
            source_text.casefold(),
            flags=re.UNICODE,
        )
    )
    return len(matches) == 1 and matches[0].start() <= 2


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
    return _namespace_payload_references(payload, f"s{segment_index + 1}-")


def _namespace_payload_references(payload: ExtractionPayload, prefix: str) -> ExtractionPayload:
    entity_ids = _build_namespaced_ids(
        [entity.client_id for entity in payload.entities if entity.client_id],
        prefix,
    )
    table_ids = _build_namespaced_ids(
        [table.client_id for table in payload.random_tables],
        prefix,
    )
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


def _build_namespaced_ids(client_ids: list[str], prefix: str) -> dict[str, str]:
    namespaced: dict[str, str] = {}
    used: set[str] = set()
    for client_id in client_ids:
        base = f"{prefix}{client_id}"
        candidate = base[:80]
        suffix = 2
        while candidate in used:
            marker = f"-{suffix}"
            candidate = f"{base[: 80 - len(marker)]}{marker}"
            suffix += 1
        namespaced[client_id] = candidate
        used.add(candidate)
    return namespaced


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
