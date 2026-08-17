"""Progresión del plan — adaptador sobre `MotorCientifico`.

Desde el paso 4 del rediseño **el cálculo no está aquí**: generar el plan,
recalcularlo desde un tiempo real, extenderlo y clasificar el rendimiento son
métodos del motor único (`app/dominio/servicios/motor.py`). Este módulo traduce
entre `WeekEntry` —la forma que consumen los servicios y los schemas, en
inglés— y `SemanaGenerada`, y desaparece cuando esos consumidores hablen
directamente con el motor.

Que aquí viviera un algoritmo era el problema de fondo: el motor "oficial" de
`app/domain/` no corría, este sí, y las reglas comunes divergían solas.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.dominio.entidades import lunes_de
from app.dominio.servicios.motor import FASES_POR_DEFECTO, MOTOR, SemanaGenerada
from app.dominio.servicios.motor import fases_por_defecto as _fases_por_defecto
from app.dominio.servicios.tablas import TOLERANCIA_DE_ESTADO

# Tolerancia para clasificar real vs. esperado (fracción del tiempo esperado).
STATUS_TOLERANCE = TOLERANCIA_DE_ESTADO  # ±0.4%

DEFAULT_PHASES = FASES_POR_DEFECTO


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


def _a_entry(s: SemanaGenerada) -> WeekEntry:
    return WeekEntry(
        week_number=s.numero, week_date=s.fecha, expected_time=s.tiempo_esperado,
        pace_100m=s.ritmo_100, planned_km=s.km, phase=s.fase,
        improvement_vs_prev=s.mejora_vs_anterior,
        cumulative_improvement=s.mejora_acumulada,
        zones=s.zonas, disabled=s.deshabilitada,
    )


def _a_semana(w: WeekEntry) -> SemanaGenerada:
    return SemanaGenerada(
        numero=w.week_number, fecha=w.week_date, tiempo_esperado=w.expected_time,
        ritmo_100=w.pace_100m, km=w.planned_km, fase=w.phase,
        mejora_vs_anterior=w.improvement_vs_prev,
        mejora_acumulada=w.cumulative_improvement,
        zonas=w.zones, deshabilitada=w.disabled,
    )


def default_phase_ranges(total_weeks: int) -> list[dict]:
    """Fases por defecto (Base/Construcción/Pico/Descenso) en rangos de semanas."""
    return _fases_por_defecto(total_weeks)


def monday_of(start_date: date, week_number: int) -> date:
    """Fecha del lunes de la semana N (1-indexada) desde la fecha de inicio."""
    return lunes_de(start_date, week_number)


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
    semanas = MOTOR.generar_plan(
        distance, current_time, goal_time, total_weeks, total_km, curve, start_date,
        semanas_por_micro=weeks_per_micro, fases=phases, estilo=stroke, piscina=pool,
        n_mac=n_mac, edad=age,
    )
    return [_a_entry(s) for s in semanas]


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
    semanas = MOTOR.generar_extension(
        distance, current_time, realistic_ceiling, goal_time, safe_rate, n_ext,
        start_date, macro_weeks, weekly_km, estilo=stroke, piscina=pool,
    )
    return [_a_entry(s) for s in semanas]


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
    """Recalcula in situ: devuelve **las mismas** filas que recibió.

    Los llamadores escriben esas filas en la base de datos después, así que el
    adaptador copia el resultado sobre los objetos originales en vez de crear
    otros. Cambiarlo convertiría un recálculo en un plan nuevo sin id.
    """
    recalculadas = {
        s.numero: s
        for s in MOTOR.recalcular_desde(
            [_a_semana(w) for w in weeks], from_week, anchor_time, goal_time, curve,
            distance, deshabilitadas=disabled_weeks, estilo=stroke, piscina=pool,
            n_mac=n_mac, edad=age,
        )
    }
    for week in weeks:
        s = recalculadas.get(week.week_number)
        if s is None:
            continue
        week.expected_time = s.tiempo_esperado
        week.pace_100m = s.ritmo_100
        week.improvement_vs_prev = s.mejora_vs_anterior
        week.zones = s.zonas
        week.disabled = s.deshabilitada
    return weeks


def performance_status(real_time: float, expected_time: float) -> str:
    """Clasifica el rendimiento real contra el plan: ahead | on_track | behind."""
    return MOTOR.estado_de_rendimiento(real_time, expected_time)
