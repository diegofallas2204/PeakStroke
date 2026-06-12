"""Zonas de entrenamiento — fuente de verdad única.

Factores por banda de distancia derivados de la calculadora de pronósticos
('pronosticos PABLO belen.xlsx') y validados contra la teoría (Maglischo,
Fernandes et al.). Cada zona tiene un rango (min, max) que se aplica sobre el
pace por 100m del tiempo meta de la prueba: a mayor distancia de prueba, los
factores se comprimen porque el ritmo de competencia ya es cercano al aeróbico.

Jerarquía (de más lento a más rápido): R1 > R2 > MVO2 > RL > V.
"""
from __future__ import annotations

ZONE_ORDER = ["R1", "R2", "MVO2", "RL", "V"]

ZONE_LABELS = {
    "R1": "Base aeróbica",
    "R2": "Umbral aeróbico",
    "MVO2": "VO2 máximo",
    "RL": "Resistencia lactato",
    "V": "Velocidad pura",
}

# Bandas: (distancia_max_inclusive, {zona: (factor_min, factor_max)})
# None = la zona no se prescribe para esa distancia de prueba.
_ZONE_BANDS: list[tuple[int, dict[str, tuple[float, float] | None]]] = [
    (50, {
        "R1": (1.26, 1.35), "R2": (1.20, 1.25), "MVO2": (1.15, 1.20),
        "RL": (1.06, 1.12), "V": (1.02, 1.05),
    }),
    (100, {
        "R1": (1.21, 1.30), "R2": (1.15, 1.20), "MVO2": (1.15, 1.20),
        "RL": (1.06, 1.12), "V": (1.02, 1.05),
    }),
    (200, {
        "R1": (1.20, 1.30), "R2": (1.12, 1.18), "MVO2": (1.10, 1.15),
        "RL": (1.05, 1.10), "V": (1.02, 1.05),
    }),
    (500, {
        "R1": (1.15, 1.20), "R2": (1.10, 1.12), "MVO2": (1.08, 1.10),
        "RL": None, "V": None,
    }),
    (1000, {
        "R1": (1.11, 1.15), "R2": (1.05, 1.10), "MVO2": (1.05, 1.10),
        "RL": None, "V": None,
    }),
    (10000, {
        "R1": (1.10, 1.12), "R2": (1.05, 1.10), "MVO2": None,
        "RL": None, "V": None,
    }),
]

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


def zone_factors_for(distance: int) -> dict[str, tuple[float, float] | None]:
    """Retorna los rangos de factores de zona para una distancia de prueba."""
    for max_dist, factors in _ZONE_BANDS:
        if distance <= max_dist:
            return factors
    return _ZONE_BANDS[-1][1]


def calc_zones(pace_100m: float, distance: int) -> dict[str, dict[str, float] | None]:
    """Tiempos objetivo por 100m para cada zona, con rango min/mid/max.

    `pace_100m` es el pace del tiempo esperado de la semana; los factores
    dependen de la distancia de la prueba (banda del Excel de pronósticos).
    """
    factors = zone_factors_for(distance)
    zones: dict[str, dict[str, float] | None] = {}
    for zone in ZONE_ORDER:
        rng = factors.get(zone)
        if rng is None:
            zones[zone] = None
            continue
        lo, hi = rng
        zones[zone] = {
            "min": round(pace_100m * lo, 2),
            "mid": round(pace_100m * (lo + hi) / 2, 2),
            "max": round(pace_100m * hi, 2),
        }
    return zones


def zone_km_distribution(specialty: str, weekly_km: float) -> dict[str, float]:
    """Kilómetros sugeridos por zona para la semana según especialidad."""
    mix = SPECIALTY_ZONE_MIX.get(specialty, SPECIALTY_ZONE_MIX["medio_fondo"])
    return {zone: round(weekly_km * frac, 1) for zone, frac in mix.items()}
