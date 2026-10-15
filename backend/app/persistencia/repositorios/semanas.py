"""Las semanas de una prueba objetivo: leerlas con su contexto y guardarlas (C9, 2026-10-13).

**No es otro agregado.** La semana cuelga de la prueba, que cuelga de la
inscripción, que cuelga del macrociclo (§5.4, raíz del agregado de
planificación). Por eso este repositorio **compone** al de macrociclos, como el
de inscripciones, y lo que deja ver de una semana es lo que su macrociclo deja
ver: `macros.semana()` y `macros.prueba()` siguen siendo la única comprobación
de acceso, con sus dos filtros (el club y el atleta).

Hasta este punto de C9, `api/v1/macrociclos/semanas.py` recibía las filas y las
escribía él: `week.disabled = …`, `w.recalc_time = …`, y un `repo.confirmar()`
al final. Ahora recibe un `PlanDePrueba` —entidades— y devuelve las semanas a
`guardar`, que escribe **solo lo que una semana puede cambiar**.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select

from app.dominio.entidades import Atleta, Inscripcion, Macrociclo, PruebaObjetivo, Semana
from app.persistencia.mapeo import (
    atleta_desde_fila,
    inscripcion_desde_fila,
    macrociclo_desde_fila,
    prueba_objetivo_desde_fila,
    semana_desde_fila,
)
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, Plan, WeeklyPlan

from .macrociclos import RepositorioDeMacrociclos


@dataclass(frozen=True, slots=True)
class PlanDePrueba:
    """Las semanas de una prueba y todo lo que hace falta para leerlas o recalcularlas.

    No es una entidad: es lo que el repositorio entrega junto para que quien
    pinta la tabla o reancla la curva no tenga que ir a por el macrociclo (la
    piscina, la curva, las fases), la inscripción (el atleta, su base aeróbica)
    y la ficha (la edad, la especialidad) por separado.
    """

    macro: Macrociclo
    inscripcion: Inscripcion
    atleta: Atleta
    prueba: PruebaObjetivo
    semanas: tuple[Semana, ...]        # en orden de número

    def semana(self, semana_id: int) -> Semana | None:
        return next((s for s in self.semanas if s.id == semana_id), None)


class RepositorioDeSemanas:
    """Las semanas que alcanza quien pregunta, a través de su macrociclo."""

    __slots__ = ("macros",)

    def __init__(self, macros: RepositorioDeMacrociclos) -> None:
        self.macros = macros

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def plan_de(self, prueba_id: int) -> PlanDePrueba | None:
        """El plan de esa prueba. `None` si no es visible (el router: 404)."""
        fila = await self.macros.prueba(prueba_id)
        return await self._plan(fila) if fila is not None else None

    async def plan_de_la_semana(self, semana_id: int) -> PlanDePrueba | None:
        """El plan de la prueba a la que pertenece esa semana. `None` es 404.

        La comprobación de acceso es la de la **semana** (`macros.semana`): su
        macrociclo visible, su inscripción activa y, si pregunta un atleta, que
        sea la suya. A partir de ahí la prueba se lee sin volver a filtrar.
        """
        semana = await self.macros.semana(semana_id)
        if semana is None:
            return None
        fila = await self.macros.prueba_sin_acotar(semana.athlete_event_id)
        return await self._plan(fila) if fila is not None else None

    async def _plan(self, fila: AthleteEvent) -> PlanDePrueba:
        inscripcion = fila.athlete_plan
        # La ficha de una inscripción a la que ya se tiene acceso. Lleva el
        # equipo en la condición aunque la FK compuesta ya lo garantice: ninguna
        # lectura de este repositorio sale sin él. Sin `is_active`: una ficha de
        # baja sigue teniendo su plan.
        ficha = (await self.macros.db.execute(select(Swimmer).where(
            Swimmer.id == inscripcion.swimmer_id,
            Swimmer.team_id == self.macros.principal.team_id,
        ))).scalar_one()
        return PlanDePrueba(
            macro=macrociclo_desde_fila(inscripcion.plan),
            inscripcion=inscripcion_desde_fila(inscripcion),
            atleta=atleta_desde_fila(ficha),
            prueba=prueba_objetivo_desde_fila(fila),
            semanas=tuple(sorted(
                (semana_desde_fila(w) for w in fila.weeks), key=lambda s: s.numero,
            )),
        )

    # ── Escritura ────────────────────────────────────────────────────────────

    async def guardar(self, semanas: Iterable[Semana]) -> None:
        """Guarda el estado de esas semanas y confirma lo que haya en la sesión.

        Escribe **solo lo que la entidad puede cambiar**: el tiempo recalculado,
        el parón y su razón. El tiempo esperado, la fecha, los kilómetros y la
        fase se fijaron al inscribir y no tienen quien los mueva: aunque la
        entidad llegara con otro `esperado`, la curva ideal de la base no cambia.

        Las filas se releen acotadas, con los mismos filtros que `macros.semana`.
        Una semana que no sea visible para quien escribe no se salta en
        silencio: `LookupError`, porque llegar aquí con una es un error de
        programación y no una petición que responder con 404.
        """
        por_id = {s.id: s for s in semanas}
        stmt = self.macros.acotar(
            select(WeeklyPlan)
            .join(AthleteEvent, AthleteEvent.id == WeeklyPlan.athlete_event_id)
            .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
            .join(Plan, Plan.id == AthletePlan.plan_id)
            .where(WeeklyPlan.id.in_(por_id), AthletePlan.is_active.is_(True)),
        )
        stmt = self.macros.principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)
        filas = list((await self.macros.db.execute(stmt)).scalars())
        if len(filas) != len(por_id):
            ajenas = sorted(set(por_id) - {f.id for f in filas}, key=str)
            raise LookupError(f"Semanas que no se pueden escribir desde aquí: {ajenas}")
        for fila in filas:
            semana = por_id[fila.id]
            fila.recalc_time = semana.recalculado.segundos if semana.recalculado else None
            fila.disabled = semana.deshabilitada
            fila.disable_reason = semana.razon
        await self.macros.db.commit()
