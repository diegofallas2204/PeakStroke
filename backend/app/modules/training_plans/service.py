"""
training_plans/service.py — Lógica de negocio para macrociclos.

Responsabilidades:
  - CRUD de macrociclos y fases
  - Incorporar atletas con sus pruebas y base aeróbica
  - Generar/regenerar el plan semanal via ProgressionEngine
  - Actualizar semanas con resultados reales
  - Cálculo de T-30/T-15

Regla: ningún router importa desde aquí directamente — solo vía Depends.
"""
from __future__ import annotations

import statistics
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.tier_limits import get_tier_limit
from app.modules.training_plans.models import (
    AerobicTest,
    AerobicTestSplit,
    AthleteMacrocycle,
    AthleteEvent,
    Macrocycle,
    MacrocyclePhase,
    Swimmer,
    WeeklyPlan,
)
from app.modules.training_plans.progression_engine import ProgressionEngine, calculate_aerobic_base
from app.modules.training_plans.schemas import (
    AddAthleteRequest,
    AerobicTestCreate,
    MacrocycleCreate,
    MacrocycleUpdate,
    SwimmerCreate,
    SwimmerUpdate,
    UpdateWeekRequest,
)

engine = ProgressionEngine()


# ---------------------------------------------------------------------------
# Macrociclos
# ---------------------------------------------------------------------------

async def create_macrocycle(db: AsyncSession, owner_id: int, data: MacrocycleCreate) -> Macrocycle:
    # Verificar límite de tier
    user = await db.get(__import__("app.modules.auth.models", fromlist=["User"]).User, owner_id)
    tier = getattr(user, "tier", "free") if user else "free"
    existing_count = await db.scalar(
        select(Macrocycle).where(Macrocycle.owner_id == owner_id).with_only_columns(
            __import__("sqlalchemy", fromlist=["func"]).func.count()
        )
    ) or 0
    max_macros = get_tier_limit(tier, "macrocycles")
    if isinstance(max_macros, int) and existing_count >= max_macros:
        raise PermissionError(f"Tu plan '{tier}' permite máximo {max_macros} macrociclo(s)")

    macro = Macrocycle(
        owner_id=owner_id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        total_weeks=data.total_weeks,
        microcycle_weeks=data.microcycle_weeks,
        sessions_per_week=data.sessions_per_week,
        total_km=data.total_km,
        progression_curve=data.progression_curve,
        notes=data.notes,
    )
    db.add(macro)
    await db.flush()  # genera macro.id

    # Crear fases por defecto si no se proveen
    phases_data = data.phases or _default_phases(data.total_weeks)
    for p in phases_data:
        db.add(MacrocyclePhase(
            macrocycle_id=macro.id,
            name=p.name,
            week_start=p.week_start,
            week_end=p.week_end,
            color=p.color,
        ))

    await db.flush()
    return macro


def _default_phases(total_weeks: int) -> list:
    """Fases por defecto si el entrenador no las define."""
    from app.modules.training_plans.schemas import PhaseCreate
    if total_weeks == 12:
        return [
            PhaseCreate(name="Base", week_start=1, week_end=4, color="#3B82F6"),
            PhaseCreate(name="Construcción", week_start=5, week_end=8, color="#F59E0B"),
            PhaseCreate(name="Pico", week_start=9, week_end=11, color="#EF4444"),
            PhaseCreate(name="Descenso", week_start=12, week_end=12, color="#6B7280"),
        ]
    else:  # 18 semanas
        return [
            PhaseCreate(name="Base", week_start=1, week_end=5, color="#3B82F6"),
            PhaseCreate(name="Construcción", week_start=6, week_end=12, color="#F59E0B"),
            PhaseCreate(name="Pico", week_start=13, week_end=16, color="#EF4444"),
            PhaseCreate(name="Descenso", week_start=17, week_end=18, color="#6B7280"),
        ]


async def get_macrocycles(db: AsyncSession, owner_id: int) -> list[Macrocycle]:
    result = await db.execute(
        select(Macrocycle)
        .where(Macrocycle.owner_id == owner_id)
        .options(selectinload(Macrocycle.phases))
        .order_by(Macrocycle.created_at.desc())
    )
    return list(result.scalars().all())


