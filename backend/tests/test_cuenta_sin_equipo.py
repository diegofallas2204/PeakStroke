"""La cuenta sin club entra; la cuenta revocada NO.

Desde el 2026-08-10 una cuenta puede existir sin pertenecer a ningún equipo: es
el atleta que se registró y espera invitación, y tiene que poder entrar para
llegar a sus solicitudes de ingreso. Antes el login exigía pertenencia, así que
el invitado se quedaba fuera de la única pantalla que le habría servido.

**Ese permiso abre una puerta que hay que volver a cerrar a mano.** «Sin
pertenencia» y «pertenencia revocada» se parecen mucho —`get_membership` filtra
`is_active` y devuelve `None` en los dos casos— y confundirlos convierte
"revocar el acceso" en "te bajamos de rango": la persona a la que el entrenador
le quitó el acceso seguiría entrando, ahora como cuenta del pool, y podría
canjear un código para volver a meterse en un club.

Los dos casos van juntos en este archivo a propósito: son la misma línea de
código y el segundo es el precio del primero.
"""
from __future__ import annotations

import pytest
from conftest import API, PASSWORD, World, como
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.teams.models import TeamMember

POOL_EMAIL = "delpool@test.dev"


@pytest.fixture
def auth_on(monkeypatch):
    """Login real encendido: es el único modo en el que hay login que probar."""
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


async def _crear_cuenta_del_pool(db: AsyncSession) -> User:
    """Una cuenta sin pertenencia: existe en el sistema y no está en ningún club."""
    user = User(
        email=POOL_EMAIL, name="Cuenta Del Pool",
        password_hash=hash_password(PASSWORD),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestLaCuentaSinClubEntra:
    async def test_login_sin_pertenencia(self, client, world: World, db, auth_on):
        await _crear_cuenta_del_pool(db)
        r = await client.post(
            f"{API}/auth/login", json={"email": POOL_EMAIL, "password": PASSWORD},
        )
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] is None
        assert r.json()["user"]["team_id"] is None

    async def test_y_puede_ver_su_perfil(self, client, world: World, db, auth_on):
        await _crear_cuenta_del_pool(db)
        token = (await client.post(
            f"{API}/auth/login", json={"email": POOL_EMAIL, "password": PASSWORD},
        )).json()["access_token"]
        r = await client.get(
            f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["email"] == POOL_EMAIL

    async def test_pero_no_llega_a_ningun_dato_de_equipo(
        self, client, world: World, db, auth_on,
    ):
        await _crear_cuenta_del_pool(db)
        token = (await client.post(
            f"{API}/auth/login", json={"email": POOL_EMAIL, "password": PASSWORD},
        )).json()["access_token"]
        cabeceras = {"Authorization": f"Bearer {token}"}
        for ruta in ("/swimmers/", "/plans/", "/aerobic-tests/", "/auth/members"):
            r = await client.get(API + ruta, headers=cabeceras)
            assert r.status_code == 403, ruta


class TestLaCuentaRevocadaNO:
    """El precio del permiso de arriba, cobrado aquí."""

    async def _revocar(self, db: AsyncSession, email: str) -> None:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        membership = (await db.execute(
            select(TeamMember).where(TeamMember.user_id == user.id)
        )).scalar_one()
        membership.is_active = False
        await db.commit()

    async def test_a_quien_le_revocaron_el_acceso_no_entra(
        self, client, world: World, db, auth_on,
    ):
        """Revocado ≠ sin club. Confundirlos deja entrar a quien echaste."""
        await self._revocar(db, world.sofia_email)
        r = await client.post(
            f"{API}/auth/login",
            json={"email": world.sofia_email, "password": PASSWORD},
        )
        assert r.status_code == 401

    async def test_ni_renueva_la_sesion_que_ya_tenia(
        self, client, world: World, db, auth_on,
    ):
        """Revocar mientras la sesión está viva corta en el siguiente refresh."""
        assert (await client.post(
            f"{API}/auth/login",
            json={"email": world.sofia_email, "password": PASSWORD},
        )).status_code == 200

        await self._revocar(db, world.sofia_email)
        assert (await client.post(f"{API}/auth/refresh")).status_code == 401

    async def test_ni_se_presenta_como_cuenta_del_pool(
        self, client, world: World, db,
    ):
        """403, no `role: null`. Revocado y sin club son estados distintos.

        Sin login (modo desarrollo) la cabecera de identidad llega igual a
        `/auth/me`, así que la distinción hay que hacerla ahí y no solo en el
        login: si no, la interfaz le pintaría a quien echaste la pantalla de
        "elige tu equipo".
        """
        await self._revocar(db, world.sofia_email)
        r = await client.get(f"{API}/auth/me", headers=como(world.sofia_email))
        assert r.status_code == 403
