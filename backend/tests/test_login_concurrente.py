# ruff: noqa: F811 — las fixtures de `carreras` se importan y se piden por nombre
"""Un login —o un segundo cambio— con la contraseña vieja que se solapa con un
cambio de contraseña.

Lo vio el revisor de TODO-30 (2026-10-20), y es anterior a él: el login verifica
la contraseña con Argon2 (~200 ms) y después escribe su acceso. Si en medio la
víctima cambia la contraseña —el gesto de «echa al que me robó la cuenta»—:

- el login releía la cuenta al escribir y firmaba tokens de la generación
  **nueva**: quien probara la vieja en bucle seguía dentro después del cambio;
- si el hash necesitaba rehash, el login escribía el de la contraseña **vieja**
  encima del nuevo: el cambio de contraseña se deshacía.

Ahora el login escribe con un `UPDATE ... WHERE password_hash = :verificado`
(`RepositorioDeUsuarios.registrar_acceso`): si la contraseña cambió desde que se
verificó, 0 filas, y es un 401 auditado como `credenciales_cambiadas`.

La vuelta 2 del revisor vio el mismo hueco en el **cambio** de contraseña: dos
`/me/password` a la vez escribían cada uno su hash y la generación «leída + 1»,
así que la generación subía una sola vez y la sesión nueva del primero
sobrevivía al cambio del segundo. Ahora el cambio también es condicional
(`RepositorioDeUsuarios.cambiar_password`, generación `token_version + 1` en
SQL), y el que pierde recibe 409.

`/me/password` exige `Principal`: los dos casos corren solo con club.
"""
from __future__ import annotations

import asyncio

import pytest
from carreras import (  # noqa: F401  (las fixtures se usan por nombre)
    COOKIE,
    auth_on,
    bearer,
    cuenta,
    entrar,
    eventos,
    nuevo_cliente,
    sesiones,
)
from conftest import API, PASSWORD

from app.core.auditoria import TipoDeEvento
from app.persistencia.repositorios import RepositorioDeUsuarios

NUEVA = "otra-contrasena-larga"


def _parar_el_acceso(monkeypatch, correo: str) -> tuple[asyncio.Event, asyncio.Event]:
    """Para la primera escritura del acceso de ese login (ya verificó la
    contraseña) hasta `seguir`. Vale antes y después del arreglo: se para en el
    método que la escriba, `guardar` o `registrar_acceso`."""
    llego, seguir = asyncio.Event(), asyncio.Event()
    pendiente = [True]

    def parar(real):
        async def parado(self, usuario):
            if pendiente[0] and usuario.ultimo_login is not None and usuario.correo == correo:
                pendiente[0] = False
                llego.set()
                async with asyncio.timeout(10):
                    await seguir.wait()
            return await real(self, usuario)
        return parado

    for metodo in ("guardar", "registrar_acceso"):
        real = getattr(RepositorioDeUsuarios, metodo, None)
        if real is not None:
            monkeypatch.setattr(RepositorioDeUsuarios, metodo, parar(real))
    return llego, seguir


async def _carrera(nuevo_cliente, correo: str, monkeypatch):
    """Un login con la vieja parado justo antes de escribir; mientras, la
    víctima cambia la contraseña desde su sesión. Devuelve (cambio, login)."""
    portatil = await entrar(nuevo_cliente(), correo)
    llego, seguir = _parar_el_acceso(monkeypatch, correo)
    ladron = asyncio.create_task(entrar(nuevo_cliente(), correo))
    async with asyncio.timeout(10):
        await llego.wait()
    cambio = await nuevo_cliente().post(
        f"{API}/auth/me/password", headers=bearer(portatil),
        json={"current_password": PASSWORD, "new_password": NUEVA},
    )
    seguir.set()
    return cambio, await ladron


def _con_club(request) -> None:
    if request.node.callspec.params["cuenta"] == "sin_club":
        pytest.skip("/me/password exige club (Principal); sin club es 403")


