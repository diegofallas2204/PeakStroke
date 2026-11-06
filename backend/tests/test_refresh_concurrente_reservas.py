# ruff: noqa: F811 — las fixtures de `carreras` se importan y se piden por nombre
"""Carreras de un refresh contra otro gesto que gana mientras está parado.

1. Contra un **cambio de contraseña** (TODO-25, revisor vuelta 2): la contraseña
   sube la generación —y desde TODO-30 borra las sesiones—, así que esa cookie
   ya estaba muerta. Es un 401 simple, no un reuso: antes se revocaba otra vez,
   matando la sesión recién emitida a quien la cambió.
2. Contra un **logout** de la misma sesión (voz externa de TODO-30): la fila ya
   no existe. Releerla con `db.refresh` daba 500; ahora es un 401 simple.
3. Un **login** contra un cambio de contraseña (decisión D6 de TODO-30): el
   login leyó la generación vieja y abre su sesión después de que la
   contraseña borrara las filas. La fila queda, pero sus tokens no validan: la
   generación es la defensa, y borrar las filas es limpieza.

El 503 de `/me/password` de TODO-25 ya no existe: abrir una sesión no compite.
"""
from __future__ import annotations

import asyncio

import pytest
from carreras import (  # noqa: F401  (las fixtures se usan por nombre)
    COOKIE,
    auth_on,
    cuenta,
    entrar,
    eventos,
    generacion,
    nuevo_cliente,
    sesiones,
)
from conftest import API, PASSWORD

from app.core.auditoria import TipoDeEvento
from app.persistencia.repositorios import RepositorioDeSesionesAbiertas

NUEVA = "otra-contrasena-larga"


def _con_club(request) -> None:
    """`/me/password` pide `Principal`: a una cuenta sin club le responde 403."""
    if request.node.callspec.params["cuenta"] == "sin_club":
        pytest.skip("/me/password exige club (Principal); sin club es 403")


async def _reusos(correo: str) -> int:
    return len(await eventos(correo, TipoDeEvento.REFRESH_REUSADO))


def _parar_en(monkeypatch, metodo: str) -> tuple[asyncio.Event, asyncio.Event]:
    """Para la primera llamada a `RepositorioDeSesionesAbiertas.<metodo>` hasta
    que el test diga `seguir`; `llego` avisa de que ya leyó todo."""
    llego, seguir = asyncio.Event(), asyncio.Event()
    pendiente = [True]
    real = getattr(RepositorioDeSesionesAbiertas, metodo)

    async def parado(self, sesion):
        if pendiente[0]:
            pendiente[0] = False
            llego.set()
            async with asyncio.timeout(10):
                await seguir.wait()
        return await real(self, sesion)

    monkeypatch.setattr(RepositorioDeSesionesAbiertas, metodo, parado)
    return llego, seguir


async def _cambiar(nuevo_cliente, acceso: dict[str, str]):
    return await nuevo_cliente().post(
        f"{API}/auth/me/password", headers=acceso,
        json={"current_password": PASSWORD, "new_password": NUEVA},
    )


async def test_un_refresh_que_pierde_contra_un_cambio_de_contrasena_no_es_reuso(
    nuevo_cliente, sesiones, cuenta, monkeypatch, request,
):
    _con_club(request)
    user_id, correo = cuenta
    r = await entrar(nuevo_cliente(), correo)
    acceso = {"Authorization": f"Bearer {r.json()['access_token']}"}
    version = await generacion(sesiones, user_id)

    llego, seguir = _parar_en(monkeypatch, "rotar")
    refresco = asyncio.create_task(nuevo_cliente(r.cookies[COOKIE]).post(f"{API}/auth/refresh"))
    async with asyncio.timeout(10):
        await llego.wait()
    cambio = await _cambiar(nuevo_cliente, acceso)
    seguir.set()
    rr = await refresco

    assert cambio.status_code == 200, cambio.text
    assert rr.status_code == 401, rr.text
    assert await generacion(sesiones, user_id) == version + 1, (
        "se revocó otra vez: la sesión nueva de quien cambió la contraseña murió"
    )
    assert await _reusos(correo) == 0
    assert (await nuevo_cliente(cambio.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 200


async def test_un_refresh_que_pierde_contra_el_logout_de_su_sesion_no_es_reuso(
    nuevo_cliente, sesiones, cuenta, monkeypatch,
):
    _, correo = cuenta
    cookie = (await entrar(nuevo_cliente(), correo)).cookies[COOKIE]
    otro = await entrar(nuevo_cliente(), correo)

    llego, seguir = _parar_en(monkeypatch, "rotar")
    refresco = asyncio.create_task(nuevo_cliente(cookie).post(f"{API}/auth/refresh"))
    async with asyncio.timeout(10):
        await llego.wait()
    salir = await nuevo_cliente(cookie).post(f"{API}/auth/logout")
    seguir.set()
    rr = await refresco

    assert salir.status_code == 204
    assert rr.status_code == 401, rr.text
    assert await _reusos(correo) == 0
    assert (await nuevo_cliente(otro.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 200


async def test_un_login_a_la_vez_que_un_cambio_de_contrasena_no_abre_nada_que_valga(
    nuevo_cliente, sesiones, cuenta, monkeypatch, request,
):
    _con_club(request)
    _, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    acceso = {"Authorization": f"Bearer {portatil.json()['access_token']}"}

    llego, seguir = _parar_en(monkeypatch, "abrir")
    movil = asyncio.create_task(entrar(nuevo_cliente(), correo))
    async with asyncio.timeout(10):
        await llego.wait()
    cambio = await _cambiar(nuevo_cliente, acceso)   # su `abrir` ya no se para
    seguir.set()
    rm = await movil

    assert cambio.status_code == 200, cambio.text
    assert rm.status_code == 200, rm.text            # entró con la contraseña de antes
    tarde = {"Authorization": f"Bearer {rm.json()['access_token']}"}
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=tarde)).status_code == 401
    assert (await nuevo_cliente(rm.cookies[COOKIE]).post(f"{API}/auth/refresh")).status_code == 401
    assert (await nuevo_cliente(cambio.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 200
