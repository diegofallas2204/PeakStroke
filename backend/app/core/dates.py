"""Aritmética de calendario compartida.

Vive en `core/` y no en un módulo porque la usan dos (`plans` y `swimmers`), y
las reglas del proyecto prohíben que un módulo importe lógica de otro. No va en
`engine/` ni en `domain/` porque no es ciencia de natación: el motor consume la
edad ya calculada (ajusta al alza el techo `I_max` de los menores), pero pasar
de fecha de nacimiento a años cumplidos es calendario y nada más.
"""
from __future__ import annotations

from datetime import date


def age_at(birth_date: date | None, ref: date | None = None) -> int | None:
    """Edad en años cumplidos en la fecha `ref` (hoy si no se indica).

    None si no hay fecha de nacimiento — la ficha puede no tenerla, y devolver 0
    haría pasar por recién nacido a quien solo tiene el dato sin rellenar.

    La fecha de referencia importa: la edad que ajusta el techo de mejora es la
    que se tiene **al empezar el macrociclo**, no la de hoy, o un plan pasaría a
    calcularse distinto el día del cumpleaños.
    """
    if birth_date is None:
        return None
    ref = ref or date.today()
    years = ref.year - birth_date.year
    if (ref.month, ref.day) < (birth_date.month, birth_date.day):
        years -= 1
    return max(years, 0)
