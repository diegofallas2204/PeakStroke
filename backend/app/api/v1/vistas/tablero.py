"""Agregaciones del tablero: estado del equipo, progresión y cumplimiento.

**Esto es una vista, no un módulo de dominio.** No tiene modelo, no escribe y no
impone ninguna regla: pide al repositorio de macrociclos lo que necesita y le da
forma. Cuando vivía en `modules/dashboard/` importaba `plans.access`,
`plans.service` y tres modelos de `plans` —P5 del §0— y lo hacía por una razón
que ya no existe: necesitaba `current_week_of(plan)` para saber en qué semana
iba el macrociclo. Ahora recibe un `Macrociclo` y se lo pregunta a él.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.entidades import Macrociclo
from app.dominio.servicios.kilometraje import km_por_zona
from app.dominio.servicios.motor import MOTOR
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import AthleteEvent

from .schemas import (
    AthleteStatusRow,
    CompetitionInfo,
    DashboardSummary,
    PhaseStrip,
    TeamWeekPoint,
    TeamWeekResponse,
    TeamWeekZones,
)

_STROKE_LABELS = {
    "libre": "Libre", "espalda": "Espalda", "pecho": "Pecho",
    "mariposa": "Mariposa", "combinado": "Combinado",
}


def event_label(event: AthleteEvent) -> str:
    return f"{event.distance}m {_STROKE_LABELS.get(event.stroke, event.stroke)}"


async def _swimmers_for(db: AsyncSession, events: list[AthleteEvent]) -> dict[int, Swimmer]:
    ids = {e.athlete_plan.swimmer_id for e in events}
    if not ids:
        return {}
    rows = (await db.execute(select(Swimmer).where(Swimmer.id.in_(ids)))).scalars()
    return {s.id: s for s in rows}


async def build_summary(
    db: AsyncSession, repo: RepositorioDeMacrociclos, macro: Macrociclo,
) -> DashboardSummary:
    """El estado del macrociclo, acotado a quien pregunta.

    Hasta el 2026-08-06 no recibía el `Principal` y por eso le enseñaba al atleta
    las ocho filas del club con nombre y tiempo de cada uno. Hoy el alcance viaja
    dentro del repositorio y no hay forma de pedir las pruebas sin él.
    """
    current = macro.semana_actual()
    events = await repo.pruebas_de(macro.id)
    swimmers = await _swimmers_for(db, events)

    statuses: list[AthleteStatusRow] = []
    counts = {"ahead": 0, "on_track": 0, "behind": 0, "pending": 0}
    deviations: list[float] = []
    weeks_passed = 0
    weeks_with_real = 0

    for event in events:
        swimmer = swimmers.get(event.athlete_plan.swimmer_id)
        weeks = sorted(event.weeks, key=lambda w: w.week_number)
        cur = next((w for w in weeks if w.week_number == current), None)
        reals = [w for w in weeks if w.real_time is not None]
        last_real = max(reals, key=lambda w: w.week_number) if reals else None

        if current:
            past = [w for w in weeks if w.week_number <= current and not w.disabled]
            weeks_passed += len(past)
            weeks_with_real += sum(1 for w in past if w.real_time is not None)
        for w in reals:
            deviations.append((w.real_time - w.expected_time) / w.expected_time * 100)

        status = "pending"
        if cur is not None and cur.real_time is not None:
            status = MOTOR.estado_de_rendimiento(cur.real_time, cur.expected_time)
        elif last_real is not None:
            status = MOTOR.estado_de_rendimiento(last_real.real_time, last_real.expected_time)
        counts[status] = counts.get(status, 0) + 1

        total_improvement = event.current_time - event.goal_time
        progress = 0.0
        if last_real is not None and total_improvement > 0:
            progress = (event.current_time - last_real.real_time) / total_improvement * 100
        statuses.append(AthleteStatusRow(
            athlete_plan_id=event.athlete_plan_id, swimmer_id=event.athlete_plan.swimmer_id,
            event_id=event.id, name=swimmer.name if swimmer else "—",
            specialty=swimmer.specialty if swimmer else "medio_fondo",
            event_label=event_label(event),
            expected_time=cur.expected_time if cur else event.goal_time,
            recalc_time=cur.recalc_time if cur else None,
            real_time=cur.real_time if cur else None,
            status=status,
            diff_seconds=round(cur.real_time - cur.expected_time, 2)
            if cur and cur.real_time is not None else None,
            goal_time=event.goal_time, current_time=event.current_time,
            progress_percent=round(max(0.0, min(progress, 110.0)), 1),
        ))

    progression_points = _team_progression(macro, events, current)
    fase_actual = macro.fase_de(current) if current else None

    return DashboardSummary(
        plan_id=macro.id, plan_name=macro.nombre,
        plan_status=macro.estado_efectivo().value,
        start_date=macro.inicio,
        total_weeks=macro.semanas, current_week=current,
        # `fase_de` cae en la última fase para una semana fuera de rango; aquí
        # solo se pinta la que contiene de verdad a la semana en curso.
        current_phase=fase_actual.nombre
        if fase_actual is not None and current is not None and fase_actual.contiene(current)
        else None,
        # Derivado de `events`, que ya viene acotado. Contar la nómina entera
        # delataba cuánta gente hay en el macrociclo incluso cuando las filas de
        # abajo solo traían una.
        athletes_total=len({e.athlete_plan.swimmer_id for e in events}),
        events_total=len(events),
        ahead=counts["ahead"], on_track=counts["on_track"],
        behind=counts["behind"], pending=counts["pending"],
        compliance_percent=round(weeks_with_real / weeks_passed * 100, 1) if weeks_passed else 0.0,
        avg_deviation_percent=round(sum(deviations) / len(deviations), 2) if deviations else None,
        progression=progression_points,
        statuses=statuses,
        phases=[
            PhaseStrip(
                name=f.nombre, type=f.fase.value, color=f.color,
                week_start=f.semana_inicio, week_end=f.semana_fin,
                is_current=bool(current and f.contiene(current)),
            )
            for f in macro.fases
        ],
        competitions=[
            CompetitionInfo(
                name=c.nombre, week_number=c.semana,
                week_date=macro.lunes_de(c.semana),
                days=c.dias, is_main=c.es_principal,
                weeks_away=(c.semana - current) if current else None,
            )
            for c in macro.competencias
        ],
    )


def _team_progression(
    macro: Macrociclo, events: list[AthleteEvent], current: int | None,
) -> list[TeamWeekPoint]:
    """Promedio del % de mejora planificada vs. real acumulada del equipo."""
    points = []
    for week_n in range(1, macro.semanas + 1):
        expected_fracs, real_fracs = [], []
        for event in events:
            total_improvement = event.current_time - event.goal_time
            if total_improvement <= 0:
                continue
            week = next((w for w in event.weeks if w.week_number == week_n), None)
            if week is None:
                continue
            expected_fracs.append(
                (event.current_time - week.expected_time) / total_improvement * 100
            )
            if week.real_time is not None:
                real_fracs.append(
                    (event.current_time - week.real_time) / total_improvement * 100
                )
        points.append(TeamWeekPoint(
            week_number=week_n,
            date_label=macro.lunes_de(week_n).strftime("%d/%m"),
            expected_progress=round(sum(expected_fracs) / len(expected_fracs), 1)
            if expected_fracs else 0.0,
            real_progress=round(sum(real_fracs) / len(real_fracs), 1) if real_fracs else None,
            is_current=week_n == current,
        ))
    return points


async def team_week(
    db: AsyncSession, repo: RepositorioDeMacrociclos,
    macro: Macrociclo, week_number: int,
) -> TeamWeekResponse:
    """La tabla de la semana del equipo. Solo llega aquí un entrenador.

    El guard vive en el router (`require_coach`), no aquí: es la puerta más
    ancha del API —nombres, ritmos y tiempos de todo el equipo— y el plan la
    deja fuera del alcance del atleta. `repo.pruebas_de` acota igualmente por
    nadador, que no sobra: si mañana esta función la llama otro sitio sin guard,
    el filtro sigue puesto.
    """
    events = await repo.pruebas_de(macro.id)
    swimmers = await _swimmers_for(db, events)
    fase = macro.fase_de(week_number)
    phase = fase.nombre if fase is not None and fase.contiene(week_number) else None
    rows = []
    for event in events:
        swimmer = swimmers.get(event.athlete_plan.swimmer_id)
        specialty = swimmer.specialty if swimmer else "medio_fondo"
        week = next((w for w in event.weeks if w.week_number == week_number), None)
        if week is None:
            rows.append(TeamWeekZones(
                event_id=event.id, week_id=None, name=swimmer.name if swimmer else "—",
                specialty=specialty, event_label=event_label(event),
                expected_time=None, pace_100m=None, real_time=None, status=None,
                zones=None, zone_km=None, planned_km=None,
            ))
            continue
        effective = week.recalc_time if week.recalc_time is not None else week.expected_time
        pace = effective / (event.distance / 100)
        rows.append(TeamWeekZones(
            event_id=event.id, week_id=week.id, name=swimmer.name if swimmer else "—",
            specialty=specialty, event_label=event_label(event),
            expected_time=week.expected_time, pace_100m=round(pace, 2),
            real_time=week.real_time,
            status=MOTOR.estado_de_rendimiento(week.real_time, week.expected_time)
            if week.real_time is not None else None,
            zones=MOTOR.zonas(pace, event.distance, event.stroke, macro.piscina.value),
            zone_km=km_por_zona(week.planned_km, distancia=event.distance, especialidad=specialty),
            planned_km=week.planned_km, disabled=week.disabled,
        ))
    return TeamWeekResponse(
        week_number=week_number,
        date_label=macro.lunes_de(week_number).strftime("%d/%m"),
        phase=phase, rows=rows,
    )
