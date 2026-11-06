"""TODO-25 y TODO-30: peticiones a la vez sobre la rotación del refresh.

TODO-25: la rotación era leer-comparar-escribir en Python, y dos `/auth/refresh`
a la vez con la misma cookie pasaban los dos. Ahora se gasta con un `UPDATE ...
WHERE refresh_rotation = :leida`, y la que llega segunda es el reuso.

TODO-30: la rotación era **una por cuenta**, así que un login en otro
dispositivo a la vez que un refresh también lo convertía en reuso. Desde el
2026-10-20 cada login abre su sesión: el CAS es de esa sesión, el reuso corta
esa y los logins no compiten con nada.

Las fixtures (una sesión de base de datos por petición, cuentas con y sin club,
los dos motores) viven en `carreras.py`. La barrera de `a_la_vez` para cada
petición justo antes de escribir su sesión, que es la ventana que en producción
depende de la suerte.

Corre contra SQLite siempre y contra PostgreSQL si `PEAKSTROKE_TEST_POSTGRES_URL`
apunta a una base **desechable** ya migrada (p. ej. `peakstroke_c9`), y cada
caso con una cuenta **sin club** y otra **con club**: la primera versión de
TODO-25 solo se probó sin club y el login que perdía daba 500 con club.
"""
# ruff: noqa: F811 — las fixtures de `carreras` se importan y se piden por nombre
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from carreras import (  # noqa: F401  (las fixtures se usan por nombre)
    COOKIE,
    a_la_vez,
    abiertas,
    auth_on,
    bearer,
    cuenta,
    entrar,
    eventos,
    generacion,
    nuevo_cliente,
    sesiones,
    sid_de,
)
from conftest import API

from app.core.auditoria import TipoDeEvento
from app.persistencia.repositorios import RepositorioDeSesionesAbiertas
from app.persistencia.repositorios.sesiones_abiertas import RotacionPerdida


async def _reusos(correo: str) -> list[str]:
    return await eventos(correo, TipoDeEvento.REFRESH_REUSADO)


# ── Dos refresh de la misma sesión ───────────────────────────────────────────

