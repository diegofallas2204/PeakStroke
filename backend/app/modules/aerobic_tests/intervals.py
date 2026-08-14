"""Tiempos de entrenamiento de un atleta a partir de su test aeróbico.

Un test dice a qué ritmo nada el atleta hoy. La pizarra necesita además cada
cuánto sale, y eso son las zonas más el intervalo (`engine/send_off.py`).

**Aquí no se calcula ninguna zona.** Las zonas salen de `engine/zones.calc_zones`
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

from app.core.dependencies import Principal
from app.engine.send_off import ZONE_ORDER, training_intervals
from app.engine.zones import ZONE_LABELS, calc_zones

# Lectura explícita de la puerta de acceso y de los modelos de `plans`
# (permitido por las reglas del proyecto): de qué semana sale el ritmo lo decide
# ese módulo, no este. Duplicar `visible_to` aquí sería tener dos respuestas.
from app.modules.plans.access import visible_to
from app.modules.plans.models import AthleteEvent, AthletePlan, Plan, WeeklyPlan
from app.modules.plans.service import current_week_of

from .models import AerobicTest
from .schemas import (
    TrainingIntervalResponse,
    TrainingIntervalsResponse,
)


async def _reference_event(
    db: AsyncSession, test: AerobicTest, principal: Principal,
) -> tuple[Plan, AthleteEvent] | None:
    """El macrociclo y la prueba principal del atleta del test, si los tiene.

    Prefiere el macrociclo al que el propio test está colgado; si el test es
    suelto, cae al macrociclo vivo del atleta. En ambos casos pasa por
    `visible_to`: que el test sea visible no implica que su macrociclo lo sea.
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
    filas = (await db.execute(visible_to(stmt, principal))).all()
    return filas[0] if filas else None


def _week_pace(plan: Plan, event: AthleteEvent) -> tuple[float, int] | None:
    """Ritmo de carrera /100m de la semana en curso y su número.

    Mismo cálculo que la tabla del equipo: el tiempo efectivo de la semana
    (recalculado si lo hay, esperado si no) llevado a 100m.
    """
    semanas: list[WeeklyPlan] = sorted(event.weeks, key=lambda w: w.week_number)
    if not semanas:
        return None
    numero = current_week_of(plan) or semanas[0].week_number
    semana = next(
        (w for w in semanas if w.week_number == numero),
        min(semanas, key=lambda w: abs(w.week_number - numero)),
    )
    efectivo = semana.recalc_time if semana.recalc_time is not None else semana.expected_time
    return efectivo / (event.distance / 100), semana.week_number


async def training_intervals_for(
    db: AsyncSession, test: AerobicTest, principal: Principal,
    rep_distance: int = 100,
) -> TrainingIntervalsResponse:
    """Ritmo + salida por zona para las repeticiones que pida el entrenador."""
    medido = _measured_ratio(test)
    base = TrainingIntervalsResponse(
        test_id=test.id, rep_distance=rep_distance, measured_ratio=medido,
    )

    par = await _reference_event(db, test, principal)
    if par is None:
        return base
    plan, event = par
    ref = _week_pace(plan, event)
    if ref is None:
        return base
    pace, week_number = ref

    zonas = calc_zones(pace, event.distance, event.stroke, plan.pool)
    intervalos = training_intervals(
        {z: (zonas[z] or {}).get("mid") for z in ZONE_ORDER},
        rep_distance=rep_distance,
        measured_ratio=medido,
    )
    base.reference_pace = round(pace, 2)
    base.reference_week = week_number
    base.event_label = f"{event.distance}m {event.stroke}"
    base.zones = [
        TrainingIntervalResponse(
            zone=iv.zone, label=ZONE_LABELS.get(iv.zone, iv.zone),
            pace_100=iv.pace_100, work=iv.work, rest=iv.rest,
            interval=iv.interval, rest_ratio=iv.rest_ratio,
            measured_interval=iv.measured_interval,
            denser_than_measured=iv.denser_than_measured,
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
