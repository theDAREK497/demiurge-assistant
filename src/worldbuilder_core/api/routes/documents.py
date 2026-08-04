from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import DocumentExtractionJob, EmbeddingJob, KnowledgeDocument, World
from worldbuilder_core.schemas import (
    DocumentExtractionJobRead,
    EmbeddingIndexStatus,
    EmbeddingJobRead,
    KnowledgeDocumentProcessResult,
    KnowledgeDocumentRead,
)
from worldbuilder_core.services.document_extraction_jobs import (
    enqueue_document_extraction,
    pause_document_extraction_job,
    resume_document_extraction_job,
)
from worldbuilder_core.services.embedding_index import (
    EmbeddingConfigurationError,
    clear_embedding_index,
    embedding_status,
)
from worldbuilder_core.services.embedding_jobs import (
    cancel_world_embedding_jobs,
    enqueue_embedding_job,
)
from worldbuilder_core.services.document_ingestion import (
    DocumentIngestionError,
    InvalidDocumentError,
    UnsupportedDocumentError,
    delete_document,
    pause_document,
    process_document,
    resume_document,
    safe_filename,
)

router = APIRouter(tags=["documents"])


@router.post(
    "/worlds/{world_id}/documents",
    response_model=KnowledgeDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    world_id: str,
    request: Request,
    session: DbSession,
    filename: str = Query(min_length=1, max_length=255),
    is_secret: bool = False,
) -> KnowledgeDocument:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=404, detail="World not found")
    try:
        filename = safe_filename(filename)
    except UnsupportedDocumentError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except InvalidDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    settings = request.app.state.worldbuilder_settings
    document_id = str(uuid4())
    directory = Path(settings.upload_dir) / "documents" / world_id
    directory.mkdir(parents=True, exist_ok=True)
    storage_path = directory / f"{document_id}{Path(filename).suffix.lower()}"
    temporary_path = storage_path.with_suffix(storage_path.suffix + ".part")
    digest = hashlib.sha256()
    received = 0
    try:
        with temporary_path.open("wb") as output:
            async for block in request.stream():
                received += len(block)
                if received > settings.max_document_bytes:
                    raise HTTPException(status_code=413, detail="Document is too large")
                digest.update(block)
                output.write(block)
        if received == 0:
            raise HTTPException(status_code=422, detail="Document is empty")
        temporary_path.replace(storage_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        storage_path.unlink(missing_ok=True)
        raise

    document = KnowledgeDocument(
        id=document_id,
        world_id=world_id,
        filename=filename,
        media_type=request.headers.get("content-type", "application/octet-stream")[:120],
        storage_path=str(storage_path),
        sha256=digest.hexdigest(),
        is_secret=is_secret,
    )
    session.add(document)
    try:
        session.commit()
        session.refresh(document)
    except IntegrityError as exc:
        session.rollback()
        storage_path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="This document is already uploaded") from exc
    return document


@router.get("/worlds/{world_id}/documents", response_model=list[KnowledgeDocumentRead])
def list_documents(world_id: str, session: DbSession) -> list[KnowledgeDocument]:
    if session.get(World, world_id) is None:
        raise HTTPException(status_code=404, detail="World not found")
    return list(
        session.scalars(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.world_id == world_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
    )


@router.get(
    "/worlds/{world_id}/document-extraction-jobs",
    response_model=list[DocumentExtractionJobRead],
)
def list_document_extraction_jobs(
    world_id: str,
    session: DbSession,
) -> list[DocumentExtractionJob]:
    if session.get(World, world_id) is None:
        raise HTTPException(status_code=404, detail="World not found")
    return list(
        session.scalars(
            select(DocumentExtractionJob)
            .where(DocumentExtractionJob.world_id == world_id)
            .order_by(DocumentExtractionJob.created_at.desc())
        )
    )


@router.get("/worlds/{world_id}/embedding-status", response_model=EmbeddingIndexStatus)
def get_embedding_status(world_id: str, session: DbSession) -> EmbeddingIndexStatus:
    if session.get(World, world_id) is None:
        raise HTTPException(status_code=404, detail="World not found")
    return embedding_status(session, world_id)


@router.post("/worlds/{world_id}/embeddings/process", response_model=EmbeddingJobRead)
def process_embeddings(
    world_id: str,
    session: DbSession,
    batch_size: int = Query(default=16, ge=1, le=64),
) -> EmbeddingJob:
    if session.get(World, world_id) is None:
        raise HTTPException(status_code=404, detail="World not found")
    try:
        return enqueue_embedding_job(session, world_id, batch_size=batch_size)
    except EmbeddingConfigurationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/embedding-jobs/{job_id}", response_model=EmbeddingJobRead)
def get_embedding_job(job_id: str, session: DbSession) -> EmbeddingJob:
    job = session.get(EmbeddingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Embedding job not found")
    return job


@router.delete("/worlds/{world_id}/embeddings", response_model=EmbeddingIndexStatus)
def delete_embeddings(world_id: str, session: DbSession) -> EmbeddingIndexStatus:
    if session.get(World, world_id) is None:
        raise HTTPException(status_code=404, detail="World not found")
    cancel_world_embedding_jobs(session, world_id)
    return clear_embedding_index(session, world_id)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentRead)
def get_document(document_id: str, session: DbSession) -> KnowledgeDocument:
    return _get_document(session, document_id)


@router.post(
    "/documents/{document_id}/extract",
    response_model=DocumentExtractionJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def extract_document(
    document_id: str,
    session: DbSession,
    output_language: Literal["ru", "en"] = "ru",
) -> DocumentExtractionJob:
    try:
        return enqueue_document_extraction(
            session,
            _get_document(session, document_id),
            output_language=output_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/document-extraction-jobs/{job_id}",
    response_model=DocumentExtractionJobRead,
)
def get_document_extraction_job(job_id: str, session: DbSession) -> DocumentExtractionJob:
    job = session.get(DocumentExtractionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Document extraction job not found")
    return job


@router.post(
    "/document-extraction-jobs/{job_id}/pause",
    response_model=DocumentExtractionJobRead,
)
def pause_extraction_job(job_id: str, session: DbSession) -> DocumentExtractionJob:
    try:
        return pause_document_extraction_job(session, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/document-extraction-jobs/{job_id}/resume",
    response_model=DocumentExtractionJobRead,
)
def resume_extraction_job(job_id: str, session: DbSession) -> DocumentExtractionJob:
    try:
        return resume_document_extraction_job(session, job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/documents/{document_id}/process", response_model=KnowledgeDocumentProcessResult)
def process_document_batch(
    document_id: str,
    session: DbSession,
    batch_size: int = Query(default=50, ge=1, le=500),
) -> KnowledgeDocumentProcessResult:
    document = _get_document(session, document_id)
    try:
        return process_document(session, document, batch_size=batch_size)
    except DocumentIngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/documents/{document_id}/pause", response_model=KnowledgeDocumentRead)
def pause_document_processing(document_id: str, session: DbSession) -> KnowledgeDocument:
    return pause_document(session, _get_document(session, document_id))


@router.post("/documents/{document_id}/resume", response_model=KnowledgeDocumentRead)
def resume_document_processing(document_id: str, session: DbSession) -> KnowledgeDocument:
    return resume_document(session, _get_document(session, document_id))


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(document_id: str, session: DbSession) -> Response:
    delete_document(session, _get_document(session, document_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_document(session: DbSession, document_id: str) -> KnowledgeDocument:
    document = session.get(KnowledgeDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
