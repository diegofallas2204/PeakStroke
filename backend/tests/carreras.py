"""Fixtures y ayudas para probar carreras entre peticiones (TODO-25).

Una sesión de base de datos **por petición** —no la compartida del harness, con
la que no hay dos lecturas que puedan correr—, cuentas con y sin club que se
crean y se borran en cada test, y SQLite siempre más PostgreSQL si
`PEAKSTROKE_TEST_POSTGRES_URL` apunta a una base **desechable** ya migrada (p.
ej. `peakstroke_c9`). Lo usan `test_refresh_concurrente.py` y
`test_refresh_concurrente_reservas.py`; los tests importan de aquí las fixtures.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable

import pytest
import pytest_asyncio
from conftest import API, PASSWORD
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1.auth import service as auth_service
from app.api.v1.auth.schemas import UserCreate
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, get_db
from app.core.security import decode_token
from app.main import app
from app.persistencia.repositorios import RepositorioDeEquipos, RepositorioDeUsuarios
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import User

_PG = os.environ.get("PEAKSTROKE_TEST_POSTGRES_URL")
COOKIE = settings.refresh_cookie_name


@pytest_asyncio.fixture(params=[
    "sqlite",
    pytest.param("postgresql", marks=pytest.mark.skipif(
        not _PG, reason="sin PEAKSTROKE_TEST_POSTGRES_URL",
    )),
])
async def sesiones(request) -> async_sessionmaker[AsyncSession]:
    if request.param == "sqlite":
        yield AsyncSessionLocal
        await engine.dispose()
        return
    motor = create_async_engine(_PG)
    yield async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    await motor.dispose()
    await engine.dispose()   # la auditoría escribe con el motor de la app (SQLite)


@pytest_asyncio.fixture(params=["sin_club", "con_club"])
async def cuenta(request, sesiones) -> tuple[int, str]:
    """Una cuenta sin club (entra igual: es el pool) o entrenador de un club
    propio, con un correo que no choca."""
    correo = f"todo25-{uuid.uuid4().hex[:10]}@test.dev"
    async with sesiones() as s:
        if request.param == "sin_club":
            user = await RepositorioDeUsuarios(s).crear(
                correo=correo, nombre="Carrera",
                password_hash=auth_service.hash_password(PASSWORD),
            )
            await s.commit()
        else:
            club = await RepositorioDeEquipos(s).crear(f"Club {correo}")
            user = await auth_service.create_user(
                s, UserCreate(email=correo, name="Carrera", password=PASSWORD, role="coach"),
                club.id,
            )
        user_id = user.id
    yield user_id, correo
    async with sesiones() as s:
        clubes = select(TeamMember.team_id).where(TeamMember.user_id == user_id)
        club_ids = list((await s.execute(clubes)).scalars())
        await s.execute(delete(TeamMember).where(TeamMember.user_id == user_id))
        await s.execute(delete(Team).where(Team.id.in_(club_ids)))
        await s.execute(delete(User).where(User.id == user_id))
        await s.commit()


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


@pytest_asyncio.fixture
async def nuevo_cliente(sesiones, auth_on):
    """Fábrica de clientes; cada petición abre **su** sesión, como en producción."""
    async def _get_db():
        async with sesiones() as s:
            yield s

    app.dependency_overrides[get_db] = _get_db
    abiertos: list[AsyncClient] = []

    def fabrica(cookie: str | None = None) -> AsyncClient:
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        if cookie is not None:
            c.cookies.set(COOKIE, cookie, path="/api/v1/auth")
        abiertos.append(c)
        return c

    yield fabrica
    for c in abiertos:
        await c.aclose()
    app.dependency_overrides.clear()


async def a_la_vez(monkeypatch, *peticiones: Awaitable):
    """Lanza las peticiones juntas y para cada una justo antes de gastar la
    rotación hasta que todas hayan llegado: todas leyeron la misma."""
    barrera = asyncio.Barrier(len(peticiones))
    esperan = [len(peticiones)]   # solo la primera rotación de cada una: el reintento no espera
    real = RepositorioDeUsuarios.guardar

    async def guardar(self, usuario):
        # Contra la fila, no contra `rotacion_leida`, para que corra también en
        # HEAD; aquí vale porque el endpoint retiene la fila de su `user`.
        fila = await self.db.get(User, usuario.id)
        if usuario.rotacion_de_refresh != fila.refresh_rotation and esperan[0]:
            esperan[0] -= 1
            async with asyncio.timeout(10):
                await barrera.wait()
        return await real(self, usuario)

    with monkeypatch.context() as m:
        m.setattr(RepositorioDeUsuarios, "guardar", guardar)
        return await asyncio.gather(*peticiones)


async def columnas(sesiones, user_id: int) -> tuple[int, int]:
    async with sesiones() as s:
        fila = (await s.execute(
            select(User.token_version, User.refresh_rotation).where(User.id == user_id),
        )).one()
    return fila.token_version, fila.refresh_rotation


async def entrar(cliente: AsyncClient, correo: str):
    return await cliente.post(f"{API}/auth/login", json={"email": correo, "password": PASSWORD})


def rotacion_de(respuesta) -> int:
    return decode_token(respuesta.cookies[COOKIE], "refresh").rotation
