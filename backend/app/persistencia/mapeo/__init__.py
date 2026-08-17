"""Traducción fila ↔ entidad de dominio."""
from __future__ import annotations

from .desde_modelos import (
    atleta_desde_fila,
    macrociclo_desde_fila,
    test_desde_fila,
)

__all__ = ["atleta_desde_fila", "macrociclo_desde_fila", "test_desde_fila"]
