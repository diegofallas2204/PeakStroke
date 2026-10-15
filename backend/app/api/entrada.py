"""Lo que comparten los cuerpos de petición: números finitos y un 422 que se pinta.

TODO-23 (C9, 2026-10-14). El `json` de Python acepta `Infinity`, `-Infinity` y
`NaN` al leer, y `Field(gt=0)` deja pasar `Infinity`. Llegaba al motor o al
constructor de un `Tiempo` y salía como un 500. Dos piezas, y hacen falta las
dos:

- **`Entrada`**: base de todo cuerpo con un `float` (`allow_inf_nan=False`).
  Rechaza el número en el 422 en vez de dejarlo entrar.
  `tests/test_entrada_finita.py` recorre las rutas y falla si un cuerpo nuevo
  con un `float` no hereda de aquí.
- **`validacion_pintable`**: el manejador del 422. El de FastAPI copia en cada
  error el valor recibido (`input`), y un `inf` no se puede escribir en JSON
  (`json.dumps(..., allow_nan=False)` revienta): el 422 que avisaba del número
  se convertía él mismo en un 500. Este hace lo mismo que el de FastAPI y solo
  cambia los números no finitos por su texto («inf», «nan»). Cualquier otro 422
  sale byte a byte igual que antes.
"""
from __future__ import annotations

import math

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class Entrada(BaseModel):
    """Cuerpo de petición cuyos `float` tienen que ser finitos."""

    model_config = ConfigDict(allow_inf_nan=False)


def _pintable(valor: object) -> object:
    if isinstance(valor, float) and not math.isfinite(valor):
        return str(valor)
    if isinstance(valor, dict):
        return {k: _pintable(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_pintable(v) for v in valor]
    return valor


async def validacion_pintable(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422, content={"detail": _pintable(jsonable_encoder(exc.errors()))},
    )
