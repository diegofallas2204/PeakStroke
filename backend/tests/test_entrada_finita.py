"""TODO-23 (C9, 2026-10-14): un número infinito en el cuerpo da 422, no 500.

El `json` de Python acepta `Infinity`/`NaN`, `Field(gt=0)` deja pasar
`Infinity`, y el 422 de FastAPI copiaba el valor recibido en el error, que no
se puede escribir en JSON: el aviso del número malo salía como un 500. Lo que
fija este archivo:

- todo cuerpo con un `float` hereda de `api.entrada.Entrada` (recorre las rutas);
- cada ruta con un `float` en el cuerpo responde 422 a `Infinity`, `-Infinity`,
  `NaN` y `1e999`, con un cuerpo que se puede leer;
- el resto de los 422 sale igual que con el manejador de FastAPI.
"""
from __future__ import annotations

import json
import math
import typing

import pytest
from conftest import API, World, como
from fastapi.routing import APIRoute
from pydantic import BaseModel

from app.api.entrada import Entrada
from app.main import app


def _rutas(rutas):
    for r in rutas:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):
            yield from _rutas(r.original_router.routes)
        elif isinstance(getattr(r, "routes", None), list):
            yield from _rutas(r.routes)


def _modelos_con_float(modelo: type[BaseModel], vistos: set) -> set[type[BaseModel]]:
    """El modelo y los anidados que tienen algún `float` (o `list[float]`, `float | None`)."""
    if modelo in vistos:
        return set()
    vistos.add(modelo)
    con_float: set[type[BaseModel]] = set()
    for campo in modelo.model_fields.values():
        pila = [campo.annotation]
        while pila:
            tipo = pila.pop()
            if tipo is float:
                con_float.add(modelo)
            pila += list(typing.get_args(tipo))
            if isinstance(tipo, type) and issubclass(tipo, BaseModel):
                con_float |= _modelos_con_float(tipo, vistos)
    return con_float


def _cuerpos_con_float() -> dict[str, set[type[BaseModel]]]:
    por_ruta: dict[str, set[type[BaseModel]]] = {}
    for ruta in _rutas(app.routes):
        for param in ruta.dependant.body_params:
            for tipo in (param.field_info.annotation, *typing.get_args(param.field_info.annotation)):
                if isinstance(tipo, type) and issubclass(tipo, BaseModel):
                    modelos = _modelos_con_float(tipo, set())
                    if modelos:
                        clave = f"{sorted(ruta.methods)[0]} {ruta.endpoint.__module__}.{ruta.name}"
                        por_ruta[clave] = modelos
    return por_ruta


def test_todo_cuerpo_con_un_float_rechaza_los_no_finitos():
    cuerpos = _cuerpos_con_float()
    assert len(cuerpos) >= 9, cuerpos                 # que el recorrido vio algo
    sueltos = {m.__name__ for modelos in cuerpos.values() for m in modelos
               if not issubclass(m, Entrada) or m.model_config.get("allow_inf_nan") is not False}
    assert sueltos == set()


_RAROS = ["Infinity", "-Infinity", "NaN", "1e999"]


def _con(cuerpo: dict, campo: str, raro: str) -> str:
    """El cuerpo en JSON con `campo` sustituido por el literal `raro` sin comillas."""
    texto = json.dumps(cuerpo | {campo: "__RARO__"})
    return texto.replace('"__RARO__"', raro)


@pytest.mark.parametrize("raro", _RAROS)
async def test_cada_ruta_con_un_float_da_422_y_se_puede_leer(client, world: World, raro):
    jefe = {**como(world.owner_email), "Content-Type": "application/json"}
    casos = [
        ("POST", f"{API}/swimmers/", {"name": "Raro"}, "weight_kg"),
        ("PUT", f"{API}/swimmers/{world.sofia_swimmer_id}", {}, "height_cm"),
        ("POST", f"{API}/plans/", {"name": "Raro", "start_date": "2027-03-01", "total_weeks": 12}, "total_km"),
        ("POST", f"{API}/aerobic-tests/", {"swimmer_id": world.sofia_swimmer_id, "test_type": "DIRECT",
                                            "test_date": "2026-10-01"}, "direct_per100"),
        ("POST", f"{API}/aerobic-tests/analyze", {"test_type": "T30", "splits": [80.0, 81.0]}, "send_off"),
        ("POST", f"{API}/simulator/run", {"distance": 200, "stroke": "libre", "goal_time": 120.0,
                                           "total_weeks": 12, "total_km": 300}, "current_time"),
        ("POST", f"{API}/simulator/season", {"distance": 200, "stroke": "libre"}, "current_time"),
    ]
    semana = (await client.get(f"{API}/plans/events/{world.sofia_event_id}/weeks", headers=jefe)).json()[3]
    casos.append(("PATCH", f"{API}/plans/weeks/{semana['id']}", {}, "real_time"))
    for metodo, url, cuerpo, campo in casos:
        r = await client.request(metodo, url, content=_con(cuerpo, campo, raro), headers=jefe)
        assert r.status_code == 422, (metodo, url, raro, r.status_code, r.text[:200])
        assert r.json()["detail"], url                                   # se pinta


async def test_un_infinito_anidado_tambien(client, world: World):
    """`EventInput` va dentro de `AddAthleteRequest`."""
    jefe = {**como(world.owner_email), "Content-Type": "application/json"}
    cuerpo = ('{"swimmer_id": 1, "events": [{"distance": 200, "stroke": "libre", '
              '"current_time": Infinity, "goal_time": 120.0}]}')
    r = await client.post(f"{API}/plans/{world.plan_id}/athletes", content=cuerpo, headers=jefe)
    assert r.status_code == 422 and r.json()["detail"]
    r = await client.post(f"{API}/aerobic-tests/", headers=jefe, content=(
        '{"swimmer_id": 1, "test_type": "T30", "test_date": "2026-10-01", "splits": [80.0, NaN]}'))
    assert r.status_code == 422 and r.json()["detail"]


@pytest.mark.parametrize("cuerpo", [
    {"name": "x", "gender": "Z", "weight_kg": -1},
    {"name": "Bien", "specialty": "sprint"},
    {},
])
async def test_un_422_normal_sale_byte_a_byte_como_con_el_de_fastapi(cuerpo):
    """El manejador nuevo solo cambia los números no finitos: el resto, idéntico."""
    from fastapi.exception_handlers import request_validation_exception_handler
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError

    from app.api.entrada import validacion_pintable
    from app.api.v1.atletas.schemas import SwimmerCreate

    with pytest.raises(ValidationError) as error:
        SwimmerCreate.model_validate(cuerpo)
    exc = RequestValidationError([{**e, "loc": ("body", *e["loc"])} for e in error.value.errors()])
    assert (await validacion_pintable(None, exc)).body == (
        await request_validation_exception_handler(None, exc)
    ).body


async def test_un_input_infinito_se_pinta_como_texto():
    from fastapi.exceptions import RequestValidationError

    from app.api.entrada import validacion_pintable

    exc = RequestValidationError([{"type": "finite_number", "loc": ("body", "x"),
                                   "msg": "Input should be a finite number", "input": math.inf,
                                   "ctx": {"lista": [1.0, -math.inf, math.nan]}}])
    detalle = json.loads((await validacion_pintable(None, exc)).body)["detail"][0]
    assert (detalle["input"], detalle["ctx"]["lista"]) == ("inf", [1.0, "-inf", "nan"])
