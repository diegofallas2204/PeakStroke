"""Aritmética de calendario compartida. **Envoltorio en retirada.**

La edad nació duplicada (`plans/service.age_at` y `swimmers/service._age`, la
misma aritmética con dos firmas) y este módulo la unificó. Eso arregló la
duplicación pero dejó la regla fuera de su objeto, que es el modelo anémico —P4
de `docs/REDISENO.md` §0—: una función que recibe la fecha de nacimiento de un
atleta en vez de un atleta que sabe su edad.

Desde el paso 2 del rediseño (2026-08-16) la regla es `Atleta.edad_en()` y aquí
solo queda la delegación, para los llamadores que todavía tienen una fecha suelta
y no la ficha. Se borra cuando no quede ninguno.
"""
from __future__ import annotations

from datetime import date

from app.dominio.entidades import anios_cumplidos


def age_at(birth_date: date | None, ref: date | None = None) -> int | None:
    """Edad en años cumplidos en la fecha `ref` (hoy si no se indica).

    None si no hay fecha de nacimiento — la ficha puede no tenerla, y devolver 0
    haría pasar por recién nacido a quien solo tiene el dato sin rellenar.

    La fecha de referencia importa: la edad que ajusta el techo de mejora es la
    que se tiene **al empezar el macrociclo**, no la de hoy, o un plan pasaría a
    calcularse distinto el día del cumpleaños.
    """
    return anios_cumplidos(birth_date, ref)
