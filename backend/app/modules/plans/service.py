"""Lógica de negocio del módulo plans: CRUD + orquestación del motor."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import Principal
from app.engine import progression
from app.engine.zones import calc_zones, zone_km_distribution
from app.modules.swimmers.models import Swimmer

from .models import (
    AthleteEvent, AthletePlan, Competition, Plan, PlanCoach, PlanPhase, WeeklyPlan,
)
from .schemas import (
    AddAthleteRequest, AthletePlanResponse, PlanCreate, PlanResponse,
    PlanUpdate, WeekResponse, WeekUpdateRequest,
)

_PLAN_LOAD = (
    selectinload(Plan.phases),
    selectinload(Plan.competitions),
    selectinload(Plan.athlete_plans).selectinload(AthletePlan.events),
)


def age_at(birth_date: date | None, ref: date) -> int | None:
    """Edad en años cumplidos en la fecha `ref` (None si no hay fecha de nacimiento)."""
    if birth_date is None:
        return None
    years = ref.year - birth_date.year
    if (ref.month, ref.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(years, 0)


def current_week_of(plan: Plan, today: date | None = None) -> int | None:
    today = today or date.today()
    start = progression.monday_of(plan.start_date, 1)
    delta_weeks = (today - start).days // 7 + 1
    if delta_weeks < 1:
        return None
    return min(delta_weeks, plan.total_weeks)


def effective_status(plan: Plan, today: date | None = None) -> str:
    """Estado mostrado al entrenador.

    Suspendido / inactivo (draft) / completado (finished) son overrides manuales
    y mandan tal cual. Si el macrociclo está vigente (active) pero su última
    semana ya pasó, se auto-marca como completado por fecha.
    """
    if plan.status in ("suspended", "draft", "finished"):
        return plan.status
    today = today or date.today()
    last_week_end = progression.monday_of(plan.start_date, plan.total_weeks) + timedelta(days=6)
    if today > last_week_end:
        return "finished"
    return "active"


async def _swimmer_map(db: AsyncSession, ids: list[int]) -> dict[int, Swimmer]:
    if not ids:
        return {}
    rows = (await db.execute(select(Swimmer).where(Swimmer.id.in_(ids)))).scalars()
    return {s.id: s for s in rows}


async def to_plan_response(db: AsyncSession, plan: Plan) -> PlanResponse:
    resp = PlanResponse.model_validate(plan)
    resp.current_week = current_week_of(plan)
    resp.effective_status = effective_status(plan)
    swimmers = await _swimmer_map(db, [ap.swimmer_id for ap in plan.athlete_plans])
    athletes = []
    for ap in plan.athlete_plans:
        item = AthletePlanResponse.model_validate(ap)
        swimmer = swimmers.get(ap.swimmer_id)
        if swimmer:
            item.swimmer_name = swimmer.name
            item.specialty = swimmer.specialty
        athletes.append(item)
    resp.athletes = athletes
    return resp


def visible_to(stmt, principal: Principal):
    """Acota una consulta de macrociclos a los que el solicitante puede ver.

    Tres casos, en este orden:
      · **Dueño del equipo** — todos los de su equipo. Sin esta excepción, los
        macrociclos de un entrenador que se va no los podría rescatar nadie.
      · **Entrenador** — solo aquellos en los que figura en `plan_coaches`.
      · **Atleta** — solo aquellos en los que está inscrito.

    Es la única puerta: `list_plans` y `get_plan` pasan por aquí, así que un
    macrociclo ajeno no se cuela ni listándolo ni pidiéndolo por id.
    """
    stmt = stmt.where(Plan.team_id == principal.team_id)
    if principal.sees_every_plan:
        return stmt

    if principal.is_coach:
        suyos = select(PlanCoach.plan_id).where(PlanCoach.coach_id == principal.id)
    else:
        suyos = (
            select(AthletePlan.plan_id)
            .join(Swimmer, Swimmer.id == AthletePlan.swimmer_id)
            .where(Swimmer.user_id == principal.id)
        )
    return stmt.where(Plan.id.in_(suyos))


async def list_plans(db: AsyncSession, principal: Principal) -> list[Plan]:
    stmt = visible_to(select(Plan).options(*_PLAN_LOAD), principal)
    return list((await db.execute(stmt.order_by(Plan.created_at.desc()))).scalars())


async def get_plan(db: AsyncSession, plan_id: int, principal: Principal) -> Plan | None:
    """None si no existe **o** si el solicitante no debe verlo.

    Ambos casos se responden con 404: un 403 confirmaría que ese macrociclo
    existe en algún equipo.
    """
    stmt = visible_to(select(Plan).options(*_PLAN_LOAD).where(Plan.id == plan_id), principal)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _plan_unscoped(db: AsyncSession, plan_id: int) -> Plan | None:
    """Recarga interna tras escribir, cuando el acceso ya está comprobado."""
    stmt = select(Plan).options(*_PLAN_LOAD).where(Plan.id == plan_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_plan(db: AsyncSession, data: PlanCreate, team_id: int, coach_id: int) -> Plan:
    """El equipo y el entrenador NO vienen del cliente: salen de la sesión.

    Si el equipo fuese un campo del schema, cualquiera podría crear macrociclos
    dentro de un equipo ajeno con solo cambiar un número en la petición.
    """
    plan = Plan(**data.model_dump(exclude={"phases", "competitions"}), team_id=team_id)
    plan.coaches.append(PlanCoach(coach_id=coach_id, team_id=team_id))
    phases = [p.model_dump() for p in data.phases] or \
        progression.default_phase_ranges(data.total_weeks)
    for i, p in enumerate(phases):
        plan.phases.append(PlanPhase(
            name=p["name"], type=p.get("type", "base"), color=p.get("color", "#8b5cf6"),
            week_start=p["week_start"], week_end=p["week_end"], sort=i,
        ))
    for c in data.competitions:
        plan.competitions.append(Competition(**c.model_dump()))
    db.add(plan)
    await db.commit()
    return (await _plan_unscoped(db, plan.id))  # type: ignore[return-value]


async def update_plan(db: AsyncSession, plan: Plan, data: PlanUpdate) -> Plan:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    return (await _plan_unscoped(db, plan.id))  # type: ignore[return-value]


async def delete_plan(db: AsyncSession, plan: Plan) -> None:
    await db.delete(plan)
    await db.commit()


# ── Atletas en el plan ───────────────────────────────────────────────
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
        weeks = progression.generate_plan(
            distance=event.distance, current_time=event.current_time,
            goal_time=event.goal_time, total_weeks=plan.total_weeks,
            total_km=plan.total_km, curve=plan.progression_curve,
            start_date=plan.start_date, weeks_per_micro=plan.weeks_per_micro,
            phases=phases or None, stroke=event.stroke, pool=plan.pool,
            n_mac=plan.n_mac, age=age,
        )
        for w in weeks:
            event.weeks.append(WeeklyPlan(
                week_number=w.week_number, week_date=w.week_date,
                planned_km=w.planned_km, expected_time=w.expected_time, phase=w.phase,
            ))
        athlete_plan.events.append(event)
    db.add(athlete_plan)
    await db.commit()
    await db.refresh(athlete_plan)
    return athlete_plan


async def remove_athlete(db: AsyncSession, plan_id: int, athlete_plan_id: int) -> bool:
    ap = await db.get(AthletePlan, athlete_plan_id)
    if ap is None or ap.plan_id != plan_id:
        return False
    await db.delete(ap)
    await db.commit()
    return True


# ── Semanas ──────────────────────────────────────────────────────────
_EVENT_LOAD = (
    selectinload(AthleteEvent.weeks),
    selectinload(AthleteEvent.athlete_plan).selectinload(AthletePlan.plan)
    .selectinload(Plan.competitions),
)


async def get_event(
    db: AsyncSession, event_id: int, principal: Principal | None = None,
) -> AthleteEvent | None:
    """Prueba objetivo de un atleta dentro de un plan.

    Con `principal`, solo la devuelve si ese macrociclo le es visible. Es la
    comprobación que impide el acceso directo por id: las pruebas y las semanas
    se piden por su propio identificador, sin mencionar el plan, así que sin
    esto bastaría con probar números para leer los datos de otro club.
    """
    stmt = select(AthleteEvent).options(*_EVENT_LOAD).where(AthleteEvent.id == event_id)
    if principal is not None:
        stmt = visible_to(
            stmt.join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
                .join(Plan, Plan.id == AthletePlan.plan_id),
            principal,
        )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_week(
    db: AsyncSession, week_id: int, principal: Principal,
) -> WeeklyPlan | None:
    """Semana concreta, solo si su macrociclo le es visible al solicitante."""
    stmt = visible_to(
        select(WeeklyPlan)
        .join(AthleteEvent, AthleteEvent.id == WeeklyPlan.athlete_event_id)
        .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
        .join(Plan, Plan.id == AthletePlan.plan_id)
        .where(WeeklyPlan.id == week_id),
        principal,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


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

    event = await get_event(db, week.athlete_event_id)
    if event is not None:
        await _recalculate_event(db, event)
    return event


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
