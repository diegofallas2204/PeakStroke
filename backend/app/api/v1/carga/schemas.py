"""Schemas de la carga de entrenamiento. Todo derivado: aquí no se escribe nada."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class LoadDay(BaseModel):
    date: date
    stss: float
    ctl: float
    atl: float
    tsb: float
    # `None` sin alerta o durante el calentamiento. "advertencia" | "peligro".
    alert: str | None = None
    # "tsb_bajo" | "fatiga_sostenida"
    reasons: list[str] = []


class TrainingLoadResponse(BaseModel):
    swimmer_id: int
    desde: date
    hasta: date
    # Primer día con carga. Sin sesiones con CSS no hay serie y vale `None`.
    history_start: date | None
    # Menos de 42 días de historia a `hasta`: la curva se enseña, sin alertas.
    warming_up: bool
    # Sesiones anteriores al primer test aeróbico: sin CSS no tienen sTSS.
    sessions_without_css: int
    days: list[LoadDay]
