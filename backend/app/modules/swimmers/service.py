"""Lógica de negocio del módulo swimmers."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Swimmer
from .schemas import SwimmerCreate, SwimmerResponse, SwimmerUpdate


def _age(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def to_response(swimmer: Swimmer) -> SwimmerResponse:
    resp = SwimmerResponse.model_validate(swimmer)
    resp.age = _age(swimmer.birth_date)
    return resp


async def list_swimmers(db: AsyncSession, search: str | None = None) -> list[Swimmer]:
    stmt = select(Swimmer).order_by(Swimmer.name)
    if search:
        stmt = stmt.where(Swimmer.name.ilike(f"%{search}%"))
    return list((await db.execute(stmt)).scalars())


async def get_swimmer(db: AsyncSession, swimmer_id: int) -> Swimmer | None:
    return await db.get(Swimmer, swimmer_id)


async def create_swimmer(db: AsyncSession, data: SwimmerCreate) -> Swimmer:
    swimmer = Swimmer(**data.model_dump())
    db.add(swimmer)
    await db.commit()
    await db.refresh(swimmer)
    return swimmer


async def update_swimmer(db: AsyncSession, swimmer: Swimmer, data: SwimmerUpdate) -> Swimmer:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(swimmer, field, value)
    await db.commit()
    await db.refresh(swimmer)
    return swimmer


async def delete_swimmer(db: AsyncSession, swimmer: Swimmer) -> None:
    await db.delete(swimmer)
    await db.commit()
