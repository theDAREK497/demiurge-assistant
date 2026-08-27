from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, or_, select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import (
    Entity,
    EntityRevision,
    ExtractionProposal,
    Relationship,
    ViewerRole,
    World,
    WorldChange,
)
from worldbuilder_core.schemas import (
    EntityRevisionRead,
    WorldChangeCreate,
    WorldChangeRead,
    WorldChangeUpdate,
)
from worldbuilder_core.services.change_history import record_world_change

router = APIRouter(tags=["experience"])


def _ensure_world(session: DbSession, world_id: str) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


@router.get("/worlds/{world_id}/changes", response_model=list[WorldChangeRead])
def list_world_changes(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
    subject_id: str | None = None,
    q: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[WorldChange]:
    _ensure_world(session, world_id)
    stmt: Select[tuple[WorldChange]] = select(WorldChange).where(WorldChange.world_id == world_id)
    if role == ViewerRole.player:
        stmt = stmt.where(WorldChange.is_secret.is_(False))
    if subject_id:
        stmt = stmt.where(WorldChange.subject_id == subject_id)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                WorldChange.subject_name.ilike(pattern),
                WorldChange.summary.ilike(pattern),
                WorldChange.evidence.ilike(pattern),
                WorldChange.effective_at.ilike(pattern),
            )
        )
    return list(session.scalars(stmt.order_by(WorldChange.created_at.desc(), WorldChange.id.desc()).limit(limit)))


@router.post("/worlds/{world_id}/changes", response_model=WorldChangeRead, status_code=status.HTTP_201_CREATED)
def create_world_change(world_id: str, payload: WorldChangeCreate, session: DbSession) -> WorldChange:
    world = _ensure_world(session, world_id)
    subject_name = _validate_subject(
        session,
        world,
        payload.subject_type,
        payload.subject_id,
        payload.subject_name,
    )
    _validate_links(
        session,
        world_id,
        payload.causal_change_ids,
        payload.supersedes_change_id,
    )
    change = record_world_change(
        session,
        world_id=world_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        subject_name=subject_name,
        change_kind=payload.change_kind,
        source_type="manual",
        source_id=None,
        summary=payload.summary,
        effective_at=payload.effective_at,
        evidence=payload.evidence,
        confidence=payload.confidence,
        causal_change_ids=payload.causal_change_ids,
        supersedes_change_id=payload.supersedes_change_id,
        is_secret=payload.is_secret,
    )
    session.commit()
    session.refresh(change)
    return change


@router.patch("/changes/{change_id}", response_model=WorldChangeRead)
def update_world_change(change_id: str, payload: WorldChangeUpdate, session: DbSession) -> WorldChange:
    change = session.get(WorldChange, change_id)
    if change is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World change not found")
    data = payload.model_dump(exclude_unset=True)
    if any(data.get(key) is None for key in ("subject_type", "change_kind", "summary", "confidence", "is_secret") if key in data):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Required change fields cannot be null",
        )
    if "causal_change_ids" in data and data["causal_change_ids"] is None:
        data["causal_change_ids"] = []
    subject_type = data.get("subject_type", change.subject_type)
    subject_id = data.get("subject_id", change.subject_id)
    requested_name = data.get("subject_name", change.subject_name)
    world = _ensure_world(session, change.world_id)
    data["subject_name"] = _validate_subject(session, world, subject_type, subject_id, requested_name)
    causal_ids = data.get("causal_change_ids", change.causal_change_ids)
    supersedes_id = data.get("supersedes_change_id", change.supersedes_change_id)
    _validate_links(session, change.world_id, causal_ids, supersedes_id, current_change_id=change.id)
    _ensure_no_causal_cycle(session, change, causal_ids)
    for key, value in data.items():
        setattr(change, key, value)
    session.add(change)
    session.commit()
    session.refresh(change)
    return change


@router.get("/worlds/{world_id}/entity-revisions", response_model=list[EntityRevisionRead])
def list_entity_revisions(
    world_id: str,
    session: DbSession,
    entity_id: str | None = None,
    role: ViewerRole = ViewerRole.master,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EntityRevision]:
    _ensure_world(session, world_id)
    stmt: Select[tuple[EntityRevision]] = select(EntityRevision).where(EntityRevision.world_id == world_id)
    if entity_id:
        stmt = stmt.where(EntityRevision.entity_id == entity_id)
    if role == ViewerRole.player:
        stmt = stmt.where(EntityRevision.is_secret.is_(False))
    return list(session.scalars(stmt.order_by(EntityRevision.created_at.desc()).limit(limit)))


def _validate_subject(
    session: DbSession,
    world: World,
    subject_type: str,
    subject_id: str | None,
    subject_name: str | None,
) -> str | None:
    if subject_type == "world":
        if subject_id not in {None, world.id}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="World subject is invalid")
        return subject_name or world.name
    if not subject_id:
        return subject_name
    model = {"entity": Entity, "relationship": Relationship, "proposal": ExtractionProposal}.get(subject_type)
    subject = session.get(model, subject_id) if model is not None else None
    if subject is None or subject.world_id != world.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Subject is not in this world")
    if subject_type == "entity":
        return subject_name or subject.name
    return subject_name


def _validate_links(
    session: DbSession,
    world_id: str,
    causal_ids: list[str],
    supersedes_id: str | None,
    *,
    current_change_id: str | None = None,
) -> None:
    linked_ids = set(causal_ids)
    if supersedes_id:
        linked_ids.add(supersedes_id)
    if current_change_id and current_change_id in linked_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A change cannot reference itself")
    if not linked_ids:
        return
    found = set(
        session.scalars(
            select(WorldChange.id).where(WorldChange.world_id == world_id, WorldChange.id.in_(linked_ids))
        )
    )
    if found != linked_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Linked changes must be in this world")


def _ensure_no_causal_cycle(session: DbSession, change: WorldChange, causal_ids: list[str]) -> None:
    pending = list(causal_ids)
    visited: set[str] = set()
    while pending:
        candidate_id = pending.pop()
        if candidate_id == change.id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Causal links cannot form a cycle")
        if candidate_id in visited:
            continue
        visited.add(candidate_id)
        candidate = session.get(WorldChange, candidate_id)
        if candidate is not None:
            pending.extend(candidate.causal_change_ids)
