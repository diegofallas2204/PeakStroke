"""Las semanas de una prueba: cómo se pintan y qué pasa al apuntar un tiempo.

Apuntar un tiempo real no cambia solo esa semana: reancla la curva restante al
último tiempo registrado (`_recalculate_event`). Por eso las tres funciones
viven juntas — leer `update_week` sin el recálculo debajo cuenta media historia.

**La curva ideal (`expected_time`) no se toca nunca.** Lo que se reescribe es
`recalc_time`, que es una segunda columna: sin esa separación no habría contra
qué comparar el progreso.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import age_at
from app.core.dependencies import Principal
from app.engine import progression
from app.engine.zones import calc_zones, zone_km_distribution

# Lectura explícita de un modelo de otro módulo (permitido por las reglas del
# proyecto). No se importa lógica ajena.
from app.modules.swimmers.models import Swimmer

from .access import event_unscoped, get_week
from .models import AthleteEvent
from .schemas import WeekResponse, WeekUpdateRequest


async def event_weeks_response(db: AsyncSession, event: AthleteEvent) -> list[WeekResponse]:
    swimmer = await db.get(Swimmer, event.athlete_plan.swimmer_id)
    specialty = swimmer.specialty if swimmer else "medio_fondo"
    pool = event.athlete_plan.plan.pool
    comp_weeks = {c.week_number for c in event.athlete_plan.plan.competitions}
    result = []
    for w in sorted(event.weeks, key=lambda x: x.week_number):
        effective = w.recalc_time if w.recalc_time is not None else w.expected_time
        pace = effective / (event.distance / 100)
        status = diff_s = diff_p = None
        if w.real_time is not None:
            status = progression.performance_status(w.real_time, w.expected_time)
            diff_s = round(w.real_time - w.expected_time, 2)
            diff_p = round((w.real_time - w.expected_time) / w.expected_time * 100, 2)
        result.append(WeekResponse(
            id=w.id, week_number=w.week_number, week_date=w.week_date,
            date_label=w.week_date.strftime("%d/%m"),
            planned_km=w.planned_km, expected_time=w.expected_time,
            recalc_time=w.recalc_time, pace_100m=round(pace, 2),
            zones=calc_zones(pace, event.distance, event.stroke, pool),
            zone_km=zone_km_distribution(w.planned_km, distance=event.distance, specialty=specialty),
            real_time=w.real_time, status=status,
            diff_seconds=diff_s, diff_percent=diff_p,
            phase=w.phase, disabled=w.disabled, disable_reason=w.disable_reason,
            is_competition=w.week_number in comp_weeks,
        ))
    return result


async def update_week(
    db: AsyncSession, week_id: int, data: WeekUpdateRequest, principal: Principal,
) -> AthleteEvent | None:
    """None —y el router lo traduce a 404— si esa semana no le corresponde.

    `access.get_week` es la única comprobación de acceso de todo el camino: a
    partir de ahí las recargas son `event_unscoped`, porque volver a filtrar lo
    que ya se autorizó solo añade sitios donde equivocarse.
    """
    week = await get_week(db, week_id, principal)
    if week is None:
        return None
    if data.clear_real_time:
        week.real_time = None
    elif data.real_time is not None:
        week.real_time = data.real_time
    if data.disabled is not None:
        week.disabled = data.disabled
        week.disable_reason = data.disable_reason if data.disabled else None
    await db.commit()

    event = await event_unscoped(db, week.athlete_event_id)
    if event is None:
        return None
    await _recalculate_event(db, event)
    # Segunda recarga: `_recalculate_event` reescribe `recalc_time` de todas las
    # semanas, y la respuesta tiene que salir con esos valores ya puestos.
    return await event_unscoped(db, event.id)


async def _recalculate_event(db: AsyncSession, event: AthleteEvent) -> None:
    """Recalcula la curva restante anclada al último tiempo real registrado.

    Las semanas con parón no progresan; la mejora restante se redistribuye
    entre las semanas activas. La curva ideal original no se modifica.
    """
    weeks = sorted(event.weeks, key=lambda w: w.week_number)
    real_weeks = [w for w in weeks if w.real_time is not None]
    disabled = {w.week_number for w in weeks if w.disabled}

    if not real_weeks and not disabled:
        for w in weeks:
            w.recalc_time = None
        await db.commit()
        return

    if real_weeks:
        anchor = max(real_weeks, key=lambda w: w.week_number)
        anchor_week, anchor_time = anchor.week_number, anchor.real_time
    else:
        anchor_week, anchor_time = 0, event.current_time

    plan = event.athlete_plan.plan
    swimmer = await db.get(Swimmer, event.athlete_plan.swimmer_id)
    age = age_at(swimmer.birth_date, plan.start_date) if swimmer else None
    entries = [
        progression.WeekEntry(
            week_number=w.week_number, week_date=w.week_date,
            expected_time=w.expected_time, pace_100m=0.0, planned_km=w.planned_km,
            phase=w.phase, improvement_vs_prev=0.0, cumulative_improvement=0.0,
        )
        for w in weeks
    ]
    progression.recalculate_remaining(
        entries, from_week=anchor_week + 1, anchor_time=float(anchor_time),
        goal_time=event.goal_time, curve=plan.progression_curve,
        distance=event.distance, disabled_weeks=disabled, stroke=event.stroke,
        pool=plan.pool, n_mac=plan.n_mac, age=age,
    )
    recalc_map = {e.week_number: e.expected_time for e in entries
                  if e.week_number > anchor_week}
    for w in weeks:
        w.recalc_time = recalc_map.get(w.week_number)
    await db.commit()
