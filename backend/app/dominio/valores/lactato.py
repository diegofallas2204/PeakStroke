"""Los vocabularios del test de lactato (nota 26 y 28 del vault, 2026-11-13).

Cerrados, como los demás: la base los impone con un CHECK
(`tablas/vocabulario.py`) y el API con un `Literal`. Los rangos de lactato por
zona no están aquí sino junto a `Zona` (`zona.py`), porque de ellos depende el
«dentro/fuera de zona» y tienen que vivir en un solo sitio.
"""
from __future__ import annotations

from .escalas import _EscalaTextual


class ModoDeLactato(_EscalaTextual):
    """Qué pregunta responde el test.

    `CONTROL`: serie a ritmo constante (la del 22/09). Responde «¿esta
    prescripción produce el lactato de su zona en este atleta?». El rango de
    velocidades es estrecho, así que **no traza la curva lactato-velocidad**.

    `ESCALONADO`: cada repetición más rápida (5-7×200). Es el que daría la curva
    y las zonas individuales. El modelo ya lo admite; el ajuste de curva y los
    umbrales llegan en su propio bloque (no mueven el motor hasta entonces).
    """

    CONTROL = "control"
    ESCALONADO = "escalonado"


class TipoDeDescanso(_EscalaTextual):
    """Pausa fija entre repeticiones, o intervalo de salida.

    Con los dos, lo que se apunta y se guarda es el **tiempo nadado** de cada
    repetición (la regla de la nota 19): el test de lactato no admite llegadas
    de reloj, así que aquí no hay conversión que olvidar.
    """

    PAUSA = "pausa"
    SALIDA = "salida"


class SitioDeMuestra(_EscalaTextual):
    DEDO = "dedo"
    LOBULO = "lobulo"


class MetodoDeFc(_EscalaTextual):
    BANDA = "banda"
    PALPACION = "palpacion"
    OPTICO = "optico"


class EstadoDeZona(_EscalaTextual):
    """Dónde cae una muestra respecto al rango de la zona que se buscaba."""

    DEBAJO = "debajo"
    DENTRO = "dentro"
    ENCIMA = "encima"
