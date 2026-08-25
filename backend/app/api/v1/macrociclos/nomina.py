"""Quién está inscrito en el macrociclo: meterlo, sacarlo y devolverlo.

La regla de **un atleta, un macrociclo vivo** no está aquí sino en
`inscripcion.py`, y la impone el router antes de llamar a `add_athlete` /
`restore_athlete`. Aquí solo está el efecto sobre la inscripción, incluido el
que importa: **sacar a alguien es darle de baja, nunca borrarlo**.

Entra un `Macrociclo`, no una fila: la generación del plan necesita sus fases,
sus semanas y su piscina, y todo eso ya viene dentro de la entidad. Lo que sale
sigue siendo una fila (`AthletePlan`) porque `Inscripcion` (§5.6) todavía no
está construida.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import age_at
from app.dominio.entidades import Macrociclo
from app.dominio.servicios.motor import MOTOR
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, WeeklyPlan

from .schemas import AddAthleteRequest


async def add_athlete(
    db: AsyncSession, repo: RepositorioDeMacrociclos,
    macro: Macrociclo, data: AddAthleteRequest,
) -> AthletePlan:
    athlete_plan = AthletePlan(
        plan_id=macro.id, swimmer_id=data.swimmer_id, team_id=macro.equipo_id,
        aerobic_base=data.aerobic_base, aerobic_base_source=data.aerobic_base_source,
    )
    phases = [
        {"name": f.nombre, "week_start": f.semana_inicio, "week_end": f.semana_fin}
        for f in macro.fases
    ]
    # Edad al inicio del macro: ajusta al alza el techo I_max de menores (juventud).
    swimmer = await db.get(Swimmer, data.swimmer_id)
    age = age_at(swimmer.birth_date, macro.inicio) if swimmer else None
    for event_data in data.events:
        event = AthleteEvent(**event_data.model_dump())
        semanas = MOTOR.generar_plan(
            distancia=event.distance, tiempo_actual=event.current_time,
            tiempo_meta=event.goal_time, semanas=macro.semanas,
            km_totales=macro.km_totales, curva=macro.curva,
            inicio=macro.inicio, semanas_por_micro=macro.semanas_por_micro,
            fases=phases or None, estilo=event.stroke, piscina=macro.piscina.value,
            n_mac=macro.n_mac, edad=age,
            # El nivel sale del test aeróbico cuando la inscripción lo trae: es
            # el dato para el que la tabla de niveles está calibrada. Derivarlo
            # del ritmo de carrera deja un borde de una décima que mueve el
            # volumen un 45 % (defecto 1 de §10.4).
            base_aerobica=data.aerobic_base,
        )
        for s in semanas:
            event.weeks.append(WeeklyPlan(
                week_number=s.numero, week_date=s.fecha,
                planned_km=s.km, expected_time=s.tiempo_esperado, phase=s.fase,
            ))
        athlete_plan.events.append(event)
    await repo.guardar(athlete_plan)
    await db.refresh(athlete_plan)
    return athlete_plan


async def remove_athlete(
    repo: RepositorioDeMacrociclos, plan_id: int, athlete_plan_id: int,
) -> bool:
    """Saca al atleta del macrociclo. **Da de baja la inscripción, no la borra.**

    Hasta el 2026-08-07 hacía `db.delete(ap)`, y `AthletePlan` cascadea a
    `athlete_events` y de ahí a `weekly_plans`: se llevaba las 12 semanas del
    atleta y todos los tiempos reales que había registrado. Reproducido con el
    harness — `weekly_plans` pasaba de 36 filas a 24, incluido un tiempo puesto
    un segundo antes.

    False si no existe o si es de otro macrociclo; el router lo traduce a 404.
    """
    ap = await repo.inscripcion(athlete_plan_id)
    if ap is None or ap.plan_id != plan_id or not ap.is_active:
        return False
    ap.is_active = False
    await repo.confirmar()
    return True


async def restore_athlete(
    repo: RepositorioDeMacrociclos, plan_id: int, athlete_plan_id: int,
) -> bool:
    """Vuelve a inscribir a un atleta dado de baja, con su histórico intacto.

    Sin esta puerta, la baja lógica de arriba sería un borrado con otro nombre:
    el dato seguiría en la tabla pero nadie podría recuperarlo desde la
    aplicación.
    """
    ap = await repo.inscripcion(athlete_plan_id)
    if ap is None or ap.plan_id != plan_id or ap.is_active:
        return False
    ap.is_active = True
    await repo.confirmar()
    return True
