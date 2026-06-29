from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from worldbuilder_core.api.routes import assets, entities, import_export, llm, proposals, relationships, retrieval, world_rules, worlds
from worldbuilder_core.config import get_settings
from worldbuilder_core.db import create_db_and_tables
from worldbuilder_core.schemas import HealthRead


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    create_db_and_tables()
    yield


def create_app(*, create_tables_on_startup: bool = True) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan if create_tables_on_startup else None)
    static_dir = Path(__file__).parent / "static"
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    @app.get("/health", response_model=HealthRead, tags=["system"])
    def health() -> HealthRead:
        return HealthRead()

    @app.get("/", include_in_schema=False)
    def app_index() -> RedirectResponse:
        return RedirectResponse(url="/app/")

    app.include_router(worlds.router, prefix=settings.api_prefix)
    app.include_router(entities.router, prefix=settings.api_prefix)
    app.include_router(relationships.router, prefix=settings.api_prefix)
    app.include_router(world_rules.router, prefix=settings.api_prefix)
    app.include_router(import_export.router, prefix=settings.api_prefix)
    app.include_router(llm.router, prefix=settings.api_prefix)
    app.include_router(retrieval.router, prefix=settings.api_prefix)
    app.include_router(proposals.router, prefix=settings.api_prefix)
    app.include_router(assets.router, prefix=settings.api_prefix)
    app.mount("/assets", StaticFiles(directory=upload_dir), name="assets")
    app.mount("/app", StaticFiles(directory=static_dir, html=True), name="app")
    return app


app = create_app()
