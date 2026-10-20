"""TODO-25: dos `/auth/refresh` a la vez con la misma cookie.

La rotación era leer-comparar-escribir en Python: las dos peticiones leían la
misma rotación, las dos pasaban `refresh_gastado` y las dos escribían la
siguiente. Quien copiara la cookie y la usara en el mismo instante que la
víctima recibía un par válido, y el robo no se detectaba.

Ahora la rotación se gasta con un `UPDATE ... WHERE refresh_rotation = :leida`:
la que llega segunda no encuentra la suya (0 filas) y es el reuso de siempre.
Login también rota, y dos logins a la vez **no** son un robo: reintentan.

Las fixtures (una sesión por petición, cuentas con y sin club, los dos motores)
viven en `carreras.py`. La barrera de `a_la_vez` hace que las dos peticiones
hayan leído antes de que ninguna escriba, que es la ventana que en producción
depende de la suerte.

Corre contra SQLite siempre y contra PostgreSQL si `PEAKSTROKE_TEST_POSTGRES_URL`
apunta a una base **desechable** ya migrada (p. ej. `peakstroke_c9`), y cada
caso con una cuenta **sin club** y otra **con club**: la primera versión del
arreglo solo se probó sin club y el login que perdía la carrera daba 500 con
club (el `rollback` caducaba la pertenencia ya leída; lo vio el revisor). Las
cuentas se crean y se borran en cada test.

**Las carreras HTTP se pueden correr contra HEAD** (antes del arreglo): no
importan nada nuevo arriba —`RotacionPerdida` se importa dentro de los tests de
repositorio— y ahí salen 200 y 200, el rojo de TODO-25.
"""
# ruff: noqa: F811 — las fixtures de `carreras` se importan y se piden por nombre
from __future__ import annotations

import pytest
from carreras import (  # noqa: F401  (las fixtures se usan por nombre)
    COOKIE,
    a_la_vez,
    auth_on,
    columnas,
    cuenta,
    entrar,
    nuevo_cliente,
    rotacion_de,
    sesiones,
)
from conftest import API
from sqlalchemy import select

from app.core.auditoria import TipoDeEvento
from app.core.database import AsyncSessionLocal, engine
from app.persistencia.repositorios import RepositorioDeUsuarios
from app.persistencia.tablas.auditoria import EventoDeAuditoria

# ── La carrera ───────────────────────────────────────────────────────────────

async def test_dos_refresh_a_la_vez_uno_gana_y_el_otro_es_reuso(
    nuevo_cliente, sesiones, cuenta, monkeypatch,
):
    """**El de TODO-25.** En HEAD salían 200 y 200: dos pares válidos."""
    user_id, correo = cuenta
    r = await entrar(nuevo_cliente(), correo)
    assert r.status_code == 200, r.text
    cookie = r.cookies[COOKIE]
    version, rotacion = await columnas(sesiones, user_id)

    a, b = nuevo_cliente(cookie), nuevo_cliente(cookie)
    ra, rb = await a_la_vez(
        monkeypatch, a.post(f"{API}/auth/refresh"), b.post(f"{API}/auth/refresh"),
    )

    assert sorted([ra.status_code, rb.status_code]) == [200, 401], (ra.text, rb.text)
    assert await columnas(sesiones, user_id) == (version + 1, rotacion + 1), (
        "la que perdió no cortó las sesiones"
    )
    # El corte es para las dos partes: el par que ganó tampoco vale ya.
    ganador = ra if ra.status_code == 200 else rb
    assert (await nuevo_cliente(ganador.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 401
    acceso = {"Authorization": f"Bearer {ganador.json()['access_token']}"}
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=acceso)).status_code == 401


