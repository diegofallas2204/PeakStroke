"""Las reglas del equipo que no son consultas.

Las consultas están en `persistencia/repositorios/equipos.py` y las reglas en
`dominio.entidades.Equipo` (§5.2, 2026-10-14): quién puede ser dueño lo decide
`Equipo.transferir_propiedad`. Aquí queda pedirle al club que cambie y cómo se
pinta hacia fuera.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.persistencia.repositorios import RepositorioDeEquipos
from app.persistencia.tablas.equipos import Team
from app.persistencia.tablas.usuarios import User

from .schemas import TeamResponse


async def transfer_ownership(
    repo: RepositorioDeEquipos, equipo: Team, new_owner_id: int,
) -> Team:
    """Cede la propiedad a otro entrenador **activo** del mismo equipo.

    Las tres comprobaciones son de `Equipo.transferir_propiedad`, que levanta
    `OperacionDeEquipoImposible` (un `ValueError`: el router lo convierte en 400).
    """
    # Con las inactivas incluidas a propósito: hace falta poder decir "esa
    # cuenta tiene el acceso revocado" en vez de "no pertenece a este equipo",
    # que sería falso y mandaría al entrenador a buscar donde no es.
    miembro = await repo.pertenencia(new_owner_id, incluir_inactivas=True)
    club = repo.como_equipo(equipo)
    club.transferir_propiedad(repo.como_pertenencia(miembro) if miembro else None)
    return await repo.guardar_equipo(club)


async def rename_team(repo: RepositorioDeEquipos, equipo: Team, nombre: str) -> Team:
    club = repo.como_equipo(equipo)
    club.renombrar(nombre)
    return await repo.guardar_equipo(club)


async def to_response(
    db: AsyncSession, repo: RepositorioDeEquipos, equipo: Team, principal: Principal,
) -> TeamResponse:
    coaches, athletes, swimmers = await repo.conteos(equipo.id)
    dueno = await db.get(User, equipo.owner_id) if equipo.owner_id is not None else None
    return TeamResponse(
        id=equipo.id, name=equipo.name, owner_id=equipo.owner_id,
        owner_name=dueno.name if dueno else None,
        # Del equipo que se pinta, no del `Principal`: tras transferir, quien
        # pregunta acaba de dejar de ser dueño y el `Principal` se tomó antes.
        is_owner=equipo.owner_id == principal.id,
        coaches=coaches, athletes=athletes, swimmers=swimmers,
    )
