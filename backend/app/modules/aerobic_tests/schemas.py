"""Schemas Pydantic del módulo aerobic_tests."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AerobicTestCreate(BaseModel):
    swimmer_id: int
    plan_id: int | None = None
    test_type: str = Field(pattern="^(T30|T15|CUSTOM|CSS|DIRECT)$")
    test_date: date
    # T30/T15/CUSTOM: tiempos de cada repetición en segundos
    splits: list[float] = Field(default=[], max_length=200)
    rep_distance: int = Field(default=100, ge=25, le=2000)
    # DIRECT: parcial aeróbico ya calculado (s/100m)
    direct_per100: float | None = Field(default=None, gt=0)
    # CSS: tiempos de 400m y 50m
    t400: float | None = Field(default=None, gt=0)
    t50: float | None = Field(default=None, gt=0)
    notes: str | None = None


class SplitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rep_number: int
    split_time: float


class AerobicTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    swimmer_id: int
    plan_id: int | None
    test_type: str
    test_date: date
    rep_count: int | None
    rep_distance: int | None
    avg_per100: float
    std_dev: float | None
    trend: str | None
    css_ms: float | None
    notes: str | None
    splits: list[SplitResponse]
    per100_splits: list[float] = []


class AnalyzePreviewRequest(BaseModel):
    splits: list[float] = Field(min_length=1, max_length=200)
    rep_distance: int = Field(default=100, ge=25, le=2000)


class AnalyzePreviewResponse(BaseModel):
    per100_splits: list[float]
    avg_per100: float
    std_dev: float
    trend: str
    trend_slope: float
