"""Simulador de escenarios: ejecuta el motor sin persistir nada."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.dominio.servicios.motor import MOTOR
from app.engine.curves import CURVES
from app.engine.feasibility import analyze_feasibility
from app.engine.progression import WeekEntry, generate_extension, generate_plan
from app.engine.zones import zone_km_distribution

from .schemas import (
    FeasibilityResponse,
    MacroProjectionItem,
    SeasonRequest,
    SeasonResponse,
    SimulationRequest,
    SimulationResponse,
    SimWeek,
)

router = APIRouter()


def _to_simweek(w: WeekEntry, specialty: str, distance: int) -> SimWeek:
    return SimWeek(
        week_number=w.week_number, date_label=w.week_date.strftime("%d/%m"),
        expected_time=w.expected_time, pace_100m=w.pace_100m,
        planned_km=w.planned_km, phase=w.phase,
        improvement_vs_prev=w.improvement_vs_prev,
        cumulative_improvement=w.cumulative_improvement,
        zones=w.zones,
        zone_km=zone_km_distribution(w.planned_km, distance=distance, specialty=specialty),
    )


@router.post("/run", response_model=SimulationResponse)
async def run_simulation(data: SimulationRequest):
    start = data.start_date or date.today()
    feasibility = analyze_feasibility(
        distance=data.distance, stroke=data.stroke,
        current_time=data.current_time, goal_time=data.goal_time,
        total_weeks=data.total_weeks, weeks_per_micro=data.weeks_per_micro,
        n_mac=data.n_mac, age=data.swimmer_age,
    )
    weeks = generate_plan(
        distance=data.distance, current_time=data.current_time,
        goal_time=data.goal_time, total_weeks=data.total_weeks,
        total_km=data.total_km, curve=data.curve, start_date=start,
        weeks_per_micro=data.weeks_per_micro, stroke=data.stroke, pool=data.pool,
        n_mac=data.n_mac, age=data.swimmer_age,
    )

    # Semanas de extensión: continuación realista del motor cuando la meta supera
    # el techo del macro (mismas que cuenta `recommended_weeks`). Vacío si es factible.
    extension: list[WeekEntry] = []
    if feasibility.extension_weeks:
        extension = generate_extension(
            distance=data.distance, current_time=data.current_time,
            realistic_ceiling=feasibility.realistic_ceiling, goal_time=data.goal_time,
            safe_rate=feasibility.safe_rate_per_week, n_ext=feasibility.extension_weeks,
            start_date=start, macro_weeks=data.total_weeks,
            weekly_km=weeks[-1].planned_km if weeks else 0.0,
            stroke=data.stroke, pool=data.pool,
        )

    curves: dict[str, list[float]] = {}
    for curve_name in CURVES:
        alt = generate_plan(
            distance=data.distance, current_time=data.current_time,
            goal_time=data.goal_time, total_weeks=data.total_weeks,
            total_km=data.total_km, curve=curve_name, start_date=start,
            weeks_per_micro=data.weeks_per_micro, stroke=data.stroke, pool=data.pool,
            n_mac=data.n_mac, age=data.swimmer_age,
        )
        curves[curve_name] = [w.expected_time for w in alt]

    return SimulationResponse(
        feasibility=FeasibilityResponse(
            status=feasibility.status, message=feasibility.message,
            tier=feasibility.tier, improvement_total=feasibility.improvement_total,
            improvement_per_micro=feasibility.improvement_per_micro,
            window_min=feasibility.window_min, window_max=feasibility.window_max,
            recommended_weeks=feasibility.recommended_weeks,
            extension_weeks=feasibility.extension_weeks,
            realistic_ceiling=feasibility.realistic_ceiling,
            safe_rate_per_week=feasibility.safe_rate_per_week,
            detail=feasibility.detail,
        ),
        weeks=[_to_simweek(w, data.specialty, data.distance) for w in weeks],
        extension_weeks=[_to_simweek(w, data.specialty, data.distance) for w in extension],
        curves=curves,
    )


@router.post("/season", response_model=SeasonResponse)
async def project_season(data: SeasonRequest):
    """Proyección ANUAL: encadena N macrociclos (re-test entre cada uno) con el
    motor científico y la compara con el techo de la literatura.

    El estilo y la piscina no entran: la proyección solo lee el techo realista
    de cada macro, que es de la distancia y el nivel. Se seguían pasando porque
    la firma vieja los pedía.
    """
    proj = MOTOR.proyectar_temporada(
        tiempo_actual=data.current_time, distancia=data.distance,
        n_macros=data.n_macros, edad=data.swimmer_age,
    )
    return SeasonResponse(
        level=proj.nivel, n_macros=proj.n_macros,
        season_start=proj.inicio, season_end=proj.fin,
        season_improvement_s=proj.mejora_s,
        season_improvement_pct=proj.mejora_pct,
        annual_low_pct=proj.rango_bajo_pct, annual_high_pct=proj.rango_alto_pct,
        verdict=proj.veredicto, message=proj.mensaje,
        macros=[
            MacroProjectionItem(
                n_mac=m.n_mac, start_time=m.tiempo_inicial, end_time=m.tiempo_final,
                improvement_s=m.mejora_s, improvement_pct=m.mejora_pct,
            )
            for m in proj.macros
        ],
    )
