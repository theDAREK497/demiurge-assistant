from fastapi import APIRouter, HTTPException, Query, status

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.schemas import WorldExport, WorldImportResult
from worldbuilder_core.services.import_export import (
    InvalidSnapshotError,
    WorldAlreadyExistsError,
    WorldNotFoundError,
    export_world,
    import_world,
)

router = APIRouter(tags=["import/export"])


@router.get("/worlds/{world_id}/export", response_model=WorldExport)
def export_world_snapshot(world_id: str, session: DbSession) -> WorldExport:
    try:
        return export_world(session, world_id)
    except WorldNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found") from exc


@router.post("/worlds/import", response_model=WorldImportResult, status_code=status.HTTP_201_CREATED)
def import_world_snapshot(
    snapshot: WorldExport,
    session: DbSession,
    replace_existing: bool = Query(default=False),
) -> WorldImportResult:
    try:
        return import_world(session, snapshot, replace_existing=replace_existing)
    except WorldAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="World already exists. Pass replace_existing=true to overwrite it.",
        ) from exc
    except InvalidSnapshotError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
