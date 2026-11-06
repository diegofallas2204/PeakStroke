"""Fixtures y ayudas para probar carreras entre peticiones (TODO-25, TODO-30).

Una sesión de base de datos **por petición** —no la compartida del harness, con
la que no hay dos lecturas que puedan correr—, cuentas con y sin club que se
crean y se borran en cada test, y SQLite siempre más PostgreSQL si
`PEAKSTROKE_TEST_POSTGRES_URL` apunta a una base **desechable** ya migrada (p.
ej. `peakstroke_c9`). Lo usan `test_refresh_concurrente.py`,
`test_refresh_concurrente_reservas.py` y `test_sesiones_por_dispositivo.py`; los
tests importan de aquí las fixtures.
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
from app.core.auditoria import TipoDeEvento
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine, get_db
from app.core.security import decode_token
from app.main import app
from app.persistencia.repositorios import (
    RepositorioDeEquipos,
    RepositorioDeSesionesAbiertas,
    RepositorioDeUsuarios,
)
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import OpenSession, User

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
        await s.execute(delete(OpenSession).where(OpenSession.user_id == user_id))
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
    """Lanza las peticiones juntas y para cada una justo antes de escribir su
    sesión —gastar la rotación (refresh) o abrir una (login)— hasta que todas
    hayan llegado: todas leyeron antes de que ninguna escriba.

    Hasta TODO-30 la barrera estaba en `RepositorioDeUsuarios.guardar` y solo
    paraba si la rotación de la cuenta cambiaba; con la rotación por sesión el
    login ya no rota, y ahí un login y un refresh no se habrían encontrado.
    """
    barrera = asyncio.Barrier(len(peticiones))
    esperan = [len(peticiones)]

    def parar(real):
        async def envoltorio(self, sesion):
            if esperan[0]:
                esperan[0] -= 1
                async with asyncio.timeout(10):
                    await barrera.wait()
            return await real(self, sesion)
        return envoltorio

    with monkeypatch.context() as m:
        for metodo in ("rotar", "abrir"):
            real = getattr(RepositorioDeSesionesAbiertas, metodo)
            m.setattr(RepositorioDeSesionesAbiertas, metodo, parar(real))
        return await asyncio.gather(*peticiones)


async def generacion(sesiones, user_id: int) -> int:
    async with sesiones() as s:
        return (await s.execute(
            select(User.token_version).where(User.id == user_id),
        )).scalar_one()


async def abiertas(sesiones, user_id: int) -> dict[str, int]:
    """sid → rotación de las sesiones abiertas de esa cuenta."""
    async with sesiones() as s:
        filas = (await s.execute(
            select(OpenSession.id, OpenSession.refresh_rotation)
            .where(OpenSession.user_id == user_id),
        )).all()
    return dict(filas)


async def entrar(cliente: AsyncClient, correo: str):
    return await cliente.post(f"{API}/auth/login", json={"email": correo, "password": PASSWORD})


def rotacion_de(respuesta) -> int:
    return decode_token(respuesta.cookies[COOKIE], "refresh").rotation


def sid_de(respuesta) -> str:
    return decode_token(respuesta.cookies[COOKIE], "refresh").sid


def bearer(respuesta) -> dict[str, str]:
    return {"Authorization": f"Bearer {respuesta.json()['access_token']}"}


async def eventos(correo: str, tipo: TipoDeEvento) -> list[str]:
    """Detalles de los eventos de esa cuenta. El middleware los escribe con el
    motor de la app, que en los tests es SQLite, también cuando la carrera es en
    PostgreSQL."""
    async with AsyncSessionLocal() as s:
        detalles = list((await s.execute(select(EventoDeAuditoria.detail).where(
            EventoDeAuditoria.event_type == str(tipo),
            EventoDeAuditoria.actor_email == correo,
        ))).scalars())
    await engine.dispose()
    return detalles
