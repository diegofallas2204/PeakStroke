"""Schemas Pydantic del módulo aerobic_tests."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AerobicTestCreate(BaseModel):
    swimmer_id: int
    plan_id: int | None = None
    test_type: str = Field(pattern="^(T30|T15|CUSTOM|CSS|DIRECT)$")
    test_date: date
    # T30/T15/CUSTOM: tiempos de cada repetición en segundos —o llegadas
    # acumuladas del reloj, según `input_mode`.
    splits: list[float] = Field(default=[], max_length=200)
    rep_distance: int = Field(default=100, ge=25, le=2000)
    # Intervalo de salida en segundos. Opcional: un test sin él sigue siendo
    # válido, solo no permite calcular descanso ni densidad.
    send_off: float | None = Field(default=None, gt=0, le=3600)
    # `rep` = los números son tiempos nadados · `clock` = son llegadas
    # acumuladas y hay que restarles la salida. `clock` exige `send_off`.
    input_mode: str = Field(default="rep", pattern="^(rep|clock)$")
    # DIRECT: parcial aeróbico ya calculado (s/100m)
    direct_per100: float | None = Field(default=None, gt=0)
    # CSS: tiempos de 400m y 50m
    t400: float | None = Field(default=None, gt=0)
    t50: float | None = Field(default=None, gt=0)
    notes: str | None = None


class SplitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rep_number: int
    split_time: float               # tiempo nadado
    send_off_time: float | None = None   # segundo en que arrancó
    arrival_time: float | None = None    # lo que marcaba el reloj al llegar


class AerobicTestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    swimmer_id: int
    plan_id: int | None
    test_type: str
    test_date: date
    rep_count: int | None
    rep_distance: int | None
    send_off: float | None = None
    input_mode: str = "rep"
    avg_per100: float
    std_dev: float | None
    trend: str | None
    css_ms: float | None
    notes: str | None
    splits: list[SplitResponse]
    per100_splits: list[float] = []
    # Derivados de la salida. Vacíos en los tests que no la registraron.
    rest_per_rep: list[float] = []
    avg_rest: float | None = None
    work_rest_ratio: float | None = None   # descanso medio / trabajo medio
    density: float | None = None           # fracción del ciclo que es nado
    missed_intervals: list[int] = []       # repeticiones que no llegaron a tiempo


class AnalyzePreviewRequest(BaseModel):
    splits: list[float] = Field(min_length=1, max_length=200)
    rep_distance: int = Field(default=100, ge=25, le=2000)
    send_off: float | None = Field(default=None, gt=0, le=3600)
    input_mode: str = Field(default="rep", pattern="^(rep|clock)$")


class AnalyzePreviewResponse(BaseModel):
    per100_splits: list[float]
    avg_per100: float
    std_dev: float
    trend: str
    trend_slope: float
    rep_times: list[float] = []
    rest_per_rep: list[float] = []
    avg_rest: float | None = None
    work_rest_ratio: float | None = None
    density: float | None = None
    missed_intervals: list[int] = []


class TrainingIntervalResponse(BaseModel):
    """Una línea de pizarra: a qué ritmo y cada cuánto sale la repetición."""

    zone: str
    label: str
    pace_100: float
    work: float
    rest: float
    interval: float
    rest_ratio: float
    measured_interval: float | None = None
    denser_than_measured: bool | None = None


class TrainingIntervalsResponse(BaseModel):
    """Los tiempos de entrenamiento del atleta para una distancia de repetición.

    Las zonas NO se recalculan aquí: salen de `engine/zones.calc_zones` sobre el
    ritmo de la semana del macrociclo, que es la única fuente de zonas del
    sistema. Este endpoint solo les añade la salida para la distancia que pida
    el entrenador y las contrasta con la densidad que el test midió.

    Sin macrociclo asignado no hay ritmo de referencia y `zones` viene vacío:
    inventar aquí una segunda derivación de zonas —desde la base aeróbica— daría
    dos respuestas distintas a la misma pregunta, que es justo lo que la regla de
    fuente única existe para impedir.
    """

    test_id: int
    rep_distance: int
    reference_pace: float | None = None   # ritmo de carrera /100m de la semana
    reference_week: int | None = None
    event_label: str | None = None
    measured_ratio: float | None = None   # descanso:trabajo medido en el test
    zones: list[TrainingIntervalResponse] = []
