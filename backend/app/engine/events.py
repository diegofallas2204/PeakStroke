"""Pruebas de natación válidas — fuente de verdad de combinaciones distancia × estilo.

Regla del deporte (debe coincidir con el frontend `lib/constants.ts`):

    ≥ 600m            → solo libre            (800, 1500: no hay 800 mariposa, etc.)
    300–599m          → libre o combinado     (400 libre / 400 combinado; NO 400 mariposa)
    100–299m          → todos los estilos     (incluye combinado: 100/200 IM)
    < 100m (50)       → libre, espalda, pecho, mariposa  (no hay 50 combinado estándar)

Se usa para validar cualquier formulario/endpoint que reciba (distancia, estilo)
y para filtrar los combos en la interfaz.
"""
from __future__ import annotations

# Normaliza el estilo (acepta español e inglés) a la clave canónica en español.
_STROKE_ALIASES: dict[str, str] = {
    "libre": "libre", "crol": "libre", "freestyle": "libre",
    "espalda": "espalda", "dorso": "espalda", "backstroke": "espalda",
    "pecho": "pecho", "braza": "pecho", "breaststroke": "pecho",
    "mariposa": "mariposa", "butterfly": "mariposa",
    "combinado": "combinado", "im": "combinado", "individual_medley": "combinado",
}


def normalize_stroke(stroke: str) -> str:
    key = stroke.lower().strip()
    return _STROKE_ALIASES.get(key, key)


def allowed_strokes(distance: int) -> list[str]:
    """Estilos válidos para una distancia (claves en español)."""
    if distance >= 600:
        return ["libre"]
    if distance >= 300:
        return ["libre", "combinado"]
    base = ["libre", "espalda", "pecho", "mariposa"]
    if distance >= 100:
        base.append("combinado")
    return base


def is_valid_event(distance: int, stroke: str) -> bool:
    return normalize_stroke(stroke) in allowed_strokes(distance)
