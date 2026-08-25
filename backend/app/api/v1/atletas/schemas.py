"""Schemas Pydantic del atleta.

Los catálogos cerrados (`Gender`·`Specialty`·`MainStroke`) están en
`app/api/vocabulario.py`: los comparte con la invitación por correo, que
describe la misma ficha.
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.vocabulario import Gender, MainStroke, Specialty


def _not_future(value: date | None) -> date | None:
    if value is not None and value > date.today():
        raise ValueError("La fecha de nacimiento no puede ser futura")
    return value


class SwimmerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    birth_date: date | None = None
    gender: Gender | None = None
    specialty: Specialty = "medio_fondo"
    main_stroke: MainStroke = "libre"
    weight_kg: float | None = Field(default=None, gt=0)
    height_cm: float | None = Field(default=None, gt=0)
    notes: str | None = None

    _check_birth = field_validator("birth_date")(_not_future)


class SwimmerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    birth_date: date | None = None
    gender: Gender | None = None
    specialty: Specialty | None = None
    main_stroke: MainStroke | None = None
    weight_kg: float | None = Field(default=None, gt=0)
    height_cm: float | None = Field(default=None, gt=0)
    notes: str | None = None

    _check_birth = field_validator("birth_date")(_not_future)


class SwimmerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    birth_date: date | None
    gender: str | None
    specialty: str
    main_stroke: str
    weight_kg: float | None
    height_cm: float | None
    notes: str | None
    created_at: datetime
    age: int | None = None
    # Cuenta ligada, si la tiene.
    user_id: int | None = None
    # Los nadadores se dan de baja, no se borran.
    is_active: bool = True

    # Email de la cuenta ligada. Ficha y cuenta son la misma persona, y hasta
    # el 2026-08-09 saber cuál de las dos existía obligaba a cruzar a ojo la
    # lista de atletas con la de miembros del equipo. Con el email aquí, la
    # lista de atletas se basta sola.
    #
    # El estado intermedio —código emitido y sin canjear— **no** viaja en este
    # schema: vive en `GET /link-codes/`, que es de quien es. Duplicar aquí la
    # definición de "código vivo" pondría la misma invariante en dos sitios.
    user_email: str | None = None
