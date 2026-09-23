"""Los catálogos cerrados que la API acepta, en un solo sitio.

Son `Literal` de Pydantic, no enums de dominio: lo que hacen es **rechazar en el
422** un valor que no está en la lista. Los enums equivalentes viven en
`app/dominio/valores/` y `tests/test_valores_vs_motor.py` comprueba que las dos
listas dicen lo mismo — si divergieran, la API aceptaría algo que el dominio no
sabe construir.

Viven aquí y no en `api/v1/atletas/schemas.py` porque los usan dos rebanadas: el
alta directa del entrenador y la invitación por correo describen la misma ficha.
Cuando estaban en una de las dos, la otra tenía que importar los schemas del
vecino — que es lo que `tests/test_dependencias_de_capas.py` persigue.

Espejo de `frontend/src/lib/constants.ts`.
"""
from __future__ import annotations

from typing import Literal

Gender = Literal["F", "M"]
Specialty = Literal["velocidad", "medio_fondo", "fondo", "aguas_abiertas"]
MainStroke = Literal["libre", "espalda", "pecho", "mariposa", "combinado"]
