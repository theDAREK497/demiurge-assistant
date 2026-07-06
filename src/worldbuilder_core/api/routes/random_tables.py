import random

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Select, select

from worldbuilder_core.api.deps import DbSession
from worldbuilder_core.models import RandomTable, RandomTableRow, ViewerRole, World
from worldbuilder_core.schemas import (
    RandomTableCreate,
    RandomTableRead,
    RandomTableRollRead,
    RandomTableRowCreate,
    RandomTableRowRead,
    RandomTableRowUpdate,
    RandomTableUpdate,
)

router = APIRouter(tags=["random tables"])


def ensure_world(session: DbSession, world_id: str) -> World:
    world = session.get(World, world_id)
    if world is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World not found")
    return world


def ensure_table(table: RandomTable | None, role: ViewerRole = ViewerRole.master) -> RandomTable:
    if table is None or (role == ViewerRole.player and table.is_secret):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Random table not found")
    return table


def ensure_row(row: RandomTableRow | None) -> RandomTableRow:
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Random table row not found")
    return row


@router.post("/worlds/{world_id}/random-tables", response_model=RandomTableRead, status_code=status.HTTP_201_CREATED)
def create_random_table(world_id: str, payload: RandomTableCreate, session: DbSession) -> RandomTableRead:
    ensure_world(session, world_id)
    table = RandomTable(world_id=world_id, **payload.model_dump())
    session.add(table)
    session.commit()
    session.refresh(table)
    return _table_read(table)


@router.get("/worlds/{world_id}/random-tables", response_model=list[RandomTableRead])
def list_random_tables(
    world_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
) -> list[RandomTableRead]:
    ensure_world(session, world_id)
    stmt: Select[tuple[RandomTable]] = select(RandomTable).where(RandomTable.world_id == world_id)
    if role == ViewerRole.player:
        stmt = stmt.where(RandomTable.is_secret.is_(False))
    tables = list(session.scalars(stmt.order_by(RandomTable.name.asc(), RandomTable.created_at.asc())))
    return [_table_read(table, role=role) for table in tables]


@router.get("/random-tables/{table_id}", response_model=RandomTableRead)
def get_random_table(table_id: str, session: DbSession, role: ViewerRole = ViewerRole.master) -> RandomTableRead:
    table = ensure_table(session.get(RandomTable, table_id), role)
    return _table_read(table, role=role)


@router.patch("/random-tables/{table_id}", response_model=RandomTableRead)
def update_random_table(table_id: str, payload: RandomTableUpdate, session: DbSession) -> RandomTableRead:
    table = ensure_table(session.get(RandomTable, table_id))
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(table, key, value)

    session.add(table)
    session.commit()
    session.refresh(table)
    return _table_read(table)


@router.delete("/random-tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_random_table(table_id: str, session: DbSession) -> None:
    table = ensure_table(session.get(RandomTable, table_id))
    session.delete(table)
    session.commit()


@router.post("/random-tables/{table_id}/rows", response_model=RandomTableRowRead, status_code=status.HTTP_201_CREATED)
def create_random_table_row(table_id: str, payload: RandomTableRowCreate, session: DbSession) -> RandomTableRow:
    ensure_table(session.get(RandomTable, table_id))
    row = RandomTableRow(table_id=table_id, **payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.patch("/random-table-rows/{row_id}", response_model=RandomTableRowRead)
def update_random_table_row(row_id: str, payload: RandomTableRowUpdate, session: DbSession) -> RandomTableRow:
    row = ensure_row(session.get(RandomTableRow, row_id))
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)

    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/random-table-rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_random_table_row(row_id: str, session: DbSession) -> None:
    row = ensure_row(session.get(RandomTableRow, row_id))
    session.delete(row)
    session.commit()


@router.post("/random-tables/{table_id}/roll", response_model=RandomTableRollRead)
def roll_random_table(
    table_id: str,
    session: DbSession,
    role: ViewerRole = ViewerRole.master,
) -> RandomTableRollRead:
    table = ensure_table(session.get(RandomTable, table_id), role)
    rows = _visible_rows(table, role)
    if not rows:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Random table has no visible rows")

    row = random.choices(rows, weights=[item.weight for item in rows], k=1)[0]
    return RandomTableRollRead(table_id=table.id, row=RandomTableRowRead.model_validate(row))


def _table_read(table: RandomTable, role: ViewerRole = ViewerRole.master) -> RandomTableRead:
    payload = RandomTableRead.model_validate(table)
    payload.rows = [RandomTableRowRead.model_validate(row) for row in _visible_rows(table, role)]
    return payload


def _visible_rows(table: RandomTable, role: ViewerRole) -> list[RandomTableRow]:
    rows = sorted(table.rows, key=lambda row: (row.created_at, row.id))
    if role == ViewerRole.player:
        return [row for row in rows if not row.is_secret]
    return rows
