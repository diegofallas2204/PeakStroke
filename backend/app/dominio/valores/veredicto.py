"""El veredicto de factibilidad: qué dice la ciencia de la meta que se pide.

Vivía en `escalas.py` como tres claves sin comportamiento, y los dos umbrales
que deciden entre ellas estaban en `servicios/tablas.py` (`RATIO_REALISTA`,
`RATIO_EXIGENTE`), aplicados por un `if` dentro de `envolvente.factibilidad`.
Mientras solo el motor emitía veredictos daba igual. Desde C9 (2026-10-13) lo
emite también `PruebaObjetivo.factibilidad()`, y una entidad no importa los
servicios: o los umbrales bajaban aquí, o había dos copias de los umbrales.

Bajaron aquí. Es lo que `servicios/tablas.py` ya dice de sí mismo: lo que es de
un objeto de valor vive dentro de él, y allí queda lo que no tiene ninguno.
"""
from __future__ import annotations

from typing import Self

from .escalas import _EscalaTextual

# §5.3 — «uso» es el cociente entre la mejora pedida y el techo científico del
# macro. Hasta 0.85 la meta cabe con margen; hasta 1.15 está en el borde del
# techo; por encima, el macro no alcanza y el motor propone semanas de extensión.
USO_REALISTA = 0.85
USO_EXIGENTE = 1.15


class Veredicto(_EscalaTextual):
    """Factibilidad de una meta: qué dice el motor de lo que pide el entrenador."""

    OK = "ok"
    AVISO = "warning"
    AGRESIVO = "aggressive"

    @classmethod
    def del_uso(cls, uso: float) -> Self:
        """El veredicto para ese cociente pedida / techo.

        Los dos bordes caen del lado permisivo (`<=`), como siempre lo hizo el
        motor. Un uso de cero o negativo —la meta ya está alcanzada— es `OK`.
        """
        if uso <= USO_REALISTA:
            return cls.OK
        if uso <= USO_EXIGENTE:
            return cls.AVISO
        return cls.AGRESIVO
