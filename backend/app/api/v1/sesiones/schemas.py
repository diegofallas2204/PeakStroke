"""Schemas Pydantic de las sesiones.

Los topes de distancia y duración **no son ciencia**: son guardas contra el cero
de más al teclear (30 000 m, 6 h). Lo que sí sale de una escala es el RPE,
que vive en el dominio (`RPE_MINIMO`·`RPE_MAXIMO`, CR-10).
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.dominio.entidades import RPE_MAXIMO, RPE_MINIMO

_MAX_METROS = 30_000        # por encima, casi seguro un cero de más
_MAX_SEGUNDOS = 6 * 3600    # ídem: seis horas de agua en un día es un error


class TrainingSessionCreate(BaseModel):
    swimmer_id: int
    session_date: date
    distance_m: int = Field(gt=0, le=_MAX_METROS)
    # Total, descansos incluidos: de la primera salida a la última llegada.
    duration_s: int = Field(gt=0, le=_MAX_SEGUNDOS)
    rpe: int | None = Field(default=None, ge=RPE_MINIMO, le=RPE_MAXIMO)
    notes: str | None = Field(default=None, max_length=2000)


class TrainingSessionUpdate(BaseModel):
    """Solo lo que llega se cambia. `rpe: null` o `notes: null` lo borran.

    El atleta no se cambia: una sesión apuntada a quien no era se borra y se
    apunta de nuevo.
    """

    session_date: date | None = None
    distance_m: int | None = Field(default=None, gt=0, le=_MAX_METROS)
    duration_s: int | None = Field(default=None, gt=0, le=_MAX_SEGUNDOS)
    rpe: int | None = Field(default=None, ge=RPE_MINIMO, le=RPE_MAXIMO)
    notes: str | None = Field(default=None, max_length=2000)


class TrainingSessionResponse(BaseModel):
    id: int
    swimmer_id: int
    session_date: date
    distance_m: int
    duration_s: int
    rpe: int | None
    notes: str | None
    # Derivado, no se guarda: segundos por 100 m sobre la duración total.
    pace_100m: float
