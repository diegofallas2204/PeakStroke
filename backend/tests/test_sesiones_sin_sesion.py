# ruff: noqa: F811 — las fixtures de `carreras` se importan y se piden por nombre
"""TODO-30: un token firmado no basta, tiene que ser de una sesión viva.

Desde que cada login abre una fila de `sesiones_abiertas` (ver
`test_sesiones_por_dispositivo.py`), el access y el refresh llevan su `sid`, y
`get_current_user` y `/auth/refresh` miran que la sesión exista, sea **de esa
cuenta** y no haya caducado. Y quien no vuelve a entrar no deja filas: cada
login purga las caducadas de todas las cuentas.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from carreras import (  # noqa: F401  (las fixtures se usan por nombre)
    COOKIE,
    abiertas,
    auth_on,
    bearer,
    cuenta,
    entrar,
    eventos,
    nuevo_cliente,
    sesiones,
)
from conftest import API
from sqlalchemy import delete

from app.core.auditoria import TipoDeEvento
from app.core.config import settings
from app.persistencia.repositorios import RepositorioDeUsuarios
from app.persistencia.tablas.usuarios import User


async def _refrescar(nuevo_cliente, cookie: str):
    return await nuevo_cliente(cookie).post(f"{API}/auth/refresh")


async def _filas(sesiones, user_id: int) -> int:
    return len(await abiertas(sesiones, user_id))


def _forjar(tipo: str, user_id: int, **extra) -> str:
    ahora = datetime.now(UTC)
    payload = {"sub": str(user_id), "type": tipo, "ver": 0, "iat": ahora,
               "exp": ahora + timedelta(minutes=10), **extra}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ── Tokens que no corresponden a ninguna sesión ──────────────────────────────

async def test_un_token_sin_sid_no_vale(nuevo_cliente, sesiones, cuenta):
    """En HEAD los dos valían: un token no decía de qué sesión era."""
    user_id, _ = cuenta
    acceso = {"Authorization": f"Bearer {_forjar('access', user_id)}"}
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=acceso)).status_code == 401
    refresco = _forjar("refresh", user_id, rot=0)
    assert (await _refrescar(nuevo_cliente, refresco)).status_code == 401


async def test_el_sid_de_otra_cuenta_no_vale(nuevo_cliente, sesiones, cuenta):
    """Firmado y vivo, pero la sesión es de otra persona: 401, y esa sigue intacta."""
    _, correo = cuenta
    ajena = await entrar(nuevo_cliente(), correo)
    sid = jwt.decode(ajena.cookies[COOKIE], options={"verify_signature": False})["sid"]
    async with sesiones() as s:
        otro = await RepositorioDeUsuarios(s).crear(
            correo=f"otro-{correo}", nombre="Otro", password_hash="x",
        )
        await s.commit()
        otro_id = otro.id
    try:
        acceso = {"Authorization": f"Bearer {_forjar('access', otro_id, sid=sid)}"}
        assert (await nuevo_cliente().get(f"{API}/auth/me", headers=acceso)).status_code == 401
        refresco = _forjar("refresh", otro_id, sid=sid, rot=0)
        assert (await _refrescar(nuevo_cliente, refresco)).status_code == 401
        assert (await _refrescar(nuevo_cliente, ajena.cookies[COOKIE])).status_code == 200
    finally:
        async with sesiones() as s:
            await s.execute(delete(User).where(User.id == otro_id))
            await s.commit()


async def test_una_sesion_caducada_no_vale_aunque_el_token_si(nuevo_cliente, sesiones, cuenta):
    user_id, correo = cuenta
    r = await entrar(nuevo_cliente(), correo)
    from sqlalchemy import update

    from app.persistencia.tablas.usuarios import OpenSession

    async with sesiones() as s:
        await s.execute(update(OpenSession).where(OpenSession.user_id == user_id).values(
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        ))
        await s.commit()
    assert (await _refrescar(nuevo_cliente, r.cookies[COOKIE])).status_code == 401
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=bearer(r))).status_code == 401
    assert await eventos(correo, TipoDeEvento.REFRESH_REUSADO) == []


async def test_entrar_purga_las_caducadas_de_todas_las_cuentas(nuevo_cliente, sesiones, cuenta):
    """Quien no vuelve a entrar no deja filas para siempre (decidido el 2026-10-20)."""
    from app.persistencia.tablas.usuarios import OpenSession

    user_id, correo = cuenta
    viva = await entrar(nuevo_cliente(), correo)
    async with sesiones() as s:
        otro = await RepositorioDeUsuarios(s).crear(
            correo=f"purga-{correo}", nombre="Purga", password_hash="x",
        )
        await s.commit()
        otro_id = otro.id
        ayer = datetime.now(UTC) - timedelta(days=1)
        s.add(OpenSession(id="caducada-de-otra", user_id=otro_id, created_at=ayer, expires_at=ayer))
        await s.commit()
    try:
        await entrar(nuevo_cliente(), correo)
        assert await _filas(sesiones, otro_id) == 0
        assert await _filas(sesiones, user_id) == 2
        assert (await _refrescar(nuevo_cliente, viva.cookies[COOKIE])).status_code == 200
    finally:
        async with sesiones() as s:
            await s.execute(delete(User).where(User.id == otro_id))
            await s.commit()
