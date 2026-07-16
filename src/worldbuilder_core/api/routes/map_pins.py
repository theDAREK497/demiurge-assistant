from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import joinedload

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import Entity, EntityType, MapPin, ViewerRole, World
from worldbuilder_core.schemas import MapPinCreate, MapPinRead, MapPinUpdate

router = APIRouter(tags=["map pins"])


def ensure_world(session: DbSession, world_id: str) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


def ensure_entity_in_world(session: DbSession, entity_id: str, world_id: str) -> Entity:
    entity = session.get(Entity, entity_id)
    if entity is None or entity.world_id != world_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Entity does not belong to world")
    return entity


def ensure_map_entity(session: DbSession, entity_id: str, world_id: str) -> Entity:
    entity = ensure_entity_in_world(session, entity_id, world_id)
    if entity.type != EntityType.location:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Map entity must be a location")
    return entity


def ensure_visible(pin: MapPin | None, role: ViewerRole) -> MapPin:
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map pin not found")
    if role == ViewerRole.player and not _pin_is_player_visible(pin):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map pin not found")
    return pin


@router.post("/worlds/{world_id}/map-pins", response_model=MapPinRead, status_code=status.HTTP_201_CREATED)
def create_map_pin(world_id: str, payload: MapPinCreate, session: DbSession) -> MapPin:
    ensure_world(session, world_id)
    ensure_map_entity(session, payload.map_entity_id, world_id)
    if payload.linked_entity_id:
        ensure_entity_in_world(session, payload.linked_entity_id, world_id)

    pin = MapPin(world_id=world_id, **payload.model_dump())
    session.add(pin)
    session.commit()
    session.refresh(pin)
    return pin


@router.get("/worlds/{world_id}/map-pins", response_model=list[MapPinRead])
def list_map_pins(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
    map_entity_id: str | None = None,
) -> list[MapPin]:
    ensure_world(session, world_id)
    stmt: Select[tuple[MapPin]] = (
        select(MapPin)
        .options(joinedload(MapPin.map_entity), joinedload(MapPin.linked_entity))
        .where(MapPin.world_id == world_id)
    )
    if map_entity_id:
        stmt = stmt.where(MapPin.map_entity_id == map_entity_id)

    pins = list(session.scalars(stmt.order_by(MapPin.created_at.asc(), MapPin.id.asc())))
    if role == ViewerRole.player:
        pins = [pin for pin in pins if _pin_is_player_visible(pin)]
    return pins


@router.get("/map-pins/{pin_id}", response_model=MapPinRead)
def get_map_pin(pin_id: str, session: DbSession, role: ViewerRole = ViewerRole.master) -> MapPin:
    return ensure_visible(session.get(MapPin, pin_id), role)


@router.patch("/map-pins/{pin_id}", response_model=MapPinRead)
def update_map_pin(pin_id: str, payload: MapPinUpdate, session: DbSession) -> MapPin:
    pin = session.get(MapPin, pin_id)
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map pin not found")

    data = payload.model_dump(exclude_unset=True)
    map_entity_id = data.get("map_entity_id", pin.map_entity_id)
    ensure_map_entity(session, map_entity_id, pin.world_id)
    linked_entity_id = data.get("linked_entity_id", pin.linked_entity_id)
    if linked_entity_id:
        ensure_entity_in_world(session, linked_entity_id, pin.world_id)

    for key, value in data.items():
        setattr(pin, key, value)

    session.add(pin)
    session.commit()
    session.refresh(pin)
    return pin


@router.delete("/map-pins/{pin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_map_pin(pin_id: str, session: DbSession) -> None:
    pin = session.get(MapPin, pin_id)
    if pin is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map pin not found")
    session.delete(pin)
    session.commit()


def _pin_is_player_visible(pin: MapPin) -> bool:
    if pin.is_secret or pin.map_entity.is_secret:
        return False
    return not pin.linked_entity or not pin.linked_entity.is_secret
