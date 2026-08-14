"""Lecturas del módulo link_codes: qué códigos hay vivos y a nombre de quién.

Ninguna de estas funciones decide nada ni escribe nada — las reglas están en
`service.py`. Están juntas aquí porque todas responden a la misma pregunta desde
distintos ángulos: qué invitaciones siguen en pie.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User

# `normalize_email` es la única función ajena que se importa aquí, y a propósito:
# el correo invitado se compara contra `users.email`, así que las dos formas de
# normalizarlo tienen que ser LA MISMA. Copiar el `.strip().lower()` habría
# funcionado hasta el día en que una de las dos cambie.
from app.modules.auth.service import normalize_email

# Lecturas explícitas de modelos de otros módulos (permitido por las reglas del
# proyecto): los códigos se acompañan del nombre de la ficha y del club.
from app.modules.swimmers.models import Swimmer
from app.modules.teams.models import Team

from .codes import is_live, now_utc
from .models import LinkCode


async def active_for_team(db: AsyncSession, team_id: int) -> list[LinkCode]:
    """Los códigos que todavía sirven, del equipo entero."""
    stmt = select(LinkCode).where(
        LinkCode.team_id == team_id,
        LinkCode.used_at.is_(None),
        LinkCode.revoked_at.is_(None),
    ).order_by(LinkCode.created_at.desc())
    ahora = now_utc()
    return [c for c in (await db.execute(stmt)).scalars() if is_live(c, now=ahora)]


async def active_by_swimmer(db: AsyncSession, team_id: int) -> dict[int, LinkCode]:
    """swimmer_id → su código vivo, para pintar el estado de cada ficha."""
    return {c.swimmer_id: c for c in await active_for_team(db, team_id)}


async def swimmer_names(db: AsyncSession, team_id: int) -> dict[int, str]:
    """id → nombre de cada ficha del equipo, para acompañar a los códigos."""
    stmt = select(Swimmer.id, Swimmer.name).where(Swimmer.team_id == team_id)
    return dict((await db.execute(stmt)).all())  # type: ignore[arg-type]


async def swimmer_of_team(
    db: AsyncSession, swimmer_id: int, team_id: int,
) -> Swimmer | None:
    """La ficha, solo si es de ese equipo. None si no lo es — el router da 404."""
    stmt = select(Swimmer).where(
        Swimmer.id == swimmer_id, Swimmer.team_id == team_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def pending_for(db: AsyncSession, user: User) -> list[LinkCode]:
    """Las invitaciones vivas dirigidas al correo de esa persona.

    Se busca por **correo** y no por usuario porque el entrenador invita antes
    de que exista la cuenta tan a menudo como después: quien se registre luego
    con ese correo encuentra su solicitud esperando.

    Solo salen las dirigidas (`invited_email`). Un código emitido sobre una
    ficha suelta no va dirigido a nadie, y listarlo aquí sería enseñárselo a
    quien no tiene por qué saber que existe.
    """
    stmt = select(LinkCode).where(
        LinkCode.invited_email == normalize_email(user.email),
        LinkCode.used_at.is_(None),
        LinkCode.revoked_at.is_(None),
    ).order_by(LinkCode.created_at.desc())
    ahora = now_utc()
    return [c for c in (await db.execute(stmt)).scalars() if is_live(c, now=ahora)]


@dataclass(frozen=True)
class PendingNames:
    """Los nombres que acompañan a una solicitud, ya resueltos."""

    team: str
    swimmer: str
    coach: str | None


async def describe_pending(
    db: AsyncSession, user: User,
) -> list[tuple[LinkCode, PendingNames]]:
    """Las solicitudes de esa persona con club, ficha y entrenador resueltos.

    Va aquí y no en el router porque son tres consultas: dejarlas allí habría
    metido lógica en la capa que solo debe recibir y delegar.
    """
    codes = await pending_for(db, user)
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
