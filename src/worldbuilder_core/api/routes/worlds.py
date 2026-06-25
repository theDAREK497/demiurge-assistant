from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import World
from worldbuilder_core.schemas import WorldCreate, WorldRead, WorldUpdate

router = APIRouter(prefix="/worlds", tags=["worlds"])


@router.post("", response_model=WorldRead, status_code=status.HTTP_201_CREATED)
def create_world(payload: WorldCreate, session: DbSession) -> World:
    world = World(**payload.model_dump())
    session.add(world)
    session.commit()
    session.refresh(world)
    return world


@router.get("", response_model=list[WorldRead])
def list_worlds(session: DbSession) -> list[World]:
    return list(session.scalars(select(World).order_by(World.created_at.desc())))


@router.get("/{world_id}", response_model=WorldRead)
def get_world(world_id: str, session: DbSession) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


@router.patch("/{world_id}", response_model=WorldRead)
def update_world(world_id: str, payload: WorldUpdate, session: DbSession) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(world, key, value)

    session.add(world)
    session.commit()
    session.refresh(world)
    return world


@router.delete("/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world(world_id: str, session: DbSession) -> None:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    session.delete(world)
    session.commit()

