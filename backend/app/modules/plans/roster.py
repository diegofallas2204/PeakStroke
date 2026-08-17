"""Quién está inscrito en el macrociclo: meterlo, sacarlo y devolverlo.

La regla de **un atleta, un macrociclo vivo** no está aquí sino en
`enrollment.py`, y la impone el router antes de llamar a `add_athlete` /
`restore_athlete`. Aquí solo está el efecto sobre la inscripción, incluido el
que importa: **sacar a alguien es darle de baja, nunca borrarlo**.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import age_at
from app.dominio.servicios.motor import MOTOR

# Lectura explícita de un modelo de otro módulo (permitido por las reglas del
# proyecto): la edad al inicio del macro sale de la ficha. No se importa lógica.
from app.modules.swimmers.models import Swimmer

from .models import AthleteEvent, AthletePlan, Plan, WeeklyPlan
from .schemas import AddAthleteRequest


async def add_athlete(db: AsyncSession, plan: Plan, data: AddAthleteRequest) -> AthletePlan:
    athlete_plan = AthletePlan(
        plan_id=plan.id, swimmer_id=data.swimmer_id, team_id=plan.team_id,
        aerobic_base=data.aerobic_base, aerobic_base_source=data.aerobic_base_source,
    )
    phases = [
        {"name": p.name, "week_start": p.week_start, "week_end": p.week_end}
        for p in plan.phases
    ]
    # Edad al inicio del macro: ajusta al alza el techo I_max de menores (juventud).
    swimmer = await db.get(Swimmer, data.swimmer_id)
    age = age_at(swimmer.birth_date, plan.start_date) if swimmer else None
    for event_data in data.events:
        event = AthleteEvent(**event_data.model_dump())
        semanas = MOTOR.generar_plan(
            distancia=event.distance, tiempo_actual=event.current_time,
            tiempo_meta=event.goal_time, semanas=plan.total_weeks,
            km_totales=plan.total_km, curva=plan.progression_curve,
            inicio=plan.start_date, semanas_por_micro=plan.weeks_per_micro,
            fases=phases or None, estilo=event.stroke, piscina=plan.pool,
            n_mac=plan.n_mac, edad=age,
        )
        for s in semanas:
            event.weeks.append(WeeklyPlan(
                week_number=s.numero, week_date=s.fecha,
                planned_km=s.km, expected_time=s.tiempo_esperado, phase=s.fase,
            ))
        athlete_plan.events.append(event)
    db.add(athlete_plan)
    await db.commit()
    await db.refresh(athlete_plan)
    return athlete_plan


async def remove_athlete(db: AsyncSession, plan_id: int, athlete_plan_id: int) -> bool:
    """Saca al atleta del macrociclo. **Da de baja la inscripción, no la borra.**

    Hasta el 2026-08-07 hacía `db.delete(ap)`, y `AthletePlan` cascadea a
    `athlete_events` y de ahí a `weekly_plans`: se llevaba las 12 semanas del
    atleta y todos los tiempos reales que había registrado. Reproducido con el
    harness — `weekly_plans` pasaba de 36 filas a 24, incluido un tiempo puesto
    un segundo antes.

    False si no existe o si es de otro macrociclo; el router lo traduce a 404.
    """
    ap = await db.get(AthletePlan, athlete_plan_id)
    if ap is None or ap.plan_id != plan_id or not ap.is_active:
        return False
    ap.is_active = False
    await db.commit()
    return True


async def restore_athlete(db: AsyncSession, plan_id: int, athlete_plan_id: int) -> bool:
    """Vuelve a inscribir a un atleta dado de baja, con su histórico intacto.

    Sin esta puerta, la baja lógica de arriba sería un borrado con otro nombre:
    el dato seguiría en la tabla pero nadie podría recuperarlo desde la
    aplicación.
    """
    ap = await db.get(AthletePlan, athlete_plan_id)
    if ap is None or ap.plan_id != plan_id or ap.is_active:
        return False
    ap.is_active = True
    await db.commit()
    return True