async def get_macrocycle(db: AsyncSession, macro_id: int, owner_id: int) -> Macrocycle | None:
    result = await db.execute(
        select(Macrocycle)
        .where(Macrocycle.id == macro_id, Macrocycle.owner_id == owner_id)
        .options(
            selectinload(Macrocycle.phases),
            selectinload(Macrocycle.athlete_macrocycles)
            .selectinload(AthleteMacrocycle.events)
            .selectinload(AthleteEvent.weekly_plans),
        )
    )
    return result.scalar_one_or_none()


async def update_macrocycle(
    db: AsyncSession, macro_id: int, owner_id: int, data: MacrocycleUpdate
) -> Macrocycle | None:
    macro = await db.scalar(
        select(Macrocycle).where(Macrocycle.id == macro_id, Macrocycle.owner_id == owner_id)
    )
    if not macro:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(macro, field, value)
    return macro


async def delete_macrocycle(db: AsyncSession, macro_id: int, owner_id: int) -> bool:
    macro = await db.scalar(
        select(Macrocycle).where(Macrocycle.id == macro_id, Macrocycle.owner_id == owner_id)
    )
    if not macro:
        return False
    await db.delete(macro)
    return True


# ---------------------------------------------------------------------------
# Atletas (Swimmers)
# ---------------------------------------------------------------------------

async def create_swimmer(db: AsyncSession, coach_id: int, data: SwimmerCreate) -> Swimmer:
    swimmer = Swimmer(coach_id=coach_id, **data.model_dump())
    db.add(swimmer)
    await db.flush()
    return swimmer


async def get_swimmers(db: AsyncSession, coach_id: int) -> list[Swimmer]:
    result = await db.execute(
        select(Swimmer).where(Swimmer.coach_id == coach_id).order_by(Swimmer.name)
    )
    return list(result.scalars().all())


async def update_swimmer(
    db: AsyncSession, swimmer_id: int, coach_id: int, data: SwimmerUpdate
) -> Swimmer | None:
    swimmer = await db.scalar(
        select(Swimmer).where(Swimmer.id == swimmer_id, Swimmer.coach_id == coach_id)
    )
    if not swimmer:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(swimmer, field, value)
    return swimmer


# ---------------------------------------------------------------------------
# Agregar atleta al macrociclo + generar plan
# ---------------------------------------------------------------------------

