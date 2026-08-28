from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from worldbuilder_core.models import DocumentChunkLink, EmbeddingJob, KnowledgeChunk, KnowledgeDocument
from worldbuilder_core.config import get_settings
from worldbuilder_core.schemas import EmbeddingBatchResult, EmbeddingIndexStatus
from worldbuilder_core.services.llm import build_llm_client
from worldbuilder_core.services.llm_settings import get_llm_runtime_settings


class EmbeddingConfigurationError(Exception):
    pass


def embedding_status(session: Session, world_id: str, *, model_override: str | None = None) -> EmbeddingIndexStatus:
    runtime = get_llm_runtime_settings(session)
    model = model_override or runtime.embedding_model
    total = session.scalar(
        select(func.count(func.distinct(KnowledgeChunk.id)))
        .join(DocumentChunkLink, DocumentChunkLink.chunk_id == KnowledgeChunk.id)
        .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunkLink.document_id)
        .where(KnowledgeChunk.world_id == world_id, KnowledgeDocument.status == "ready")
    ) or 0
    embedded = 0
    dimensions = None
    if model:
        embedded = session.scalar(
            select(func.count(func.distinct(KnowledgeChunk.id)))
            .join(DocumentChunkLink, DocumentChunkLink.chunk_id == KnowledgeChunk.id)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunkLink.document_id)
            .where(
                KnowledgeChunk.world_id == world_id,
                KnowledgeDocument.status == "ready",
                KnowledgeChunk.embedding_model == model,
                KnowledgeChunk.embedding.is_not(None),
            )
        ) or 0
        sample = session.scalar(
            select(KnowledgeChunk.embedding).where(
                KnowledgeChunk.world_id == world_id,
                KnowledgeChunk.embedding_model == model,
                KnowledgeChunk.embedding.is_not(None),
            )
        )
        dimensions = len(sample) if isinstance(sample, list) else None
    return EmbeddingIndexStatus(
        world_id=world_id,
        model=model,
        total_chunks=total,
        embedded_chunks=embedded,
        pending_chunks=max(total - embedded, 0),
        dimensions=dimensions,
    )


async def process_embedding_batch(
    session: Session,
    world_id: str,
    *,
    batch_size: int = 16,
    model_override: str | None = None,
    job_id: str | None = None,
    worker_id: str | None = None,
) -> EmbeddingBatchResult:
    if (job_id is None) != (worker_id is None):
        raise ValueError("job_id and worker_id must be provided together")
    runtime = get_llm_runtime_settings(session)
    model = model_override or runtime.embedding_model
    if not model:
        raise EmbeddingConfigurationError("Configure an embedding model in LLM settings first")
    chunks = list(
        session.scalars(
            select(KnowledgeChunk)
            .join(DocumentChunkLink, DocumentChunkLink.chunk_id == KnowledgeChunk.id)
            .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunkLink.document_id)
            .where(
                KnowledgeChunk.world_id == world_id,
                KnowledgeDocument.status == "ready",
                or_(
                    KnowledgeChunk.embedding.is_(None),
                    KnowledgeChunk.embedding_model != model,
                    KnowledgeChunk.embedding_model.is_(None),
                ),
            )
            .distinct()
            .order_by(KnowledgeChunk.created_at.asc())
            .limit(batch_size)
        )
    )
    if not chunks:
        return EmbeddingBatchResult(
            status=embedding_status(session, world_id, model_override=model),
            processed_in_batch=0,
        )
    client = build_llm_client(runtime, default_model=model)
    _, vectors = await client.embeddings([chunk.content for chunk in chunks], model=model)
    actual_dimensions = len(vectors[0]) if vectors else 0
    existing_vector = session.scalar(
        select(KnowledgeChunk.embedding).where(
            KnowledgeChunk.world_id == world_id,
            KnowledgeChunk.embedding_model == model,
            KnowledgeChunk.embedding.is_not(None),
        )
    )
    existing_dimensions = len(existing_vector) if existing_vector is not None else None
    if existing_dimensions is not None and actual_dimensions != existing_dimensions:
        raise EmbeddingConfigurationError(
            "Embedding model dimension changed from "
            f"{existing_dimensions} to {actual_dimensions}. Clear and rebuild the semantic index."
        )
    expected_dimensions = get_settings().embedding_dimensions
    if (
        session.bind is not None
        and session.bind.dialect.name == "postgresql"
        and actual_dimensions != expected_dimensions
    ):
        raise EmbeddingConfigurationError(
            "Embedding model returned "
            f"{actual_dimensions} dimensions, but PostgreSQL expects {expected_dimensions}. "
            "Set WORLDBUILDER_EMBEDDING_DIMENSIONS to the model dimension and recreate the vector column."
        )
    chunk_vectors = list(zip([chunk.id for chunk in chunks], vectors, strict=True))
    if job_id is not None and worker_id is not None:
        session.rollback()
        lease_guard = session.execute(
            update(EmbeddingJob)
            .where(
                EmbeddingJob.id == job_id,
                EmbeddingJob.world_id == world_id,
                EmbeddingJob.status == "running",
                EmbeddingJob.lease_owner == worker_id,
            )
            .values(heartbeat_at=datetime.now(UTC))
        )
        if lease_guard.rowcount != 1:
            session.rollback()
            return EmbeddingBatchResult(
                status=embedding_status(session, world_id, model_override=model),
                processed_in_batch=0,
            )
        chunks_by_id = {
            chunk.id: chunk
            for chunk in session.scalars(
                select(KnowledgeChunk).where(
                    KnowledgeChunk.world_id == world_id,
                    KnowledgeChunk.id.in_({chunk_id for chunk_id, _ in chunk_vectors}),
                )
            )
        }
    else:
        chunks_by_id = {chunk.id: chunk for chunk in chunks}
    for chunk_id, vector in chunk_vectors:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        chunk.embedding = vector
        chunk.embedding_model = model
    session.commit()
    return EmbeddingBatchResult(
        status=embedding_status(session, world_id, model_override=model),
        processed_in_batch=len(chunks_by_id),
    )


def clear_embedding_index(session: Session, world_id: str) -> EmbeddingIndexStatus:
    session.execute(
        update(KnowledgeChunk)
        .where(KnowledgeChunk.world_id == world_id)
        .values(embedding=None, embedding_model=None)
    )
    session.commit()
    return embedding_status(session, world_id)
