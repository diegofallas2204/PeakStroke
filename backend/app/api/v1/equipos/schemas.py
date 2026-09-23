"""Schemas Pydantic del módulo teams."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TeamResponse(BaseModel):
    id: int
    name: str
    owner_id: int | None
    owner_name: str | None
    # Quien pregunta, ¿es el dueño? Lo consume la UI para decidir qué mostrar;
    # los permisos reales los aplica el backend, no esto.
    is_owner: bool
    coaches: int
    athletes: int
    swimmers: int


class TeamUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class OwnerTransfer(BaseModel):
    new_owner_id: int


class CoachAthletes(BaseModel):
    coach_id: int
    swimmer_ids: list[int]
