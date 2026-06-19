"""Motor de progresión: genera el plan semana a semana y lo recalcula.

Funciones puras: reciben parámetros y retornan estructuras de datos, sin tocar
la base de datos. La capa de servicio persiste el resultado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .curves import curve_progress
from .km_distribution import distribute_km
from .zones import calc_zones

# Tolerancia para clasificar real vs. esperado (fracción del tiempo esperado).
STATUS_TOLERANCE = 0.004  # ±0.4%

DEFAULT_PHASES = [
    # (nombre, tipo, fracción del macrociclo, color)
    ("Base", "base", 0.30, "#22d3ee"),
    ("Construcción", "build", 0.40, "#8b5cf6"),
    ("Pico", "peak", 0.20, "#fbbf24"),
    ("Descenso", "taper", 0.10, "#34d399"),
]


@dataclass
class WeekEntry:
    week_number: int
    week_date: date
    expected_time: float
    pace_100m: float
    planned_km: float
    phase: str
    improvement_vs_prev: float
    cumulative_improvement: float
    zones: dict = field(default_factory=dict)
    disabled: bool = False


def default_phase_ranges(total_weeks: int) -> list[dict]:
    """Fases por defecto (Base/Construcción/Pico/Descenso) en rangos de semanas."""
    ranges: list[dict] = []
    start = 1
    remaining = total_weeks
    for i, (name, ptype, frac, color) in enumerate(DEFAULT_PHASES):
        if i == len(DEFAULT_PHASES) - 1:
            length = remaining
        else:
            length = max(1, round(total_weeks * frac))
            length = min(length, remaining - (len(DEFAULT_PHASES) - 1 - i))
        ranges.append({
            "name": name, "type": ptype, "color": color,
            "week_start": start, "week_end": start + length - 1, "sort": i,
        })
        start += length
        remaining -= length
    return ranges


def _phase_for_week(week: int, phases: list[dict]) -> str:
    for p in phases:
        if p["week_start"] <= week <= p["week_end"]:
            return p["name"]
    return phases[-1]["name"] if phases else "—"


def monday_of(start_date: date, week_number: int) -> date:
    """Fecha del lunes de la semana N (1-indexada) desde la fecha de inicio."""
    base = start_date - timedelta(days=start_date.weekday())
    return base + timedelta(weeks=week_number - 1)


def generate_plan(
    distance: int,
    current_time: float,
    goal_time: float,
    total_weeks: int,
    total_km: float,
    curve: str,
    start_date: date,
    weeks_per_micro: int = 4,
    phases: list[dict] | None = None,
    stroke: str = "freestyle",
    pool: str = "50",
) -> list[WeekEntry]:
    """Genera el plan completo semana a semana para una prueba de un atleta."""
    phases = phases or default_phase_ranges(total_weeks)
    total_improvement = current_time - goal_time
    km = distribute_km(total_weeks, total_km, weeks_per_micro)
    weeks: list[WeekEntry] = []
    prev = current_time
    for i in range(total_weeks):
        x = (i + 1) / total_weeks
        expected = current_time - total_improvement * curve_progress(x, curve)
        pace = expected / (distance / 100)
        entry = WeekEntry(
            week_number=i + 1,
            week_date=monday_of(start_date, i + 1),
            expected_time=round(expected, 2),
            pace_100m=round(pace, 2),
            planned_km=km[i],
            phase=_phase_for_week(i + 1, phases),
            improvement_vs_prev=round(expected - prev, 2),
            cumulative_improvement=round(current_time - expected, 2),
            zones=calc_zones(pace, distance, stroke, pool),
        )
        weeks.append(entry)
        prev = expected
    return weeks


def generate_extension(
    distance: int,
    current_time: float,
    realistic_ceiling: float,
    goal_time: float,
    safe_rate: float,
    n_ext: int,
    start_date: date,
    macro_weeks: int,
    weekly_km: float,
    stroke: str = "freestyle",
    pool: str = "50",
) -> list[WeekEntry]:
    """Semanas de EXTENSIÓN tras el macro para metas que superan el techo realista.

    Mientras el plan principal de `macro_weeks` semanas comprime la mejora pedida,
    estas filas muestran la continuación REALISTA del motor: parten del techo del
    macro (`realistic_ceiling`) y bajan al ritmo seguro `safe_rate` por semana hasta
    tocar la meta. Numeradas a continuación del macro (macro_weeks+1 …).
    """
    weeks: list[WeekEntry] = []
    prev = realistic_ceiling
    for j in range(1, n_ext + 1):
        abs_week = macro_weeks + j
        expected = max(realistic_ceiling - safe_rate * j, goal_time)
        pace = expected / (distance / 100)
        weeks.append(WeekEntry(
            week_number=abs_week,
            week_date=monday_of(start_date, abs_week),
            expected_time=round(expected, 2),
            pace_100m=round(pace, 2),
            planned_km=weekly_km,
            phase="Extensión",
            improvement_vs_prev=round(expected - prev, 2),
            cumulative_improvement=round(current_time - expected, 2),
            zones=calc_zones(pace, distance, stroke, pool),
        ))
        prev = expected
    return weeks


def recalculate_remaining(
    weeks: list[WeekEntry],
    from_week: int,
    anchor_time: float,
    goal_time: float,
    curve: str,
    distance: int,
    disabled_weeks: set[int] | None = None,
    stroke: str = "freestyle",
    pool: str = "50",
) -> list[WeekEntry]:
    """Recalcula la curva desde `from_week` anclada en un tiempo real/actual.

    Las semanas deshabilitadas (parón por lesión o vacaciones) no progresan:
    mantienen el tiempo del ancla previa y la mejora restante se redistribuye
    entre las semanas activas que quedan.
    """
    disabled_weeks = disabled_weeks or set()
    remaining = [w for w in weeks if w.week_number >= from_week]
    active = [w for w in remaining if w.week_number not in disabled_weeks]
    if not active:
        return weeks

    improvement = max(anchor_time - goal_time, 0.0)
    prev_expected = anchor_time
    progress_idx = 0
    n_active = len(active)
    for week in remaining:
        if week.week_number in disabled_weeks:
            week.disabled = True
            week.expected_time = round(prev_expected, 2)
            week.improvement_vs_prev = 0.0
        else:
            progress_idx += 1
            x = progress_idx / n_active
            expected = anchor_time - improvement * curve_progress(x, curve)
            week.disabled = False
            week.improvement_vs_prev = round(expected - prev_expected, 2)
            week.expected_time = round(expected, 2)
            prev_expected = expected
        pace = week.expected_time / (distance / 100)
        week.pace_100m = round(pace, 2)
        week.zones = calc_zones(pace, distance, stroke, pool)
    return weeks


def performance_status(real_time: float, expected_time: float) -> str:
    """Clasifica el rendimiento real contra el plan: ahead | on_track | behind."""
    diff = (real_time - expected_time) / expected_time
    if diff < -STATUS_TOLERANCE:
        return "ahead"
    if diff > STATUS_TOLERANCE:
        return "behind"
    return "on_track"
