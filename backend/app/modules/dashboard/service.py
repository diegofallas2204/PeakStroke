"""Agregaciones del dashboard: estado del equipo, progresión y cumplimiento."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import Principal
from app.engine import progression
from app.engine.zones import calc_zones, zone_km_distribution
from app.modules.plans.access import get_plan, visible_to
from app.modules.plans.models import AthleteEvent, AthletePlan, Plan
from app.modules.plans.service import current_week_of, effective_status
from app.modules.swimmers.models import Swimmer

from .schemas import (
    AthleteStatusRow, CompetitionInfo, DashboardSummary, PhaseStrip,
    TeamWeekPoint, TeamWeekResponse, TeamWeekZones,
)

_STROKE_LABELS = {
    "libre": "Libre", "espalda": "Espalda", "pecho": "Pecho",
    "mariposa": "Mariposa", "combinado": "Combinado",
}


def event_label(event: AthleteEvent) -> str:
    return f"{event.distance}m {_STROKE_LABELS.get(event.stroke, event.stroke)}"


async def _load_events(
    db: AsyncSession, plan_id: int, principal: Principal,
) -> list[AthleteEvent]:
    """Las pruebas del macrociclo que le tocan a quien pregunta.

    Punto único de acotación del módulo: `build_summary` y `team_week` salen las
    dos de aquí, así que el filtro por nadador no puede quedarse a medias en una
    y puesto en la otra.
    """
    stmt = (
        select(AthleteEvent)
        .join(AthletePlan, AthleteEvent.athlete_plan_id == AthletePlan.id)
        .options(
            selectinload(AthleteEvent.weeks),
            selectinload(AthleteEvent.athlete_plan),
        )
        .where(AthletePlan.plan_id == plan_id)
        .order_by(AthleteEvent.priority)
    )
    stmt = principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)
    return list((await db.execute(stmt)).scalars())


async def _swimmers_for(db: AsyncSession, events: list[AthleteEvent]) -> dict[int, Swimmer]:
    ids = {e.athlete_plan.swimmer_id for e in events}
    if not ids:
        return {}
    rows = (await db.execute(select(Swimmer).where(Swimmer.id.in_(ids)))).scalars()
    return {s.id: s for s in rows}


async def active_plan(db: AsyncSession, principal: Principal) -> Plan | None:
    """El macrociclo activo más reciente **de los que el usuario puede ver**."""
    stmt = visible_to(
        select(Plan).where(Plan.status == "active"), principal,
    ).order_by(Plan.created_at.desc())
    plan = (await db.execute(stmt)).scalars().first()
    if plan is None:
        return None
    return await get_plan(db, plan.id, principal)


async def build_summary(
    db: AsyncSession, plan: Plan, principal: Principal,
) -> DashboardSummary:
    """El estado del macrociclo, acotado a quien pregunta.

    Hasta el 2026-08-06 no recibía `principal` y por eso le enseñaba al atleta
    las ocho filas del club con nombre y tiempo de cada uno.
    """
    current = current_week_of(plan)
    events = await _load_events(db, plan.id, principal)
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
            status = progression.performance_status(cur.real_time, cur.expected_time)
        elif last_real is not None:
            status = progression.performance_status(last_real.real_time, last_real.expected_time)
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

    progression_points = _team_progression(plan, events, current)
    current_phase = None
    for p in plan.phases:
        if current and p.week_start <= current <= p.week_end:
            current_phase = p.name

    return DashboardSummary(
        plan_id=plan.id, plan_name=plan.name, plan_status=effective_status(plan),
        start_date=plan.start_date,
        total_weeks=plan.total_weeks, current_week=current, current_phase=current_phase,
        # Derivado de `events`, que ya viene acotado. `len(plan.athlete_plans)`
        # contaba el roster entero y delataba cuánta gente hay en el macrociclo
        # incluso cuando las filas de abajo solo traían una.
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
                name=p.name, type=p.type, color=p.color,
                week_start=p.week_start, week_end=p.week_end,
                is_current=bool(current and p.week_start <= current <= p.week_end),
            )
            for p in plan.phases
        ],
        competitions=[
            CompetitionInfo(
                name=c.name, week_number=c.week_number,
                week_date=progression.monday_of(plan.start_date, c.week_number),
                days=c.days, is_main=c.is_main,
                weeks_away=(c.week_number - current) if current else None,
            )
            for c in plan.competitions
        ],
    )


def _team_progression(
    plan: Plan, events: list[AthleteEvent], current: int | None
) -> list[TeamWeekPoint]:
    """Promedio del % de mejora planificada vs. real acumulada del equipo."""
    points = []
    for week_n in range(1, plan.total_weeks + 1):
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
            date_label=progression.monday_of(plan.start_date, week_n).strftime("%d/%m"),
            expected_progress=round(sum(expected_fracs) / len(expected_fracs), 1)
            if expected_fracs else 0.0,
            real_progress=round(sum(real_fracs) / len(real_fracs), 1) if real_fracs else None,
            is_current=week_n == current,
        ))
    return points


async def team_week(
    db: AsyncSession, plan: Plan, week_number: int, principal: Principal,
) -> TeamWeekResponse:
    """La tabla de la semana, acotada a quien pregunta.

    Es la puerta más ancha del API —nombres, ritmos y tiempos de todo el
    equipo— y por eso se acota en vez de bloquearse con `require_coach`: ese
    guard no comprueba nada con la autenticación apagada, que es como corre el
    proyecto hoy. El filtro por nadador, en cambio, se aplica siempre.
    """
    events = await _load_events(db, plan.id, principal)
    swimmers = await _swimmers_for(db, events)
    phase = next(
        (p.name for p in plan.phases if p.week_start <= week_number <= p.week_end), None
    )
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
            status=progression.performance_status(week.real_time, week.expected_time)
            if week.real_time is not None else None,
            zones=calc_zones(pace, event.distance, event.stroke, plan.pool),
            zone_km=zone_km_distribution(week.planned_km, distance=event.distance, specialty=specialty),
            planned_km=week.planned_km, disabled=week.disabled,
        ))
    return TeamWeekResponse(
        week_number=week_number,
        date_label=progression.monday_of(plan.start_date, week_number).strftime("%d/%m"),
        phase=phase, rows=rows,
    )
