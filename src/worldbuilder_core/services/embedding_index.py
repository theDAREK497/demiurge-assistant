from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from worldbuilder_core.models import DocumentChunkLink, KnowledgeChunk, KnowledgeDocument
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
) -> EmbeddingBatchResult:
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
    expected_dimensions = get_settings().embedding_dimensions
    if (
        session.bind is not None
        and session.bind.dialect.name == "postgresql"
        and any(len(vector) != expected_dimensions for vector in vectors)
    ):
        actual_dimensions = len(vectors[0]) if vectors else 0
        raise EmbeddingConfigurationError(
            "Embedding model returned "
            f"{actual_dimensions} dimensions, but PostgreSQL expects {expected_dimensions}. "
            "Set WORLDBUILDER_EMBEDDING_DIMENSIONS to the model dimension and recreate the vector column."
        )
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
        chunk.embedding_model = model
    session.commit()
    return EmbeddingBatchResult(
        status=embedding_status(session, world_id, model_override=model),
        processed_in_batch=len(chunks),
    )


def clear_embedding_index(session: Session, world_id: str) -> EmbeddingIndexStatus:
    session.execute(
        update(KnowledgeChunk)
        .where(KnowledgeChunk.world_id == world_id)
        .values(embedding=None, embedding_model=None)
    )
    session.commit()
    return embedding_status(session, world_id)
