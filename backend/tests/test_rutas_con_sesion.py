"""Toda ruta del API exige sesión, salvo una lista explícita (2026-11-13).

`CLAUDE.md` lo dice —«ningún router nuevo sin guard»— pero nada lo comprobaba,
y el simulador (`/simulator/run` y `/simulator/season`) llevaba desde el
principio sin ninguna dependencia: con el login encendido, cualquiera sin
cuenta hacía trabajar al motor, y la interfaz se lo escondía al atleta sin que
el backend se lo negara. Este archivo recorre las rutas y mira que cada una
responda 401 sin sesión con el login encendido.

Una ruta nueva sin sesión hace fallar este test. Si de verdad tiene que ser
pública (es parte de entrar o del arranque), va en `PUBLICAS`, con su porqué.
"""
from __future__ import annotations

import re

import pytest
from conftest import API, World

from app.core.config import settings
from app.main import app

# Las únicas sin sesión, y por qué.
PUBLICAS = {
    ("GET", "/health"): "comprobación de vida del despliegue",
    ("POST", "/api/v1/auth/login"): "es la que abre la sesión",
    ("POST", "/api/v1/auth/refresh"): "se identifica por la cookie de refresh, no por el access",
    ("POST", "/api/v1/auth/logout"): "ídem: salir tiene que funcionar con el access caducado",
    ("POST", "/api/v1/auth/logout-all"): "ídem",
    ("GET", "/api/v1/auth/config"): "el frontend la pide antes de saber si hay login",
    ("GET", "/api/v1/auth/dev-identities"): "404 con el login puesto; sin él, el API ya está abierto",
}


@pytest.fixture
def login_encendido(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


def _rutas() -> list[tuple[str, str]]:
    """Cada (método, ruta) del API, sacado del esquema OpenAPI.

    Del esquema y no de `app.routes`: esta versión de FastAPI envuelve cada
    router incluido en un `_IncludedRouter` y la lista solo enseñaba `/health`
    (la primera versión de este test pasaba en verde sin mirar nada).
    """
    return [
        (metodo.upper(), ruta)
        for ruta, operaciones in app.openapi()["paths"].items()
        for metodo in operaciones
    ]


def test_el_barrido_ve_todo_el_api():
    rutas = _rutas()
    assert len(rutas) > 50, len(rutas)
    assert ("POST", "/api/v1/simulator/run") in rutas


async def test_toda_ruta_exige_sesion_salvo_las_publicas(client, world: World, login_encendido):
    """Sin token, con el login encendido, todo lo que no es público es 401.

    La sesión se resuelve antes que el cuerpo y los parámetros, así que basta un
    cuerpo vacío y `1` en cada parámetro de ruta.
    """
    abiertas = []
    for metodo, ruta in _rutas():
        if (metodo, ruta) in PUBLICAS:
            continue
        url = re.sub(r"\{[^}]+\}", "1", ruta)
        r = await client.request(metodo, url, json={} if metodo in {"POST", "PUT", "PATCH"} else None)
        if r.status_code != 401:
            abiertas.append((metodo, ruta, r.status_code))
    assert abiertas == [], f"rutas que responden sin sesión: {abiertas}"


def test_la_lista_de_publicas_no_tiene_rutas_que_ya_no_existen():
    assert set(PUBLICAS) <= set(_rutas()), set(PUBLICAS) - set(_rutas())


SIMULACION = {
    "distance": 200, "stroke": "libre", "current_time": 130.0, "goal_time": 126.0,
    "total_weeks": 12, "total_km": 300,
}
TEMPORADA = {"distance": 200, "stroke": "libre", "current_time": 130.0}


@pytest.mark.parametrize(("ruta", "cuerpo"), [
    ("/simulator/run", SIMULACION), ("/simulator/season", TEMPORADA),
])
async def test_el_simulador_sin_sesion_es_401(client, world: World, login_encendido, ruta, cuerpo):
    r = await client.post(f"{API}{ruta}", json=cuerpo)
    assert r.status_code == 401


@pytest.mark.parametrize(("ruta", "cuerpo"), [
    ("/simulator/run", SIMULACION), ("/simulator/season", TEMPORADA),
])
async def test_el_simulador_es_de_entrenador(client, world: World, ruta, cuerpo):
    """El menú se lo esconde al atleta (`navConfig`); el backend también lo niega."""
    from conftest import como

    entrenador = await client.post(f"{API}{ruta}", json=cuerpo, headers=como(world.assistant_email))
    atleta = await client.post(f"{API}{ruta}", json=cuerpo, headers=como(world.sofia_email))
    assert (entrenador.status_code, atleta.status_code) == (200, 403)
