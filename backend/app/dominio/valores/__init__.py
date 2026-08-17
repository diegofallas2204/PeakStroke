"""Objetos de valor: inmutables (`frozen=True, slots=True`), sin identidad.

`slots=True` porque es lo que ya usa `Principal` y porque el coste medido de
crear uno de estos es 0,24 µs — despreciable frente a lo que compra: que una
regla que hoy es una función suelta pase a ser una invariante de un tipo.

Ver `docs/REDISENO.md` §3.
"""
from __future__ import annotations

from .escalas import (
    Especialidad,
    EstadoDeMacro,
    Fase,
    Genero,
    ModoDeIngreso,
    Nivel,
    Perfil,
    Tendencia,
    TipoDeTest,
    Veredicto,
)
from .prueba import (
    DISTANCIA_TIER_1,
    EVENTOS_DE_REFERENCIA,
    Estilo,
    Piscina,
    Prueba,
)
from .tiempo import PASO_DE_RELOJ_S, Duracion, Mejora, Ritmo, Tiempo
from .zona import JuegoDeZonas, Prescripcion, Zona, factores_de_zona

__all__ = [
    # tiempo
    "Tiempo", "Duracion", "Ritmo", "Mejora", "PASO_DE_RELOJ_S",
    # prueba
    "Prueba", "Estilo", "Piscina", "EVENTOS_DE_REFERENCIA", "DISTANCIA_TIER_1",
    # zona
    "Zona", "Prescripcion", "JuegoDeZonas", "factores_de_zona",
    # escalas
    "Nivel", "Perfil", "Fase", "Especialidad", "Genero", "TipoDeTest",
    "ModoDeIngreso", "Tendencia", "EstadoDeMacro", "Veredicto",
]
