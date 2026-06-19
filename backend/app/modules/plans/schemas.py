"""Schemas Pydantic del módulo plans."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engine.events import allowed_strokes, is_valid_event


# ── Fases y competencias ─────────────────────────────────────────────
class PhaseInput(BaseModel):
    name: str
    type: str = "base"
    week_start: int = Field(ge=1)
    week_end: int = Field(ge=1)
    color: str = "#8b5cf6"


class PhaseResponse(PhaseInput):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sort: int


class CompetitionInput(BaseModel):
    name: str
    week_number: int = Field(ge=1)
    days: int = Field(default=1, ge=1, le=10)
    is_main: bool = False


class CompetitionResponse(CompetitionInput):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Plan ─────────────────────────────────────────────────────────────
class PlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    start_date: date
    total_weeks: int = Field(ge=8, le=24)
    weeks_per_micro: int = Field(default=4, ge=3, le=6)
    total_km: float = Field(gt=0)
    progression_curve: str = "sigmoid"
    pool: Literal["25", "50"] = "50"
    n_mac: int = Field(default=1, ge=1, le=10)
    main_event: str | None = None
    notes: str | None = None
    phases: list[PhaseInput] = []
    competitions: list[CompetitionInput] = []


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    notes: str | None = None
    status: Literal["active", "draft", "finished", "suspended"] | None = None
    main_event: str | None = None
    pool: Literal["25", "50"] | None = None
    n_mac: int | None = Field(default=None, ge=1, le=10)


class EventInput(BaseModel):
    priority: int = Field(default=1, ge=1, le=5)
    distance: int = Field(ge=25, le=10000)
    stroke: str
    current_time: float = Field(gt=0)
    goal_time: float = Field(gt=0)

    @model_validator(mode="after")
    def _valid_event(self) -> "EventInput":
        if not is_valid_event(self.distance, self.stroke):
            opciones = ", ".join(allowed_strokes(self.distance))
            raise ValueError(
                f"{self.distance}m {self.stroke} no es una prueba válida. "
                f"Para {self.distance}m: {opciones}."
            )
        return self


class EventResponse(EventInput):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AddAthleteRequest(BaseModel):
    swimmer_id: int
    aerobic_base: float | None = None
    aerobic_base_source: str | None = None
    events: list[EventInput] = Field(min_length=1)


class AthletePlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    swimmer_id: int
    swimmer_name: str = ""
    specialty: str = ""
    aerobic_base: float | None
    aerobic_base_source: str | None
    events: list[EventResponse]


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    start_date: date
    total_weeks: int
    weeks_per_micro: int
    total_km: float
    progression_curve: str
    pool: str = "50"
    n_mac: int = 1
    main_event: str | None
    notes: str | None
    status: str                   # crudo en BD: active|draft|finished|suspended
    effective_status: str = "active"  # derivado por fecha (auto-completado) + override manual
    phases: list[PhaseResponse]
    competitions: list[CompetitionResponse]
    athletes: list[AthletePlanResponse] = []
    current_week: int | None = None


# ── Semanas ──────────────────────────────────────────────────────────
class WeekResponse(BaseModel):
    id: int
    week_number: int
    week_date: date
    date_label: str               # DD/MM para el eje X de los gráficos
    planned_km: float
    expected_time: float
    recalc_time: float | None
    pace_100m: float
    zones: dict
    zone_km: dict                 # km sugeridos por zona según especialidad
    real_time: float | None
    status: str | None            # ahead | on_track | behind
    diff_seconds: float | None
    diff_percent: float | None
    phase: str
    disabled: bool
    disable_reason: str | None
    is_competition: bool = False


class WeekUpdateRequest(BaseModel):
    real_time: float | None = None
    clear_real_time: bool = False
    disabled: bool | None = None
    disable_reason: str | None = None
