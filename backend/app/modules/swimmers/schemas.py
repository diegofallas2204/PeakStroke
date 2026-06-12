"""Schemas Pydantic del módulo swimmers."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SwimmerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    birth_date: date | None = None
    gender: str | None = None
    specialty: str = "medio_fondo"
    main_stroke: str = "libre"
    weight_kg: float | None = Field(default=None, gt=0)
    height_cm: float | None = Field(default=None, gt=0)
    notes: str | None = None


class SwimmerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    birth_date: date | None = None
    gender: str | None = None
    specialty: str | None = None
    main_stroke: str | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    notes: str | None = None


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
