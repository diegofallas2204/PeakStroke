"""Curvas de progresión — adaptador sobre `dominio.servicios.curvas`.

La forma de la progresión es hoy una jerarquía de clases (`Curva` y sus cinco
implementaciones, §6.2 del rediseño). Este módulo solo traduce la firma vieja
—`curve_progress(x, "science")`— para los llamadores que aún no la conocen, y
desaparece con ellos.
"""
from __future__ import annotations

from app.dominio.servicios.curvas import Curva

# "science" primero = curva por defecto del sistema.
CURVES = [c.clave for c in Curva.catalogo()]

CURVE_LABELS = {c.clave: c.etiqueta for c in Curva.catalogo()}


def curve_progress(x: float, curve: str) -> float:
    """Fracción de mejora acumulada [0..1] en el punto x [0..1]."""
    return Curva.desde_clave(curve).progreso(x)