async def add_athlete_to_macrocycle(
    db: AsyncSession, macro_id: int, owner_id: int, data: AddAthleteRequest
) -> AthleteMacrocycle:
    # Verificar que el macro pertenece al coach
    macro = await db.scalar(
        select(Macrocycle)
        .where(Macrocycle.id == macro_id, Macrocycle.owner_id == owner_id)
        .options(selectinload(Macrocycle.phases))
    )
    if not macro:
        raise ValueError("Macrociclo no encontrado")

    # Verificar que el swimmer pertenece al coach
    swimmer = await db.scalar(
        select(Swimmer).where(Swimmer.id == data.swimmer_id, Swimmer.coach_id == owner_id)
    )
    if not swimmer:
        raise ValueError("Atleta no encontrado")

    # Verificar que no esté ya en el macro
    existing = await db.scalar(
        select(AthleteMacrocycle).where(
            AthleteMacrocycle.swimmer_id == data.swimmer_id,
            AthleteMacrocycle.macrocycle_id == macro_id,
        )
    )
    if existing:
        raise ValueError("El atleta ya está en este macrociclo")

    # Resolver base aeróbica
    aerobic_base_val, aerobic_source, aerobic_test_id = None, None, None
    if data.aerobic_base:
        if data.aerobic_base.aerobic_test_id:
            test = await db.get(AerobicTest, data.aerobic_base.aerobic_test_id)
            if test and test.avg_time:
                aerobic_base_val = test.avg_time
                aerobic_source = test.test_type
                aerobic_test_id = test.id
        elif data.aerobic_base.value:
            aerobic_base_val = data.aerobic_base.value
            aerobic_source = "manual"

    # Crear AthleteMacrocycle
    am = AthleteMacrocycle(
        swimmer_id=data.swimmer_id,
        macrocycle_id=macro_id,
        aerobic_base=aerobic_base_val,
        aerobic_base_source=aerobic_source,
        aerobic_test_id=aerobic_test_id,
    )
    db.add(am)
    await db.flush()

    # Crear AthleteEvent y generar WeeklyPlan para cada prueba
    phases_list = [
        {"name": p.name, "week_start": p.week_start, "week_end": p.week_end}
        for p in macro.phases
    ]

    for event_data in data.events:
        event = AthleteEvent(
            athlete_macrocycle_id=am.id,
            priority=event_data.priority,
            distance=event_data.distance,
            stroke=event_data.stroke,
            current_time=event_data.current_time,
            goal_time=event_data.goal_time,
        )
        db.add(event)
        await db.flush()

        # Generar plan semanal
        entries = engine.generate_plan(
            distance=event_data.distance,
            stroke=event_data.stroke,
            current_time=event_data.current_time,
            goal_time=event_data.goal_time,
            num_weeks=macro.total_weeks,
            microcycle_weeks=macro.microcycle_weeks,
            total_km=macro.total_km,
            curve=macro.progression_curve,
            start_date=macro.start_date,
            phases=phases_list,
        )

        for entry in entries:
            db.add(WeeklyPlan(
                athlete_event_id=event.id,
                week_number=entry.week_number,
                week_date=entry.week_date,
                planned_km=entry.planned_km,
                expected_time=entry.expected_time,
                expected_time_recalc=entry.expected_time_recalc,
                pace_100m=entry.pace_100m,
                pace_100m_recalc=entry.pace_100m_recalc,
                zone_r1=entry.zones.r1,
                zone_r2=entry.zones.r2,
                zone_mvo2=entry.zones.mvo2,
                zone_rl=entry.zones.rl,
                zone_v=entry.zones.v,
                phase_name=entry.phase_name,
                feasibility=entry.feasibility,
            ))

    await db.flush()
    return am


# ---------------------------------------------------------------------------
# Actualizar semana (entrada real / inhabilitar)
# ---------------------------------------------------------------------------

async def update_week(
    db: AsyncSession,
    week_id: int,
    owner_id: int,
    data: UpdateWeekRequest,
) -> WeeklyPlan | None:
    # Cargar el plan con toda la cadena para verificar ownership
    week = await db.scalar(
        select(WeeklyPlan)
        .where(WeeklyPlan.id == week_id)
        .options(
            selectinload(WeeklyPlan.athlete_event)
            .selectinload(AthleteEvent.athlete_macrocycle)
            .selectinload(AthleteMacrocycle.macrocycle)
        )
    )
    if not week:
        return None
    macro = week.athlete_event.athlete_macrocycle.macrocycle
    if macro.owner_id != owner_id:
        return None

    if data.real_time is not None:
        week.real_time = data.real_time
    if data.real_km is not None:
        week.real_km = data.real_km
    if data.disabled is not None:
        week.disabled = data.disabled
        week.disable_reason = data.disable_reason if data.disabled else None

        # Regenerar curva recalculada para este evento
        await _regenerate_recalc_curve(db, week.athlete_event_id)

    return week


