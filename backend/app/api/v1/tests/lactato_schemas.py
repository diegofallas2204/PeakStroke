"""Lo que entra y sale del test de lactato.

Entra lo que se apunta; sale además todo lo derivado, que **nunca** entra: no
hay campo para la velocidad, los metros por brazada ni el estado estable.
"""
from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.api.entrada import Entrada

ZonaDeLactato = Literal["R1", "R2", "MVO2", "RL", "V"]
Conteo = Annotated[int, Field(ge=1, le=200)]


# `Entrada`: un `inf` o un `NaN` en un número de la piscina es un 422, no un 500.
class LactateRepIn(Entrada):
    swim_time: float = Field(gt=0, le=7200)                 # tiempo NADADO, s
    lactate: float | None = Field(None, ge=0, le=30)        # mmol/L
    heart_rate: int | None = Field(None, ge=30, le=250)
    effort: float | None = Field(None, ge=0, le=10)         # CR-10
    stroke_counts: list[Conteo] = Field(default_factory=list, max_length=40)
    segment_time: float | None = Field(None, gt=0, le=3600)


class LactateTestCreate(Entrada):
    swimmer_id: int
    test_date: date
    # El escalonado está en el modelo pero no en la v1: llega con su análisis.
    mode: Literal["control"] = "control"
    target_zone: ZonaDeLactato
    rep_distance: int = Field(ge=25, le=2000)
    rest_type: Literal["pausa", "salida"] | None = None
    rest_s: float | None = Field(None, gt=0, le=3600)
    proposed_min: float | None = Field(None, gt=0, le=7200)
    proposed_max: float | None = Field(None, gt=0, le=7200)
    reference_time: float | None = Field(None, gt=0, le=7200)
    counted_segment_m: int | None = Field(None, ge=10, le=2000)
    sample_site: Literal["dedo", "lobulo"] | None = None
    analyzer: str | None = Field(None, max_length=60)
    sample_minute: float | None = Field(None, ge=0, le=30)
    hr_method: Literal["banda", "palpacion", "optico"] | None = None
    notes: str | None = Field(None, max_length=2000)
    reps: list[LactateRepIn] = Field(min_length=1, max_length=40)


class LactateRepOut(BaseModel):
    rep_number: int
    swim_time: float
    lactate: float | None
    heart_rate: int | None
    effort: float | None
    stroke_counts: list[int]
    segment_time: float | None
    # Derivado
    speed: float                       # m/s
    pct_proposed: float | None
    pct_reference: float | None
    strokes_mean: float | None
    m_per_stroke: float | None
    cycle_rate: float | None           # ciclos/min
    cycle_rate_estimated: bool
    stroke_index: float | None
    internal_drift_pct: float | None
    lactate_zone: Literal["debajo", "dentro", "encima"] | None


class LactateWarning(BaseModel):
    rep_number: int
    field: Literal["tiempo", "lactato", "fc"]
    message: str


class LactateSummary(BaseModel):
    mean_time: float
    cv_pct: float
    slope: float                       # s por repetición; − = cada vez más rápido
    speed: float
    pct_proposed: float | None
    diff_proposed: float | None        # s de la media sobre el centro del propuesto
    pct_reference: float | None
    lactate_median: float | None
    lactate_min: float | None
    lactate_max: float | None
    lactate_zone: Literal["debajo", "dentro", "encima"] | None
    steady_state: bool | None
    second_half_rise: float | None
    strokes_first: float | None
    strokes_last: float | None
    stroke_drift_pct: float | None
    stroke_index: float | None


class LactateAnalysis(BaseModel):
    zone_range: tuple[float, float | None] | None
    reps: list[LactateRepOut]
    summary: LactateSummary
    warnings: list[LactateWarning]


class LactateTestResponse(LactateAnalysis):
    id: int
    swimmer_id: int
    test_date: date
    mode: str
    target_zone: str
    rep_distance: int
    rest_type: str | None
    rest_s: float | None
    proposed_min: float | None
    proposed_max: float | None
    reference_time: float | None
    counted_segment_m: int | None
    sample_site: str | None
    analyzer: str | None
    sample_minute: float | None
    hr_method: str | None
    notes: str | None
    is_active: bool
