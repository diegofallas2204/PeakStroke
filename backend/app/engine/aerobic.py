"""Análisis de tests aeróbicos: T-30, T-15, tests personalizados N×D y CSS.

Todos los resultados se normalizan a un parcial por 100m (la unidad central
del sistema), que define la base aeróbica del atleta.
"""
from __future__ import annotations

from dataclasses import dataclass

# Pendiente (s/100m por repetición) a partir de la cual el test se considera
# en mejora o en caída en lugar de estable.
_TREND_SLOPE = 0.05


@dataclass
class AerobicAnalysis:
    per100_splits: list[float]     # cada repetición normalizada a s/100m
    avg_per100: float              # base aeróbica (s/100m)
    std_dev: float                 # consistencia del test
    trend: str                     # improving | stable | declining
    trend_slope: float             # s/100m por repetición (negativo = mejora)


def analyze_splits(splits: list[float], rep_distance: int = 100) -> AerobicAnalysis:
    """Analiza los parciales de un test aeróbico.

    `splits` son los tiempos de cada repetición en segundos; `rep_distance`
    permite tests personalizados (ej. 12×400: cada split se divide entre 4
    para obtener el parcial por 100m, como hacen los entrenadores a mano).
    """
    if not splits:
        raise ValueError("Se requiere al menos un parcial")
    if rep_distance <= 0:
        raise ValueError("La distancia de repetición debe ser positiva")

    factor = rep_distance / 100.0
    per100 = [round(s / factor, 2) for s in splits]
    n = len(per100)
    avg = sum(per100) / n
    variance = sum((t - avg) ** 2 for t in per100) / n
    std = variance ** 0.5

    slope = _linear_slope(per100)
    if slope <= -_TREND_SLOPE:
        trend = "improving"
    elif slope >= _TREND_SLOPE:
        trend = "declining"
    else:
        trend = "stable"

    return AerobicAnalysis(
        per100_splits=per100,
        avg_per100=round(avg, 2),
        std_dev=round(std, 3),
        trend=trend,
        trend_slope=round(slope, 4),
    )


def _linear_slope(values: list[float]) -> float:
    """Pendiente de regresión lineal simple sobre el índice de repetición."""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den else 0.0


@dataclass
class CssResult:
    css_ms: float        # velocidad crítica de nado en m/s
    t_pace_100: float    # pace por 100m equivalente (segundos)


def css_from_400_50(t400: float, t50: float) -> CssResult:
    """Critical Swim Speed según Wakayoshi et al. (1992): 350/(T400-T50)."""
    if t400 <= t50:
        raise ValueError("El tiempo de 400m debe ser mayor al de 50m")
    css = 350.0 / (t400 - t50)
    return CssResult(css_ms=round(css, 3), t_pace_100=round(100.0 / css, 2))
