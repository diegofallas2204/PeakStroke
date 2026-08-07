"""Lógica de negocio del módulo swimmers.

**Toda consulta de lectura lleva el `Principal` entero**, no un `team_id` suelto.
No es una comodidad: son las dos fronteras. El equipo evita devolver el nadador
de otro club; el `swimmer_id` del solicitante evita devolverle al atleta la
ficha del compañero de calle. Una función que reciba solo un `swimmer_id`
acabará tarde o temprano devolviendo lo que no debe.

Las escrituras (`create`, `update`, `set_active`) siguen recibiendo `team_id`:
todas están detrás de `require_coach` y un atleta no llega a ellas.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Principal

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


async def list_swimmers(
    db: AsyncSession, principal: Principal, search: str | None = None,
    *, include_inactive: bool = False,
) -> list[Swimmer]:
    """El equipo entero para un entrenador; solo su propia ficha para un atleta."""
    stmt = select(Swimmer).where(Swimmer.team_id == principal.team_id).order_by(Swimmer.name)
    stmt = principal.scope_to_own_swimmer(stmt, Swimmer.id)
    if not include_inactive:
        stmt = stmt.where(Swimmer.is_active.is_(True))
    if search:
        stmt = stmt.where(Swimmer.name.ilike(f"%{search}%"))
    return list((await db.execute(stmt)).scalars())


async def get_swimmer(
    db: AsyncSession, swimmer_id: int, principal: Principal,
) -> Swimmer | None:
    """Devuelve None —no el nadador— si es de otro equipo o de otro atleta.

    El router traduce ese None a un 404: un 403 confirmaría que ese id existe en
    algún sitio, que es justo lo que no queremos filtrar.
    """
    stmt = select(Swimmer).where(
        Swimmer.id == swimmer_id, Swimmer.team_id == principal.team_id,
    )
    stmt = principal.scope_to_own_swimmer(stmt, Swimmer.id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_swimmer(db: AsyncSession, data: SwimmerCreate, team_id: int) -> Swimmer:
    """El equipo sale de la sesión de quien crea al nadador, nunca del cliente."""
    swimmer = Swimmer(**data.model_dump(), team_id=team_id)
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


async def set_active(db: AsyncSession, swimmer: Swimmer, active: bool) -> Swimmer:
    """Da de baja (o reactiva) al nadador.

    Sustituye al borrado: su histórico de entrenamiento —semanas, tiempos reales,
    tests aeróbicos— es el activo más valioso de la aplicación y no debe
    evaporarse por un clic. Los macrociclos en los que participa siguen intactos.
    """
    swimmer.is_active = active
    await db.commit()
    await db.refresh(swimmer)
    return swimmer
