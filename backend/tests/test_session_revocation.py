"""Cerrar sesión cierra la sesión, no solo borra la cookie.

Hasta el 2026-08-06 `POST /auth/logout` hacía exactamente una cosa:
`response.delete_cookie(...)`. El refresh token es un JWT sin `jti`, sin lista
de revocación y sin nada en el usuario contra lo que compararlo, así que seguía
siendo válido sus 30 días completos.

El ataque no es teórico y no necesita nada sofisticado: quien haya capturado la
cookie de refresh (máquina compartida, extensión del navegador, proxy
corporativo) sigue emitiendo access tokens durante un mes **después** de que la
víctima pulse "cerrar sesión". Que es precisamente la acción que se pulsa
cuando se sospecha que la cuenta está comprometida.

Estos tests corren con `auth_enabled=True`: es el único modo en el que existen
tokens que revocar.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.models import User
from conftest import API, PASSWORD, World


@pytest.fixture
def auth_on(monkeypatch):
    """Login real encendido, con un secreto que no sea el centinela de desarrollo."""
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


async def _entrar(client, email: str) -> str:
    """Inicia sesión y devuelve el access token. La cookie queda en el cliente."""
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_el_refresh_capturado_deja_de_valer_tras_cerrar_sesion(
    client, world: World, auth_on,
):
    """**El crítico.** Era el agujero: 30 días de vida útil tras el logout."""
    await _entrar(client, world.sofia_email)
    robada = client.cookies.get(settings.refresh_cookie_name)
    assert robada, "el login no dejó cookie de refresh"

    assert (await client.post(f"{API}/auth/refresh")).status_code == 200

    assert (await client.post(f"{API}/auth/logout")).status_code == 204

    # El atacante conserva su copia aunque el navegador de la víctima ya no la tenga.
    client.cookies.set(settings.refresh_cookie_name, robada, path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401


async def test_el_access_token_muere_en_la_siguiente_peticion(
    client, world: World, auth_on,
):
    """Sin comparar `ver` también en el access, logout tardaría 15 minutos.

    Esos 15 minutos son justo el margen que aprovecha quien acaba de ser
    descubierto, y la comprobación sale gratis: `get_current_principal` ya tiene
    el usuario cargado.
    """
    token = await _entrar(client, world.sofia_email)
    assert (await client.get(f"{API}/auth/me", headers=_bearer(token))).status_code == 200

    await client.post(f"{API}/auth/logout")

    assert (await client.get(f"{API}/auth/me", headers=_bearer(token))).status_code == 401


async def test_cerrar_sesion_dos_veces_no_es_un_error(client, world: World, auth_on):
    """Sin cookie válida se borra lo que haya y se devuelve 204.

    Un 401 al cerrar sesión deja al usuario sin ninguna acción que le saque del
    problema: no puede entrar y no puede salir.
    """
    await _entrar(client, world.sofia_email)
    assert (await client.post(f"{API}/auth/logout")).status_code == 204
    assert (await client.post(f"{API}/auth/logout")).status_code == 204

    client.cookies.set(settings.refresh_cookie_name, "esto-no-es-un-jwt", path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/logout")).status_code == 204


async def test_volver_a_entrar_funciona_despues_de_cerrar_sesion(
    client, db, world: World, auth_on,
):
    """Revocar no es bloquear la cuenta: el siguiente login emite la generación nueva."""
    await _entrar(client, world.sofia_email)
    await client.post(f"{API}/auth/logout")

    nuevo = await _entrar(client, world.sofia_email)
    assert (await client.get(f"{API}/auth/me", headers=_bearer(nuevo))).status_code == 200

    sofia = (await db.execute(
        select(User).where(User.email == world.sofia_email)
    )).scalar_one()
    assert sofia.token_version == 1


async def test_cerrar_sesion_no_afecta_a_otras_cuentas(client, world: World, auth_on):
    """La generación es por usuario. Que salga uno no echa a los demás."""
    token_sofia = await _entrar(client, world.sofia_email)
    client.cookies.clear()
    token_owner = await _entrar(client, world.owner_email)

    assert (await client.post(f"{API}/auth/logout")).status_code == 204  # sale el owner

    assert (await client.get(f"{API}/auth/me", headers=_bearer(token_owner))).status_code == 401
    assert (await client.get(f"{API}/auth/me", headers=_bearer(token_sofia))).status_code == 200
