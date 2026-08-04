from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from worldbuilder_core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine_kwargs = {"connect_args": {"check_same_thread": False}} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, **engine_kwargs)
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def create_db_and_tables() -> None:
    from worldbuilder_core import models

    _ = models
    if settings.database_url.startswith("postgresql"):
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    _ensure_relationship_columns()
    _ensure_document_extraction_columns()
    if settings.database_url.startswith("postgresql"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
                    "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) "
                    "WHERE embedding IS NOT NULL"
                )
            )


def _ensure_relationship_columns() -> None:
    columns = {
        "weight": "FLOAT NOT NULL DEFAULT 1.0",
        "valid_from": "VARCHAR(120)",
        "valid_to": "VARCHAR(120)",
        "evidence": "TEXT",
    }
    with engine.begin() as connection:
        if settings.database_url.startswith("sqlite"):
            existing = {row[1] for row in connection.execute(text("PRAGMA table_info(relationships)"))}
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE relationships ADD COLUMN {name} {sql_type}"))
            return
        if settings.database_url.startswith("postgresql"):
            for name, sql_type in columns.items():
                connection.execute(
                    text(f"ALTER TABLE relationships ADD COLUMN IF NOT EXISTS {name} {sql_type}")
                )


def _ensure_document_extraction_columns() -> None:
    with engine.begin() as connection:
        if settings.database_url.startswith("sqlite"):
            columns = {
                "current_segment": "INTEGER NOT NULL DEFAULT 0",
                "total_segments": "INTEGER NOT NULL DEFAULT 0",
                "partial_payloads": "JSON NOT NULL DEFAULT '[]'",
                "pause_requested": "BOOLEAN NOT NULL DEFAULT 0",
                "retry_at": "DATETIME",
            }
            existing = {
                row[1] for row in connection.execute(text("PRAGMA table_info(document_extraction_jobs)"))
            }
            for name, sql_type in columns.items():
                if name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE document_extraction_jobs ADD COLUMN {name} {sql_type}")
                    )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_extraction_jobs_retry_at "
                    "ON document_extraction_jobs (retry_at)"
                )
            )
            return
        if settings.database_url.startswith("postgresql"):
            columns = {
                "current_segment": "INTEGER NOT NULL DEFAULT 0",
                "total_segments": "INTEGER NOT NULL DEFAULT 0",
                "partial_payloads": "JSONB NOT NULL DEFAULT '[]'::jsonb",
                "pause_requested": "BOOLEAN NOT NULL DEFAULT FALSE",
                "retry_at": "TIMESTAMPTZ",
            }
            for name, sql_type in columns.items():
                connection.execute(
                    text(
                        "ALTER TABLE document_extraction_jobs "
                        f"ADD COLUMN IF NOT EXISTS {name} {sql_type}"
                    )
                )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_document_extraction_jobs_retry_at "
                    "ON document_extraction_jobs (retry_at)"
                )
            )


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
