from sqlalchemy import inspect, text

from worldbuilder_core.db import create_db_and_tables, engine


def main() -> None:
    create_db_and_tables()
    backend = engine.dialect.name
    result = {"backend": backend, "tables": len(inspect(engine).get_table_names())}
    if backend == "postgresql":
        with engine.connect() as connection:
            result["vector_extension"] = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).scalar()
            result["vector_index"] = connection.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE indexname = 'ix_knowledge_chunks_embedding_hnsw'"
                )
            ).scalar()
    print(result)


if __name__ == "__main__":
    main()
