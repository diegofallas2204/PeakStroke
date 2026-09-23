"""El conmutador de identidad de desarrollo (`X-PeakStroke-Dev-User`).

Una cabecera que dice "trátame como esta persona" es, literalmente, el agujero
que la autenticación existe para cerrar. Aquí está permitida porque solo se lee
con el login apagado — y ese "solo" es una condición en una línea de
`core/dependencies.py` que nadie va a echar de menos leyendo un diff.

El test de la línea 4 es el que importa. Si alguien la borra optimizando
imports, refactorizando la dependencia o "simplificando" el `if`, el API pasa a
aceptar suplantación arbitraria **con el login puesto** y todo lo demás sigue
en verde.
"""
from __future__ import annotations

import pytest
from conftest import API, World, como

from app.core.config import settings
from app.core.dev_identity import DEV_USER_HEADER
from app.persistencia.tablas.equipos import TeamMember


async def test_la_cabecera_cambia_a_quien_se_atribuye_la_peticion(client, world: World):
    """Sin cabecera manda `dev_user_email`; con ella, quien se pida."""
    por_defecto = await client.get(f"{API}/auth/me")
    assert por_defecto.json()["email"] == settings.dev_user_email

    suplantada = await client.get(f"{API}/auth/me", headers=como(world.sofia_email))
    assert suplantada.status_code == 200
    assert suplantada.json()["email"] == world.sofia_email
    assert suplantada.json()["role"] == "athlete"


async def test_un_email_inexistente_cae_al_por_defecto_sin_romper(client, world: World):
    """Una errata en el conmutador no puede tumbar la aplicación.

    Devolver 500 —o 404— convertiría un dedazo escribiendo un email en una
    pantalla en blanco sin pista de por qué.
    """
    r = await client.get(f"{API}/auth/me", headers=como("nadie@peakstroke.dev"))
    assert r.status_code == 200
    assert r.json()["email"] == settings.dev_user_email


async def test_una_cuenta_inactiva_cae_al_por_defecto(client, db, world: World):
    """Suplantar a alguien con el acceso revocado tiene que ser imposible.

    Si se dejara pasar, el conmutador serviría para inspeccionar exactamente lo
    que la revocación pretendía cerrar.
    """
    from sqlalchemy import select

    from app.persistencia.tablas.usuarios import User

    user = (await db.execute(
        select(User).where(User.email == world.carlos_email)
    )).scalar_one()
    user.is_active = False
    await db.commit()

    r = await client.get(f"{API}/auth/me", headers=como(world.carlos_email))
    assert r.status_code == 200
    assert r.json()["email"] == settings.dev_user_email


async def test_con_auth_encendida_la_cabecera_se_ignora(client, world: World, monkeypatch):
    """**El test crítico.** Con login real, la cabecera no vale nada.

    Se comprueba con la forma más fuerte de la afirmación: una petición que
    lleva SOLO la cabecera y ningún token tiene que ser rechazada. Si en algún
    momento devuelve 200, cualquiera con curl es quien quiera ser.
    """
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    assert settings.dev_identity_enabled is False

    r = await client.get(f"{API}/auth/me", headers=como(world.owner_email))
    assert r.status_code == 401

    # Y tampoco sirve para escribir, no solo para leer.
    escritura = await client.patch(
        f"{API}/plans/{world.plan_id}", json={"name": "secuestrado"},
        headers=como(world.owner_email),
    )
    assert escritura.status_code == 401


@pytest.mark.parametrize("entorno", ["production", "PROD"])
async def test_en_produccion_la_cabecera_se_ignora(client, world: World, monkeypatch, entorno):
    """Segunda condición de `dev_identity_enabled`, la que parece redundante.

    `_check_production` solo corre al construir Settings. Si algo muta
    `auth_enabled` en caliente, esta es la única barrera que queda en pie.
    """
    monkeypatch.setattr(settings, "environment", entorno, raising=False)
    assert settings.dev_identity_enabled is False

    r = await client.get(f"{API}/auth/me", headers=como(world.sofia_email))
    assert r.json()["email"] == settings.dev_user_email


# --- GET /auth/dev-identities (T7) -------------------------------------------

async def test_dev_identities_lista_el_equipo_con_su_rol(client, world: World):
    r = await client.get(f"{API}/auth/dev-identities")
    assert r.status_code == 200
    por_email = {i["email"]: i for i in r.json()}

    assert set(por_email) == {
        world.owner_email, world.assistant_email,
        world.sofia_email, world.carlos_email, world.huerfano_email,
    }
    assert por_email[world.owner_email]["is_owner"] is True
    assert por_email[world.assistant_email]["is_owner"] is False
    assert por_email[world.sofia_email]["swimmer_name"] == "Sofía Test"
    # El atleta sin ficha aparece igual: es un caso que hay que poder ver.
    assert por_email[world.huerfano_email]["swimmer_name"] is None


async def test_dev_identities_no_ofrece_cuentas_revocadas(client, db, world: World):
    """Ofrecer una identidad que `_dev_user` va a rechazar es ofrecer un botón roto."""
    from sqlalchemy import select

    from app.persistencia.tablas.usuarios import User

    carlos = (await db.execute(
        select(User).where(User.email == world.carlos_email)
    )).scalar_one()
    membership = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == carlos.id)
    )).scalar_one()
    membership.is_active = False
    await db.commit()

    emails = {i["email"] for i in (await client.get(f"{API}/auth/dev-identities")).json()}
    assert world.carlos_email not in emails


async def test_dev_identities_no_existe_con_auth_encendida(client, world: World, monkeypatch):
    """404 y no 403: con login real este endpoint no existe, no es que esté vetado."""
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    r = await client.get(f"{API}/auth/dev-identities")
    assert r.status_code == 404


async def test_la_cabecera_se_llama_como_dice_el_contrato(client, world: World):
    """El frontend manda este nombre exacto; cambiarlo rompe el conmutador entero."""
    assert DEV_USER_HEADER == "X-PeakStroke-Dev-User"
    r = await client.get(f"{API}/auth/me", headers={DEV_USER_HEADER: world.sofia_email})
    assert r.json()["email"] == world.sofia_email
