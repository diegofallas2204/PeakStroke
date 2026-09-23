"""Los nombres que acompañan a una solicitud, ya resueltos.

Las consultas de códigos están en `persistencia/repositorios/codigos.py`. Aquí
queda lo que es de la vista: una solicitud sin el nombre del club, de la ficha y
de quien la mandó no le dice nada a quien la recibe.

Va en un archivo aparte y no en el router porque son tres consultas: dejarlas
allí habría metido lógica en la capa que solo debe recibir y delegar.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistencia.repositorios import RepositorioDeCodigos
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.codigos import LinkCode
from app.persistencia.tablas.equipos import Team
from app.persistencia.tablas.usuarios import User


@dataclass(frozen=True)
class PendingNames:
    """Los nombres que acompañan a una solicitud, ya resueltos."""

    team: str
    swimmer: str
    coach: str | None


async def swimmer_names(db: AsyncSession, team_id: int) -> dict[int, str]:
    """id -> nombre de cada ficha del equipo, para acompañar a los códigos."""
    stmt = select(Swimmer.id, Swimmer.name).where(Swimmer.team_id == team_id)
    return dict((await db.execute(stmt)).all())  # type: ignore[arg-type]


async def describe_pending(
    db: AsyncSession, codigos: RepositorioDeCodigos, user: User,
) -> list[tuple[LinkCode, PendingNames]]:
    """Las solicitudes de esa persona con club, ficha y entrenador resueltos."""
    codes = await codigos.dirigidos_a(user.email)
    if not codes:
        return []

    equipos = dict((await db.execute(
        select(Team.id, Team.name).where(Team.id.in_({c.team_id for c in codes}))
    )).all())  # type: ignore[arg-type]
    fichas = dict((await db.execute(
        select(Swimmer.id, Swimmer.name).where(
            Swimmer.id.in_({c.swimmer_id for c in codes})
        )
    )).all())  # type: ignore[arg-type]
    entrenadores = dict((await db.execute(
        select(User.id, User.name).where(User.id.in_({c.created_by for c in codes}))
    )).all())  # type: ignore[arg-type]

    return [
        (c, PendingNames(
            team=equipos.get(c.team_id, "—"),
            swimmer=fichas.get(c.swimmer_id, "—"),
            coach=entrenadores.get(c.created_by),
        ))
        for c in codes
    ]
