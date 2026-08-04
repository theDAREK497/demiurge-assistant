import asyncio

from datetime import UTC, datetime, timedelta

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
    _merge_segment_payloads,
    _split_for_extraction,
    claim_document_extraction_job,
    enqueue_document_extraction,
    run_document_extraction_batch,
)
from worldbuilder_core.services.extraction import parse_extraction_payload
from worldbuilder_core.services.llm import LLMProviderError


def test_long_chunk_is_split_into_bounded_extraction_segments() -> None:
    source = "First paragraph. " * 90 + "\n\n" + "Second paragraph. " * 90

    segments = _split_for_extraction(source, limit=600)

    assert len(segments) > 1
    assert all(len(segment) <= 600 for segment in segments)
    assert "First paragraph." in segments[0]
    assert "Second paragraph." in segments[-1]


def test_segment_merge_namespaces_reused_client_ids_and_relationships() -> None:
    first = parse_extraction_payload(
        '{"entities":[{"client_id":"char_001","type":"character","name":"Mira"}],'
        '"relationships":[]}',
        max_entities=4,
    )
    second = parse_extraction_payload(
        '{"entities":['
        '{"client_id":"char_001","type":"character","name":"Niko"},'
        '{"client_id":"loc_001","type":"location","name":"Reed Village"}],'
        '"relationships":[{"source_client_id":"char_001","target_client_id":"loc_001",'
        '"type":"lives_in"}]}',
        max_entities=4,
    )

    merged = _merge_segment_payloads([first, second])

    assert [entity.client_id for entity in merged.entities] == ["s1-char_001", "s2-char_001", "s2-loc_001"]
    assert merged.relationships[0].source_client_id == "s2-char_001"
    assert merged.relationships[0].target_client_id == "s2-loc_001"


def test_normal_knowledge_chunk_uses_one_extraction_request() -> None:
    source = "A compact source paragraph. " * 60

    segments = _split_for_extraction(source)

    assert len(source) < 2_200
    assert segments == [source]


def test_failed_extraction_job_is_resumed_in_place() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        world = World(name="Resume World")
        session.add(world)
        session.flush()
        document = KnowledgeDocument(
            world_id=world.id,
            filename="large-book.txt",
            media_type="text/plain",
            storage_path="large-book.txt",
            sha256="b" * 64,
            status="ready",
            total_chunks=10,
            processed_chunks=10,
            is_secret=False,
        )
        session.add(document)
        session.flush()
        failed = DocumentExtractionJob(
            world_id=world.id,
            document_id=document.id,
            status="failed",
            total_chunks=10,
            processed_chunks=3,
            next_position=3,
            current_segment=2,
            total_segments=5,
            partial_payloads=[{"entities": []}, {"entities": []}],
            attempts=5,
            error="Provider unavailable",
            retry_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        session.add(failed)
        session.commit()

        resumed = enqueue_document_extraction(session, document)

        assert resumed.id == failed.id
        assert resumed.status == "queued"
        assert resumed.attempts == 0
        assert resumed.retry_at is None
        assert resumed.processed_chunks == 3
        assert resumed.current_segment == 2
        assert len(resumed.partial_payloads) == 2


def test_transient_extraction_error_waits_before_retry(monkeypatch) -> None:
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
        content = "The bell tower stands above the harbor."
        chunk = KnowledgeChunk(
            world_id=world.id,
            content_hash="e" * 64,
            fingerprint="2" * 16,
            fingerprint_band_0="0002",
            fingerprint_band_1="0002",
            fingerprint_band_2="0002",
            fingerprint_band_3="0002",
            content=content,
            char_count=len(content),
        )
        document = KnowledgeDocument(
            world_id=world.id,
            filename="retry.txt",
            media_type="text/plain",
            storage_path="retry.txt",
            sha256="f" * 64,
            status="ready",
            total_chunks=1,
            processed_chunks=1,
        )
        session.add_all([chunk, document])
        session.flush()
        session.add(DocumentChunkLink(document_id=document.id, chunk_id=chunk.id, position=0))
        session.commit()

        class FailingClient:
            async def chat(self, request):
                raise LLMProviderError("LLM provider request failed: ReadTimeout after 120 seconds")

        import worldbuilder_core.services.document_extraction_jobs as extraction_jobs

        monkeypatch.setattr(extraction_jobs, "build_llm_client", lambda *_, **__: FailingClient())
        job = enqueue_document_extraction(session, document)
        claimed = claim_document_extraction_job(session, "worker-retry")
        assert claimed is not None

        queued = asyncio.run(run_document_extraction_batch(session, job.id, "worker-retry"))

        assert queued.status == "queued"
        assert queued.attempts == 1
        assert queued.retry_at is not None
        assert queued.processed_chunks == 0
        assert claim_document_extraction_job(session, "worker-too-early") is None

        queued.retry_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        retried = claim_document_extraction_job(session, "worker-after-delay")
        assert retried is not None
        assert retried.id == job.id
        assert retried.retry_at is None


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
                assert request.max_tokens == 1_280
                assert request.response_format is not None
                assert "Relevant source excerpts:" not in request.messages[-1].content
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


def test_running_extraction_pauses_after_current_segment(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        world = World(name="Pause World")
        session.add(world)
        session.flush()
        content = "A source sentence with explicit lore. " * 90
        chunk = KnowledgeChunk(
            world_id=world.id,
            content_hash="c" * 64,
            fingerprint="1" * 16,
            fingerprint_band_0="0001",
            fingerprint_band_1="0001",
            fingerprint_band_2="0001",
            fingerprint_band_3="0001",
            content=content,
            char_count=len(content),
        )
        document = KnowledgeDocument(
            world_id=world.id,
            filename="pause.txt",
            media_type="text/plain",
            storage_path="pause.txt",
            sha256="d" * 64,
            status="ready",
            total_chunks=1,
            processed_chunks=1,
        )
        session.add_all([chunk, document])
        session.flush()
        session.add(DocumentChunkLink(document_id=document.id, chunk_id=chunk.id, position=0))
        session.add(
            AppSetting(
                key="llm.provider",
                value={
                    "base_url": "http://extractor.test/v1",
                    "default_model": "extractor",
                    "timeout_seconds": 10,
                },
            )
        )
        session.commit()

        class PausingClient:
            calls = 0

            async def chat(self, request):
                self.calls += 1
                active_job = session.scalar(select(DocumentExtractionJob))
                active_job.pause_requested = True
                session.commit()
                return LLMChatResponse(
                    model=request.model or "extractor",
                    message=LLMMessage(
                        role="assistant",
                        content=(
                            '{"entities":[],"relationships":[],"world_rules":[],'
                            '"random_tables":[],"random_table_rows":[],"notes":[]}'
                        ),
                    ),
                )

        client = PausingClient()
        import worldbuilder_core.services.document_extraction_jobs as extraction_jobs

        monkeypatch.setattr(extraction_jobs, "build_llm_client", lambda *_, **__: client)
        job = enqueue_document_extraction(session, document)
        claimed = claim_document_extraction_job(session, "worker-pause")
        assert claimed is not None

        paused = asyncio.run(run_document_extraction_batch(session, job.id, "worker-pause"))

        assert client.calls == 1
        assert paused.status == "paused"
        assert paused.pause_requested is True
        assert paused.processed_chunks == 0
        assert paused.current_segment == 1
        assert paused.total_segments == 2
        assert len(paused.partial_payloads) == 1