async def test_dos_refresh_a_la_vez_uno_gana_y_el_otro_es_reuso_de_esa_sesion(
    nuevo_cliente, sesiones, cuenta, monkeypatch,
):
    """**El de TODO-25**, acotado a la sesión desde TODO-30: se cierra esa, la
    generación no sube y el otro dispositivo sigue dentro."""
    user_id, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    movil = await entrar(nuevo_cliente(), correo)
    version = await generacion(sesiones, user_id)

    cookie = portatil.cookies[COOKIE]
    ra, rb = await a_la_vez(
        monkeypatch,
        nuevo_cliente(cookie).post(f"{API}/auth/refresh"),
        nuevo_cliente(cookie).post(f"{API}/auth/refresh"),
    )

    assert sorted([ra.status_code, rb.status_code]) == [200, 401], (ra.text, rb.text)
    assert await generacion(sesiones, user_id) == version
    assert set(await abiertas(sesiones, user_id)) == {sid_de(movil)}
    # El corte es para las dos partes de esa sesión: el par que ganó tampoco vale.
    ganador = ra if ra.status_code == 200 else rb
    assert (await nuevo_cliente(ganador.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 401
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=bearer(ganador))).status_code == 401
    assert (await nuevo_cliente(movil.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 200


async def test_el_reuso_a_la_vez_queda_registrado(nuevo_cliente, sesiones, cuenta, monkeypatch):
    """`REFRESH_REUSADO` con un detalle que lo distingue del reuso de después."""
    _, correo = cuenta
    cookie = (await entrar(nuevo_cliente(), correo)).cookies[COOKIE]
    await a_la_vez(
        monkeypatch,
        nuevo_cliente(cookie).post(f"{API}/auth/refresh"),
        nuevo_cliente(cookie).post(f"{API}/auth/refresh"),
    )
    reusos = await _reusos(correo)
    assert len(reusos) == 1 and "a la vez" in reusos[0], reusos


# ── Logins: ya no compiten con nada ──────────────────────────────────────────

async def test_un_login_en_otro_dispositivo_a_la_vez_que_un_refresh_no_es_reuso(
    nuevo_cliente, sesiones, cuenta, monkeypatch,
):
    """**El de TODO-30.** Con la rotación por cuenta el login la gastaba y el
    refresh, que perdía, se cortaba como robo."""
    _, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)

    refresco, movil = await a_la_vez(
        monkeypatch,
        nuevo_cliente(portatil.cookies[COOKIE]).post(f"{API}/auth/refresh"),
        entrar(nuevo_cliente(), correo),
    )

    assert (refresco.status_code, movil.status_code) == (200, 200), (refresco.text, movil.text)
    for sesion in (refresco, movil):
        r = await nuevo_cliente(sesion.cookies[COOKIE]).post(f"{API}/auth/refresh")
        assert r.status_code == 200, r.text
    assert await _reusos(correo) == []


async def test_dos_logins_a_la_vez_abren_dos_sesiones(nuevo_cliente, sesiones, cuenta, monkeypatch):
    """Ni reintentos ni 503 (TODO-25): abrir es un `INSERT` con un id aleatorio."""
    user_id, correo = cuenta
    version = await generacion(sesiones, user_id)

    ra, rb = await a_la_vez(
        monkeypatch, entrar(nuevo_cliente(), correo), entrar(nuevo_cliente(), correo),
    )

    assert (ra.status_code, rb.status_code) == (200, 200), (ra.text, rb.text)
    assert ra.json()["user"]["team_id"] == rb.json()["user"]["team_id"]
    assert await generacion(sesiones, user_id) == version
    assert await abiertas(sesiones, user_id) == {sid_de(ra): 0, sid_de(rb): 0}
    for r in (ra, rb):
        assert (await nuevo_cliente(r.cookies[COOKIE]).post(
            f"{API}/auth/refresh")).status_code == 200


# ── El repositorio ───────────────────────────────────────────────────────────

async def test_rotar_una_rotacion_ya_gastada_levanta_y_se_relee_la_ganadora(
    nuevo_cliente, sesiones, cuenta,
):
    """Sin HTTP: dos sesiones de base de datos con la misma sesión abierta; la
    segunda en escribir pierde. Nadie retiene las filas a propósito: el CAS
    compara contra `rotacion_leida`, no contra una fila releída."""
    user_id, correo = cuenta
    sid = sid_de(await entrar(nuevo_cliente(), correo))
    ahora = datetime.now(UTC)
    async with sesiones() as s1, sesiones() as s2:
        r1, r2 = RepositorioDeSesionesAbiertas(s1), RepositorioDeSesionesAbiertas(s2)
        a, b = await r1.de(sid, user_id), await r2.de(sid, user_id)
        a.rotar(ahora, timedelta(days=30))
        b.rotar(ahora, timedelta(days=30))
        await r1.rotar(a)
        with pytest.raises(RotacionPerdida):
            await r2.rotar(b)
        assert (await r2.de(sid, user_id)).rotacion == a.rotacion == 1


async def test_rotar_una_sesion_borrada_a_la_vez_levanta_y_releer_da_none(
    nuevo_cliente, sesiones, cuenta,
):
    """La voz externa de TODO-30: releer con `db.refresh` una fila borrada daba
    500; `de` es un `select` y devuelve None."""
    user_id, correo = cuenta
    sid = sid_de(await entrar(nuevo_cliente(), correo))
    ahora = datetime.now(UTC)
    async with sesiones() as s1, sesiones() as s2:
        r1, r2 = RepositorioDeSesionesAbiertas(s1), RepositorioDeSesionesAbiertas(s2)
        sesion = await r1.de(sid, user_id)
        assert await r2.cerrar(sid, user_id)
        sesion.rotar(ahora, timedelta(days=30))
        with pytest.raises(RotacionPerdida):
            await r1.rotar(sesion)
        assert await r1.de(sid, user_id) is None


async def test_rotar_no_escribe_con_cambios_pendientes(nuevo_cliente, sesiones, cuenta):
    """Al perder se confirma la transacción vacía: lo pendiente se confirmaría con ella."""
    from app.persistencia.tablas.usuarios import User

    user_id, correo = cuenta
    sid = sid_de(await entrar(nuevo_cliente(), correo))
    ahora = datetime.now(UTC)
    async with sesiones() as s:
        repo = RepositorioDeSesionesAbiertas(s)
        sesion = await repo.de(sid, user_id)
        sesion.rotar(ahora, timedelta(days=30))
        (await s.get(User, user_id)).name = "Pendiente"
        with pytest.raises(ValueError, match="pendiente"):
            await repo.rotar(sesion)
        await s.rollback()
    assert await abiertas(sesiones, user_id) == {sid: 0}