async def test_el_reuso_a_la_vez_queda_registrado(
    nuevo_cliente, sesiones, cuenta, monkeypatch,
):
    """`REFRESH_REUSADO` con un detalle que lo distingue del reuso de después.

    El registro lo escribe el middleware con la sesión de la app, que en los
    tests es SQLite: se lee de ahí también con PostgreSQL.
    """
    _, correo = cuenta
    cookie = (await entrar(nuevo_cliente(), correo)).cookies[COOKIE]
    a, b = nuevo_cliente(cookie), nuevo_cliente(cookie)
    await a_la_vez(monkeypatch, a.post(f"{API}/auth/refresh"), b.post(f"{API}/auth/refresh"))

    async with AsyncSessionLocal() as s:
        eventos = list((await s.execute(select(EventoDeAuditoria).where(
            EventoDeAuditoria.event_type == str(TipoDeEvento.REFRESH_REUSADO),
            EventoDeAuditoria.actor_email == correo,
        ))).scalars())
    await engine.dispose()
    assert [(e.outcome, "a la vez" in e.detail) for e in eventos] == [("fallo", True)]


async def test_dos_logins_a_la_vez_entran_los_dos(
    nuevo_cliente, sesiones, cuenta, monkeypatch,
):
    """Login también rota, y dos a la vez **no** son un robo: la que pierde la
    carrera relee y rota sobre la nueva, como dos logins seguidos."""
    user_id, correo = cuenta
    version, rotacion = await columnas(sesiones, user_id)

    ra, rb = await a_la_vez(
        monkeypatch, entrar(nuevo_cliente(), correo), entrar(nuevo_cliente(), correo),
    )

    assert (ra.status_code, rb.status_code) == (200, 200), (ra.text, rb.text)
    assert ra.json()["user"]["team_id"] == rb.json()["user"]["team_id"]
    assert await columnas(sesiones, user_id) == (version, rotacion + 2)
    assert sorted([rotacion_de(ra), rotacion_de(rb)]) == [rotacion + 1, rotacion + 2]
    ultima = ra if rotacion_de(ra) > rotacion_de(rb) else rb
    assert (await nuevo_cliente(ultima.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 200


# ── El repositorio ───────────────────────────────────────────────────────────

async def test_guardar_una_rotacion_ya_gastada_levanta_y_relee(sesiones, cuenta):
    """Sin HTTP: dos sesiones con la misma fila; la segunda en escribir pierde
    y se queda con la fila releída (la rotación de la que ganó).

    Nadie retiene las filas a propósito: la sesión las guarda con referencia
    débil y `guardar` puede encontrarse una releída que ya trae la rotación de
    la que ganó. La primera versión del arreglo comparaba contra la fila y aquí
    no levantaba."""
    from app.persistencia.repositorios.usuarios import RotacionPerdida

    user_id, _ = cuenta
    async with sesiones() as s1, sesiones() as s2:
        r1, r2 = RepositorioDeUsuarios(s1), RepositorioDeUsuarios(s2)
        u1, u2 = r1.entidad(await r1.por_id(user_id)), r2.entidad(await r2.por_id(user_id))
        u1.rotar_refresh()
        u2.rotar_refresh()
        await r1.guardar(u1)
        with pytest.raises(RotacionPerdida):
            await r2.guardar(u2)
        assert (await r2.por_id(user_id)).refresh_rotation == u1.rotacion_de_refresh


async def test_anotar_no_rota(sesiones, cuenta):
    """`anotar` lo confirma otro: una rotación perdida desharía su unidad entera."""
    user_id, _ = cuenta
    async with sesiones() as s:
        repo = RepositorioDeUsuarios(s)
        usuario = repo.entidad(await repo.por_id(user_id))
        usuario.rotar_refresh()
        with pytest.raises(ValueError, match="guardar"):
            await repo.anotar(usuario)


async def test_un_login_que_pierde_siempre_no_es_un_robo(
    nuevo_cliente, sesiones, cuenta, monkeypatch,
):
    """Si la rotación se pierde una y otra vez, 503 —inténtalo de nuevo—: ni 500
    ni sesiones cortadas."""
    from app.persistencia.repositorios.usuarios import RotacionPerdida

    user_id, correo = cuenta
    version, _ = await columnas(sesiones, user_id)
    real = RepositorioDeUsuarios.guardar

    async def perder(self, usuario):
        if usuario.roto_el_refresh():
            raise RotacionPerdida(usuario.id)
        return await real(self, usuario)

    monkeypatch.setattr(RepositorioDeUsuarios, "guardar", perder)
    r = await entrar(nuevo_cliente(), correo)
    assert r.status_code == 503, r.text
    assert COOKIE not in r.cookies
    assert (await columnas(sesiones, user_id))[0] == version