async def test_un_login_con_la_vieja_a_la_vez_que_el_cambio_no_entra(
    nuevo_cliente, sesiones, cuenta, monkeypatch, request,
):
    """En HEAD el login salía con 200 y su access valía después del cambio."""
    _con_club(request)
    _, correo = cuenta
    cambio, ladron = await _carrera(nuevo_cliente, correo, monkeypatch)

    assert cambio.status_code == 200, cambio.text
    assert ladron.status_code == 401, ladron.text
    assert COOKIE not in ladron.cookies
    assert "credenciales_cambiadas" in await eventos(correo, TipoDeEvento.LOGIN)
    assert (await nuevo_cliente(cambio.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 200


async def test_el_rehash_de_la_vieja_no_deshace_el_cambio(
    nuevo_cliente, sesiones, cuenta, monkeypatch, request,
):
    """En HEAD el login escribía el rehash de la contraseña vieja encima del
    hash nuevo: después entraba la vieja y no la nueva."""
    _con_club(request)
    _, correo = cuenta
    # Solo el primer login pide rehash —el ladrón, que llega antes—: el
    # `comprobar_credenciales` de `/me/password` no rehashea, así que si el hash nuevo se
    # pierde es por el rehash de la vieja (vuelta 2 del revisor).
    pedidos = [True]
    monkeypatch.setattr(
        "app.api.v1.auth.credenciales.needs_rehash",
        lambda _hash: pedidos.pop() if pedidos else False,
    )
    cambio, ladron = await _carrera(nuevo_cliente, correo, monkeypatch)

    assert cambio.status_code == 200, cambio.text
    assert ladron.status_code == 401, ladron.text
    vieja = await nuevo_cliente().post(f"{API}/auth/login", json={"email": correo, "password": PASSWORD})
    nueva = await nuevo_cliente().post(f"{API}/auth/login", json={"email": correo, "password": NUEVA})
    assert (vieja.status_code, nueva.status_code) == (401, 200), "el cambio de contraseña se deshizo"


def _parar_el_cambio(monkeypatch, correo: str) -> tuple[asyncio.Event, asyncio.Event]:
    """Para la primera escritura de un cambio de contraseña de esa cuenta
    (`guardar` antes del arreglo, `cambiar_password` después)."""
    llego, seguir = asyncio.Event(), asyncio.Event()
    pendiente = [True]

    def parar(real):
        async def parado(self, usuario):
            if pendiente[0] and usuario.correo == correo and usuario.hash_de_password != usuario.hash_leido:
                pendiente[0] = False
                llego.set()
                async with asyncio.timeout(10):
                    await seguir.wait()
            return await real(self, usuario)
        return parado

    for metodo in ("guardar", "cambiar_password"):
        real = getattr(RepositorioDeUsuarios, metodo, None)
        if real is not None:
            monkeypatch.setattr(RepositorioDeUsuarios, metodo, parar(real))
    return llego, seguir


async def test_dos_cambios_de_contrasena_a_la_vez_no_se_pisan(
    nuevo_cliente, sesiones, cuenta, monkeypatch, request,
):
    """La víctima verifica y se para antes de escribir; el atacante cambia la
    contraseña entero. En HEAD la víctima también salía con 200, la generación
    subía una vez y la sesión del atacante sobrevivía. Ahora la víctima pierde
    con 409: el estado es el de un solo cambio, entero y auditado."""
    from carreras import generacion

    _con_club(request)
    user_id, correo = cuenta
    victima = await entrar(nuevo_cliente(), correo)
    atacante = await entrar(nuevo_cliente(), correo)
    version = await generacion(sesiones, user_id)

    llego, seguir = _parar_el_cambio(monkeypatch, correo)
    suyo = asyncio.create_task(nuevo_cliente().post(
        f"{API}/auth/me/password", headers=bearer(victima),
        json={"current_password": PASSWORD, "new_password": "la-de-la-victima"},
    ))
    async with asyncio.timeout(10):
        await llego.wait()
    del_atacante = await nuevo_cliente().post(
        f"{API}/auth/me/password", headers=bearer(atacante),
        json={"current_password": PASSWORD, "new_password": "la-del-atacante"},
    )
    seguir.set()
    rv = await suyo

    assert del_atacante.status_code == 200, del_atacante.text
    assert rv.status_code == 409, rv.text
    assert await generacion(sesiones, user_id) == version + 1
    entra = await nuevo_cliente().post(f"{API}/auth/login", json={"email": correo, "password": "la-del-atacante"})
    no_entra = await nuevo_cliente().post(f"{API}/auth/login", json={"email": correo, "password": "la-de-la-victima"})
    assert (entra.status_code, no_entra.status_code) == (200, 401)
    assert any("credenciales_cambiadas" in d for d in await eventos(correo, TipoDeEvento.PASSWORD_CAMBIADA))
