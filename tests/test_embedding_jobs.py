import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from worldbuilder_core.db import Base
from worldbuilder_core.models import (
    AppSetting,
    DocumentChunkLink,
    KnowledgeChunk,
    KnowledgeDocument,
    World,
)
from worldbuilder_core.services.embedding_jobs import (
    claim_embedding_job,
    enqueue_embedding_job,
    run_embedding_job_batch,
)


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

        import worldbuilder_core.services.embedding_index as embedding_index

        monkeypatch.setattr(embedding_index, "build_llm_client", lambda *_, **__: FakeClient())
        job = enqueue_embedding_job(session, world.id)
        claimed = claim_embedding_job(session, "worker-test")
        assert claimed is not None
        assert claimed.id == job.id
        completed = asyncio.run(run_embedding_job_batch(session, job.id, "worker-test"))
        assert completed.status == "completed"
        assert completed.processed_chunks == 1
        assert session.get(KnowledgeChunk, chunk.id).embedding == [0.25, 0.75]
