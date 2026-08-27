from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Thread

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from worldbuilder_core.api.routes import (
    assets,
    detective_board,
    documents,
    entities,
    experience,
    import_export,
    llm,
    map_pins,
    proposals,
    random_tables,
    relationships,
    retrieval,
    world_rules,
    world_configuration,
    worlds,
)
from worldbuilder_core.config import get_settings
from worldbuilder_core.db import SessionLocal, create_db_and_tables
from worldbuilder_core.embedding_worker import run_worker
from worldbuilder_core.schemas import HealthRead
from worldbuilder_core.security import ApplicationSecurityMiddleware
from worldbuilder_core.services.assets import cleanup_stale_orphaned_assets


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    with SessionLocal() as session:
        cleanup_stale_orphaned_assets(session)
    settings = get_settings()
    worker_stop = Event()
    worker_thread = None
    if settings.local_worker_enabled and settings.database_url.startswith("sqlite"):
        worker_thread = Thread(
            target=run_worker,
            kwargs={"stop_event": worker_stop},
            name="worldbuilder-ai-worker",
            daemon=True,
        )
        worker_thread.start()
    app.state.local_worker_enabled = worker_thread is not None
    try:
        yield
    finally:
        worker_stop.set()
        if worker_thread is not None:
            worker_thread.join(timeout=5)


def create_app(*, create_tables_on_startup: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan if create_tables_on_startup else None)
    app.state.worldbuilder_settings = settings
    app.add_middleware(ApplicationSecurityMiddleware, settings=settings)
    static_dir = Path(__file__).parent / "static"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/health", response_model=HealthRead, tags=["system"])
    def health() -> HealthRead:
        return HealthRead(local_worker_enabled=bool(getattr(app.state, "local_worker_enabled", False)))

    @app.get("/", include_in_schema=False)
    def app_index() -> RedirectResponse:
        return RedirectResponse(url="/app/")

    app.include_router(worlds.router, prefix=settings.api_prefix)
    app.include_router(world_configuration.router, prefix=settings.api_prefix)
    app.include_router(entities.router, prefix=settings.api_prefix)
    app.include_router(experience.router, prefix=settings.api_prefix)
    app.include_router(relationships.router, prefix=settings.api_prefix)
    app.include_router(world_rules.router, prefix=settings.api_prefix)
    app.include_router(map_pins.router, prefix=settings.api_prefix)
    app.include_router(random_tables.router, prefix=settings.api_prefix)
    app.include_router(detective_board.router, prefix=settings.api_prefix)
    app.include_router(documents.router, prefix=settings.api_prefix)
    app.include_router(import_export.router, prefix=settings.api_prefix)
    app.include_router(llm.router, prefix=settings.api_prefix)
    app.include_router(retrieval.router, prefix=settings.api_prefix)
    app.include_router(proposals.router, prefix=settings.api_prefix)
    app.include_router(assets.router, prefix=settings.api_prefix)
    app.mount("/assets", StaticFiles(directory=upload_dir), name="assets")
    app.mount("/app", StaticFiles(directory=static_dir, html=True), name="app")
    return app


app = create_app()
