"""Zonas de entrenamiento — adaptador sobre el motor de dominio.

Las zonas se calculan con el modelo CALIBRADO del sandbox (`app.domain`):

    zona_pace = ritmo_carrera × factor[perfil][distancia] (+ corrección estilo) × piscina

`pace_100m` es el ritmo de carrera por 100m del tiempo (esperado/recalc) de la
semana — exactamente el ancla que usa el dominio. El perfil se infiere de la
distancia (velocidad/medio fondo/fondo); el estilo aplica su corrección s/100m.

La forma de salida {min, mid, max} se conserva para el frontend: `mid` es el
objetivo científico del dominio; `min`/`max` son una tolerancia de visualización
de ±1% alrededor del objetivo (no es ciencia, es ancho de banda para la UI).

Fuente de verdad del modelo: `app/domain/engine.py` (port del sandbox).
"""
from __future__ import annotations

from app.domain import (
    STROKE_ALIASES,
    STROKE_TPACE_CORRECTION_S,
    pool_factor,
    profile_for_event,
    zone_factors,
)

ZONE_ORDER = ["R1", "R2", "MVO2", "RL", "V"]

ZONE_LABELS = {
    "R1": "Base aeróbica",
    "R2": "Umbral aeróbico",
    "MVO2": "VO2 máximo",
    "RL": "Resistencia lactato",
    "V": "Velocidad pura",
}

# Tolerancia de visualización alrededor del objetivo de zona (solo UI).
_ZONE_DISPLAY_TOLERANCE = 0.01  # ±1%

# Distribución recomendada del volumen semanal por especialidad del atleta
# (Seiler 2010, Issurin 2008). Claves = zonas; valores = fracción del km semanal.
SPECIALTY_ZONE_MIX: dict[str, dict[str, float]] = {
    "velocidad":      {"R1": 0.50, "R2": 0.15, "MVO2": 0.13, "RL": 0.12, "V": 0.10},
    "medio_fondo":    {"R1": 0.60, "R2": 0.16, "MVO2": 0.12, "RL": 0.08, "V": 0.04},
    "fondo":          {"R1": 0.70, "R2": 0.14, "MVO2": 0.09, "RL": 0.05, "V": 0.02},
    "aguas_abiertas": {"R1": 0.78, "R2": 0.12, "MVO2": 0.06, "RL": 0.03, "V": 0.01},
}

SPECIALTY_LABELS = {
    "velocidad": "Velocidad",
    "medio_fondo": "Medio fondo",
    "fondo": "Fondo",
    "aguas_abiertas": "Aguas abiertas",
}


def calc_zones(
    pace_100m: float,
    distance: int,
    stroke: str = "freestyle",
    pool: str = "50",
) -> dict[str, dict[str, float] | None]:
    """Tiempos objetivo por 100m para cada zona (con rango min/mid/max).

    Usa los factores por perfil×distancia del dominio (calibrados con el pool
    nacional), la corrección de estilo y el factor de piscina. `pace_100m` es el
    ritmo de carrera por 100m de la semana.
    """
    profile = profile_for_event(distance)
    factors = zone_factors(profile, distance)
    stroke_key = STROKE_ALIASES.get(stroke.lower().strip(), "freestyle")
    corr = STROKE_TPACE_CORRECTION_S.get(stroke_key, 0.0)
    pf = pool_factor(profile, pool)

    zones: dict[str, dict[str, float] | None] = {}
    for zone in ZONE_ORDER:
        factor = factors.get(zone)
        if factor is None:
            zones[zone] = None
            continue
        target = (pace_100m * factor + corr) * pf
        zones[zone] = {
            "min": round(target * (1 - _ZONE_DISPLAY_TOLERANCE), 2),
            "mid": round(target, 2),
            "max": round(target * (1 + _ZONE_DISPLAY_TOLERANCE), 2),
        }
    return zones


def zone_km_distribution(specialty: str, weekly_km: float) -> dict[str, float]:
    """Kilómetros sugeridos por zona para la semana según especialidad."""
    mix = SPECIALTY_ZONE_MIX.get(specialty, SPECIALTY_ZONE_MIX["medio_fondo"])
    return {zone: round(weekly_km * frac, 1) for zone, frac in mix.items()}
