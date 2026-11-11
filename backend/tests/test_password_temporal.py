"""TODO-27: una contraseña temporal obliga a cambiarse antes de usar la app.

Decidido por la persona el 2026-11-10. Quien da de alta a otro —el entrenador
que invita, el operador que restablece— ve la contraseña temporal. Hasta ahora
valía para siempre. Lo que fija este archivo:

- las cuatro puertas que emiten una temporal marcan la cuenta (alta de miembro
  sin contraseña, invitación, `ops.py` al crear y al restablecer), y una
  contraseña elegida por quien da el alta no la marca;
- con la marca, todo lo que pide `Principal` responde 403 **salvo** cambiar la
  contraseña; `/auth/me` sigue respondiendo y lo dice (`must_change_password`);
- cambiarla quita la marca y la sesión nueva ya entra;
- con el login apagado no se exige nada (el conmutador de desarrollo suplanta
  cuentas sin saber su contraseña).
"""
from __future__ import annotations

import io

import pytest
from conftest import API, PASSWORD, World
from sqlalchemy import select

from app.core.config import settings
from app.persistencia.tablas.usuarios import User
from tools.operaciones import Consola, ejecutar

NUEVA = "la-que-yo-elijo-99"


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


async def _marcada(db, correo: str) -> bool:
    db.expire_all()
    return (await db.execute(
        select(User.password_temporal).where(User.email == correo),
    )).scalar_one()


async def _entrar(client, correo: str, password: str) -> dict[str, str]:
    r = await client.post(f"{API}/auth/login", json={"email": correo, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _alta_con_temporal(client, correo: str = "nuevo@test.dev") -> str:
    """Un entrenador dado de alta sin contraseña: el backend genera la temporal."""
    r = await client.post(
        f"{API}/auth/members", json={"email": correo, "name": "Nuevo Coach", "role": "coach"},
    )
    assert r.status_code == 201, r.text
    return r.json()["temporary_password"]


# --- Quién queda marcado --------------------------------------------------------

async def test_el_alta_sin_contrasena_marca_la_cuenta(client, db, world: World):
    await _alta_con_temporal(client)
    assert await _marcada(db, "nuevo@test.dev") is True


async def test_el_alta_con_contrasena_elegida_no_la_marca(client, db, world: World):
    r = await client.post(f"{API}/auth/members", json={
        "email": "elegida@test.dev", "name": "Con Clave", "role": "coach", "password": NUEVA,
    })
    assert r.status_code == 201
    assert await _marcada(db, "elegida@test.dev") is False


async def test_la_invitacion_marca_la_cuenta_que_crea(client, db, world: World):
    r = await client.post(
        f"{API}/link-codes/invite", json={"email": "invitada@test.dev", "name": "Ana Invitada"},
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["temporary_password"]
    assert await _marcada(db, "invitada@test.dev") is True


async def test_el_cli_marca_al_restablecer_y_al_crear_con_temporal(db, world: World):
    def consola(entrada: str = "") -> Consola:
        return Consola(entrada=io.StringIO(entrada), salida=io.StringIO(),
                       errores=io.StringIO(), terminal=False)

    assert await _marcada(db, world.sofia_email) is False
    assert await ejecutar(
        ("restablecer-password", "--correo", world.sofia_email),
        consola(world.sofia_email + "\n"), db,
    ) == 0
    assert await _marcada(db, world.sofia_email) is True

    assert await ejecutar(
        ("crear-cuenta", "--correo", "porcli@test.dev", "--nombre", "Por Cli", "--rol", "coach"),
        consola(), db,
    ) == 0
    assert await _marcada(db, "porcli@test.dev") is True


# --- Qué puede hacer mientras tanto ----------------------------------------------

async def test_con_la_temporal_solo_se_puede_cambiar_la_contrasena(
    client, db, world: World, auth_on,
):
    temporal = await _alta_con_temporal_con_login(client, world)
    cabeceras = await _entrar(client, "nuevo@test.dev", temporal)

    yo = await client.get(f"{API}/auth/me", headers=cabeceras)
    assert (yo.status_code, yo.json()["must_change_password"]) == (200, True)

    for metodo, ruta in [("get", "/swimmers/"), ("get", "/plans/"), ("get", "/teams/mine"),
                         ("get", "/dashboard/summary"), ("get", "/auth/members")]:
        r = await getattr(client, metodo)(f"{API}{ruta}", headers=cabeceras)
        assert r.status_code == 403, ruta
        assert "contraseña" in r.json()["detail"], ruta

    cambio = await client.post(
        f"{API}/auth/me/password", headers=cabeceras,
        json={"current_password": temporal, "new_password": NUEVA},
    )
    assert cambio.status_code == 200, cambio.text
    assert cambio.json()["user"]["must_change_password"] is False
    assert await _marcada(db, "nuevo@test.dev") is False

    nuevas = {"Authorization": f"Bearer {cambio.json()['access_token']}"}
    assert (await client.get(f"{API}/swimmers/", headers=nuevas)).status_code == 200
    # Y la temporal ya no abre nada.
    r = await client.post(f"{API}/auth/login", json={"email": "nuevo@test.dev", "password": temporal})
    assert r.status_code == 401


async def test_cambiar_la_temporal_por_ella_misma_no_la_libera(
    client, db, world: World, auth_on,
):
    temporal = await _alta_con_temporal_con_login(client, world)
    cabeceras = await _entrar(client, "nuevo@test.dev", temporal)
    r = await client.post(
        f"{API}/auth/me/password", headers=cabeceras,
        json={"current_password": temporal, "new_password": temporal},
    )
    assert r.status_code == 400
    assert await _marcada(db, "nuevo@test.dev") is True


async def _alta_con_temporal_con_login(client, world: World) -> str:
    """Con el login encendido, el alta la hace el dueño con su sesión."""
    dueno = await _entrar(client, world.owner_email, PASSWORD)
    r = await client.post(
        f"{API}/auth/members", headers=dueno,
        json={"email": "nuevo@test.dev", "name": "Nuevo Coach", "role": "coach"},
    )
    assert r.status_code == 201, r.text
    return r.json()["temporary_password"]


async def test_quien_no_tiene_temporal_no_nota_nada(client, world: World, auth_on):
    cabeceras = await _entrar(client, world.owner_email, PASSWORD)
    assert (await client.get(f"{API}/auth/me", headers=cabeceras)).json()["must_change_password"] is False
    assert (await client.get(f"{API}/swimmers/", headers=cabeceras)).status_code == 200


async def test_con_el_login_apagado_no_se_exige(client, db, world: World):
    """El conmutador de desarrollo suplanta sin contraseña: exigirle cambiar una
    que no conoce dejaría la cuenta inservible para revisar su interfaz."""
    from conftest import como

    await _alta_con_temporal(client)
    assert await _marcada(db, "nuevo@test.dev") is True
    r = await client.get(f"{API}/swimmers/", headers=como("nuevo@test.dev"))
    assert r.status_code == 200
