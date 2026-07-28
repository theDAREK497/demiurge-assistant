from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from worldbuilder_core.models import EmbeddingJob
from worldbuilder_core.services.embedding_index import (
    EmbeddingConfigurationError,
    embedding_status,
    process_embedding_batch,
)
from worldbuilder_core.services.llm import LLMProviderError
from worldbuilder_core.services.llm_settings import get_llm_runtime_settings

LEASE_SECONDS = 900


def enqueue_embedding_job(session: Session, world_id: str, *, batch_size: int = 16) -> EmbeddingJob:
    runtime = get_llm_runtime_settings(session)
    if not runtime.embedding_model:
        raise EmbeddingConfigurationError("Configure an embedding model in LLM settings first")
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:world_id))"),
            {"world_id": world_id},
        )
    existing = session.scalar(
        select(EmbeddingJob)
        .where(EmbeddingJob.world_id == world_id, EmbeddingJob.status.in_(("queued", "running")))
        .order_by(EmbeddingJob.created_at.desc())
    )
    if existing is not None:
        return existing
    status = embedding_status(session, world_id)
    job = EmbeddingJob(
        world_id=world_id,
        model=runtime.embedding_model,
        status="completed" if status.pending_chunks == 0 else "queued",
        batch_size=batch_size,
        total_chunks=status.total_chunks,
        processed_chunks=status.embedded_chunks,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def claim_embedding_job(session: Session, worker_id: str) -> EmbeddingJob | None:
    now = datetime.now(UTC)
    stmt = (
        select(EmbeddingJob)
        .where(
            or_(
                EmbeddingJob.status == "queued",
                (EmbeddingJob.status == "running") & (EmbeddingJob.lease_expires_at < now),
            ),
            EmbeddingJob.attempts < EmbeddingJob.max_attempts,
        )
        .order_by(EmbeddingJob.created_at.asc())
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
    job.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    session.commit()
    session.refresh(job)
    return job


async def run_embedding_job_batch(session: Session, job_id: str, worker_id: str) -> EmbeddingJob:
    job = session.get(EmbeddingJob, job_id)
    if job is None:
        raise LookupError("Embedding job not found")
    if job.status != "running" or job.lease_owner != worker_id:
        raise LookupError("Embedding job lease is not owned by this worker")
    try:
        result = await process_embedding_batch(
            session,
            job.world_id,
            batch_size=job.batch_size,
            model_override=job.model,
        )
        job = session.get(EmbeddingJob, job_id)
        job.processed_chunks = min(
            result.status.embedded_chunks,
            max(job.total_chunks, result.status.total_chunks),
        )
        job.total_chunks = max(job.total_chunks, result.status.total_chunks)
        job.heartbeat_at = datetime.now(UTC)
        if result.processed_in_batch == 0 or result.status.pending_chunks == 0:
            job.status = "completed"
            job.lease_owner = None
            job.lease_expires_at = None
            job.error = None
        else:
            job.status = "queued"
            job.lease_owner = None
            job.lease_expires_at = None
        session.commit()
        session.refresh(job)
        return job
    except (LLMProviderError, EmbeddingConfigurationError) as exc:
        session.rollback()
        job = session.get(EmbeddingJob, job_id)
        job.attempts += 1
        job.status = "failed" if job.attempts >= job.max_attempts else "queued"
        job.error = str(exc)[:2_000]
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = datetime.now(UTC)
        session.commit()
        session.refresh(job)
        return job


def cancel_world_embedding_jobs(session: Session, world_id: str) -> None:
    jobs = session.scalars(
        select(EmbeddingJob).where(
            EmbeddingJob.world_id == world_id,
            EmbeddingJob.status.in_(("queued", "running")),
        )
    )
    for job in jobs:
        job.status = "cancelled"
        job.lease_owner = None
        job.lease_expires_at = None
    session.commit()


def worker_identity() -> str:
    return f"worker-{uuid4().hex[:12]}"
