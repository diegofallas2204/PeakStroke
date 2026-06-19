"""Dominio puro de PeakStroke — el motor científico de predicción.

Port verbatim del sandbox (`PeakStroke Pruebas/sandbox/engine.py`), la fuente de
verdad de la ciencia. Sin I/O, sin DB, sin FastAPI: solo funciones puras y
dataclasses. La capa `app/engine/` adapta este dominio a los consumidores
(plans, simulator, dashboard) y `app/modules/*` lo persisten.

Ver `E:/Obsidian/Inbox/Peakstroke/Aplicación - Integración del Motor.md`.
"""
from __future__ import annotations

from .engine import (
    I_MAX_TABLE,
    POOL_FACTOR_25,
    STROKE_ALIASES,
    STROKE_TPACE_CORRECTION_S,
    ZONE_OVER_RACE,
    PlanResult,
    ScienceEngine,
    WeekRow,
    WeekZones,
    classify_level,
    css_from_test,
    pool_factor,
    profile_for_event,
    zone_factors,
)

__all__ = [
    "ScienceEngine",
    "PlanResult",
    "WeekRow",
    "WeekZones",
    "zone_factors",
    "profile_for_event",
    "pool_factor",
    "classify_level",
    "css_from_test",
    "I_MAX_TABLE",
    "ZONE_OVER_RACE",
    "STROKE_TPACE_CORRECTION_S",
    "STROKE_ALIASES",
    "POOL_FACTOR_25",
]
