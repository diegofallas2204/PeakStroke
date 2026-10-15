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

Las reglas de negocio —quién puede ser dueño, qué pasa si está revocado, que al
dueño no se le revoca— **no están aquí**: son de `dominio.entidades.Equipo` y
`Pertenencia` desde el 2026-10-14 (§5.2). Aquí están las consultas, la traducción
a entidad (`como_equipo`, `como_pertenencia`) y `guardar_*`, que escribe lo que
la entidad cambió. Las lecturas siguen devolviendo filas: `Principal` y la
presentación las llevan encima.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.entidades import Equipo, OperacionDeEquipoImposible, Pertenencia
from app.persistencia.mapeo.identidad import (
    equipo_desde_fila,
    pertenencia_desde_fila,
    volcar_equipo,
    volcar_pertenencia,
)
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.codigos import LinkCode
from app.persistencia.tablas.equipos import (
    ROLE_ATHLETE,
    ROLE_COACH,
    CoachAthlete,
    Team,
    TeamMember,
)
from app.persistencia.tablas.planes import PlanCoach

_CON_HISTORIA = (
    "Esa cuenta tiene historia como entrenador en el club (atletas a cargo, "
    "macrociclos o códigos emitidos): liberarla la borraría. Déjala revocada."
)


class RepositorioDeEquipos:
    """El club y sus pertenencias. Ver la cabecera: no lleva `Principal`."""

    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── El club ──────────────────────────────────────────────────────────────

    async def equipo(self, team_id: int) -> Team | None:
        return await self.db.get(Team, team_id)

    async def crear(self, nombre: str, *, confirmar: bool = True) -> Team:
        """Crea el equipo **sin dueño**: todavía no existe ningún miembro al que apuntar.

        Es el arranque en frío (`tools/ops.py crear-equipo`, `seed.py`), no
        una operación del API: no hay endpoint que cree equipos. Con
        `confirmar=False` solo le da id (`flush`): el CLI confirma el club junto
        con la cuenta de su dueño, para que un fallo al crearla no deje un club
        vacío (lo vio el revisor de D1).
        """
        equipo = Team(name=nombre)
        self.db.add(equipo)
        if not confirmar:
            await self.db.flush()
            return equipo
        await self.db.commit()
        await self.db.refresh(equipo)
        return equipo

    def como_equipo(self, fila: Team) -> Equipo:
        return equipo_desde_fila(fila)

    async def guardar_equipo(self, equipo: Equipo) -> Team:
        """Escribe el nombre y el dueño que la entidad decidió, y confirma.

        Hasta el 2026-10-14 eran `renombrar` y `fijar_dueno`, y el segundo
        escribía cualquier id que le llegara: las tres comprobaciones vivían en
        el service. Ahora el dueño solo cambia por `Equipo.transferir_propiedad`.
        """
        fila = await self.db.get(Team, equipo.id) if equipo.id is not None else None
        if fila is None:
            raise LookupError(f"No hay ningún equipo con id {equipo.id}")
        volcar_equipo(equipo, fila)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila

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

    def como_pertenencia(self, fila: TeamMember) -> Pertenencia:
        return pertenencia_desde_fila(fila)

    async def guardar_pertenencia(self, pertenencia: Pertenencia) -> TeamMember:
        """Escribe el rol y el acceso, y confirma. **Confirma la sesión entera**:
        si quien llama cambió algo más en la misma unidad de trabajo (el nombre
        de la cuenta, en `auth/service.update_member`), viaja en el mismo commit.
        """
        fila = (
            await self.db.get(TeamMember, pertenencia.id) if pertenencia.id is not None else None
        )
        if fila is None:
            raise LookupError(f"No hay ninguna pertenencia con id {pertenencia.id}")
        volcar_pertenencia(pertenencia, fila)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila

    async def liberar(self, pertenencia: Pertenencia) -> int | None:
        """Deja la cuenta sin club: desliga su ficha y **borra** la pertenencia.
        Confirma la sesión entera. Devuelve el id de la ficha desligada, si había.

        Es la excepción documentada a «nada se borra» (TODO-26, 2026-10-14):
        `team_members` tiene `UNIQUE(user_id)` y «sin club» es no tener fila, así
        que no hay otra forma de dejar a alguien en el pool sin migrar el esquema.
        El rastro queda en la auditoría (`miembro.liberado`), que no tiene FKs.

        **La ficha se queda en su club**, con su histórico: solo pierde la
        cuenta. Desligarla va **antes** de borrar, porque la FK compuesta
        `swimmers(user_id, team_id) → team_members` lo exige, y además es lo que
        deja a la persona canjear un código en otro club (`swimmers.user_id`
        es único global).

        Quién se puede liberar lo decide `Equipo.admite_liberar`. Esto se niega,
        además, a dos cosas que la entidad no ve: una pertenencia **activa**
        (borrar a alguien con el acceso vivo es echarlo sin que conste que se le
        echó) y una con **historia de entrenador** (`historia_de_entrenador`):
        las tres FKs que la citan son `ON DELETE CASCADE` y se la llevarían.
        """
        if pertenencia.activa:
            raise OperacionDeEquipoImposible(
                "Primero revoca el acceso: solo se libera una pertenencia revocada",
            )
        if any((await self.historia_de_entrenador(pertenencia)).values()):
            raise OperacionDeEquipoImposible(_CON_HISTORIA)
        fila = (
            await self.db.get(TeamMember, pertenencia.id) if pertenencia.id is not None else None
        )
        if fila is None:
            raise LookupError(f"No hay ninguna pertenencia con id {pertenencia.id}")
        ficha = (await self.db.execute(
            select(Swimmer).where(
                Swimmer.user_id == pertenencia.usuario_id,
                Swimmer.team_id == pertenencia.equipo_id,
            ),
        )).scalar_one_or_none()
        if ficha is not None:
            ficha.user_id = None
            await self.db.flush()
        await self.db.delete(fila)
        await self.db.commit()
        return ficha.id if ficha is not None else None

    async def historia_de_entrenador(self, pertenencia: Pertenencia) -> dict[str, int]:
        """Las filas que citan a esta pertenencia **como entrenador**, por tabla.

        Un atleta también puede tenerlas: basta con que antes fuera entrenador
        (el rol se cambia por `PATCH /auth/members`). Las tres FKs son
        `ON DELETE CASCADE` contra `team_members(user_id, team_id)`, así que
        borrar la pertenencia las borraría sin avisar: a quién llevaba, en qué
        macrociclos estaba y los códigos que emitió, gastados incluidos.
        """
        uid, tid = pertenencia.usuario_id, pertenencia.equipo_id
        consultas = {
            "atletas a cargo": select(func.count()).select_from(CoachAthlete).where(
                CoachAthlete.coach_id == uid, CoachAthlete.team_id == tid),
            "macrociclos": select(func.count()).select_from(PlanCoach).where(
                PlanCoach.coach_id == uid, PlanCoach.team_id == tid),
            "códigos emitidos": select(func.count()).select_from(LinkCode).where(
                LinkCode.created_by == uid, LinkCode.team_id == tid),
        }
        return {nombre: (await self.db.execute(c)).scalar_one() for nombre, c in consultas.items()}

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
