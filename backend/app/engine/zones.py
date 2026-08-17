"""Zonas de entrenamiento — adaptador sobre el motor de dominio.

Las zonas se calculan con el modelo CALIBRADO del sandbox (`app.domain`):

    zona_pace = ritmo_carrera × factor[perfil][distancia] (+ corrección estilo) × piscina

`pace_100m` es el ritmo de carrera por 100m del tiempo (esperado/recalc) de la
semana — exactamente el ancla que usa el dominio. El perfil se infiere de la
distancia (velocidad/medio fondo/fondo); el estilo aplica su corrección s/100m.

La forma de salida {min, mid, max} se conserva para el frontend: `mid` es el
objetivo científico del dominio; `min`/`max` son una tolerancia de visualización
de ±1% alrededor del objetivo (no es ciencia, es ancho de banda para la UI).

Desde el 2026-08-10 cada zona trae además `send_off` y `rest`: el intervalo de
salida para repeticiones de `rep_distance` metros. Va aquí y no en cada
consumidor porque una prescripción son **dos** números —a qué ritmo y cada
cuánto— y separarlos garantizaba que la mitad se olvidara en algún sitio. Ver
`engine/send_off.py` para de dónde sale el descanso de cada zona.

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
from app.dominio.servicios.tablas import (
    MEZCLA_DE_ZONAS_POR_DISTANCIA,
    MEZCLA_DE_ZONAS_POR_ESPECIALIDAD,
)

from .send_off import ZONE_ORDER as _ZONE_ORDER
from .send_off import clock_interval, rest_for

# Reexportado, no redefinido: `send_off.REST_RATIO` tiene una entrada por zona y
# `rest_for` revienta con una que no conozca, así que dos listas de zonas que se
# separen convierten una zona nueva en un 500 en la tabla del equipo. La
# canónica vive con la tabla de descansos; aquí se reexporta como lista porque
# es lo que consumen los llamadores de siempre.
ZONE_ORDER = list(_ZONE_ORDER)

ZONE_LABELS = {
    "R1": "Base aeróbica",
    "R2": "Umbral aeróbico",
    "MVO2": "VO2 máximo",
    "RL": "Resistencia lactato",
    "V": "Velocidad pura",
}

# Tolerancia de visualización alrededor del objetivo de zona (solo UI).
_ZONE_DISPLAY_TOLERANCE = 0.01  # ±1%

# Distribución del volumen semanal por distancia de prueba.
# Driver principal: la contribución energética aeróbica/anaeróbica cambia
# drásticamente con la distancia (Gastin 2001, Maglischo 2011):
#   50m → 5% aeróbico    → dominio V y RL
#   100m → 35% aeróbico  → equilibrio velocidad-resistencia
#   200m → 60% aeróbico  → transición
#   400m → 87% aeróbico  → umbral predominante
#   800m → 93% aeróbico  → base aeróbica muy alta
#   1500m → 95% aeróbico → máximo R1/R2
_DISTANCE_ZONE_MIX = MEZCLA_DE_ZONAS_POR_DISTANCIA

# Distribución por especialidad — se conserva como fallback cuando no hay
# distancia disponible (simulador) y como referencia de la tabla de datos.
SPECIALTY_ZONE_MIX = MEZCLA_DE_ZONAS_POR_ESPECIALIDAD

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
    rep_distance: int = 100,
) -> dict[str, dict[str, float] | None]:
    """Tiempos objetivo por 100m para cada zona (con rango min/mid/max).

    Usa los factores por perfil×distancia del dominio (calibrados con el pool
    nacional), la corrección de estilo y el factor de piscina. `pace_100m` es el
    ritmo de carrera por 100m de la semana.

    `rep_distance` es la distancia de las repeticiones que se van a nadar (100m
    por defecto, la unidad del sistema) y solo afecta a `send_off`/`rest`: el
    ritmo objetivo es por 100m siempre.
    """
    profile = profile_for_event(distance)
    factors = zone_factors(profile, distance)
    stroke_key = STROKE_ALIASES.get(stroke.lower().strip(), "freestyle")
    corr = STROKE_TPACE_CORRECTION_S.get(stroke_key, 0.0)
    pf = pool_factor(profile, pool)
    rep_factor = max(rep_distance, 1) / 100.0

    zones: dict[str, dict[str, float] | None] = {}
    for zone in ZONE_ORDER:
        factor = factors.get(zone)
        if factor is None:
            zones[zone] = None
            continue
        target = (pace_100m * factor + corr) * pf
        work = target * rep_factor
        interval = clock_interval(work + rest_for(zone, work))
        zones[zone] = {
            "min": round(target * (1 - _ZONE_DISPLAY_TOLERANCE), 2),
            "mid": round(target, 2),
            "max": round(target * (1 + _ZONE_DISPLAY_TOLERANCE), 2),
            # Cada cuánto sale la repetición y cuánto se descansa dentro de ese
            # ciclo. `rest` es el real tras cuadrar al reloj, no el teórico.
            "send_off": interval,
            "rest": round(interval - work, 2),
            "rep_distance": rep_distance,
        }
    return zones


def zone_km_distribution(
    weekly_km: float,
    distance: int | None = None,
    specialty: str | None = None,
) -> dict[str, float]:
    """Kilómetros sugeridos por zona para la semana.

    La distribución prioriza la distancia del evento (driver fisiológico
    directo); cae en la especialidad cuando no hay distancia disponible.
    Para distancias intermedias se interpola entre los dos puntos más cercanos.
    """
    if distance is not None:
        sorted_dists = sorted(_DISTANCE_ZONE_MIX.keys())
        if distance <= sorted_dists[0]:
            mix = _DISTANCE_ZONE_MIX[sorted_dists[0]]
        elif distance >= sorted_dists[-1]:
            mix = _DISTANCE_ZONE_MIX[sorted_dists[-1]]
        elif distance in _DISTANCE_ZONE_MIX:
            mix = _DISTANCE_ZONE_MIX[distance]
        else:
            # Interpolación lineal entre los dos puntos más cercanos
            lo = max(d for d in sorted_dists if d < distance)
            hi = min(d for d in sorted_dists if d > distance)
            t = (distance - lo) / (hi - lo)
            lo_mix = _DISTANCE_ZONE_MIX[lo]
            hi_mix = _DISTANCE_ZONE_MIX[hi]
            mix = {z: lo_mix[z] + t * (hi_mix[z] - lo_mix[z]) for z in ZONE_ORDER}
    else:
        sp = specialty or "medio_fondo"
        mix = SPECIALTY_ZONE_MIX.get(sp, SPECIALTY_ZONE_MIX["medio_fondo"])

    return {zone: round(weekly_km * mix[zone], 1) for zone in ZONE_ORDER}
