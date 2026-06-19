"""Schemas del simulador de escenarios (stateless)."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.engine.events import allowed_strokes, is_valid_event


class SimulationRequest(BaseModel):
    distance: int = Field(ge=25, le=10000)
    stroke: str = "libre"
    current_time: float = Field(gt=0)
    goal_time: float = Field(gt=0)
    total_weeks: int = Field(ge=4, le=30)
    weeks_per_micro: int = Field(default=4, ge=3, le=6)
    total_km: float = Field(gt=0)
    curve: str = "sigmoid"
    pool: Literal["25", "50"] = "50"
    start_date: date | None = None
    specialty: str = "medio_fondo"
    n_mac: int = Field(default=1, ge=1, le=10)
    swimmer_age: int | None = None

    @model_validator(mode="after")
    def _valid_event(self) -> "SimulationRequest":
        if not is_valid_event(self.distance, self.stroke):
            opciones = ", ".join(allowed_strokes(self.distance))
            raise ValueError(
                f"{self.distance}m {self.stroke} no es una prueba válida. "
                f"Para {self.distance}m: {opciones}."
            )
        return self


class SimWeek(BaseModel):
    week_number: int
    date_label: str
    expected_time: float
    pace_100m: float
    planned_km: float
    phase: str
    improvement_vs_prev: float
    cumulative_improvement: float
    zones: dict
    zone_km: dict


class FeasibilityResponse(BaseModel):
    status: str
    message: str
    tier: int
    improvement_total: float
    improvement_per_micro: float
    window_min: float | None
    window_max: float
    recommended_weeks: int | None
    extension_weeks: int | None
    realistic_ceiling: float
    safe_rate_per_week: float
    detail: dict


class SimulationResponse(BaseModel):
    feasibility: FeasibilityResponse
    weeks: list[SimWeek]
    extension_weeks: list[SimWeek]   # semanas extra realistas (vacío si la meta es factible)
    curves: dict[str, list[float]]   # nombre de curva -> tiempos esperados
