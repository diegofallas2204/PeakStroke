"""Schemas Pydantic del módulo plans."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.dominio.valores import Fase, Prueba


# ── Fases y competencias ─────────────────────────────────────────────
class PhaseInput(BaseModel):
    """Un tramo del macrociclo: el nombre es del entrenador, el tipo de la ciencia.

    `type` es la clave de una de las cinco `Fase` y no tiene valor por defecto:
    un tramo que no dice qué fase es no le sirve de nada a la ciencia, y adivinar
    cuál es fue justo lo que dejó P3 abierto. Los tipos de antes de P3
    (`base|build|peak|taper`) dan 422.
    """

    name: str
    type: str
    week_start: int = Field(ge=1)
    week_end: int = Field(ge=1)
    color: str = "#8b5cf6"

    @field_validator("type")
    @classmethod
    def _una_fase_del_macro(cls, valor: str) -> str:
        return Fase.del_macro(valor).value


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
    # Sin curva (R7): la de un plan real es siempre la científica. Un cliente
    # viejo que la siga mandando no rompe: Pydantic ignora el campo de más.
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
    def _valid_event(self) -> EventInput:
        # Construir la `Prueba` ES la validación: el combo imposible no llega a
        # existir, y el mensaje sale del dominio. Ver `app/dominio/valores/prueba.py`.
        Prueba(self.distance, self.stroke)
        return self


class EventResponse(EventInput):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AddAthleteRequest(BaseModel):
    swimmer_id: int
    aerobic_base: float | None = None
    aerobic_base_source: str | None = None
    events: list[EventInput] = Field(min_length=1)


class AssignableAthlete(BaseModel):
    """Una ficha que hoy puede entrar en el macrociclo.

    Se devuelve la edad **al inicio del plan**, no la de hoy: es la que usa el
    motor para ajustar el techo de mejora de un menor, así que enseñar otra en
    el formulario que dispara la simulación sería enseñar un dato distinto del
    que se va a aplicar.
    """

    id: int
    name: str
    age: int | None = None
    specialty: str
    main_stroke: str


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
    """Los dos campos de arriba los escribe el atleta; los dos de abajo, no.

    No todos los campos de una semana pesan lo mismo. El tiempo real es el dato
    que el atleta aporta sobre sí mismo. El parón (`disabled`) es una decisión de
    entrenamiento —lesión, vacaciones, competencia— que redistribuye la mejora
    restante entre las semanas activas vía `_recalculate_event`: quien lo pone
    está reescribiendo la curva, no registrando un resultado.

    Es una autorización **por campo**, no por endpoint, y por eso no la puede
    resolver una dependencia de FastAPI: la misma ruta acepta las dos cosas. La
    comprueba `touches_coach_only_fields()`, aquí abajo, para que la regla viva
    pegada a los campos que gobierna y no en un `if` perdido en el router.
    """

    real_time: float | None = None
    clear_real_time: bool = False
    disabled: bool | None = None
    disable_reason: str | None = None

    def touches_coach_only_fields(self) -> bool:
        """True si la petición intenta escribir algo reservado al entrenador.

        Mira los campos *enviados*, no los que traen valor: mandar
        `{"disabled": false}` es tanto reactivar una semana parada como mandar
        `true` es pararla. Un `None` por omisión no cuenta.
        """
        enviados = self.model_fields_set
        return bool(enviados & {"disabled", "disable_reason"})
