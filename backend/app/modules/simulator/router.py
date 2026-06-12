"""Simulador de escenarios: ejecuta el motor sin persistir nada."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.engine.curves import CURVES
from app.engine.feasibility import analyze_feasibility
from app.engine.progression import generate_plan
from app.engine.zones import zone_km_distribution

from .schemas import FeasibilityResponse, SimulationRequest, SimulationResponse, SimWeek

router = APIRouter()


@router.post("/run", response_model=SimulationResponse)
async def run_simulation(data: SimulationRequest):
    start = data.start_date or date.today()
    feasibility = analyze_feasibility(
        distance=data.distance, stroke=data.stroke,
        current_time=data.current_time, goal_time=data.goal_time,
        total_weeks=data.total_weeks, weeks_per_micro=data.weeks_per_micro,
    )
    weeks = generate_plan(
        distance=data.distance, current_time=data.current_time,
        goal_time=data.goal_time, total_weeks=data.total_weeks,
        total_km=data.total_km, curve=data.curve, start_date=start,
        weeks_per_micro=data.weeks_per_micro,
    )
    curves: dict[str, list[float]] = {}
    for curve_name in CURVES:
        alt = generate_plan(
            distance=data.distance, current_time=data.current_time,
            goal_time=data.goal_time, total_weeks=data.total_weeks,
            total_km=data.total_km, curve=curve_name, start_date=start,
            weeks_per_micro=data.weeks_per_micro,
        )
        curves[curve_name] = [w.expected_time for w in alt]

    return SimulationResponse(
        feasibility=FeasibilityResponse(
            status=feasibility.status, message=feasibility.message,
            tier=feasibility.tier, improvement_total=feasibility.improvement_total,
            improvement_per_micro=feasibility.improvement_per_micro,
            window_min=feasibility.window_min, window_max=feasibility.window_max,
            recommended_weeks=feasibility.recommended_weeks, detail=feasibility.detail,
        ),
        weeks=[
            SimWeek(
                week_number=w.week_number, date_label=w.week_date.strftime("%d/%m"),
                expected_time=w.expected_time, pace_100m=w.pace_100m,
                planned_km=w.planned_km, phase=w.phase,
                improvement_vs_prev=w.improvement_vs_prev,
                cumulative_improvement=w.cumulative_improvement,
                zones=w.zones,
                zone_km=zone_km_distribution(data.specialty, w.planned_km),
            )
            for w in weeks
        ],
        curves=curves,
    )
