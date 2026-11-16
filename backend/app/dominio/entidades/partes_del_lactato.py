"""Las piezas del test de lactato: una repetición, el protocolo y la recuperación.

Siguen la plantilla del entrenador (`Tabla Medición`, 2026-11-16): por
repetición, la serie, el tiempo, la intensidad (esfuerzo 1-10), el lactato, la
FC, los conteos de brazada y los parciales; en el pie, la recuperación (minuto,
FC y lactato). Todo opcional salvo el tiempo: la hoja real dejaba columnas
enteras sin llenar.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..valores import MetodoDeFc, SitioDeMuestra, Tiempo

LACTATO = (0.0, 30.0)     # mmol/L
FC = (30, 250)            # lat/min
ESFUERZO = (0.0, 10.0)    # CR-10
BRAZADAS = (1, 200)       # por tramo


def en_rango(valor: float | None, limites: tuple[float, float], que: str) -> float | None:
    if valor is None:
        return None
    if not (limites[0] <= valor <= limites[1]) or (isinstance(valor, float) and not math.isfinite(valor)):
        raise ValueError(f"{que} fuera de rango: {valor} (entre {limites[0]} y {limites[1]})")
    return valor


@dataclass(frozen=True, slots=True)
class Repeticion:
    """Una repetición. `tiempo` es siempre el tiempo NADADO."""

    numero: int
    tiempo: Tiempo
    lactato: float | None = None
    fc: int | None = None
    esfuerzo: float | None = None
    brazadas: tuple[int, ...] = ()
    # Lo que tardó en el tramo contado. Con él la frecuencia deja de ser estimada.
    tiempo_tramo: Tiempo | None = None
    # «Serie» de la plantilla: para un test con varias series (2 × 4×400…).
    serie: int | None = None
    # «Parciales» de la plantilla: los tiempos de cada tramo igual (4 × 100 de un 400).
    parciales: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.numero < 1:
            raise ValueError("Las repeticiones se numeran desde 1")
        if not isinstance(self.tiempo, Tiempo):
            raise TypeError("El tiempo de una repetición es un Tiempo")
        if self.serie is not None and self.serie < 1:
            raise ValueError("Las series se numeran desde 1")
        en_rango(self.lactato, LACTATO, "Lactato")
        en_rango(self.fc, FC, "Frecuencia cardiaca")
        en_rango(self.esfuerzo, ESFUERZO, "Esfuerzo")
        object.__setattr__(self, "brazadas", tuple(int(b) for b in self.brazadas))
        for b in self.brazadas:
            en_rango(b, BRAZADAS, "Conteo de brazadas")
        object.__setattr__(self, "parciales", tuple(float(p) for p in self.parciales))
        if any(not (math.isfinite(p) and p > 0) for p in self.parciales):
            raise ValueError("Los parciales son tiempos positivos")

    def brazadas_medias(self) -> float | None:
        return sum(self.brazadas) / len(self.brazadas) if self.brazadas else None

    def deriva_interna_pct(self) -> float | None:
        """Del primer al último conteo de la misma repetición, en %."""
        if len(self.brazadas) < 2:
            return None
        return (self.brazadas[-1] - self.brazadas[0]) / self.brazadas[0] * 100


@dataclass(frozen=True, slots=True)
class ProtocoloDeMuestra:
    """Cómo se midió. Sin esto las muestras no se comparan entre tests (nota 28 §5).

    El sitio importa: el dedo da valores más altos que el lóbulo.
    """

    sitio: SitioDeMuestra | None = None
    analizador: str | None = None
    minuto: float | None = None          # minuto tras la repetición
    metodo_fc: MetodoDeFc | None = None


@dataclass(frozen=True, slots=True)
class MuestraDeRecuperacion:
    """Una medición después de la serie: el bloque de recuperación de la plantilla.

    El pico de lactato no llega al terminar sino unos minutos después; por eso
    se muestrea en varios minutos (3, 5, 7, 10 es lo habitual).
    """

    minuto: float
    fc: int | None = None
    lactato: float | None = None

    def __post_init__(self) -> None:
        if not (math.isfinite(self.minuto) and 0 <= self.minuto <= 120):
            raise ValueError("El minuto de recuperación va de 0 a 120")
        en_rango(self.lactato, LACTATO, "Lactato")
        en_rango(self.fc, FC, "Frecuencia cardiaca")
