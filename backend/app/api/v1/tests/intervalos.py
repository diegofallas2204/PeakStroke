"""Tiempos de entrenamiento de un atleta a partir de su test aeróbico.

Un test dice a qué ritmo nada el atleta hoy. La pizarra necesita además cada
cuánto sale, y eso son las zonas más el intervalo
(`dominio/servicios/intervalos.py`).

**Aquí no se calcula ninguna zona.** Las zonas salen de `MOTOR.zonas`
sobre el ritmo de la semana del macrociclo —la única fuente de zonas del
sistema— y este módulo solo elige de qué semana y para qué distancia de
repetición. Derivarlas de la base aeróbica habría evitado depender del
macrociclo, pero al precio de dos respuestas distintas a "¿cuál es la zona R2 de
este atleta?", que es exactamente lo que la regla de fuente única prohíbe.

Sin macrociclo inscrito no hay ritmo de referencia y la respuesta viene con
`zones` vacío: es la verdad, y la interfaz puede decir qué falta para llenarla.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dominio.entidades import Macrociclo
from app.dominio.servicios.intervalos import intervalos_de_entrenamiento
from app.dominio.servicios.motor import MOTOR
from app.dominio.valores import Zona

# De qué semana sale el ritmo lo decide el agregado de planificación, no este
# módulo: su repositorio acota la consulta (`acotar`) y su entidad contesta en
# qué semana va (`semana_actual`). Antes eran tres imports a un módulo hermano
# —la puerta de acceso, cuatro modelos y una regla pura de su `service`—, que es
# P5 del §0. Ahora es una lectura hacia abajo, `api → persistencia → dominio`.
from app.persistencia.mapeo import macrociclo_desde_fila
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, Plan, WeeklyPlan
from app.persistencia.tablas.tests_aerobicos import AerobicTest

from .schemas import (
    TrainingIntervalResponse,
    TrainingIntervalsResponse,
)


async def _reference_event(
    db: AsyncSession, macrociclos: RepositorioDeMacrociclos, test: AerobicTest,
) -> tuple[Plan, AthleteEvent] | None:
    """El macrociclo y la prueba principal del atleta del test, si los tiene.

    Prefiere el macrociclo al que el propio test está colgado; si el test es
    suelto, cae al macrociclo vivo del atleta. En ambos casos pasa por
    `repo.acotar`: que el test sea visible no implica que su macrociclo lo sea.
    """
    stmt = (
        select(Plan, AthleteEvent)
        .join(AthletePlan, AthletePlan.plan_id == Plan.id)
        .join(AthleteEvent, AthleteEvent.athlete_plan_id == AthletePlan.id)
        .where(
            AthletePlan.swimmer_id == test.swimmer_id,
            AthletePlan.is_active.is_(True),
        )
        .options(selectinload(AthleteEvent.weeks))
        .order_by(AthleteEvent.priority, AthleteEvent.id)
    )
    if test.plan_id is not None:
        stmt = stmt.where(Plan.id == test.plan_id)
    filas = (await db.execute(macrociclos.acotar(stmt))).all()
    return filas[0] if filas else None


def _week_pace(macro: Macrociclo, event: AthleteEvent) -> tuple[float, int] | None:
    """Ritmo de carrera /100m de la semana en curso y su número.

    Mismo cálculo que la tabla del equipo: el tiempo efectivo de la semana
    (recalculado si lo hay, esperado si no) llevado a 100m.
    """
    semanas: list[WeeklyPlan] = sorted(event.weeks, key=lambda w: w.week_number)
    if not semanas:
        return None
    numero = macro.semana_actual() or semanas[0].week_number
    semana = next(
        (w for w in semanas if w.week_number == numero),
        min(semanas, key=lambda w: abs(w.week_number - numero)),
    )
    efectivo = semana.recalc_time if semana.recalc_time is not None else semana.expected_time
    return efectivo / (event.distance / 100), semana.week_number


async def training_intervals_for(
    db: AsyncSession, macrociclos: RepositorioDeMacrociclos, test: AerobicTest,
    rep_distance: int = 100,
) -> TrainingIntervalsResponse:
    """Ritmo + salida por zona para las repeticiones que pida el entrenador."""
    medido = _measured_ratio(test)
    base = TrainingIntervalsResponse(
        test_id=test.id, rep_distance=rep_distance, measured_ratio=medido,
    )

    par = await _reference_event(db, macrociclos, test)
    if par is None:
        return base
    plan, event = par
    macro = macrociclo_desde_fila(plan)
    ref = _week_pace(macro, event)
    if ref is None:
        return base
    pace, week_number = ref

    zonas = MOTOR.zonas(pace, event.distance, event.stroke, macro.piscina.value)
    intervalos = intervalos_de_entrenamiento(
        {z.value: (zonas[z.value] or {}).get("mid") for z in Zona.ordenadas()},
        distancia_rep=rep_distance,
        ratio_medido=medido,
    )
    base.reference_pace = round(pace, 2)
    base.reference_week = week_number
    base.event_label = f"{event.distance}m {event.stroke}"
    base.zones = [
        TrainingIntervalResponse(
            zone=iv.zona, label=Zona(iv.zona).etiqueta,
            pace_100=iv.ritmo_100, work=iv.trabajo, rest=iv.descanso,
            interval=iv.salida, rest_ratio=iv.ratio_descanso,
            measured_interval=iv.salida_medida,
            denser_than_measured=iv.mas_denso_que_lo_medido,
        )
        for iv in intervalos.values()
    ]
    return base


def _measured_ratio(test: AerobicTest) -> float | None:
    """Descanso : trabajo que el atleta sostuvo en el test, si lo registró."""
    if test.send_off is None or not test.splits:
        return None
    trabajo = sum(s.split_time for s in test.splits) / len(test.splits)
    if trabajo <= 0:
        return None
    return round((test.send_off - trabajo) / trabajo, 4)