async def _regenerate_recalc_curve(db: AsyncSession, athlete_event_id: int) -> None:
    """Recalcula expected_time_recalc para todas las semanas de un evento."""
    weeks_result = await db.execute(
        select(WeeklyPlan)
        .where(WeeklyPlan.athlete_event_id == athlete_event_id)
        .order_by(WeeklyPlan.week_number)
    )
    weeks = list(weeks_result.scalars().all())
    if not weeks:
        return

    event = await db.get(AthleteEvent, athlete_event_id)
    if not event:
        return

    am = await db.get(AthleteMacrocycle, event.athlete_macrocycle_id)
    macro = await db.get(Macrocycle, am.macrocycle_id) if am else None
    if not macro:
        return

    disabled = {w.week_number for w in weeks if w.disabled}
    phases_result = await db.execute(
        select(MacrocyclePhase).where(MacrocyclePhase.macrocycle_id == macro.id)
    )
    phases = [
        {"name": p.name, "week_start": p.week_start, "week_end": p.week_end}
        for p in phases_result.scalars().all()
    ]

    entries = engine.generate_plan(
        distance=event.distance,
        stroke=event.stroke,
        current_time=event.current_time,
        goal_time=event.goal_time,
        num_weeks=macro.total_weeks,
        microcycle_weeks=macro.microcycle_weeks,
        total_km=macro.total_km,
        curve=macro.progression_curve,
        start_date=macro.start_date,
        phases=phases,
        disabled_weeks=disabled,
    )

    entry_map = {e.week_number: e for e in entries}
    for week in weeks:
        entry = entry_map.get(week.week_number)
        if entry:
            week.expected_time_recalc = entry.expected_time_recalc
            week.pace_100m_recalc = entry.pace_100m_recalc


# ---------------------------------------------------------------------------
# Vista tabla del equipo
# ---------------------------------------------------------------------------

async def get_team_table(
    db: AsyncSession,
    macro_id: int,
    owner_id: int,
    week_number: int,
) -> list[dict]:
    """
    Retorna una fila por cada (atleta × prueba) para la semana indicada.
    """
    macro = await db.scalar(
        select(Macrocycle).where(Macrocycle.id == macro_id, Macrocycle.owner_id == owner_id)
    )
    if not macro:
        return []

    result = await db.execute(
        select(AthleteMacrocycle)
        .where(AthleteMacrocycle.macrocycle_id == macro_id)
        .options(
            selectinload(AthleteMacrocycle.swimmer),
            selectinload(AthleteMacrocycle.events)
            .selectinload(AthleteEvent.weekly_plans),
        )
    )
    athlete_macros = list(result.scalars().all())

    rows = []
    for am in athlete_macros:
        for event in am.events:
            if not event.is_active:
                continue
            week = next(
                (w for w in event.weekly_plans if w.week_number == week_number), None
            )
            if week:
                rows.append({
                    "swimmer_id": am.swimmer.id,
                    "swimmer_name": am.swimmer.name,
                    "athlete_macrocycle_id": am.id,
                    "event": event,
                    "week": week,
                })

    return rows


# ---------------------------------------------------------------------------
# T-30/T-15
# ---------------------------------------------------------------------------

async def create_aerobic_test(
    db: AsyncSession, coach_id: int, data: AerobicTestCreate
) -> AerobicTest:
    # Verificar ownership del swimmer
    swimmer = await db.scalar(
        select(Swimmer).where(Swimmer.id == data.swimmer_id, Swimmer.coach_id == coach_id)
    )
    if not swimmer:
        raise ValueError("Atleta no encontrado")

    stats = calculate_aerobic_base(data.splits)

    test = AerobicTest(
        swimmer_id=data.swimmer_id,
        macrocycle_id=data.macrocycle_id,
        test_type=data.test_type,
        test_date=data.test_date,
        repetitions=len(data.splits),
        avg_time=stats["avg_time"],
        std_dev=stats["std_dev"],
        notes=data.notes,
    )
    db.add(test)
    await db.flush()

    for i, split_time in enumerate(data.splits, start=1):
        db.add(AerobicTestSplit(
            aerobic_test_id=test.id,
            rep_number=i,
            split_time=split_time,
        ))

    await db.flush()
    return test


async def get_aerobic_tests(
    db: AsyncSession, swimmer_id: int, coach_id: int
) -> list[AerobicTest]:
    result = await db.execute(
        select(AerobicTest)
        .join(Swimmer)
        .where(AerobicTest.swimmer_id == swimmer_id, Swimmer.coach_id == coach_id)
        .options(selectinload(AerobicTest.splits))
        .order_by(AerobicTest.test_date.desc())
    )
    return list(result.scalars().all())
