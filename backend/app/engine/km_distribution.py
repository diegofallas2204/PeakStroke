"""Distribución del kilometraje semanal del macrociclo.

Combina dos señales respaldadas por la teoría (Bompa & Haff 2009, Issurin 2008):
1. Envolvente macro: rampa de volumen hasta ~70% del ciclo y descenso (taper)
   de 40-60% hacia la competencia.
2. Onda de microciclo 3:1 (o 4:1 en micros de 5 semanas): tres/cuatro semanas
   de carga progresiva y una de descarga para supercompensación.

El resultado se normaliza para que la suma sea exactamente el total planificado.
"""
from __future__ import annotations

# Onda intra-microciclo: carga relativa de cada semana dentro del micro.
_MICRO_WAVE = {
    4: [0.78, 0.90, 1.00, 0.58],
    5: [0.72, 0.84, 0.94, 1.00, 0.58],
}


def _macro_envelope(index: int, total: int) -> float:
    """Rampa 0.65 -> 1.0 hasta el 70% del ciclo, luego taper hasta 0.40."""
    x = index / (total - 1) if total > 1 else 0.0
    if x <= 0.70:
        return 0.65 + 0.35 * (x / 0.70)
    return 1.0 - 0.60 * ((x - 0.70) / 0.30)


def distribute_km(total_weeks: int, total_km: float, weeks_per_micro: int = 4) -> list[float]:
    """Kilómetros planificados por semana (lista de longitud total_weeks)."""
    wave = _MICRO_WAVE.get(weeks_per_micro, _MICRO_WAVE[4])
    raw: list[float] = []
    for i in range(total_weeks):
        envelope = _macro_envelope(i, total_weeks)
        micro_pos = i % weeks_per_micro
        # La última semana siempre es descarga (taper final), no pico de carga.
        if i == total_weeks - 1:
            factor = envelope * 0.55
        else:
            factor = envelope * wave[min(micro_pos, len(wave) - 1)]
        raw.append(factor)
    total_raw = sum(raw)
    return [round(f * total_km / total_raw, 1) for f in raw]
