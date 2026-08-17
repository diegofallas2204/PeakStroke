"""Factibilidad del objetivo — adaptador sobre `dominio.servicios.envolvente`.

El veredicto lo da el motor único desde el paso 4: compara la mejora pedida con
el techo científico del nivel para esa prueba (§5.3) y, cuando lo supera, dice
cuántas semanas extra harían falta al ritmo seguro. Aquí queda la forma vieja
del resultado, que es lo que el simulador todavía consume.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.dominio.servicios.envolvente import DISTANCIA_TIER_1, factibilidad
from app.dominio.servicios.tablas import (
    MAX_SEMANAS_EXTENSION as MAX_EXTENSION_WEEKS,
)
from app.dominio.servicios.tablas import (
    RATIO_EXIGENTE as WARNING_RATIO,
)
from app.dominio.servicios.tablas import (
    RATIO_REALISTA as OK_RATIO,
)

TIER1_THRESHOLD = DISTANCIA_TIER_1

__all__ = [
    "MAX_EXTENSION_WEEKS", "OK_RATIO", "TIER1_THRESHOLD", "WARNING_RATIO",
    "FeasibilityResult", "analyze_feasibility",
]


@dataclass
class FeasibilityResult:
    status: str                      # ok | warning | aggressive
    message: str
    tier: int
    improvement_total: float         # segundos a mejorar
    improvement_per_micro: float     # s/microciclo requerido
    window_min: float | None
    window_max: float                 # techo recomendado s/micro
    recommended_weeks: int | None     # si aggressive: semanas TOTALES sugeridas
    extension_weeks: int | None       # solo las semanas EXTRA tras el macro (capadas)
    realistic_ceiling: float          # mejor tiempo realista al cerrar el macro (s)
    safe_rate_per_week: float         # mejora segura media por semana (s/sem)
    detail: dict


def analyze_feasibility(
    distance: int,
    stroke: str,
    current_time: float,
    goal_time: float,
    total_weeks: int,
    weeks_per_micro: int = 4,
    n_mac: int = 1,
    age: int | None = None,
) -> FeasibilityResult:
    """`stroke` no entra en el cálculo: el techo I_max es de la distancia."""
    f = factibilidad(
        distance, current_time, goal_time, total_weeks,
        semanas_por_micro=weeks_per_micro, n_mac=n_mac, edad=age,
    )
    return FeasibilityResult(
        status=f.estado, message=f.mensaje, tier=f.tier,
        improvement_total=f.mejora_total_s, improvement_per_micro=f.mejora_por_micro_s,
        window_min=None, window_max=f.techo_por_micro_s,
        recommended_weeks=f.semanas_recomendadas, extension_weeks=f.semanas_extra,
        realistic_ceiling=f.techo_realista, safe_rate_per_week=f.ritmo_seguro_semanal_s,
        detail=f.detalle,
    )
