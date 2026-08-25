"""Las reglas del equipo que no son consultas.

Las consultas están en `persistencia/repositorios/equipos.py`. Aquí queda lo que
decide: quién puede ser dueño, y cómo se pinta el club hacia fuera.

Cuando `Equipo` y `Pertenencia` sean entidades (§5.2 del rediseño),
`transfer_ownership` se convierte en `Equipo.transferir_propiedad(nuevo_jefe)` y
este archivo se queda solo con la presentación.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.persistencia.repositorios import RepositorioDeEquipos
from app.persistencia.tablas.equipos import ROLE_COACH, Team
from app.persistencia.tablas.usuarios import User

from .schemas import TeamResponse


async def transfer_ownership(
    repo: RepositorioDeEquipos, equipo: Team, new_owner_id: int,
) -> Team:
    """Cede la propiedad a otro entrenador **activo** del mismo equipo.

    Las tres comprobaciones son la razón de ser de esta función: la FK compuesta
    del esquema garantiza que el nuevo dueño sea miembro del equipo, pero no que
    esté activo ni que sea entrenador. Un equipo cuyo dueño es un atleta —o una
    cuenta revocada— se queda sin nadie capaz de administrarlo.
    """
    # Con las inactivas incluidas a propósito: hace falta poder decir "esa
    # cuenta tiene el acceso revocado" en vez de "no pertenece a este equipo",
    # que sería falso y mandaría al entrenador a buscar donde no es.
    miembro = await repo.pertenencia(new_owner_id, incluir_inactivas=True)
    if miembro is None or miembro.team_id != equipo.id:
        raise ValueError("Esa cuenta no pertenece a este equipo")
    if miembro.role != ROLE_COACH:
        raise ValueError("Solo un entrenador puede ser dueño del equipo")
    if not miembro.is_active:
        raise ValueError("Esa cuenta tiene el acceso revocado")

    return await repo.fijar_dueno(equipo, new_owner_id)


async def to_response(
    db: AsyncSession, repo: RepositorioDeEquipos, equipo: Team, principal: Principal,
) -> TeamResponse:
    coaches, athletes, swimmers = await repo.conteos(equipo.id)
    dueno = await db.get(User, equipo.owner_id) if equipo.owner_id is not None else None
    return TeamResponse(
        id=equipo.id, name=equipo.name, owner_id=equipo.owner_id,
        owner_name=dueno.name if dueno else None,
        is_owner=principal.is_owner,
        coaches=coaches, athletes=athletes, swimmers=swimmers,
    )
