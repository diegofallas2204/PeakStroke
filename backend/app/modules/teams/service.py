"""Lógica de negocio del módulo teams."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.swimmers.models import Swimmer

from .models import ROLE_COACH, CoachAthlete, Team, TeamMember


async def get_team(db: AsyncSession, team_id: int) -> Team | None:
    return await db.get(Team, team_id)


async def create_team(db: AsyncSession, name: str) -> Team:
    """Crea el equipo sin dueño: todavía no existe ningún miembro al que apuntar."""
    team = Team(name=name)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


async def add_member(
    db: AsyncSession, team_id: int, user_id: int, role: str = ROLE_COACH,
) -> TeamMember:
    member = TeamMember(team_id=team_id, user_id=user_id, role=role)
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


async def get_membership(
    db: AsyncSession, user_id: int, *, include_inactive: bool = False,
) -> TeamMember | None:
    """La pertenencia **activa** del usuario, salvo que se pida lo contrario.

    Antes no filtraba `is_active` y `core/dependencies._principal_for` sí, así
    que dos funciones respondían la misma pregunta con semánticas distintas.
    Hoy no era explotable porque los tres llamadores compensaban por su cuenta,
    pero depender de que cada llamador se acuerde es exactamente el patrón que
    produjo el agujero del scoping: la respuesta segura tiene que ser la que
    sale por defecto.

    `include_inactive=True` para quien necesite distinguir "no es de este
    equipo" de "está aquí pero revocado" — `transfer_ownership` lo necesita
    para dar un error que se entienda.
    """
    stmt = select(TeamMember).where(TeamMember.user_id == user_id)
    if not include_inactive:
        stmt = stmt.where(TeamMember.is_active.is_(True))
    return (await db.execute(stmt)).scalar_one_or_none()


async def transfer_ownership(db: AsyncSession, team: Team, new_owner_id: int) -> Team:
    """Cede la propiedad a otro entrenador **activo** del mismo equipo.

    Las tres comprobaciones son la razón de ser de esta función: la FK compuesta
    del esquema garantiza que el nuevo dueño sea miembro del equipo, pero no que
    esté activo ni que sea entrenador. Un equipo cuyo dueño es un atleta —o una
    cuenta revocada— se queda sin nadie capaz de administrarlo.
    """
    # Con las inactivas incluidas a propósito: hace falta poder decir "esa
    # cuenta tiene el acceso revocado" en vez de "no pertenece a este equipo",
    # que sería falso y mandaría al entrenador a buscar donde no es.
    member = await get_membership(db, new_owner_id, include_inactive=True)
    if member is None or member.team_id != team.id:
        raise ValueError("Esa cuenta no pertenece a este equipo")
    if member.role != ROLE_COACH:
        raise ValueError("Solo un entrenador puede ser dueño del equipo")
    if not member.is_active:
        raise ValueError("Esa cuenta tiene el acceso revocado")

    team.owner_id = new_owner_id
    await db.commit()
    await db.refresh(team)
    return team


async def team_counts(db: AsyncSession, team_id: int) -> tuple[int, int, int]:
    """(entrenadores activos, atletas activos, nadadores activos) del equipo."""
    stmt = (
        select(TeamMember.role, func.count())
        .where(TeamMember.team_id == team_id, TeamMember.is_active.is_(True))
        .group_by(TeamMember.role)
    )
    por_rol = dict((await db.execute(stmt)).all())

    swimmers_stmt = (
        select(func.count())
        .select_from(Swimmer)
        .where(Swimmer.team_id == team_id, Swimmer.is_active.is_(True))
    )
    swimmers = (await db.execute(swimmers_stmt)).scalar_one()
    return por_rol.get(ROLE_COACH, 0), por_rol.get("athlete", 0), swimmers


async def owner_name(db: AsyncSession, team: Team) -> str | None:
    if team.owner_id is None:
        return None
    user = await db.get(User, team.owner_id)
    return user.name if user else None


# --- Asignación entrenador ↔ atleta -----------------------------------------

async def athletes_of_coach(db: AsyncSession, team_id: int, coach_id: int) -> list[int]:
    stmt = select(CoachAthlete.swimmer_id).where(
        CoachAthlete.team_id == team_id, CoachAthlete.coach_id == coach_id,
    )
    return list((await db.execute(stmt)).scalars())


async def set_athletes_of_coach(
    db: AsyncSession, team_id: int, coach_id: int, swimmer_ids: list[int],
) -> list[int]:
    """Reemplaza la lista de atletas a cargo de un entrenador.

    No hace falta comprobar que los nadadores sean del equipo: la FK compuesta
    `(swimmer_id, team_id)` lo impide a nivel de motor.
    """
    actuales = set(await athletes_of_coach(db, team_id, coach_id))
    deseados = set(swimmer_ids)

    for swimmer_id in deseados - actuales:
        db.add(CoachAthlete(team_id=team_id, coach_id=coach_id, swimmer_id=swimmer_id))
    if actuales - deseados:
        stmt = select(CoachAthlete).where(
            CoachAthlete.team_id == team_id,
            CoachAthlete.coach_id == coach_id,
            CoachAthlete.swimmer_id.in_(actuales - deseados),
        )
        for fila in (await db.execute(stmt)).scalars():
            await db.delete(fila)

    await db.commit()
    return sorted(deseados)
