"""
training_plans/progression_engine.py — Motor de progresión portado al backend.

Genera el plan semanal completo para un AthleteEvent dado:
  - Curva ideal (todas las semanas)
  - Curva recalculada (redistribuyendo en semanas no deshabilitadas)
  - Zonas de entrenamiento por semana (R1..V en pace_100m)
  - Distribución de kilómetros con taper

Motor de dos tiers:
  Tier 1 (≥400m): guiado por base aeróbica, regla 1s/micro
  Tier 2 (<400m):  ventanas de mejora fisiológica por evento

Fuente de verdad de factores: zones_config (al final de este archivo).
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

# ---------------------------------------------------------------------------
# Configuración de zonas y factores (fuente de verdad única del backend)
# ---------------------------------------------------------------------------

TIER_1_THRESHOLD_M = 400

ZONE_FACTORS: dict[str, float] = {
    "R1": 1.375, "R2": 1.275, "MVO2": 1.175, "RL": 1.125, "V": 1.075,
}

DISTANCE_FACTORS: dict[int, float] = {
    50: 0.15, 100: 0.45, 200: 1.80, 400: 4.00, 800: 8.00, 1500: 15.00,
}

AEROBIC_RATIO: dict[int, float] = {
    50: 0.15, 100: 0.325, 200: 0.625, 400: 0.875, 800: 0.925, 1500: 0.960,
}

STROKE_FACTORS: dict[str, float] = {
    "libre": 1.000, "espalda": 0.900, "mariposa": 0.760,
    "pecho": 0.680, "combinado": 0.800,
}

SPEED_WINDOWS: dict[tuple[int, str], tuple[float, float]] = {
    (100, "libre"): (0.40, 0.60), (100, "espalda"): (0.35, 0.50),
    (100, "mariposa"): (0.30, 0.50), (100, "pecho"): (0.25, 0.45),
    (50, "libre"): (0.10, 0.25), (50, "espalda"): (0.10, 0.22),
    (50, "mariposa"): (0.08, 0.20), (50, "pecho"): (0.08, 0.18),
    (200, "libre"): (0.80, 1.20), (200, "espalda"): (0.60, 0.90),
    (200, "mariposa"): (0.50, 0.80), (200, "pecho"): (0.45, 0.70),
}

AEROBIC_BASE_IMPROVEMENT_PER_MICRO = 1.0
FEASIBILITY_WARNING_MULTIPLIER = 1.5

CurveType = Literal["linear", "exponential", "logarithmic", "sigmoid"]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WeekZones:
    pace_100m: float
    r1: float
    r2: float
    mvo2: float
    rl: float
    v: float


@dataclass
class WeekEntry:
    week_number: int
    week_date: date
    planned_km: float
    expected_time: float        # curva ideal
    expected_time_recalc: float  # curva recalculada (si hay parones)
    pace_100m: float
    pace_100m_recalc: float
    zones: WeekZones
    phase_name: str
    feasibility: str            # ok | warning | aggressive
    disabled: bool = False


@dataclass
class FeasibilityResult:
    status: str   # ok | warning | aggressive
    message: str


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

class ProgressionEngine:

    def generate_plan(
        self,
        *,
        distance: int,
        stroke: str,
        current_time: float,
        goal_time: float,
        num_weeks: int,
        microcycle_weeks: int,
        total_km: float,
        curve: CurveType,
        start_date: date,
        phases: list[dict],          # [{"name": "Base", "week_start": 1, "week_end": 4}, ...]
        disabled_weeks: set[int] | None = None,
    ) -> list[WeekEntry]:
        """
        Genera el plan semana a semana para un AthleteEvent.

        Args:
            distance:          Metros de la prueba.
            stroke:            Estilo ('libre', 'espalda', etc.)
            current_time:      Tiempo actual en segundos.
            goal_time:         Tiempo meta en segundos.
            num_weeks:         Semanas totales del macrociclo.
            microcycle_weeks:  Semanas por microciclo (4 o 5).
            total_km:          Km totales del macro.
            curve:             Tipo de curva de progresión.
            start_date:        Fecha de inicio (lunes de la semana 1).
            phases:            Lista de fases con rangos de semana.
            disabled_weeks:    Semanas inhabilitadas por parón.
        """
        disabled_weeks = disabled_weeks or set()
        total_improvement = current_time - goal_time
        num_micros = num_weeks / microcycle_weeks
        feasibility = self._check_feasibility(distance, stroke, total_improvement, num_micros)
        km_per_week = self._distribute_km(num_weeks, total_km)

        # Curva ideal sobre todas las semanas
        ideal_times = self._apply_curve(current_time, total_improvement, num_weeks, curve)

        # Curva recalculada: redistribuye sobre semanas activas
        active_indices = [i for i in range(num_weeks) if (i + 1) not in disabled_weeks]
        recalc_times = list(ideal_times)  # copia base
        if disabled_weeks and active_indices:
            # Calcular mejora restante a partir de la primera semana deshabilitada
            first_disabled = min(disabled_weeks)
            remaining_improvement = ideal_times[first_disabled - 2] - goal_time if first_disabled > 1 else total_improvement
            active_after = [i for i in active_indices if i >= first_disabled - 1]
            if active_after:
                recalc_after = self._apply_curve(
                    ideal_times[first_disabled - 2] if first_disabled > 1 else current_time,
                    remaining_improvement,
                    len(active_after),
                    curve,
                )
                for j, idx in enumerate(active_after):
                    recalc_times[idx] = recalc_after[j]

        # Construir WeekEntry por semana
        phase_map = self._build_phase_map(phases, num_weeks)
        entries: list[WeekEntry] = []

        for i in range(num_weeks):
            week_num = i + 1
            exp_t = ideal_times[i]
            rec_t = recalc_times[i]
            p100 = self._pace_100m(exp_t, distance)
            p100r = self._pace_100m(rec_t, distance)

            entries.append(WeekEntry(
                week_number=week_num,
                week_date=start_date + timedelta(weeks=i),
                planned_km=km_per_week[i],
                expected_time=exp_t,
                expected_time_recalc=rec_t,
                pace_100m=p100,
                pace_100m_recalc=p100r,
                zones=self._calculate_zones(p100),
                phase_name=phase_map.get(week_num, ""),
                feasibility=feasibility.status,
                disabled=week_num in disabled_weeks,
            ))

        return entries

    # ── Cálculo de factibilidad ────────────────────────────────────────────

    def _check_feasibility(
        self, distance: int, stroke: str, total_improvement: float, num_micros: float
    ) -> FeasibilityResult:
        imp_per_micro = total_improvement / num_micros if num_micros else 0

        if distance >= TIER_1_THRESHOLD_M:
            # Tier 1: basado en regla aeróbica
            sf = STROKE_FACTORS.get(stroke, 0.80)
            ar = AEROBIC_RATIO.get(distance, 0.85)
            df = DISTANCE_FACTORS.get(distance, distance / 100)
            ceiling = AEROBIC_BASE_IMPROVEMENT_PER_MICRO * df * sf * ar
            if imp_per_micro <= ceiling:
                return FeasibilityResult("ok", f"Objetivo realista ({imp_per_micro:.2f} s/micro)")
            elif imp_per_micro <= ceiling * FEASIBILITY_WARNING_MULTIPLIER:
                return FeasibilityResult("warning", f"Objetivo exigente ({imp_per_micro:.2f} s/micro, techo {ceiling:.2f})")
            return FeasibilityResult("aggressive", f"Objetivo agresivo ({imp_per_micro:.2f} s/micro supera techo {ceiling:.2f})")
        else:
            # Tier 2: ventana por evento
            key = (distance, stroke)
            window = SPEED_WINDOWS.get(key, (0.20, 0.50))
            wmin, wmax = window
            if imp_per_micro <= wmax:
                return FeasibilityResult("ok", f"Dentro de la ventana realista ({wmin:.2f}–{wmax:.2f} s/micro)")
            elif imp_per_micro <= wmax * FEASIBILITY_WARNING_MULTIPLIER:
                return FeasibilityResult("warning", f"Exigente ({imp_per_micro:.2f} s/micro, techo {wmax:.2f})")
            return FeasibilityResult("aggressive", f"Agresivo ({imp_per_micro:.2f} s/micro supera techo {wmax:.2f})")

    # ── Curvas de progresión ───────────────────────────────────────────────

    def _curve_value(self, x: float, curve: CurveType) -> float:
        """Progreso acumulado normalizado [0, 1] en la posición x [0, 1]."""
        x = max(0.0, min(1.0, x))
        if curve == "linear":
            return x
        elif curve == "exponential":
            k = 4.0
            return (1.0 - math.exp(-k * x)) / (1.0 - math.exp(-k))
        elif curve == "logarithmic":
            return math.log(1.0 + 9.0 * x) / math.log(10.0)
        elif curve == "sigmoid":
            def _s(t: float) -> float:
                return 1.0 / (1.0 + math.exp(-10.0 * (t - 0.5)))
            s0, s1 = _s(0.0), _s(1.0)
            return (_s(x) - s0) / (s1 - s0)
        return x

    def _apply_curve(
        self, start_time: float, total_improvement: float, num_weeks: int, curve: CurveType
    ) -> list[float]:
        return [
            start_time - total_improvement * self._curve_value((i + 1) / num_weeks, curve)
            for i in range(num_weeks)
        ]

    # ── Zonas ─────────────────────────────────────────────────────────────

    def _pace_100m(self, race_time: float, distance: int) -> float:
        return race_time / (distance / 100.0)

    def _calculate_zones(self, pace_100m: float) -> WeekZones:
        return WeekZones(
            pace_100m=pace_100m,
            r1=pace_100m * ZONE_FACTORS["R1"],
            r2=pace_100m * ZONE_FACTORS["R2"],
            mvo2=pace_100m * ZONE_FACTORS["MVO2"],
            rl=pace_100m * ZONE_FACTORS["RL"],
            v=pace_100m * ZONE_FACTORS["V"],
        )

    # ── Distribución de kilómetros ─────────────────────────────────────────

    def _distribute_km(self, num_weeks: int, total_km: float) -> list[float]:
        raw = []
        for i in range(num_weeks):
            x = i / max(num_weeks - 1, 1)
            factor = (0.65 + 0.35 * (x / 0.70)) if x <= 0.70 else (1.00 - 0.60 * ((x - 0.70) / 0.30))
            raw.append(max(factor, 0.10))
        total_raw = sum(raw)
        return [round(f * total_km / total_raw, 1) for f in raw]

    # ── Mapa de fases ─────────────────────────────────────────────────────

    def _build_phase_map(self, phases: list[dict], num_weeks: int) -> dict[int, str]:
        phase_map: dict[int, str] = {}
        for phase in phases:
            for w in range(phase["week_start"], phase["week_end"] + 1):
                if 1 <= w <= num_weeks:
                    phase_map[w] = phase["name"]
        return phase_map


# ---------------------------------------------------------------------------
# T-30/T-15: cálculo de base aeróbica desde splits
# ---------------------------------------------------------------------------

def calculate_aerobic_base(splits: list[float]) -> dict:
    """
    Calcula estadísticas del test T-30/T-15.

    Args:
        splits: Lista de tiempos en segundos (30 o 15 repeticiones)

    Returns:
        {avg_time, std_dev, trend_slope, trend_direction}
    """
    if not splits:
        raise ValueError("La lista de splits no puede estar vacía")

    avg = statistics.mean(splits)
    std = statistics.stdev(splits) if len(splits) > 1 else 0.0

    # Tendencia lineal simple (pendiente)
    n = len(splits)
    xs = list(range(1, n + 1))
    x_mean = statistics.mean(xs)
    numerator = sum((xs[i] - x_mean) * (splits[i] - avg) for i in range(n))
    denominator = sum((xs[i] - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0.0

    return {
        "avg_time": round(avg, 3),
        "std_dev": round(std, 3),
        "trend_slope": round(slope, 4),  # positivo = se cansa (más lento), negativo = mejora
        "trend_direction": "deteriorating" if slope > 0.05 else "stable" if slope > -0.05 else "improving",
    }
