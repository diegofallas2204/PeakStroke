"""Dominio puro de PeakStroke — el motor científico de predicción.

Port verbatim del sandbox (`PeakStroke Pruebas/sandbox/engine.py`), la fuente de
verdad de la ciencia. Sin I/O, sin DB, sin FastAPI: solo funciones puras y
dataclasses. La capa `app/engine/` adapta este dominio a los consumidores
(plans, simulator, dashboard) y `app/modules/*` lo persisten.

Ver `E:/Obsidian/Inbox/Peakstroke/Aplicación - Integración del Motor.md`.
"""
from __future__ import annotations

from .engine import (
    ANNUAL_IMPROVEMENT_RANGE,
    I_MAX_TABLE,
    MACROCYCLE_DEGRADATION,
    POOL_FACTOR_25,
    STROKE_ALIASES,
    STROKE_TPACE_CORRECTION_S,
    ZONE_OVER_RACE,
    MacroProjection,
    PlanResult,
    ScienceEngine,
    SeasonProjection,
    WeekRow,
    WeekZones,
    classify_level,
    css_from_test,
    pool_factor,
    profile_for_event,
    science_curve_progress,
    youth_imax_factor,
    zone_factors,
)

__all__ = [
    "ScienceEngine",
    "PlanResult",
    "WeekRow",
    "WeekZones",
    "SeasonProjection",
    "MacroProjection",
    "zone_factors",
    "profile_for_event",
    "pool_factor",
    "classify_level",
    "css_from_test",
    "science_curve_progress",
    "youth_imax_factor",
    "I_MAX_TABLE",
    "MACROCYCLE_DEGRADATION",
    "ANNUAL_IMPROVEMENT_RANGE",
    "ZONE_OVER_RACE",
    "STROKE_TPACE_CORRECTION_S",
    "STROKE_ALIASES",
    "POOL_FACTOR_25",
]
