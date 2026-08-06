"""Envelope científico de mejora — fuente única del techo I_max.

Centraliza la ciencia que acota cuánto y cuán rápido puede mejorar un atleta en
un macrociclo, derivada del motor de dominio (`app.domain`):

- nivel = clasificación por umbral (ritmo de carrera × factor MVO2), §2.4
- techo total = I_MAX_TABLE[nivel][evento] × degradación^(n_mac-1) × juventud × (semanas/5)
- ritmo seguro POR SEMANA = el mayor escalón semanal de la curva científica
  (la curva F_FASE es la trayectoria validada; su semana más rápida —el taper—
  define el ritmo fisiológico máximo). Ninguna curva puede superarlo.

Tanto `feasibility.analyze_feasibility` (veredicto) como
`progression.generate_plan` (acotar la curva elegida) consumen este envelope, de
modo que el techo que muestra la UI y el punto donde cierra la curva coinciden.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain import (
    I_MAX_TABLE,
    MACROCYCLE_DEGRADATION,
    classify_level,
    profile_for_event,
    youth_imax_factor,
    zone_factors,
)

from .curves import curve_progress


def nearest_event(distance: int) -> int:
    known = sorted(I_MAX_TABLE["elite"].keys())
    return min(known, key=lambda d: abs(d - distance))


def level_for(distance: int, current_time: float) -> str:
    """Clasifica el nivel por el umbral (ritmo de carrera × factor MVO2)."""
    profile = profile_for_event(distance)
    race_pace_0 = current_time / (distance / 100.0)
    threshold = race_pace_0 * zone_factors(profile, distance)["MVO2"]
    return classify_level(threshold)


def _peak_week_fraction(total_weeks: int) -> float:
    """Mayor escalón semanal de la curva científica sobre `total_weeks`.

    Es la fracción del techo total que la fisiología permite ganar en su semana
    más rápida (el taper). Sirve de tope al ritmo de cualquier curva."""
    n = max(total_weeks, 1)
    return max(
        curve_progress(k / n, "science") - curve_progress((k - 1) / n, "science")
        for k in range(1, n + 1)
    )


@dataclass
class Envelope:
    level: str
    event: int
    i_max_total: float        # fracción del tiempo actual (techo de mejora del macro)
    safe_total_s: float       # mejora máx creíble en el macro (s)
    realistic_ceiling: float  # mejor tiempo realista al cerrar el macro (s)
    peak_week_s: float        # mejora máx fisiológica de una sola semana (s)


def science_envelope(
    distance: int,
    current_time: float,
    total_weeks: int,
    n_mac: int = 1,
    age: int | None = None,
) -> Envelope:
    """Techo de mejora I_max + ritmo seguro por semana para (prueba, nivel, macro)."""
    event = nearest_event(distance)
    level = level_for(distance, current_time)
    i_max_meso = (
        I_MAX_TABLE[level][event]
        * (MACROCYCLE_DEGRADATION ** (n_mac - 1))
        * youth_imax_factor(age)
    )
    i_max_total = i_max_meso * (total_weeks / 5.0)
    safe_total_s = current_time * i_max_total
    realistic_ceiling = current_time - safe_total_s
    peak_week_s = safe_total_s * _peak_week_fraction(total_weeks)
    return Envelope(
        level=level, event=event, i_max_total=i_max_total,
        safe_total_s=safe_total_s, realistic_ceiling=realistic_ceiling,
        peak_week_s=peak_week_s,
    )
