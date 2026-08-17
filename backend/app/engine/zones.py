"""Zonas de entrenamiento — adaptador sobre `MotorCientifico.zonas`.

    zona = ritmo_carrera × factor[perfil][distancia] (+ corrección estilo) × piscina

`pace_100m` es el ritmo de carrera por 100 m del tiempo (esperado o recalculado)
de la semana. Desde el paso 4 el cálculo entero —incluida la salida de cada
zona— vive en el motor único; aquí queda la firma vieja y las etiquetas que
consume la interfaz.
"""
from __future__ import annotations

from app.dominio.servicios.kilometraje import km_por_zona
from app.dominio.servicios.motor import MOTOR
from app.dominio.servicios.tablas import MEZCLA_DE_ZONAS_POR_ESPECIALIDAD
from app.dominio.valores import Zona

# La lista canónica es el orden del enum `Zona`, que ES la jerarquía (R1 → V).
ZONE_ORDER = [z.value for z in Zona.ordenadas()]

ZONE_LABELS = {z.value: z.etiqueta for z in Zona.ordenadas()}

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
    """Tiempos objetivo por 100 m de cada zona, con su intervalo de salida."""
    return MOTOR.zonas(pace_100m, distance, stroke, pool, rep_distance)


def zone_km_distribution(
    weekly_km: float,
    distance: int | None = None,
    specialty: str | None = None,
) -> dict[str, float]:
    """Kilómetros sugeridos por zona para la semana."""
    return km_por_zona(weekly_km, distance, specialty)
