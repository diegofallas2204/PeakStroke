"""La forma de la progresión: `Curva` y sus cinco implementaciones (§6.2).

Una curva contesta una sola pregunta: **qué fracción de la mejora total va
acumulada cuando ha transcurrido la fracción `x` del macrociclo**. Es
`f(0) = 0`, `f(1) = 1` y monótona creciente; el motor pone el resto (cuánta
mejora hay, qué semana es cuál, qué acota la fisiología).

La científica es la del sistema. Las otras cuatro existen para **comparar
escenarios en el simulador**, y conviene recordar por qué eso no es inocuo:
todas cierran en el mismo punto, pero a mitad de plan difieren hasta 1,30 s
contra una tolerancia de ±0,4 %, así que el mismo nado sale `AHEAD` con la
científica y `BEHIND` con la exponencial (decisión R7, §10.4).

Antes de este paso, añadir una curva eran cuatro ediciones en tres archivos:
la función, la lista `CURVES`, el diccionario `CURVE_LABELS` y su parámetro de
forma suelto. Aquí es una clase con su clave, su etiqueta y su parámetro dentro.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from ..valores import Fase
from .tablas import MACRO_15_FASES


class Curva(ABC):
    """Fracción de mejora acumulada en el punto `x` del macrociclo."""

    __slots__ = ()

    clave: str
    etiqueta: str

    @abstractmethod
    def _f(self, x: float) -> float:
        """La forma, ya normalizada a f(0)=0 y f(1)=1."""

    def progreso(self, x: float) -> float:
        """Fracción acumulada [0..1] en x [0..1], con x acotado a ese rango."""
        return self._f(max(0.0, min(1.0, x)))

    # ── Catálogo ────────────────────────────────────────────────────────────

    @classmethod
    def desde_clave(cls, clave: str | None) -> Curva:
        """La curva de esa clave. Una desconocida cae en la científica.

        Cae en vez de reventar a propósito: la clave llega del simulador como
        texto, y hasta R7 (2026-09-23) llegaba además de una columna de texto
        libre (`plans.progression_curve`). Caer en la científica es caer en la
        que la literatura respalda, no en una cualquiera — y es también la única
        que usa un plan real (`Macrociclo.curva`).
        """
        return _CATALOGO.get((clave or "").strip().lower(), _CIENTIFICA)

    @classmethod
    def catalogo(cls) -> tuple[Curva, ...]:
        """Todas, con la científica primero: es la de por defecto."""
        return _ORDEN


class Cientifica(Curva):
    """Distribución F_FASE: back-loaded, con el pico en el taper.

    Es la integral normalizada de la densidad de mejora — cada fase aporta
    mejora a un ritmo proporcional a su `f_fase`—, así que crece lento en base
    general y acelera hacia el taper (supercompensación). ≈59 % de la mejora cae
    en la segunda mitad y ≈18 % en el taper. Validada en las notas 09/16/17 del
    vault (Mujika 1995; cohorte de periodización; Morais 2021).

    Los tramos salen de la forma del macro de 15 semanas y de `Fase.f_fase`: no
    hay una tercera copia de los pesos aquí dentro.
    """

    __slots__ = ()
    clave = "science"
    etiqueta = "Científica (F_FASE)"

    def _f(self, x: float) -> float:
        acumulado = 0.0
        for x0, x1, peso in _TRAMOS:
            if x <= x0:
                break
            acumulado += peso * (min(x, x1) - x0)
        return acumulado / _TRAMOS_TOTAL


class Lineal(Curva):
    """Mejora constante semana a semana."""

    __slots__ = ()
    clave = "linear"
    etiqueta = "Lineal"

    def _f(self, x: float) -> float:
        return x


class Sigmoide(Curva):
    """Adaptación lenta, aceleración en construcción, meseta en el taper."""

    __slots__ = ()
    clave = "sigmoid"
    etiqueta = "Sigmoidal"
    # Cuanto más alta, más plano el inicio y el final y más brusco el centro.
    PENDIENTE = 10.0

    def _f(self, x: float) -> float:
        def s(t: float) -> float:
            return 1 / (1 + math.exp(-self.PENDIENTE * (t - 0.5)))
        return (s(x) - s(0)) / (s(1) - s(0))


class Exponencial(Curva):
    """Mejora rápida al principio — el atleta que recupera forma."""

    __slots__ = ()
    clave = "exponential"
    etiqueta = "Exponencial"
    # Cuanto más alta, más adelantada la mejora (front-loaded).
    K = 4.0

    def _f(self, x: float) -> float:
        return (1 - math.exp(-self.K * x)) / (1 - math.exp(-self.K))


class Logaritmica(Curva):
    """Mejoras decrecientes — el atleta cerca de su techo."""

    __slots__ = ()
    clave = "logarithmic"
    etiqueta = "Logarítmica"
    ESCALA = 9.0

    def _f(self, x: float) -> float:
        return math.log(1 + self.ESCALA * x) / math.log(1 + self.ESCALA)


def _tramos() -> list[tuple[float, float, float]]:
    """(x_ini, x_fin, peso) de cada fase como fracción del macro científico."""
    total = MACRO_15_FASES[-1][1]
    return [
        ((ini - 1) / total, fin / total, Fase.desde_texto(fase).f_fase)
        for ini, fin, fase in MACRO_15_FASES
    ]


_TRAMOS = _tramos()
_TRAMOS_TOTAL = sum(peso * (x1 - x0) for x0, x1, peso in _TRAMOS)

_CIENTIFICA = Cientifica()
# La científica primero: es la curva por defecto del sistema.
_ORDEN: tuple[Curva, ...] = (
    _CIENTIFICA, Sigmoide(), Lineal(), Exponencial(), Logaritmica(),
)
_CATALOGO: dict[str, Curva] = {c.clave: c for c in _ORDEN}
