"""
progression_engine.py — Motor central de progresión de rendimiento.

Calcula el plan semanal de mejora para un atleta dado su prueba,
tiempos actuales/meta, duración del macrociclo y curva de progresión.

Implementa el modelo de dos tiers:
  Tier 1 (≥ 400m): la mejora está guiada por la base aeróbica.
                   Regla empírica: 1s/micro en R1 → mejora escalada por
                   distancia × estilo × ratio aeróbico.
  Tier 2 (< 400m): la mejora se controla con ventanas de mejora realistas
                   por evento y estilo (fracciones de segundo/micro).

Referencia bitácora: Entradas #001 y #002.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from app.config.training_zones import (
    AEROBIC_BASE_IMPROVEMENT_PER_MICRO,
    AEROBIC_RATIO,
    DISTANCE_FACTORS,
    FEASIBILITY_WARNING_MULTIPLIER,
    SPEED_WINDOWS,
    STROKE_FACTORS,
    TIER_1_THRESHOLD_M,
    ZONE_FACTORS,
    ZONE_LABELS,
)
from app.utils.time_utils import pace_per_100m, to_time_str

CurveType = Literal["linear", "exponential", "logarithmic", "sigmoid"]


# ---------------------------------------------------------------------------
# Data classes de salida
# ---------------------------------------------------------------------------

@dataclass
class TrainingZones:
    """Tiempos objetivo por zona de entrenamiento (segundos por 100m)."""
    pace_100m: float
    R1:   float
    R2:   float
    MVO2: float
    RL:   float
    V:    float

    def as_dict(self) -> dict[str, float]:
        return {
            "R1": self.R1, "R2": self.R2,
            "MVO2": self.MVO2, "RL": self.RL, "V": self.V,
        }

    def pretty(self) -> str:
        lines = []
        for key, label in ZONE_LABELS.items():
            val = getattr(self, key)
            lines.append(f"  {key:<5} ({label:<40}) {to_time_str(val)} /100m")
        return "\n".join(lines)


@dataclass
class WeeklyEntry:
    """
    Plan calculado para una semana del macrociclo.

    El campo central para el entrenador es `pace_100m` (parcial de carrera
    por cada 100m), ya que es la referencia para escalar series de cualquier
    distancia: 100m, 200m, 300m, 400m, etc.

    Las zonas de entrenamiento (zones.R1, R2...) también se expresan en
    segundos por 100m, derivadas de pace_100m × factor_de_zona.

    Para pruebas de 50m: pace_100m = expected_time × 2 (aproximación que
    no considera diferencia de salida — ver bitácora entrada #004).
    """
    week_number:           int
    week_date:             date
    planned_km:            float
    expected_time:         float   # tiempo TOTAL de la prueba (ej: 4:52.00 para 400m)
    pace_100m:             float   # parcial POR 100m — referencia de entrenamiento
    aerobic_target:        float   # R1 /100m — base aeróbica objetivo esta semana
    improvement_vs_prev:   float   # mejora vs. semana anterior (negativo = más rápido)
    improvement_pct:       float   # porcentaje de mejora semana a semana
    cumulative_improvement: float  # mejora acumulada desde inicio (segundos)
    zones:                 TrainingZones


@dataclass
class FeasibilityAnalysis:
    """Resultado del análisis de factibilidad del objetivo."""
    tier:                  int
    total_improvement:     float       # segundos de mejora requeridos
    improvement_per_micro: float       # segundos de mejora por microciclo
    window_min:            float | None
    window_max:            float | None
    status: Literal["ok", "warning", "aggressive"]
    message:               str

    @property
    def status_emoji(self) -> str:
        return {"ok": "✓", "warning": "⚡", "aggressive": "⚠"}[self.status]


@dataclass
class MacrocyclePlan:
    """Resultado completo del análisis de un macrociclo."""
    distance:             int
    stroke:               str
    current_time:         float
    target_time:          float
    num_weeks:            int
    weeks_per_microcycle: int
    total_km:             float
    curve:                CurveType
    feasibility:          FeasibilityAnalysis
    weekly_plan:          list[WeeklyEntry]

    def summary(self) -> str:
        fe = self.feasibility
        return (
            f"Tier {fe.tier} | "
            f"Mejora: {fe.total_improvement:.2f}s | "
            f"{fe.improvement_per_micro:.2f} s/micro | "
            f"{fe.status_emoji} {fe.status.upper()}"
        )


# ---------------------------------------------------------------------------
# Motor principal
# ---------------------------------------------------------------------------

class ProgressionEngine:
    """
    Genera planes de progresión semanales para nadadores de competencia.

    Uso básico:
        engine = ProgressionEngine()
        plan = engine.analyze(
            distance=100, stroke='mariposa',
            current_time=67.8, target_time=62.0,
            num_weeks=12, weeks_per_microcycle=4,
            total_km=320, curve='sigmoid',
            start_date=date(2025, 3, 31),
        )
    """

    # ── API pública ────────────────────────────────────────────────────────

    def analyze(
        self,
        distance: int,
        stroke: str,
        current_time: float,
        target_time: float,
        num_weeks: int,
        weeks_per_microcycle: int,
        total_km: float,
        curve: CurveType = "sigmoid",
        start_date: date | None = None,
    ) -> MacrocyclePlan:
        """
        Analiza la factibilidad del objetivo y genera el plan semanal.

        Args:
            distance:             Distancia de la prueba en metros.
            stroke:               Estilo (libre, mariposa, espalda, pecho, combinado).
            current_time:         Tiempo actual del atleta en segundos.
            target_time:          Tiempo meta al final del macrociclo en segundos.
            num_weeks:            Duración total del macrociclo en semanas.
            weeks_per_microcycle: Semanas por microciclo (4 o 5).
            total_km:             Kilometraje total planificado para el macrociclo.
            curve:                Curva de distribución de la mejora.
            start_date:           Fecha de inicio (default: hoy).
        """
        if start_date is None:
            start_date = date.today()

        stroke = stroke.lower().strip()
        num_micros = num_weeks / weeks_per_microcycle

        feasibility = self._analyze_feasibility(
            distance, stroke,
            total_improvement=current_time - target_time,
            num_micros=num_micros,
        )

        weekly_plan = self._generate_weekly_plan(
            distance=distance,
            stroke=stroke,
            current_time=current_time,
            target_time=target_time,
            num_weeks=num_weeks,
            total_km=total_km,
            curve=curve,
            start_date=start_date,
        )

        return MacrocyclePlan(
            distance=distance,
            stroke=stroke,
            current_time=current_time,
            target_time=target_time,
            num_weeks=num_weeks,
            weeks_per_microcycle=weeks_per_microcycle,
            total_km=total_km,
            curve=curve,
            feasibility=feasibility,
            weekly_plan=weekly_plan,
        )

    # ── Factibilidad ───────────────────────────────────────────────────────

    def _analyze_feasibility(
        self,
        distance: int,
        stroke: str,
        total_improvement: float,
        num_micros: float,
    ) -> FeasibilityAnalysis:

        tier = 1 if distance >= TIER_1_THRESHOLD_M else 2
        imp_per_micro = total_improvement / num_micros if num_micros > 0 else 0.0

        if tier == 1:
            return self._feasibility_tier1(distance, stroke, imp_per_micro)
        else:
            return self._feasibility_tier2(distance, stroke, total_improvement, imp_per_micro)

    def _feasibility_tier1(
        self,
        distance: int,
        stroke: str,
        imp_per_micro: float,
    ) -> FeasibilityAnalysis:
        """
        Tier 1: compara contra la mejora esperada según la regla 1s/micro.
        La mejora esperada en la prueba = 1s_base × dist_factor × stroke_factor × aerobic_ratio
        """
        stroke_f   = STROKE_FACTORS.get(stroke, 0.80)
        aerobic_r  = AEROBIC_RATIO.get(distance, 0.85)
        dist_f     = DISTANCE_FACTORS.get(distance, distance / 100)

        expected_per_micro = (
            AEROBIC_BASE_IMPROVEMENT_PER_MICRO * dist_f * stroke_f * aerobic_r
        )
        window_max = expected_per_micro * FEASIBILITY_WARNING_MULTIPLIER

        if imp_per_micro <= expected_per_micro:
            status = "ok"
            msg = (
                f"Objetivo conservador/realista. "
                f"Mejora esperada por la regla aeróbica: {expected_per_micro:.2f} s/micro, "
                f"requerido: {imp_per_micro:.2f} s/micro."
            )
        elif imp_per_micro <= window_max:
            status = "warning"
            msg = (
                f"Objetivo exigente pero posible. "
                f"Requerido: {imp_per_micro:.2f} s/micro "
                f"(máximo recomendado: {expected_per_micro:.2f} s/micro)."
            )
        else:
            status = "aggressive"
            msg = (
                f"Objetivo agresivo. "
                f"Requerido: {imp_per_micro:.2f} s/micro supera el techo de "
                f"{window_max:.2f} s/micro para {distance}m {stroke}. "
                f"Considera ampliar el macrociclo o ajustar la meta."
            )

        return FeasibilityAnalysis(
            tier=1,
            total_improvement=imp_per_micro * (1 / 1),  # placeholder
            improvement_per_micro=imp_per_micro,
            window_min=None,
            window_max=expected_per_micro,
            status=status,
            message=msg,
        )

    def _feasibility_tier2(
        self,
        distance: int,
        stroke: str,
        total_improvement: float,
        imp_per_micro: float,
    ) -> FeasibilityAnalysis:
        """
        Tier 2: compara contra la ventana de mejora fisiológica
        específica para el evento y estilo.
        """
        key = (distance, stroke)
        window = SPEED_WINDOWS.get(key)

        # Fallback: buscar por distancia si no hay clave exacta
        if window is None:
            for (d, _), v in SPEED_WINDOWS.items():
                if d == distance:
                    window = v
                    break

        if window is None:
            window = (0.20, 0.50)  # fallback seguro

        w_min, w_max = window

        if imp_per_micro <= w_max:
            status = "ok"
            msg = (
                f"Dentro de la ventana realista "
                f"({w_min:.2f}–{w_max:.2f} s/micro para {distance}m {stroke})."
            )
        elif imp_per_micro <= w_max * FEASIBILITY_WARNING_MULTIPLIER:
            status = "warning"
            msg = (
                f"Exigente pero alcanzable con muy buen trabajo. "
                f"Requerido: {imp_per_micro:.2f} s/micro, "
                f"techo normal: {w_max:.2f} s/micro."
            )
        else:
            status = "aggressive"
            msg = (
                f"Objetivo agresivo para {distance}m {stroke}. "
                f"Requerido: {imp_per_micro:.2f} s/micro supera el techo "
                f"de {w_max:.2f} s/micro. "
                f"Considera extender el macrociclo o revisar la meta."
            )

        return FeasibilityAnalysis(
            tier=2,
            total_improvement=total_improvement,
            improvement_per_micro=imp_per_micro,
            window_min=w_min,
            window_max=w_max,
            status=status,
            message=msg,
        )

    # ── Curvas de progresión ───────────────────────────────────────────────

    def _curve_progress(self, x: float, curve: CurveType) -> float:
        """
        Progreso acumulado normalizado en la posición x (0→1 del macrociclo).
        Retorna un valor en [0, 1] que representa qué fracción de la mejora
        total ya debe haberse alcanzado en esa semana.

        Curvas:
          linear:      mejora constante cada semana.
          exponential: mejoras rápidas al inicio, se desacelera.
          logarithmic: ganancias decrecientes (inicio rápido, final lento).
          sigmoid:     lento → rápido → lento (S-curve, más fisiológica).
        """
        x = max(0.0, min(1.0, x))  # clamp a [0, 1]

        if curve == "linear":
            return x

        elif curve == "exponential":
            k = 4.0
            return (1.0 - math.exp(-k * x)) / (1.0 - math.exp(-k))

        elif curve == "logarithmic":
            return math.log(1.0 + 9.0 * x) / math.log(10.0)

        elif curve == "sigmoid":
            def _sig(t: float) -> float:
                return 1.0 / (1.0 + math.exp(-10.0 * (t - 0.5)))
            s0, s1 = _sig(0.0), _sig(1.0)
            return (_sig(x) - s0) / (s1 - s0)

        return x  # fallback lineal

    # ── Zonas de entrenamiento ─────────────────────────────────────────────

    def _calculate_zones(self, pace_100m_s: float) -> TrainingZones:
        """
        Calcula las zonas de entrenamiento a partir del parcial /100m.
        Cada zona = parcial × factor de zona.
        """
        return TrainingZones(
            pace_100m=pace_100m_s,
            R1=pace_100m_s   * ZONE_FACTORS["R1"],
            R2=pace_100m_s   * ZONE_FACTORS["R2"],
            MVO2=pace_100m_s * ZONE_FACTORS["MVO2"],
            RL=pace_100m_s   * ZONE_FACTORS["RL"],
            V=pace_100m_s    * ZONE_FACTORS["V"],
        )

    # ── Distribución de kilómetros ─────────────────────────────────────────

    def _distribute_km(self, num_weeks: int, total_km: float) -> list[float]:
        """
        Distribuye el kilometraje total entre semanas usando una carga
        progresiva con descenso (taper) en las últimas semanas.

        Patrón: sube gradualmente hasta ~70% del macrociclo,
        luego cae para el periodo de pico/descenso.
        """
        raw: list[float] = []
        for i in range(num_weeks):
            x = i / max(num_weeks - 1, 1)   # 0.0 a 1.0
            if x <= 0.70:
                factor = 0.65 + 0.35 * (x / 0.70)   # 0.65 → 1.00
            else:
                taper_x = (x - 0.70) / 0.30
                factor = 1.00 - 0.60 * taper_x       # 1.00 → 0.40
            raw.append(max(factor, 0.10))

        total_raw = sum(raw)
        return [round(f * total_km / total_raw, 1) for f in raw]

    # ── Plan semanal ───────────────────────────────────────────────────────

    def _generate_weekly_plan(
        self,
        distance: int,
        stroke: str,
        current_time: float,
        target_time: float,
        num_weeks: int,
        total_km: float,
        curve: CurveType,
        start_date: date,
    ) -> list[WeeklyEntry]:
        """
        Genera la lista de WeeklyEntry con el plan completo semana a semana.
        """
        total_improvement = current_time - target_time
        km_per_week = self._distribute_km(num_weeks, total_km)

        entries: list[WeeklyEntry] = []
        prev_time = current_time

        for i in range(num_weeks):
            # Progreso acumulado al final de esta semana
            x = (i + 1) / num_weeks
            progress = self._curve_progress(x, curve)

            expected_time = current_time - total_improvement * progress
            p100m = pace_per_100m(expected_time, distance)
            zones = self._calculate_zones(p100m)

            improvement = expected_time - prev_time   # negativo = más rápido
            improvement_pct = (improvement / prev_time * 100) if prev_time else 0.0

            entries.append(WeeklyEntry(
                week_number=i + 1,
                week_date=start_date + timedelta(weeks=i),
                planned_km=km_per_week[i],
                expected_time=expected_time,
                pace_100m=p100m,
                aerobic_target=zones.R1,
                improvement_vs_prev=improvement,
                improvement_pct=improvement_pct,
                cumulative_improvement=current_time - expected_time,
                zones=zones,
            ))
            prev_time = expected_time

        return entries
