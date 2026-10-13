"""El agregado de planificación: quién ve qué macrociclo y por dónde se lee.

Era `modules/plans/access.py`, y sigue siendo **la única puerta** a los
macrociclos y a todo lo que cuelga de ellos. Lo que cambia con el paso 5 es la
altura a la que está la puerta y lo que sale por ella: antes, para saber en qué
semana iba un plan, el tablero importaba `plans.service.current_week_of` y
cuatro modelos de `plans` —dos módulos que se leen el uno al otro no son dos
módulos—; ahora recibe un `Macrociclo` que ya lo sabe.

Dos filtros, y hay que pasar los dos:

    acotar()                 ──▶  ¿es un macrociclo que te toca?      (el club)
    scope_to_own_swimmer()   ──▶  ¿es TU fila dentro de él?           (el atleta)

El segundo se añadió el 2026-08-06. `acotar` deja pasar el plan entero a
cualquiera inscrito en él, así que por sí solo permitía que un atleta leyera y
sobrescribiera las semanas de sus compañeros.

**Por qué algunos métodos devuelven filas y no entidades.** `Semana` (§5.8) no
existe todavía: es el punto 4 de C9. La `Inscripcion` es entidad desde el
2026-10-05 (`inscripciones.py`) y la `PruebaObjetivo` desde el 2026-10-13, pero
quien lee una prueba casi siempre viene a por sus semanas, así que `prueba()` y
`pruebas_de()` siguen devolviendo la fila con sus `weeks` cargadas; quien solo
quiere la prueba la traduce con `mapeo.prueba_objetivo_desde_fila`. El
macrociclo en sí **siempre** sale como entidad.
"""
from __future__ import annotations

from sqlalchemy import false, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.principal import Principal
from app.dominio.entidades import Macrociclo
from app.dominio.roles import Alcance
from app.dominio.valores import EstadoDeMacro
from app.persistencia.mapeo import macrociclo_desde_fila
from app.persistencia.tablas.planes import (
    AthleteEvent,
    AthletePlan,
    Plan,
    PlanCoach,
    WeeklyPlan,
)
from app.persistencia.tablas.tests_aerobicos import AerobicTest

_PLAN_LOAD = (
    selectinload(Plan.phases),
    selectinload(Plan.competitions),
    selectinload(Plan.athlete_plans).selectinload(AthletePlan.events),
)

_EVENT_LOAD = (
    selectinload(AthleteEvent.weeks),
    selectinload(AthleteEvent.athlete_plan).selectinload(AthletePlan.plan)
    .selectinload(Plan.competitions),
    # Las fases, porque la semana guarda la clave y la tabla enseña el nombre
    # que el entrenador le puso al tramo.
    selectinload(AthleteEvent.athlete_plan).selectinload(AthletePlan.plan)
    .selectinload(Plan.phases),
)


