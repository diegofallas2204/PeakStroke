"""Análisis de factibilidad del objetivo del macrociclo.

Dos regímenes según la fisiología de la prueba:
- Tier 1 (>= 400m): la mejora la gobierna la base aeróbica. Regla empírica:
  1 s/microciclo en R1, escalada por factores de distancia, estilo y la
  proporción aeróbica de la prueba.
- Tier 2 (< 400m): mejora por ventana fraccionada según distancia+estilo
  (ventanas realistas de s/microciclo observadas en pruebas de velocidad).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

TIER1_THRESHOLD = 400

DISTANCE_FACTORS = {50: 0.15, 100: 0.45, 200: 1.80, 400: 4.00, 800: 8.00, 1500: 15.0}
AEROBIC_RATIO = {50: 0.15, 100: 0.325, 200: 0.625, 400: 0.875, 800: 0.925, 1500: 0.96}
STROKE_FACTORS = {
    "libre": 1.00, "espalda": 0.90, "mariposa": 0.76,
    "pecho": 0.68, "combinado": 0.80,
}

# Ventanas (min, max) de mejora realista en s/microciclo para pruebas Tier 2.
SPEED_WINDOWS: dict[tuple[int, str], tuple[float, float]] = {
    (100, "libre"): (0.40, 0.60), (100, "mariposa"): (0.30, 0.50),
    (100, "espalda"): (0.35, 0.50), (100, "pecho"): (0.25, 0.45),
    (100, "combinado"): (0.30, 0.50),
    (50, "libre"): (0.10, 0.25), (50, "mariposa"): (0.08, 0.20),
    (50, "espalda"): (0.10, 0.22), (50, "pecho"): (0.08, 0.18),
    (200, "libre"): (0.80, 1.20), (200, "mariposa"): (0.50, 0.80),
    (200, "espalda"): (0.60, 0.90), (200, "pecho"): (0.45, 0.70),
    (200, "combinado"): (0.55, 0.85),
}
_DEFAULT_WINDOW = (0.20, 0.50)


@dataclass
class FeasibilityResult:
    status: str                      # ok | warning | aggressive
    message: str
    tier: int
    improvement_total: float         # segundos a mejorar
    improvement_per_micro: float     # s/microciclo requerido
    window_min: float | None
    window_max: float                 # techo recomendado s/micro
    recommended_weeks: int | None     # si aggressive: semanas sugeridas
    detail: dict


def analyze_feasibility(
    distance: int,
    stroke: str,
    current_time: float,
    goal_time: float,
    total_weeks: int,
    weeks_per_micro: int = 4,
) -> FeasibilityResult:
    total_improvement = current_time - goal_time
    num_micros = max(total_weeks / weeks_per_micro, 0.001)
    per_micro = total_improvement / num_micros

    if total_improvement <= 0:
        return FeasibilityResult(
            status="ok",
            message="El tiempo meta ya fue alcanzado: el plan será de mantenimiento.",
            tier=1 if distance >= TIER1_THRESHOLD else 2,
            improvement_total=total_improvement, improvement_per_micro=0.0,
            window_min=None, window_max=0.0, recommended_weeks=None, detail={},
        )

    if distance >= TIER1_THRESHOLD:
        return _tier1(distance, stroke, total_improvement, per_micro, weeks_per_micro)
    return _tier2(distance, stroke, total_improvement, per_micro, weeks_per_micro)


def _recommend_weeks(total_improvement: float, ceiling_per_micro: float, weeks_per_micro: int) -> int:
    micros_needed = total_improvement / max(ceiling_per_micro, 0.001)
    return int(math.ceil(micros_needed * weeks_per_micro))


def _tier1(distance: int, stroke: str, total_imp: float, per_micro: float,
           weeks_per_micro: int) -> FeasibilityResult:
    dist_f = DISTANCE_FACTORS.get(distance, distance / 100)
    stroke_f = STROKE_FACTORS.get(stroke, 0.80)
    aero_r = AEROBIC_RATIO.get(distance, 0.85)
    expected = 1.0 * dist_f * stroke_f * aero_r   # regla: 1 s/micro en R1
    ceiling = expected * 1.5

    if per_micro <= expected:
        status = "ok"
        message = (f"Objetivo realista. La regla aeróbica permite hasta "
                   f"{expected:.2f} s/micro y el plan requiere {per_micro:.2f} s/micro.")
    elif per_micro <= ceiling:
        status = "warning"
        message = (f"Exigente pero posible: requiere {per_micro:.2f} s/micro frente a un "
                   f"máximo recomendado de {expected:.2f} s/micro.")
    else:
        status = "aggressive"
        message = (f"Objetivo agresivo: {per_micro:.2f} s/micro supera el techo de "
                   f"{ceiling:.2f} s/micro. Amplía el macrociclo o ajusta la meta.")
    return FeasibilityResult(
        status=status, message=message, tier=1,
        improvement_total=total_imp, improvement_per_micro=per_micro,
        window_min=None, window_max=expected,
        recommended_weeks=_recommend_weeks(total_imp, expected, weeks_per_micro)
        if status == "aggressive" else None,
        detail={"distance_factor": dist_f, "stroke_factor": stroke_f,
                "aerobic_ratio": aero_r, "expected_per_micro": expected},
    )


def _tier2(distance: int, stroke: str, total_imp: float, per_micro: float,
           weeks_per_micro: int) -> FeasibilityResult:
    w_min, w_max = SPEED_WINDOWS.get((distance, stroke), _DEFAULT_WINDOW)
    if per_micro <= w_max:
        status = "ok"
        message = (f"Dentro de la ventana realista ({w_min:.2f}-{w_max:.2f} s/micro) "
                   f"para {distance}m {stroke}.")
    elif per_micro <= w_max * 1.5:
        status = "warning"
        message = (f"Exigente: requiere {per_micro:.2f} s/micro con un techo de "
                   f"{w_max:.2f} s/micro para {distance}m {stroke}.")
    else:
        status = "aggressive"
        message = (f"Agresivo: {per_micro:.2f} s/micro supera el techo de {w_max:.2f} "
                   f"s/micro para {distance}m {stroke}. Extiende el macrociclo o ajusta la meta.")
    return FeasibilityResult(
        status=status, message=message, tier=2,
        improvement_total=total_imp, improvement_per_micro=per_micro,
        window_min=w_min, window_max=w_max,
        recommended_weeks=_recommend_weeks(total_imp, w_max, weeks_per_micro)
        if status == "aggressive" else None,
        detail={"window": [w_min, w_max]},
    )
