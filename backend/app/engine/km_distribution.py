"""Distribución del kilometraje — adaptador sobre `dominio.servicios.kilometraje`."""
from __future__ import annotations

from app.dominio.servicios.kilometraje import reparto_de_km


def distribute_km(total_weeks: int, total_km: float, weeks_per_micro: int = 4) -> list[float]:
    """Kilómetros planificados por semana (lista de longitud total_weeks)."""
    return reparto_de_km(total_weeks, total_km, weeks_per_micro)
