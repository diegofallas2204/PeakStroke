"""Análisis de factibilidad del objetivo — adaptador sobre el motor de dominio.

Usa la ciencia de I_max del sandbox (`app.domain`): compara la mejora pedida
contra el techo científico del nivel del atleta para la prueba, escalado por el
número de mesociclos del macro. Reemplaza las bandas/ventanas anteriores.

- nivel = clasificación por umbral (ritmo de carrera × factor MVO2), §2.4
- techo  = I_MAX_TABLE[nivel][evento] × (semanas / 5)                  §4.2 / §5.3
- ratio  = mejora_pedida% / techo% → ok (≤0.85) | warning (≤1.15) | aggressive

Tier (1 = ≥400m aeróbico, 2 = <400m velocidad) se conserva solo como etiqueta.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain import MAX_EXTENSION_WEEKS

from .envelope import science_envelope

TIER1_THRESHOLD = 400
OK_RATIO = 0.85
WARNING_RATIO = 1.15
# El tope de semanas de extensión NO se declara aquí: se importa del motor de
# dominio (`app.domain.MAX_EXTENSION_WEEKS`, alias `ScienceEngine.MAX_EXTENSION_WEEKS`),
# que es la única fuente. Hasta 2026-08-13 este módulo tenía su propio 26 bajo un
# comentario que afirmaba coincidir con el dominio, donde valía 30: el simulador
# sugería 41 semanas mientras el motor extendía hasta 45.

__all__ = ["FeasibilityResult", "MAX_EXTENSION_WEEKS", "analyze_feasibility"]


@dataclass
class FeasibilityResult:
    status: str                      # ok | warning | aggressive
    message: str
    tier: int
    improvement_total: float         # segundos a mejorar
    improvement_per_micro: float     # s/microciclo requerido
    window_min: float | None
    window_max: float                 # techo recomendado s/micro
    recommended_weeks: int | None     # si aggressive: semanas TOTALES sugeridas (macro + extensión)
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
    total_improvement = current_time - goal_time
    num_micros = max(total_weeks / weeks_per_micro, 0.001)
    per_micro = total_improvement / num_micros
    tier = 1 if distance >= TIER1_THRESHOLD else 2

    if total_improvement <= 0:
        return FeasibilityResult(
            status="ok",
            message="El tiempo meta ya fue alcanzado: el plan será de mantenimiento.",
            tier=tier, improvement_total=total_improvement, improvement_per_micro=0.0,
            window_min=None, window_max=0.0, recommended_weeks=None,
            extension_weeks=None, realistic_ceiling=current_time,
            safe_rate_per_week=0.0, detail={},
        )

    env = science_envelope(distance, current_time, total_weeks, n_mac=n_mac, age=age)
    level, event = env.level, env.event
    i_max_total = env.i_max_total                       # techo de mejora (fracción)
    safe_total_s = env.safe_total_s                     # mejora máx creíble en el macro (s)
    realistic_ceiling = env.realistic_ceiling           # mejor tiempo realista al cerrar el macro

    pct = total_improvement / current_time
    ratio = pct / i_max_total if i_max_total else 999.0

    ceiling_per_micro = safe_total_s / num_micros       # techo s/micro
    # Modelo de EXTENSIÓN (espejo del motor de dominio, §5.3): el macro cierra en
    # el techo realista y, si la meta lo supera, se añaden semanas extra al ritmo
    # seguro medio por semana hasta alcanzarla. Esto reemplaza la antigua fórmula
    # lineal `ceil(pct / (i_max_meso/5))`, que disparaba semanas absurdas.
    safe_rate_per_week = safe_total_s / total_weeks if total_weeks else 0.0

    detail = {
        "level": level, "event": event, "i_max_meso": round(i_max_total / (total_weeks / 5.0), 4),
        "i_max_total_pct": round(i_max_total * 100, 2), "ratio": round(ratio, 3),
        "requested_pct": round(pct * 100, 2),
    }

    if ratio <= OK_RATIO:
        status = "ok"
        message = (f"Realista — pides {pct*100:.2f}% y el techo científico para "
                   f"{level}/{event}m en {total_weeks} sem es {i_max_total*100:.2f}% "
                   f"(uso {ratio*100:.0f}%).")
        recommended = None
        n_ext = None
    elif ratio <= WARNING_RATIO:
        status = "warning"
        message = (f"Exigente — pides {pct*100:.2f}%, cerca del techo "
                   f"{i_max_total*100:.2f}% ({ratio*100:.0f}% del máximo).")
        recommended = None
        n_ext = None
    else:
        status = "aggressive"
        remaining = realistic_ceiling - goal_time       # lo que falta tras el macro (s)
        n_ext = math.ceil(remaining / safe_rate_per_week) if safe_rate_per_week > 0 else 0
        n_ext = max(0, min(n_ext, MAX_EXTENSION_WEEKS))
        recommended = total_weeks + n_ext
        capped = " (tope alcanzado; la meta sigue siendo muy exigente)" if n_ext == MAX_EXTENSION_WEEKS else ""
        message = (f"Agresivo — pides {pct*100:.2f}%, supera el techo "
                   f"{i_max_total*100:.2f}% ({ratio*100:.0f}%). El motor estima "
                   f"~{recommended} semanas en total ({n_ext} extra){capped}.")

    return FeasibilityResult(
        status=status, message=message, tier=tier,
        improvement_total=total_improvement, improvement_per_micro=per_micro,
        window_min=None, window_max=round(ceiling_per_micro, 3),
        recommended_weeks=recommended, extension_weeks=n_ext,
        realistic_ceiling=round(realistic_ceiling, 2),
        safe_rate_per_week=round(safe_rate_per_week, 4), detail=detail,
    )
