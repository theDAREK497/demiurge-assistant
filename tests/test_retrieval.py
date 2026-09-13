from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from worldbuilder_core.db import Base
from worldbuilder_core.models import (
    DocumentChunkLink,
    Entity,
    KnowledgeChunk,
    KnowledgeDocument,
    ViewerRole,
    World,
)
from worldbuilder_core.services.retrieval import (
    _entity_query_score,
    _entity_type_query_bonus,
    _query_terms,
    _select_document_chunks,
)


def test_query_terms_remove_question_filler_and_keep_names() -> None:
    assert _query_terms("Кто такой Виктор Тимофеев?") == ["виктор", "тимофеев"]


def test_entity_query_score_prefers_full_name_over_partial_mentions() -> None:
    terms = _query_terms("Кто такой Виктор Тимофеев?")
    subject = Entity(
        world_id="world-1",
        type="character",
        name="Научный руководитель",
        description="Виктор Тимофеев руководил проектом Семя.",
    )
    relative = Entity(
        world_id="world-1",
        type="character",
        name="Александр",
        summary="Сын Виктора.",
    )

    assert _entity_query_score(subject, terms) > _entity_query_score(relative, terms)


def test_entity_type_query_bonus_understands_who_questions() -> None:
    character = Entity(world_id="world-1", type="character", name="Виктор")
    location = Entity(world_id="world-1", type="location", name="Лаборатория")

    assert _entity_type_query_bonus(character, "Кто такой Виктор?") == 100
    assert _entity_type_query_bonus(location, "Кто такой Виктор?") == 0


def test_short_query_can_use_vector_retrieval_without_lexical_terms() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        world = World(name="Short Query")
        session.add(world)
        session.flush()
        document = KnowledgeDocument(
            world_id=world.id,
            filename="short.txt",
            media_type="text/plain",
            storage_path="short.txt",
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
            content="Ив является проводником экспедиции.",
            char_count=36,
            embedding=[1.0, 0.0],
            embedding_model="embed",
        )
        session.add_all([document, chunk])
        session.flush()
        session.add(DocumentChunkLink(document_id=document.id, chunk_id=chunk.id, position=0))
        session.commit()

        excerpts = _select_document_chunks(
            session,
            world.id,
            role=ViewerRole.master,
            query="Ив",
            query_embedding=[1.0, 0.0],
            embedding_model="embed",
            max_chunks=4,
        )

        assert [excerpt.chunk_id for excerpt in excerpts] == [chunk.id]
