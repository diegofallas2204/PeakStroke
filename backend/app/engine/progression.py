"""Motor de progresión: genera el plan semana a semana y lo recalcula.

Funciones puras: reciben parámetros y retornan estructuras de datos, sin tocar
la base de datos. La capa de servicio persiste el resultado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.dominio.entidades import lunes_de

from .curves import curve_progress
from .envelope import science_envelope
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
    """Fecha del lunes de la semana N (1-indexada) desde la fecha de inicio.

    La regla es del macrociclo y vive en `dominio.entidades.macrociclo.lunes_de`
    desde el paso 2 del rediseño. Aquí queda la delegación porque este módulo la
    usa dentro de bucles que no tienen un `Macrociclo` a mano; conservar la copia
    la habría dejado divergiendo sola, que es lo que ya pasó dos veces.
    """
    return lunes_de(start_date, week_number)


def clamp_weekly_rate(expected: list[float], current_time: float, peak_week_s: float) -> list[float]:
    """Acota la mejora de cada semana al ritmo fisiológico máximo `peak_week_s`.

    Recorre las semanas en orden: si una pide mejorar más de `peak_week_s` (típico
    de la exponencial, que carga la mejora al inicio), toma solo el tope y *difiere*
    el excedente a las semanas siguientes (modelo causal: no se puede mejorar más
    rápido de lo que la fisiología permite, así que esa ganancia ocurre después).

    La curva científica nunca se recorta (su semana más rápida define `peak_week_s`);
    solo reparte de forma distinta a las curvas con picos artificiales. Si el techo
    del macro ya acota la mejora total, el excedente diferido siempre se reabsorbe
    antes del final, así que la curva cierra en el mismo punto, solo con otra forma.
    """
    if peak_week_s <= 0:
        return list(expected)
    # Incrementos pedidos por la curva ideal (semana a semana).
    intended: list[float] = []
    prev_ideal = current_time
    for e in expected:
        intended.append(prev_ideal - e)
        prev_ideal = e
    # Redistribución: tope por semana + diferir el excedente a las siguientes.
    out: list[float] = []
    prev = current_time
    carry = 0.0
    for want_now in intended:
        want = want_now + carry            # incremento pedido + lo diferido
        take = min(want, peak_week_s) if want > 0 else want
        carry = want - take                # lo que no cupo se difiere
        prev = prev - take
        out.append(prev)
    return out


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
    n_mac: int = 1,
    age: int | None = None,
) -> list[WeekEntry]:
    """Genera el plan completo semana a semana para una prueba de un atleta.

    La curva elegida define la FORMA de la progresión, pero queda acotada por la
    ciencia (techo I_max del nivel/prueba, vía `science_envelope`):
    - la mejora dentro del macro nunca supera el techo realista (`realistic_ceiling`);
      una meta más agresiva continúa en la tabla de extensión, no en esta curva.
    - ninguna semana mejora más rápido que el ritmo fisiológico máximo (`peak_week_s`).
    Así la curva cierra justo donde la tarjeta de factibilidad dice que es realista,
    y la diferencia entre funciones (sigmoide/exp/log/lineal) es solo de forma.
    """
    phases = phases or default_phase_ranges(total_weeks)
    km = distribute_km(total_weeks, total_km, weeks_per_micro)

    env = science_envelope(distance, current_time, total_weeks, n_mac=n_mac, age=age)
    # Nunca mejorar más allá del techo I_max dentro del macro (la meta agresiva
    # continúa en la extensión). Para metas factibles, in_macro_target = meta.
    in_macro_target = max(goal_time, env.realistic_ceiling)
    improvement = max(current_time - in_macro_target, 0.0)

    ideal = [current_time - improvement * curve_progress((i + 1) / total_weeks, curve)
             for i in range(total_weeks)]
    bounded = clamp_weekly_rate(ideal, current_time, env.peak_week_s)

    weeks: list[WeekEntry] = []
    prev = current_time
    for i in range(total_weeks):
        expected = bounded[i]
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
    n_mac: int = 1,
    age: int | None = None,
) -> list[WeekEntry]:
    """Recalcula la curva desde `from_week` anclada en un tiempo real/actual.

    Las semanas deshabilitadas (parón por lesión o vacaciones) no progresan:
    mantienen el tiempo del ancla previa y la mejora restante se redistribuye
    entre las semanas activas que quedan.

    Queda acotada por la misma ciencia que `generate_plan`: desde el ancla, la
    mejora de las semanas activas restantes no supera el techo I_max (calculado
    sobre esas semanas) ni el ritmo fisiológico máximo por semana.
    """
    disabled_weeks = disabled_weeks or set()
    remaining = [w for w in weeks if w.week_number >= from_week]
    active = [w for w in remaining if w.week_number not in disabled_weeks]
    if not active:
        return weeks

    n_active = len(active)
    env = science_envelope(distance, anchor_time, n_active, n_mac=n_mac, age=age)
    # No mejorar más allá del techo realista de las semanas restantes; la meta
    # más exigente queda fuera del alcance del tramo, no se fuerza.
    in_macro_target = max(goal_time, env.realistic_ceiling)
    improvement = max(anchor_time - in_macro_target, 0.0)
    ideal = [anchor_time - improvement * curve_progress((k + 1) / n_active, curve)
             for k in range(n_active)]
    bounded = clamp_weekly_rate(ideal, anchor_time, env.peak_week_s)

    prev_expected = anchor_time
    idx = 0
    for week in remaining:
        if week.week_number in disabled_weeks:
            week.disabled = True
            week.expected_time = round(prev_expected, 2)
            week.improvement_vs_prev = 0.0
        else:
            expected = bounded[idx]
            idx += 1
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
