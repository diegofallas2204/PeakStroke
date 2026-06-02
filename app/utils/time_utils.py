"""
time_utils.py — Conversión y formateo de tiempos de natación.

Responsabilidad única: transformar entre representaciones de tiempo
(string legible ↔ segundos flotante).
"""


def to_seconds(time_str: str) -> float:
    """
    Convierte un tiempo en formato string a segundos.

    Formatos aceptados:
      '1:05.32'  →  65.32
      '65.32'    →  65.32
      '1:05'     →  65.0
      '10:20.00' →  620.0

    Raises:
        ValueError: si el formato no es reconocible.
    """
    time_str = time_str.strip().replace(",", ".")

    if ":" in time_str:
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Formato de tiempo inválido: '{time_str}'")
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60.0 + seconds
    else:
        return float(time_str)


def to_time_str(seconds: float, precision: int = 2) -> str:
    """
    Convierte segundos flotantes a formato mm:ss.cc legible.

    Ejemplos:
      65.32  →  '1:05.32'
      620.0  →  '10:20.00'
      52.8   →  '0:52.80'

    Args:
        seconds:   Tiempo en segundos (debe ser ≥ 0).
        precision: Decimales en la parte de segundos (default 2).
    """
    if seconds < 0:
        return "--:--.--"

    minutes = int(seconds // 60)
    secs = seconds % 60

    if precision == 2:
        sec_str = f"{secs:05.2f}"
    elif precision == 1:
        sec_str = f"{secs:04.1f}"
    else:
        sec_str = f"{int(secs):02d}"

    return f"{minutes}:{sec_str}"


def improvement_str(delta_seconds: float) -> str:
    """
    Formatea una diferencia de tiempo con signo.

    Ejemplos:
      -0.32  →  '-0.32 s'
      +0.15  →  '+0.15 s'
       0.0   →  ' 0.00 s'
    """
    sign = "-" if delta_seconds < 0 else "+"
    return f"{sign}{abs(delta_seconds):.2f} s"


def pace_per_100m(race_time: float, distance_m: int) -> float:
    """
    Calcula el parcial por cada 100m a partir del tiempo total de la prueba.

    Ejemplo:
      race_time=300.0, distance_m=400  →  75.0 s/100m
    """
    return race_time / (distance_m / 100.0)
