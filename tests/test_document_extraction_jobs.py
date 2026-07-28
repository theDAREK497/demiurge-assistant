import asyncio

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from worldbuilder_core.db import Base
from worldbuilder_core.models import (
    AppSetting,
    DocumentChunkLink,
    DocumentExtractionJob,
    ExtractionProposal,
    KnowledgeChunk,
    KnowledgeDocument,
    World,
)
from worldbuilder_core.schemas import LLMChatResponse, LLMMessage
from worldbuilder_core.services.document_extraction_jobs import (
    _split_for_extraction,
    claim_document_extraction_job,
    enqueue_document_extraction,
    run_document_extraction_batch,
)


def test_long_chunk_is_split_into_bounded_extraction_segments() -> None:
    source = "First paragraph. " * 90 + "\n\n" + "Second paragraph. " * 90

    segments = _split_for_extraction(source, limit=600)

    assert len(segments) > 1
    assert all(len(segment) <= 600 for segment in segments)
    assert "First paragraph." in segments[0]
    assert "Second paragraph." in segments[-1]


def test_worker_extracts_chunks_into_one_deduplicated_secret_proposal(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        world = World(name="Book World")
        session.add(world)
        session.flush()
        document = KnowledgeDocument(
            world_id=world.id,
            filename="book.txt",
            media_type="text/plain",
            storage_path="book.txt",
            sha256="a" * 64,
            status="ready",
            total_chunks=2,
            processed_chunks=2,
            is_secret=True,
        )
        session.add(document)
        session.flush()
        for position, content in enumerate(
            (
                "Quest: Recover the Moon Bell. Roll a rumor on the road.",
                "The Moon Bell quest ends when the bell returns.",
            )
        ):
            chunk = KnowledgeChunk(
                world_id=world.id,
                content_hash=str(position + 1) * 64,
                fingerprint=str(position) * 16,
                fingerprint_band_0=f"{position:04d}",
                fingerprint_band_1=f"{position:04d}",
                fingerprint_band_2=f"{position:04d}",
                fingerprint_band_3=f"{position:04d}",
                content=content,
                char_count=len(content),
            )
            session.add(chunk)
            session.flush()
            session.add(
                DocumentChunkLink(
                    document_id=document.id,
                    chunk_id=chunk.id,
                    position=position,
                )
            )
        session.add(
            AppSetting(
                key="llm.provider",
                value={
                    "base_url": "http://extractor.test/v1",
                    "default_model": "chat",
                    "extractor_model": "extractor",
                    "timeout_seconds": 10,
                    "max_entities_per_extract": 12,
                },
            )
        )
        session.commit()

        class FakeClient:
            async def chat(self, request):
                content = """
                {
                  "entities": [
                    {
                      "client_id": "moon-bell",
                      "type": "quest",
                      "name": "The Moon Bell",
                      "summary": "Return the bell."
                    }
                  ],
                  "random_tables": [
                    {
                      "client_id": "road-rumors",
                      "name": "Road Rumors"
                    }
                  ],
                  "random_table_rows": [
                    {
                      "table_client_id": "road-rumors",
                      "result": "A bell rings beneath the road."
                    }
                  ]
                }
                """
                return LLMChatResponse(
                    model=request.model or "extractor",
                    message=LLMMessage(role="assistant", content=content),
                )

        import worldbuilder_core.services.document_extraction_jobs as extraction_jobs

        monkeypatch.setattr(extraction_jobs, "build_llm_client", lambda *_, **__: FakeClient())
        job = enqueue_document_extraction(session, document)

        for _ in range(2):
            claimed = claim_document_extraction_job(session, "worker-test")
            assert claimed is not None
            asyncio.run(run_document_extraction_batch(session, claimed.id, "worker-test"))

        completed = session.get(DocumentExtractionJob, job.id)
        assert completed is not None
        assert completed.status == "completed"
        assert completed.processed_chunks == 2
        assert completed.proposal_count == 1

        proposals = list(session.scalars(select(ExtractionProposal)))
        assert len(proposals) == 1
        payload = proposals[0].payload
        assert len(payload["entities"]) == 1
        assert payload["entities"][0]["is_secret"] is True
        assert "quest" in payload["entities"][0]["tags"]
        assert len(payload["random_tables"]) == 1
        assert payload["random_tables"][0]["is_secret"] is True
        assert len(payload["random_table_rows"]) == 1
        assert payload["random_table_rows"][0]["is_secret"] is True
