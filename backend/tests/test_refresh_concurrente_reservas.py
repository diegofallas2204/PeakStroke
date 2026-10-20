# ruff: noqa: F811 — las fixtures de `carreras` se importan y se piden por nombre
"""TODO-25, lo que dejó la segunda vuelta del revisor (2026-10-18).

1. Un refresh que pierde la rotación contra un **cambio de contraseña** no es un
   reuso: la contraseña subió la generación y esa cookie ya estaba muerta. Antes
   se revocaba otra vez —matando la sesión recién emitida a quien la cambió— y
   el registro anotaba un `REFRESH_REUSADO` falso.
2. `guardar` no rota con cambios pendientes en la sesión: al perder la rotación
   confirma la transacción vacía, y lo pendiente se confirmaría con ella.
3. Si `/me/password` no puede abrir la sesión nueva, el 503 dice que la
   contraseña **ya** cambió, no «inténtalo de nuevo».
"""
from __future__ import annotations

import asyncio

import pytest
from carreras import (  # noqa: F401  (las fixtures se usan por nombre)
    COOKIE,
    auth_on,
    columnas,
    cuenta,
    entrar,
    nuevo_cliente,
    sesiones,
)
from conftest import API, PASSWORD
from sqlalchemy import select

from app.core.auditoria import TipoDeEvento
from app.core.database import AsyncSessionLocal, engine
from app.persistencia.repositorios import RepositorioDeUsuarios
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.usuarios import User

NUEVA = "otra-contrasena-larga"


def _con_club(request) -> None:
    """`/me/password` pide `Principal`: a una cuenta sin club le responde 403."""
    if request.node.callspec.params["cuenta"] == "sin_club":
        pytest.skip("/me/password exige club (Principal); sin club es 403")


async def _reusos(correo: str) -> int:
    """`REFRESH_REUSADO` de esa cuenta. Los escribe el middleware con el motor de
    la app, que en los tests es SQLite, también cuando la carrera es en PostgreSQL."""
    async with AsyncSessionLocal() as s:
        eventos = (await s.execute(select(EventoDeAuditoria).where(
            EventoDeAuditoria.event_type == str(TipoDeEvento.REFRESH_REUSADO),
            EventoDeAuditoria.actor_email == correo,
        ))).scalars().all()
    await engine.dispose()
    return len(eventos)


async def test_un_refresh_que_pierde_contra_un_cambio_de_contrasena_no_es_reuso(
    nuevo_cliente, sesiones, cuenta, monkeypatch, request,
):
    """El refresh lee, se para justo antes de gastar la rotación, la contraseña
    cambia entera (generación +1, rotación +1) y el refresh sigue: pierde."""
    _con_club(request)
    user_id, correo = cuenta
    r = await entrar(nuevo_cliente(), correo)
    cookie, acceso = r.cookies[COOKIE], r.json()["access_token"]
    version, _ = await columnas(sesiones, user_id)

    llego, seguir = asyncio.Event(), asyncio.Event()
    pendiente = [True]   # solo se para la primera rotación: la del refresh
    real = RepositorioDeUsuarios.guardar

    async def guardar(self, usuario):
        if usuario.roto_el_refresh() and pendiente[0]:
            pendiente[0] = False
            llego.set()
            async with asyncio.timeout(10):
                await seguir.wait()
        return await real(self, usuario)

    monkeypatch.setattr(RepositorioDeUsuarios, "guardar", guardar)
    refresco = asyncio.create_task(nuevo_cliente(cookie).post(f"{API}/auth/refresh"))
    async with asyncio.timeout(10):
        await llego.wait()
    cambio = await nuevo_cliente().post(
        f"{API}/auth/me/password",
        json={"current_password": PASSWORD, "new_password": NUEVA},
        headers={"Authorization": f"Bearer {acceso}"},
    )
    seguir.set()
    rr = await refresco

    assert cambio.status_code == 200, cambio.text
    assert rr.status_code == 401, rr.text
    assert (await columnas(sesiones, user_id))[0] == version + 1, (
        "se revocó otra vez: la sesión nueva de quien cambió la contraseña murió"
    )
    assert await _reusos(correo) == 0
    assert (await nuevo_cliente(cambio.cookies[COOKIE]).post(
        f"{API}/auth/refresh")).status_code == 200


async def test_guardar_no_rota_con_cambios_pendientes(sesiones, cuenta):
    user_id, _ = cuenta
    async with sesiones() as s:
        repo = RepositorioDeUsuarios(s)
        fila = await repo.por_id(user_id)
        usuario = repo.entidad(fila)
        usuario.rotar_refresh()
        fila.name = "Pendiente"            # algo sin confirmar en la misma sesión
        with pytest.raises(ValueError, match="pendiente"):
            await repo.guardar(usuario)
        await s.rollback()
    async with sesiones() as s:
        nombre, rotacion = (await s.execute(
            select(User.name, User.refresh_rotation).where(User.id == user_id),
        )).one()
    assert (nombre, rotacion) == ("Carrera", usuario.rotacion_leida)


async def test_el_503_del_cambio_de_contrasena_dice_que_ya_cambio(
    nuevo_cliente, sesiones, cuenta, monkeypatch, request,
):
    from app.persistencia.repositorios.usuarios import RotacionPerdida

    _con_club(request)
    _, correo = cuenta
    acceso = (await entrar(nuevo_cliente(), correo)).json()["access_token"]
    real = RepositorioDeUsuarios.guardar

    async def perder(self, usuario):
        if usuario.roto_el_refresh():
            raise RotacionPerdida(usuario.id)
        return await real(self, usuario)

    with monkeypatch.context() as m:
        m.setattr(RepositorioDeUsuarios, "guardar", perder)
        r = await nuevo_cliente().post(
            f"{API}/auth/me/password",
            json={"current_password": PASSWORD, "new_password": NUEVA},
            headers={"Authorization": f"Bearer {acceso}"},
        )
    assert r.status_code == 503, r.text
    assert "ya cambió" in r.json()["detail"]
    nueva = await nuevo_cliente().post(
        f"{API}/auth/login", json={"email": correo, "password": NUEVA},
    )
    assert nueva.status_code == 200, nueva.text
