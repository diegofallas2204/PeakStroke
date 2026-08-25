"""Simulador de escenarios: ejecuta el motor sin persistir nada."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.dominio.servicios.curvas import Curva
from app.dominio.servicios.kilometraje import km_por_zona
from app.dominio.servicios.motor import MOTOR, SemanaGenerada

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


def _to_simweek(s: SemanaGenerada, specialty: str, distance: int) -> SimWeek:
    return SimWeek(
        week_number=s.numero, date_label=s.fecha.strftime("%d/%m"),
        expected_time=s.tiempo_esperado, pace_100m=s.ritmo_100,
        planned_km=s.km, phase=s.fase,
        improvement_vs_prev=s.mejora_vs_anterior,
        cumulative_improvement=s.mejora_acumulada,
        zones=s.zonas,
        zone_km=km_por_zona(s.km, distancia=distance, especialidad=specialty),
    )


@router.post("/run", response_model=SimulationResponse)
async def run_simulation(data: SimulationRequest):
    start = data.start_date or date.today()
    factibilidad = MOTOR.factibilidad(
        distancia=data.distance, tiempo_actual=data.current_time,
        tiempo_meta=data.goal_time, semanas=data.total_weeks,
        semanas_por_micro=data.weeks_per_micro, n_mac=data.n_mac,
        edad=data.swimmer_age,
    )
    weeks = MOTOR.generar_plan(
        distancia=data.distance, tiempo_actual=data.current_time,
        tiempo_meta=data.goal_time, semanas=data.total_weeks,
        km_totales=data.total_km, curva=data.curve, inicio=start,
        semanas_por_micro=data.weeks_per_micro, estilo=data.stroke, piscina=data.pool,
        n_mac=data.n_mac, edad=data.swimmer_age,
    )

    # Semanas de extensión: continuación realista del motor cuando la meta supera
    # el techo del macro (mismas que cuenta `recommended_weeks`). Vacío si es factible.
    extension: list[SemanaGenerada] = []
    if factibilidad.semanas_extra:
        extension = MOTOR.generar_extension(
            distancia=data.distance, tiempo_actual=data.current_time,
            techo_realista=factibilidad.techo_realista, tiempo_meta=data.goal_time,
            ritmo_seguro=factibilidad.ritmo_seguro_semanal_s,
            n_extra=factibilidad.semanas_extra,
            inicio=start, semanas_del_macro=data.total_weeks,
            km_semanales=weeks[-1].km if weeks else 0.0,
            estilo=data.stroke, piscina=data.pool,
        )

    curves: dict[str, list[float]] = {}
    for forma in Curva.catalogo():
        alt = MOTOR.generar_plan(
            distancia=data.distance, tiempo_actual=data.current_time,
            tiempo_meta=data.goal_time, semanas=data.total_weeks,
            km_totales=data.total_km, curva=forma.clave, inicio=start,
            semanas_por_micro=data.weeks_per_micro, estilo=data.stroke,
            piscina=data.pool, n_mac=data.n_mac, edad=data.swimmer_age,
        )
        curves[forma.clave] = [s.tiempo_esperado for s in alt]

    return SimulationResponse(
        feasibility=FeasibilityResponse(
            status=factibilidad.estado, message=factibilidad.mensaje,
            tier=factibilidad.tier, improvement_total=factibilidad.mejora_total_s,
            improvement_per_micro=factibilidad.mejora_por_micro_s,
            # `window_min` nunca tuvo valor: la banda inferior se retiró al pasar
            # a un techo científico y el schema conservó el campo.
            window_min=None, window_max=factibilidad.techo_por_micro_s,
            recommended_weeks=factibilidad.semanas_recomendadas,
            extension_weeks=factibilidad.semanas_extra,
            realistic_ceiling=factibilidad.techo_realista,
            safe_rate_per_week=factibilidad.ritmo_seguro_semanal_s,
            detail=factibilidad.detalle,
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
