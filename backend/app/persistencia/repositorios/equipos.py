"""El agregado Equipo: el club, la pertenencia y quién lleva a quién.

**Este repositorio no recibe `Principal`, y es el único.** No es un descuido: el
equipo *es* la frontera que los demás repositorios aplican, y `Principal` se
construye a partir de lo que sale de aquí (`core/dependencies._principal_for`
pregunta por la pertenencia antes de que exista ninguna identidad). Un
repositorio acotado por lo que él mismo tiene que resolver sería circular.

Lo que sostiene la frontera, entonces, es la regla de siempre: **el `team_id`
sale de la sesión, nunca del cuerpo de la petición**. Todos los endpoints de
`api/v1/equipos/` operan sobre `principal.team_id` y ninguno acepta un id de
equipo del cliente.

Las reglas de negocio —quién puede ser dueño, qué pasa si está revocado— **no
están aquí** sino en `api/v1/equipos/service.py`. Aquí solo están las consultas.
Cuando `Equipo` y `Pertenencia` sean entidades (§5.2), esas reglas se mudan
dentro de ellas y este archivo se queda solo con el SQL.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.equipos import (
    ROLE_ATHLETE,
    ROLE_COACH,
    CoachAthlete,
    Team,
    TeamMember,
)


class RepositorioDeEquipos:
    """El club y sus pertenencias. Ver la cabecera: no lleva `Principal`."""

    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── El club ──────────────────────────────────────────────────────────────

    async def equipo(self, team_id: int) -> Team | None:
        return await self.db.get(Team, team_id)

    async def crear(self, nombre: str) -> Team:
        """Crea el equipo **sin dueño**: todavía no existe ningún miembro al que apuntar.

        Es el arranque en frío (`tools/create_user.py --new-team`, `seed.py`), no
        una operación del API: no hay endpoint que cree equipos.
        """
        equipo = Team(name=nombre)
        self.db.add(equipo)
        await self.db.commit()
        await self.db.refresh(equipo)
        return equipo

    async def renombrar(self, equipo: Team, nombre: str) -> Team:
        equipo.name = nombre
        await self.db.commit()
        await self.db.refresh(equipo)
        return equipo

    async def fijar_dueno(self, equipo: Team, user_id: int) -> Team:
        """Escribe el nuevo dueño. **Las tres comprobaciones no están aquí.**

        Quién puede serlo —entrenador, miembro de este equipo y con el acceso
        vivo— lo decide `api/v1/equipos/service.transfer_ownership`, porque es
        una regla de negocio y no una consulta.
        """
        equipo.owner_id = user_id
        await self.db.commit()
        await self.db.refresh(equipo)
        return equipo

    # ── La pertenencia ───────────────────────────────────────────────────────

    async def pertenencia(
        self, user_id: int, *, incluir_inactivas: bool = False,
    ) -> TeamMember | None:
        """La pertenencia **activa** del usuario, salvo que se pida lo contrario.

        Antes no filtraba `is_active` y `core/dependencies._principal_for` sí,
        así que dos funciones respondían la misma pregunta con semánticas
        distintas. No era explotable porque los llamadores compensaban por su
        cuenta, pero depender de que cada llamador se acuerde es exactamente el
        patrón que produjo el agujero del scoping: **la respuesta segura tiene
        que ser la que sale por defecto.**

        `incluir_inactivas=True` para quien necesite distinguir "no es de este
        equipo" de "está aquí pero revocado" — `transfer_ownership` lo necesita
        para dar un error que se entienda, y `/auth/me` para no dejar entrar a
        quien acaban de echar como si fuera una cuenta del pool.
        """
        stmt = select(TeamMember).where(TeamMember.user_id == user_id)
        if not incluir_inactivas:
            stmt = stmt.where(TeamMember.is_active.is_(True))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def conteos(self, team_id: int) -> tuple[int, int, int]:
        """(entrenadores activos, atletas activos, nadadores activos) del equipo."""
        stmt = (
            select(TeamMember.role, func.count())
            .where(TeamMember.team_id == team_id, TeamMember.is_active.is_(True))
            .group_by(TeamMember.role)
        )
        por_rol = dict((await self.db.execute(stmt)).all())

        fichas = (await self.db.execute(
            select(func.count()).select_from(Swimmer)
            .where(Swimmer.team_id == team_id, Swimmer.is_active.is_(True))
        )).scalar_one()
        return por_rol.get(ROLE_COACH, 0), por_rol.get(ROLE_ATHLETE, 0), fichas

    # ── Asignación entrenador ↔ atleta ───────────────────────────────────────

    async def atletas_de(self, team_id: int, coach_id: int) -> list[int]:
        stmt = select(CoachAthlete.swimmer_id).where(
            CoachAthlete.team_id == team_id, CoachAthlete.coach_id == coach_id,
        )
        return list((await self.db.execute(stmt)).scalars())

    async def fijar_atletas_de(
        self, team_id: int, coach_id: int, swimmer_ids: list[int],
    ) -> list[int]:
        """Reemplaza la lista de atletas a cargo de un entrenador.

        No hace falta comprobar que los nadadores sean del equipo: la FK
        compuesta `(swimmer_id, team_id)` lo impide a nivel de motor.
        """
        actuales = set(await self.atletas_de(team_id, coach_id))
        deseados = set(swimmer_ids)

        for swimmer_id in deseados - actuales:
            self.db.add(CoachAthlete(
                team_id=team_id, coach_id=coach_id, swimmer_id=swimmer_id,
            ))
        if actuales - deseados:
            stmt = select(CoachAthlete).where(
                CoachAthlete.team_id == team_id,
                CoachAthlete.coach_id == coach_id,
                CoachAthlete.swimmer_id.in_(actuales - deseados),
            )
            for fila in (await self.db.execute(stmt)).scalars():
                await self.db.delete(fila)

        await self.db.commit()
        return sorted(deseados)
