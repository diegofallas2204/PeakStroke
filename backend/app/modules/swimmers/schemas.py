"""Schemas Pydantic del módulo swimmers."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Catálogos de dominio (espejo de frontend/src/lib/constants.ts).
Gender = Literal["F", "M"]
Specialty = Literal["velocidad", "medio_fondo", "fondo", "aguas_abiertas"]
MainStroke = Literal["libre", "espalda", "pecho", "mariposa", "combinado"]


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
    # Cuenta ligada, si la tiene. Lo consume la sección Perfil para ofrecer solo
    # los nadadores que aún no tienen acceso.
    user_id: int | None = None
    # Los nadadores se dan de baja, no se borran.
    is_active: bool = True