class RepositorioDeMacrociclos:
    """Los macrociclos que alcanza un `Principal`, y nada más.

    Se construye por petición con la sesión y la identidad. Que el alcance sea un
    campo del objeto y no un argumento de cada método es a propósito: un
    parámetro que se puede omitir se acaba omitiendo, y así fue como el filtro
    por nadador tardó en llegar a la mitad de las consultas.
    """

    __slots__ = ("db", "principal")

    def __init__(self, db: AsyncSession, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    # ── El filtro ────────────────────────────────────────────────────────────

    def acotar(self, stmt):
        """El primero de los dos filtros: los macrociclos que le tocan.

        No pregunta por el rol sino por su **alcance**, y quién cae en cuál lo
        decide la jerarquía de `Rol`, no un `if` de aquí. `TODOS` es el dueño
        —sin esa excepción, los macrociclos de un entrenador que se va no los
        rescataría nadie—, `LOS_MIOS` el entrenador (`plan_coaches`) y `SOLO_YO`
        el atleta (donde esté inscrito).

        Es público porque hay consultas que no son de macrociclos pero sí tienen
        que respetar su alcance: `aerobic_tests` busca el macrociclo de
        referencia de un test y pasa su propio `select` por aquí. Duplicar el
        filtro allí sería tener dos respuestas a la misma pregunta.

        El caso final no es una caída permisiva sino la contraria: un alcance que
        este método no sepa traducir a una consulta no ve NADA.
        """
        stmt = stmt.where(Plan.team_id == self.principal.team_id)
        alcance = self.principal.rol.alcance_de_macrociclos()
        if alcance is Alcance.TODOS:
            return stmt

        if alcance is Alcance.LOS_MIOS:
            suyos = select(PlanCoach.plan_id).where(PlanCoach.coach_id == self.principal.id)
        elif alcance is Alcance.SOLO_YO and self.principal.swimmer_id is not None:
            # El nadador sale del `Principal`, que ya lo resolvió llevando el
            # equipo en la condición del join. Antes se derivaba aquí otra vez
            # con `Swimmer.user_id == principal.id` a secas: dos funciones
            # respondiendo la misma pregunta con semánticas distintas, que es el
            # patrón que produjo el agujero del scoping. Coincidían solo porque
            # `Swimmer.user_id` es UNIQUE global, y `teams/models.py` anticipa
            # quitar la restricción de un-usuario-un-equipo.
            suyos = select(AthletePlan.plan_id).where(
                AthletePlan.swimmer_id == self.principal.swimmer_id,
                # A quien sacaron del macrociclo deja de vérselo, aunque su
                # histórico siga en la tabla.
                AthletePlan.is_active.is_(True),
            )
        else:
            # Atleta sin ficha de nadador (no está inscrito en ningún macrociclo,
            # y decirlo explícitamente evita una consulta que no puede devolver
            # nada) y, con él, `NINGUNO` y cualquier alcance futuro. Fallar
            # cerrado.
            return stmt.where(false())
        return stmt.where(Plan.id.in_(suyos))

    # ── El macrociclo, como entidad ──────────────────────────────────────────

    async def por_id(self, plan_id: int) -> Macrociclo | None:
        """`None` si no existe **o** si el solicitante no debe verlo.

        Ambos casos se responden con 404: un 403 confirmaría que ese macrociclo
        existe en algún equipo.
        """
        fila = await self.fila_de(plan_id)
        return macrociclo_desde_fila(fila) if fila is not None else None

    async def activo(self) -> Macrociclo | None:
        """El macrociclo vigente más reciente **de los que alcanza**."""
        fila = await self._fila_del_activo()
        return macrociclo_desde_fila(fila) if fila is not None else None

    async def recargar(self, plan_id: int) -> Macrociclo:
        """Relee un macrociclo **cuyo acceso ya está comprobado**, tras escribir."""
        return macrociclo_desde_fila(await self.fila_sin_acotar(plan_id))

    # ── El macrociclo, como fila ─────────────────────────────────────────────
    #
    # Mientras `Semana` no sea entidad (punto 4 de C9), quien necesite la nómina
    # con sus semanas necesita la fila con sus relaciones cargadas.

    async def filas(self) -> list[Plan]:
        stmt = self.acotar(select(Plan).options(*_PLAN_LOAD))
        return list((await self.db.execute(stmt.order_by(Plan.created_at.desc()))).scalars())

    async def fila_de(self, plan_id: int) -> Plan | None:
        stmt = self.acotar(select(Plan).options(*_PLAN_LOAD).where(Plan.id == plan_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _fila_del_activo(self) -> Plan | None:
        stmt = self.acotar(
            select(Plan).where(Plan.status == EstadoDeMacro.ACTIVO.value),
        ).order_by(Plan.created_at.desc())
        fila = (await self.db.execute(stmt)).scalars().first()
        if fila is None:
            return None
        # Segunda pasada para traer las relaciones. La primera ordena sobre la
        # tabla pelada a propósito: cargarlo todo para descartar n-1 planes es
        # trabajo tirado.
        return await self.fila_de(fila.id)

    async def fila_sin_acotar(self, plan_id: int) -> Plan:
        """Recarga interna tras escribir, **cuando el acceso ya está comprobado**."""
        stmt = select(Plan).options(*_PLAN_LOAD).where(Plan.id == plan_id)
        return (await self.db.execute(stmt)).scalar_one()

    # ── Lo que cuelga del macrociclo ─────────────────────────────────────────

    async def prueba(self, event_id: int) -> AthleteEvent | None:
        """Prueba objetivo de un atleta dentro de un plan, solo si le es visible.

        Impide el acceso directo por id: las pruebas y las semanas se piden por
        su propio identificador, sin mencionar el plan, así que sin esto bastaría
        con probar números para leer los datos de otro club.
        """
        stmt = self.acotar(
            select(AthleteEvent).options(*_EVENT_LOAD)
            .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
            .join(Plan, Plan.id == AthletePlan.plan_id)
            .where(AthleteEvent.id == event_id, AthletePlan.is_active.is_(True)),
        )
        stmt = self.principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def prueba_sin_acotar(self, event_id: int) -> AthleteEvent | None:
        """Recarga interna tras escribir, **cuando el acceso ya está comprobado**.

        No la llames desde un router: para eso está `prueba()`.
        """
        stmt = select(AthleteEvent).options(*_EVENT_LOAD).where(AthleteEvent.id == event_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def semana(self, week_id: int) -> WeeklyPlan | None:
        """Semana concreta, solo si su macrociclo **y su atleta** le corresponden.

        La segunda condición es la que faltaba, y es la que más caro salía:
        escribir el tiempo real de un compañero dispara el recálculo, que le
        reescribe la curva de progresión entera. El plan de entrenamiento de una
        persona, borrado por otra.
        """
        stmt = self.acotar(
            select(WeeklyPlan)
            .join(AthleteEvent, AthleteEvent.id == WeeklyPlan.athlete_event_id)
            .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
            .join(Plan, Plan.id == AthletePlan.plan_id)
            .where(WeeklyPlan.id == week_id, AthletePlan.is_active.is_(True)),
        )
        stmt = self.principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def pruebas_de(self, plan_id: int) -> list[AthleteEvent]:
        """Las pruebas del macrociclo que le tocan a quien pregunta.

        Punto único de acotación de las vistas: el resumen y la tabla del equipo
        salen los dos de aquí, así que el filtro por nadador no puede quedarse a
        medias en uno y puesto en el otro. `is_active` porque un atleta al que
        sacaron conserva su histórico pero no vuelve a aparecer.
        """
        stmt = (
            select(AthleteEvent)
            .join(AthletePlan, AthleteEvent.athlete_plan_id == AthletePlan.id)
            .options(
                selectinload(AthleteEvent.weeks),
                selectinload(AthleteEvent.athlete_plan),
            )
            .where(AthletePlan.plan_id == plan_id, AthletePlan.is_active.is_(True))
            .order_by(AthleteEvent.priority)
        )
        stmt = self.principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)
        return list((await self.db.execute(stmt)).scalars())

    # Las inscripciones (`inscripcion`, `inscritos_en`, `inscripciones_vivas`)
    # se mudaron a `inscripciones.py` el 2026-10-05 (C9): este archivo pasaba
    # de 300 líneas y esa era su división natural.

    # ── Escritura ────────────────────────────────────────────────────────────

    async def guardar(self, fila: Plan) -> None:
        self.db.add(fila)
        await self.db.commit()

    async def confirmar(self) -> None:
        """Persiste lo que ya está en la sesión.

        Es lo poco que hoy se puede con las semanas: `Semana` no es entidad
        todavía (§5.8, punto 4 de C9). `Inscripcion` y `PruebaObjetivo` ya lo
        son y se guardan por `RepositorioDeInscripciones.guardar`.
        """
        await self.db.commit()

    async def tests_que_bloquean_el_borrado(self, plan_id: int) -> int:
        """Cuántos tests aeróbicos impiden borrar ese macrociclo.

        `fk_aerobic_tests_plan_in_team` no lleva `ondelete`, así que la base de
        datos rechaza el borrado con un `IntegrityError` y el entrenador recibía
        un 500 con una traza — y solo cuando el dato lo provocaba, con lo que
        aparecía en producción y no al desarrollar. Contar antes en vez de
        capturar la excepción es a propósito: el número es lo que hace accionable
        el mensaje ("tiene 12 tests asociados"), y de un `IntegrityError` no se
        puede sacar.
        """
        return (await self.db.execute(
            select(func.count()).select_from(AerobicTest)
            .where(AerobicTest.plan_id == plan_id)
        )).scalar_one()

    async def borrar(self, fila: Plan) -> None:
        await self.db.delete(fila)
        await self.db.commit()
