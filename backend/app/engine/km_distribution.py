"""Distribución del kilometraje semanal del macrociclo.

Combina dos señales respaldadas por la teoría (Bompa & Haff 2009, Issurin 2008):
1. Envolvente macro: rampa de volumen hasta ~70% del ciclo y descenso (taper)
   de 40-60% hacia la competencia.
2. Onda de microciclo 3:1 (o 4:1 en micros de 5 semanas): tres/cuatro semanas
   de carga progresiva y una de descarga para supercompensación.

El resultado se normaliza para que la suma sea exactamente el total planificado.
"""
from __future__ import annotations

from app.dominio.servicios.tablas import (
    CAIDA_DEL_TAPER,
    DESCARGA_ULTIMA_SEMANA,
    ONDA_DEL_MICRO,
    RAMPA_HASTA,
    RAMPA_INICIAL,
)

# Onda intra-microciclo: carga relativa de cada semana dentro del micro. La tabla
# vive en `dominio/servicios/tablas.py` desde el paso 4; aquí solo se lee.
_MICRO_WAVE = ONDA_DEL_MICRO


def _macro_envelope(index: int, total: int) -> float:
    """Rampa 0.65 -> 1.0 hasta el 70% del ciclo, luego taper hasta 0.40."""
    x = index / (total - 1) if total > 1 else 0.0
    if x <= RAMPA_HASTA:
        return RAMPA_INICIAL + (1.0 - RAMPA_INICIAL) * (x / RAMPA_HASTA)
    return 1.0 - CAIDA_DEL_TAPER * ((x - RAMPA_HASTA) / (1.0 - RAMPA_HASTA))


def distribute_km(total_weeks: int, total_km: float, weeks_per_micro: int = 4) -> list[float]:
    """Kilómetros planificados por semana (lista de longitud total_weeks)."""
    wave = _MICRO_WAVE.get(weeks_per_micro, _MICRO_WAVE[4])
    raw: list[float] = []
    for i in range(total_weeks):
        envelope = _macro_envelope(i, total_weeks)
        micro_pos = i % weeks_per_micro
        # La última semana siempre es descarga (taper final), no pico de carga.
        if i == total_weeks - 1:
            factor = envelope * DESCARGA_ULTIMA_SEMANA
        else:
            factor = envelope * wave[min(micro_pos, len(wave) - 1)]
        raw.append(factor)
    total_raw = sum(raw)
    return [round(f * total_km / total_raw, 1) for f in raw]
