"""
training_plans/schemas.py — Pydantic schemas para el módulo de macrociclos.

Convención:
  XCreate   → entrada para crear
  XUpdate   → actualización parcial (todos los campos opcionales)
  XResponse → salida al cliente
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


# ---------------------------------------------------------------------------
# Macrociclo
# ---------------------------------------------------------------------------

class PhaseCreate(BaseModel):
    name: str
    week_start: int
    week_end: int
    color: str | None = None


class MacrocycleCreate(BaseModel):
    name: str
    start_date: date
    end_date: date
    total_weeks: Literal[12, 18]
    microcycle_weeks: Literal[4, 5] = 4
    sessions_per_week: int = 5
    total_km: float
    progression_curve: Literal["linear", "exponential", "logarithmic", "sigmoid"] = "sigmoid"
    notes: str | None = None
    phases: list[PhaseCreate] = []

    @field_validator("total_km")
    @classmethod
    def km_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("El kilometraje total debe ser mayor a 0")
        return v

    @model_validator(mode="after")
    def phases_cover_all_weeks(self) -> "MacrocycleCreate":
        if not self.phases:
            return self
        covered = set()
        for p in self.phases:
            covered.update(range(p.week_start, p.week_end + 1))
        expected = set(range(1, self.total_weeks + 1))
        if not expected.issubset(covered):
            missing = sorted(expected - covered)
            raise ValueError(f"Las fases no cubren todas las semanas: faltan {missing}")
        return self


class MacrocycleUpdate(BaseModel):
    name: str | None = None
    total_km: float | None = None
    sessions_per_week: int | None = None
    progression_curve: str | None = None
    notes: str | None = None
    status: str | None = None


class PhaseResponse(BaseModel):
    id: int
    name: str
    week_start: int
    week_end: int
    color: str | None

    model_config = {"from_attributes": True}


class MacrocycleResponse(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    total_weeks: int
    microcycle_weeks: int
    sessions_per_week: int
    total_km: float
    progression_curve: str
    status: str
    notes: str | None
    created_at: datetime
    phases: list[PhaseResponse] = []
    swimmer_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Atletas
# ---------------------------------------------------------------------------

class SwimmerCreate(BaseModel):
    name: str
    birth_date: date | None = None
    gender: Literal["M", "F", "X"] | None = None
    weight: float | None = None
    height: float | None = None
    specialty: str | None = None
    notes: str | None = None


class SwimmerUpdate(BaseModel):
    name: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    weight: float | None = None
    height: float | None = None
    specialty: str | None = None
    notes: str | None = None


class SwimmerResponse(BaseModel):
    id: int
    name: str
    birth_date: date | None
    gender: str | None
    weight: float | None
    height: float | None
    specialty: str | None
    age: int | None = None  # calculado

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pruebas del atleta
# ---------------------------------------------------------------------------

class AthleteEventCreate(BaseModel):
    priority: Literal[1, 2, 3]
    distance: Literal[50, 100, 200, 400, 800, 1500]
    stroke: Literal["libre", "espalda", "mariposa", "pecho", "combinado"]
    current_time: float   # segundos
    goal_time: float      # segundos

    @model_validator(mode="after")
    def goal_faster_than_current(self) -> "AthleteEventCreate":
        if self.goal_time >= self.current_time:
            raise ValueError("El tiempo meta debe ser menor al tiempo actual")
        return self


class AthleteEventResponse(BaseModel):
    id: int
    priority: int
    distance: int
    stroke: str
    current_time: float
    goal_time: float
    is_active: bool
    improvement_seconds: float    # calculado
    improvement_pct: float        # calculado
    feasibility: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Agregar atleta al macrociclo
# ---------------------------------------------------------------------------

class AerobicBaseInput(BaseModel):
    """Base aeróbica al incorporar un atleta a un macrociclo."""
    value: float | None = None           # pace_100m directo en segundos
    aerobic_test_id: int | None = None   # o desde un test registrado


class AddAthleteRequest(BaseModel):
    swimmer_id: int
    events: list[AthleteEventCreate]
    aerobic_base: AerobicBaseInput | None = None

    @field_validator("events")
    @classmethod
    def at_most_three_events(cls, v: list) -> list:
        if len(v) == 0:
            raise ValueError("Debe definir al menos una prueba")
        if len(v) > 3:
            raise ValueError("Máximo 3 pruebas por atleta por macrociclo")
        priorities = [e.priority for e in v]
        if len(set(priorities)) != len(priorities):
            raise ValueError("Las prioridades de las pruebas deben ser únicas (1, 2 o 3)")
        return v


# ---------------------------------------------------------------------------
# Plan semanal
# ---------------------------------------------------------------------------

class WeekZonesResponse(BaseModel):
    pace_100m: float
    r1: float
    r2: float
    mvo2: float
    rl: float
    v: float


class WeeklyPlanResponse(BaseModel):
    id: int
    week_number: int
    week_date: date        # formato DD/MM en el frontend (eje X)
    planned_km: float | None
    expected_time: float | None       # curva ideal (segundos)
    expected_time_recalc: float | None  # curva recalculada
    pace_100m: float | None
    zones: WeekZonesResponse | None   # calculado al serializar
    real_time: float | None
    real_km: float | None
    disabled: bool
    disable_reason: str | None
    phase_name: str | None
    feasibility: str | None

    model_config = {"from_attributes": True}


class UpdateWeekRequest(BaseModel):
    """El entrenador actualiza una semana: ingresa tiempo real o la inhabilita."""
    real_time: float | None = None
    real_km: float | None = None
    disabled: bool | None = None
    disable_reason: Literal["lesion", "vacaciones", "otro"] | None = None


# ---------------------------------------------------------------------------
# Vista tabla del equipo
# ---------------------------------------------------------------------------

class TeamRowResponse(BaseModel):
    """Una fila de la tabla del equipo para una semana dada."""
    swimmer_id: int
    swimmer_name: str
    athlete_macrocycle_id: int
    event: AthleteEventResponse
    week: WeeklyPlanResponse


# ---------------------------------------------------------------------------
# T-30/T-15
# ---------------------------------------------------------------------------

class AerobicTestCreate(BaseModel):
    swimmer_id: int
    macrocycle_id: int | None = None
    test_type: Literal["T30", "T15"]
    test_date: date
    splits: list[float]     # lista de tiempos en segundos (30 o 15 valores)
    notes: str | None = None

    @field_validator("splits")
    @classmethod
    def validate_splits(cls, v: list[float]) -> list[float]:
        if len(v) not in (15, 30):
            raise ValueError("Deben ser exactamente 15 o 30 parciales")
        return v


class AerobicTestResponse(BaseModel):
    id: int
    swimmer_id: int
    test_type: str
    test_date: date
    repetitions: int
    avg_time: float | None
    std_dev: float | None
    trend_direction: str | None = None

    model_config = {"from_attributes": True}
