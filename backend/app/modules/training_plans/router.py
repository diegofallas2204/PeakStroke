"""
training_plans/router.py — Endpoints del módulo de macrociclos.

Prefijo: /api/v1/training-plans

Endpoints:
  Macrociclos:
    POST   /                          → crear macrociclo
    GET    /                          → listar macrociclos del coach
    GET    /{macro_id}                → detalle con atletas y semanas
    PATCH  /{macro_id}                → actualizar metadatos
    DELETE /{macro_id}                → eliminar

  Atletas en macrociclo:
    POST   /{macro_id}/athletes       → agregar atleta + pruebas → genera plan
    GET    /{macro_id}/team           → tabla del equipo (semana X)

  Plan semanal:
    PATCH  /weeks/{week_id}           → ingresar tiempo real / inhabilitar semana

  Atletas (CRUD):
    POST   /swimmers                  → crear atleta
    GET    /swimmers                  → listar atletas del coach
    PATCH  /swimmers/{swimmer_id}     → actualizar atleta

  T-30/T-15:
    POST   /aerobic-tests             → registrar test
    GET    /aerobic-tests/{swimmer_id}→ historial de tests de un atleta
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_feature
from app.modules.training_plans import service
from app.modules.training_plans.models import AthleteEvent, WeeklyPlan
from app.modules.training_plans.schemas import (
    AddAthleteRequest,
    AerobicTestCreate,
    AerobicTestResponse,
    MacrocycleCreate,
    MacrocycleResponse,
    MacrocycleUpdate,
    SwimmerCreate,
    SwimmerResponse,
    SwimmerUpdate,
    TeamRowResponse,
    UpdateWeekRequest,
    WeeklyPlanResponse,
    WeekZonesResponse,
)

router = APIRouter(prefix="/training-plans", tags=["Training Plans"])


# ---------------------------------------------------------------------------
# Helpers de serialización
# ---------------------------------------------------------------------------

def _serialize_week(week: WeeklyPlan) -> WeeklyPlanResponse:
    zones = None
    if week.zone_r1 is not None and week.pace_100m is not None:
        zones = WeekZonesResponse(
            pace_100m=week.pace_100m,
            r1=week.zone_r1,
            r2=week.zone_r2,
            mvo2=week.zone_mvo2,
            rl=week.zone_rl,
            v=week.zone_v,
        )
    return WeeklyPlanResponse(
        id=week.id,
        week_number=week.week_number,
        week_date=week.week_date,
        planned_km=week.planned_km,
        expected_time=week.expected_time,
        expected_time_recalc=week.expected_time_recalc,
        pace_100m=week.pace_100m,
        zones=zones,
        real_time=week.real_time,
        real_km=week.real_km,
        disabled=week.disabled,
        disable_reason=week.disable_reason,
        phase_name=week.phase_name,
        feasibility=week.feasibility,
    )


def _serialize_event(event: AthleteEvent) -> dict:
    total = event.current_time - event.goal_time
    pct = round(total / event.current_time * 100, 2) if event.current_time else 0
    return {
        "id": event.id,
        "priority": event.priority,
        "distance": event.distance,
        "stroke": event.stroke,
        "current_time": event.current_time,
        "goal_time": event.goal_time,
        "is_active": event.is_active,
        "improvement_seconds": round(total, 2),
        "improvement_pct": pct,
        "feasibility": (event.weekly_plans[0].feasibility if event.weekly_plans else None),
    }


def _swimmer_age(birth_date) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


# ---------------------------------------------------------------------------
# Macrociclos
# ---------------------------------------------------------------------------

@router.post("/", response_model=MacrocycleResponse, status_code=status.HTTP_201_CREATED)
async def create_macrocycle(
    data: MacrocycleCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        macro = await service.create_macrocycle(db, current_user.id, data)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return MacrocycleResponse(
        **{k: v for k, v in vars(macro).items() if not k.startswith("_")},
        swimmer_count=0,
    )


@router.get("/", response_model=list[MacrocycleResponse])
async def list_macrocycles(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    macros = await service.get_macrocycles(db, current_user.id)
    return [
        MacrocycleResponse(
            **{k: v for k, v in vars(m).items() if not k.startswith("_")},
            swimmer_count=len(m.athlete_macrocycles) if hasattr(m, "athlete_macrocycles") else 0,
        )
        for m in macros
    ]


@router.get("/{macro_id}", response_model=dict)
async def get_macrocycle(
    macro_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    macro = await service.get_macrocycle(db, macro_id, current_user.id)
    if not macro:
        raise HTTPException(status_code=404, detail="Macrociclo no encontrado")

    athletes = []
    for am in macro.athlete_macrocycles:
        events = []
        for ev in am.events:
            events.append({
                **_serialize_event(ev),
                "weekly_plans": [_serialize_week(w).model_dump() for w in ev.weekly_plans],
            })
        athletes.append({
            "athlete_macrocycle_id": am.id,
            "swimmer_id": am.swimmer.id if am.swimmer else None,
            "aerobic_base": am.aerobic_base,
            "aerobic_base_source": am.aerobic_base_source,
            "events": events,
        })

    return {
        "id": macro.id,
        "name": macro.name,
        "start_date": macro.start_date,
        "end_date": macro.end_date,
        "total_weeks": macro.total_weeks,
        "microcycle_weeks": macro.microcycle_weeks,
        "sessions_per_week": macro.sessions_per_week,
        "total_km": macro.total_km,
        "progression_curve": macro.progression_curve,
        "status": macro.status,
        "notes": macro.notes,
        "phases": [{"id": p.id, "name": p.name, "week_start": p.week_start, "week_end": p.week_end, "color": p.color} for p in macro.phases],
        "athletes": athletes,
    }


@router.patch("/{macro_id}", response_model=MacrocycleResponse)
async def update_macrocycle(
    macro_id: int,
    data: MacrocycleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    macro = await service.update_macrocycle(db, macro_id, current_user.id, data)
    if not macro:
        raise HTTPException(status_code=404, detail="Macrociclo no encontrado")
    return MacrocycleResponse(**{k: v for k, v in vars(macro).items() if not k.startswith("_")})


@router.delete("/{macro_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_macrocycle(
    macro_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    deleted = await service.delete_macrocycle(db, macro_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Macrociclo no encontrado")


# ---------------------------------------------------------------------------
# Atletas en macrociclo
# ---------------------------------------------------------------------------

@router.post("/{macro_id}/athletes", status_code=status.HTTP_201_CREATED)
async def add_athlete(
    macro_id: int,
    data: AddAthleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        am = await service.add_athlete_to_macrocycle(db, macro_id, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"athlete_macrocycle_id": am.id, "message": "Atleta agregado y plan generado"}


@router.get("/{macro_id}/team", response_model=list[dict])
async def get_team_table(
    macro_id: int,
    week: int = Query(1, ge=1, le=18),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = await service.get_team_table(db, macro_id, current_user.id, week)
    return [
        {
            "swimmer_id": r["swimmer_id"],
            "swimmer_name": r["swimmer_name"],
            "athlete_macrocycle_id": r["athlete_macrocycle_id"],
            "event": _serialize_event(r["event"]),
            "week": _serialize_week(r["week"]).model_dump(),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Plan semanal
# ---------------------------------------------------------------------------

@router.patch("/weeks/{week_id}", response_model=dict)
async def update_week(
    week_id: int,
    data: UpdateWeekRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    week = await service.update_week(db, week_id, current_user.id, data)
    if not week:
        raise HTTPException(status_code=404, detail="Semana no encontrada")
    return _serialize_week(week).model_dump()


# ---------------------------------------------------------------------------
# Atletas (CRUD)
# ---------------------------------------------------------------------------

@router.post("/swimmers", response_model=SwimmerResponse, status_code=status.HTTP_201_CREATED)
async def create_swimmer(
    data: SwimmerCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    swimmer = await service.create_swimmer(db, current_user.id, data)
    return SwimmerResponse(**{k: v for k, v in vars(swimmer).items() if not k.startswith("_")},
                           age=_swimmer_age(swimmer.birth_date))


@router.get("/swimmers", response_model=list[SwimmerResponse])
async def list_swimmers(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    swimmers = await service.get_swimmers(db, current_user.id)
    return [
        SwimmerResponse(**{k: v for k, v in vars(s).items() if not k.startswith("_")},
                        age=_swimmer_age(s.birth_date))
        for s in swimmers
    ]


@router.patch("/swimmers/{swimmer_id}", response_model=SwimmerResponse)
async def update_swimmer(
    swimmer_id: int,
    data: SwimmerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    swimmer = await service.update_swimmer(db, swimmer_id, current_user.id, data)
    if not swimmer:
        raise HTTPException(status_code=404, detail="Atleta no encontrado")
    return SwimmerResponse(**{k: v for k, v in vars(swimmer).items() if not k.startswith("_")},
                           age=_swimmer_age(swimmer.birth_date))


# ---------------------------------------------------------------------------
# T-30/T-15
# ---------------------------------------------------------------------------

@router.post("/aerobic-tests", response_model=AerobicTestResponse, status_code=status.HTTP_201_CREATED)
async def create_aerobic_test(
    data: AerobicTestCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        test = await service.create_aerobic_test(db, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return AerobicTestResponse(
        **{k: v for k, v in vars(test).items() if not k.startswith("_")},
        trend_direction=None,
    )


@router.get("/aerobic-tests/{swimmer_id}", response_model=list[AerobicTestResponse])
async def list_aerobic_tests(
    swimmer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    tests = await service.get_aerobic_tests(db, swimmer_id, current_user.id)
    return [
        AerobicTestResponse(**{k: v for k, v in vars(t).items() if not k.startswith("_")})
        for t in tests
    ]
