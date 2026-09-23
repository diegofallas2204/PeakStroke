"""Conversión de tiempos de natación: 'm:ss.cc' <-> segundos."""
from __future__ import annotations


def to_seconds(value: str | float | int) -> float:
    """Convierte '1:05.32', '65.32' o 65.32 a segundos (float)."""
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(",", ".")
    if not raw:
        raise ValueError("Tiempo vacío")
    parts = raw.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return float(parts[0]) * 60.0 + float(parts[1])
    if len(parts) == 3:
        return float(parts[0]) * 3600.0 + float(parts[1]) * 60.0 + float(parts[2])
    raise ValueError(f"Formato de tiempo no reconocido: {value!r}")


def to_clock(seconds: float, decimals: int = 2) -> str:
    """Convierte segundos a 'm:ss.cc' (o 'ss.cc' si es menor a un minuto)."""
    if seconds is None or seconds < 0:
        return "--:--"
    minutes = int(seconds // 60)
    rest = seconds - minutes * 60
    if minutes == 0:
        return f"{rest:.{decimals}f}"
    width = 3 + decimals if decimals > 0 else 2
    return f"{minutes}:{rest:0{width}.{decimals}f}"
