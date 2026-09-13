import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from worldbuilder_core.db import Base
from worldbuilder_core.models import (
    AppSetting,
    DocumentChunkLink,
    EmbeddingJob,
    KnowledgeChunk,
    KnowledgeDocument,
    World,
)
from worldbuilder_core.services.embedding_jobs import (
    claim_embedding_job,
    enqueue_embedding_job,
    run_embedding_job_batch,
)
from worldbuilder_core.services.llm import LLMProviderError


def test_worker_claims_and_completes_embedding_job(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        world = World(name="Worker World")
        session.add(world)
        session.flush()
        document = KnowledgeDocument(
            world_id=world.id,
            filename="worker.txt",
            media_type="text/plain",
            storage_path="worker.txt",
            sha256="a" * 64,
            status="ready",
            total_chunks=1,
            processed_chunks=1,
        )
        chunk = KnowledgeChunk(
            world_id=world.id,
            content_hash="b" * 64,
            fingerprint="0" * 16,
            fingerprint_band_0="0000",
            fingerprint_band_1="0000",
            fingerprint_band_2="0000",
            fingerprint_band_3="0000",
            content="The worker embeds this text.",
            char_count=28,
        )
        session.add_all([document, chunk])
        session.flush()
        session.add(DocumentChunkLink(document_id=document.id, chunk_id=chunk.id, position=0))
        session.add(
            AppSetting(
                key="llm.provider",
                value={
                    "base_url": "http://embedding.test/v1",
                    "default_model": "chat",
                    "embedding_model": "embed",
                    "timeout_seconds": 10,
                    "max_entities_per_extract": 12,
                },
            )
        )
        session.commit()

        class FakeClient:
            async def embeddings(self, inputs, *, model=None):
                assert inputs == ["The worker embeds this text."]
                return model, [[0.25, 0.75]]

        from worldbuilder_core.services import embedding_index

        monkeypatch.setattr(embedding_index, "build_llm_client", lambda *_, **__: FakeClient())
        job = enqueue_embedding_job(session, world.id)
        claimed = claim_embedding_job(session, "worker-test")
        assert claimed is not None
        assert claimed.id == job.id
        completed = asyncio.run(run_embedding_job_batch(session, job.id, "worker-test"))
        assert completed.status == "completed"
        assert completed.processed_chunks == 1
        assert session.get(KnowledgeChunk, chunk.id).embedding == [0.25, 0.75]


def test_embedding_failure_waits_before_retry_and_success_resets_attempts(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        world = World(name="Retry World")
        session.add(world)
        session.flush()
        document = KnowledgeDocument(
            world_id=world.id,
            filename="retry.txt",
            media_type="text/plain",
            storage_path="retry.txt",
            sha256="c" * 64,
            status="ready",
            total_chunks=1,
            processed_chunks=1,
        )
        chunk = KnowledgeChunk(
            world_id=world.id,
            content_hash="d" * 64,
            fingerprint="0" * 16,
            fingerprint_band_0="0000",
            fingerprint_band_1="0000",
            fingerprint_band_2="0000",
            fingerprint_band_3="0000",
            content="Retry this embedding once.",
            char_count=26,
        )
        session.add_all([document, chunk])
        session.flush()
        session.add(DocumentChunkLink(document_id=document.id, chunk_id=chunk.id, position=0))
        session.add(
            AppSetting(
                key="llm.provider",
                value={
                    "base_url": "http://embedding.test/v1",
                    "default_model": "chat",
                    "embedding_model": "embed",
                    "timeout_seconds": 10,
                    "max_entities_per_extract": 12,
                },
            )
        )
        session.commit()

        class FakeClient:
            calls = 0

            async def embeddings(self, inputs, *, model=None):
                self.calls += 1
                if self.calls == 1:
                    raise LLMProviderError("temporary channel error")
                return model, [[0.4, 0.6]]

        fake_client = FakeClient()
        from worldbuilder_core.services import embedding_index

        monkeypatch.setattr(embedding_index, "build_llm_client", lambda *_, **__: fake_client)
        job = enqueue_embedding_job(session, world.id)
        claimed = claim_embedding_job(session, "worker-retry")
        assert claimed is not None

        queued = asyncio.run(run_embedding_job_batch(session, job.id, "worker-retry"))

        assert queued.status == "queued"
        assert queued.attempts == 1
        assert queued.retry_at is not None
        assert claim_embedding_job(session, "too-early") is None

        queued.retry_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        retried = claim_embedding_job(session, "worker-retry")
        assert retried is not None
        completed = asyncio.run(run_embedding_job_batch(session, job.id, "worker-retry"))

        assert completed.status == "completed"
        assert completed.attempts == 0
        assert completed.retry_at is None
        assert completed.error is None


def test_changing_embedding_model_cancels_stale_active_job() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        world = World(name="Model Switch")
        session.add(world)
        session.flush()
        document = KnowledgeDocument(
            world_id=world.id,
            filename="switch.txt",
            media_type="text/plain",
            storage_path="switch.txt",
            sha256="e" * 64,
            status="ready",
            total_chunks=1,
            processed_chunks=1,
        )
        chunk = KnowledgeChunk(
            world_id=world.id,
            content_hash="f" * 64,
            fingerprint="0" * 16,
            fingerprint_band_0="0000",
            fingerprint_band_1="0000",
            fingerprint_band_2="0000",
            fingerprint_band_3="0000",
            content="Model switch source.",
            char_count=20,
        )
        session.add_all([document, chunk])
        session.flush()
        session.add(DocumentChunkLink(document_id=document.id, chunk_id=chunk.id, position=0))
        setting = AppSetting(
            key="llm.provider",
            value={
                "base_url": "http://embedding.test/v1",
                "default_model": "chat",
                "embedding_model": "embed-v1",
                "timeout_seconds": 10,
                "max_entities_per_extract": 12,
            },
        )
        session.add(setting)
        session.commit()
        old_job = enqueue_embedding_job(session, world.id)

        setting.value = {**setting.value, "embedding_model": "embed-v2"}
        session.commit()
        new_job = enqueue_embedding_job(session, world.id)

        session.refresh(old_job)
        assert old_job.status == "cancelled"
        assert new_job.id != old_job.id
        assert new_job.model == "embed-v2"


def test_cancelled_embedding_job_cannot_write_a_late_provider_response(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        world = World(name="Cancellation Guard")
        session.add(world)
        session.flush()
        document = KnowledgeDocument(
            world_id=world.id,
            filename="cancel.txt",
            media_type="text/plain",
            storage_path="cancel.txt",
            sha256="1" * 64,
            status="ready",
            total_chunks=1,
            processed_chunks=1,
        )
        chunk = KnowledgeChunk(
            world_id=world.id,
            content_hash="2" * 64,
            fingerprint="0" * 16,
            fingerprint_band_0="0000",
            fingerprint_band_1="0000",
            fingerprint_band_2="0000",
            fingerprint_band_3="0000",
            content="Do not store this late response.",
            char_count=32,
        )
        session.add_all([document, chunk])
        session.flush()
        session.add(DocumentChunkLink(document_id=document.id, chunk_id=chunk.id, position=0))
        session.add(
            AppSetting(
                key="llm.provider",
                value={
                    "base_url": "http://embedding.test/v1",
                    "default_model": "chat",
                    "embedding_model": "embed",
                    "timeout_seconds": 10,
                    "max_entities_per_extract": 12,
                },
            )
        )
        session.commit()
        job = enqueue_embedding_job(session, world.id)
        claimed = claim_embedding_job(session, "worker-cancelled")
        assert claimed is not None

        class CancellingClient:
            async def embeddings(self, inputs, *, model=None):
                active_job = session.get(EmbeddingJob, job.id)
                active_job.status = "cancelled"
                active_job.lease_owner = None
                active_job.lease_expires_at = None
                session.commit()
                return model, [[0.1, 0.9]]

        from worldbuilder_core.services import embedding_index

        monkeypatch.setattr(embedding_index, "build_llm_client", lambda *_, **__: CancellingClient())
        cancelled = asyncio.run(run_embedding_job_batch(session, job.id, "worker-cancelled"))

        assert cancelled.status == "cancelled"
        session.refresh(chunk)
        assert chunk.embedding is None
