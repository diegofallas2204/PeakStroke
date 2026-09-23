"""El vínculo cuenta ↔ ficha solo se crea si las dos partes actúan.

Lo que estos tests fijan no es el endpoint sino la propiedad: **nadie liga a
nadie por su cuenta**. Antes el entrenador elegía un nombre de un desplegable y
ya estaba; ahora hacen falta un código emitido y un canje, y cada una de las
formas de saltarse la segunda mitad tiene su test aquí.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import API, World, como
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.codigos import LinkCode
from app.persistencia.tablas.equipos import TeamMember
from app.persistencia.tablas.usuarios import User

pytestmark = pytest.mark.asyncio

CODES = f"{API}/link-codes"


async def _emitir(client: AsyncClient, swimmer_id: int, email: str) -> dict:
    r = await client.post(CODES + "/", json={"swimmer_id": swimmer_id}, headers=como(email))
    assert r.status_code == 201, r.text
    return r.json()


# --- Emitir ------------------------------------------------------------------

async def test_el_entrenador_emite_un_codigo_para_una_ficha_sin_cuenta(
    client: AsyncClient, world: World,
):
    data = await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email)
    assert data["swimmer_name"] == "Nadador Sin Cuenta"
    # Con guion: es lo que se dicta por teléfono.
    assert len(data["code"]) == 9 and data["code"][4] == "-"


async def test_no_se_emite_codigo_para_una_ficha_que_ya_tiene_cuenta(
    client: AsyncClient, world: World,
):
    r = await client.post(
        CODES + "/", json={"swimmer_id": world.sofia_swimmer_id},
        headers=como(world.owner_email),
    )
    assert r.status_code == 409


async def test_un_atleta_no_puede_emitir_codigos(client: AsyncClient, world: World):
    r = await client.post(
        CODES + "/", json={"swimmer_id": world.sin_cuenta_swimmer_id},
        headers=como(world.sofia_email),
    )
    assert r.status_code == 403


async def test_emitir_de_nuevo_revoca_el_anterior(
    client: AsyncClient, world: World,
):
    """El código que "se perdió" tiene que dejar de servir, no convivir con el nuevo."""
    viejo = await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email)
    nuevo = await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email)
    assert viejo["code"] != nuevo["code"]

    vivos = (await client.get(CODES + "/", headers=como(world.owner_email))).json()
    assert [c["code"] for c in vivos] == [nuevo["code"]]

    r = await client.post(
        CODES + "/redeem", json={"code": viejo["code"]}, headers=como(world.huerfano_email),
    )
    assert r.status_code == 400


# --- Canjear -----------------------------------------------------------------

async def test_el_canje_liga_la_ficha_a_quien_lo_canjea(
    client: AsyncClient, db: AsyncSession, world: World,
):
    code = (await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email))["code"]

    r = await client.post(
        CODES + "/redeem", json={"code": code}, headers=como(world.huerfano_email),
    )
    assert r.status_code == 200, r.text
    assert r.json()["swimmer_name"] == "Nadador Sin Cuenta"

    # La sesión del atleta ya reporta su ficha: es lo que activa todo el scoping.
    me = (await client.get(f"{API}/auth/me", headers=como(world.huerfano_email))).json()
    assert me["swimmer_id"] == world.sin_cuenta_swimmer_id

    swimmer = await db.get(Swimmer, world.sin_cuenta_swimmer_id)
    await db.refresh(swimmer)
    assert swimmer.user_id is not None


async def test_un_codigo_solo_se_canjea_una_vez(client: AsyncClient, world: World):
    code = (await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email))["code"]
    primero = await client.post(
        CODES + "/redeem", json={"code": code}, headers=como(world.huerfano_email),
    )
    assert primero.status_code == 200

    segundo = await client.post(
        CODES + "/redeem", json={"code": code}, headers=como(world.carlos_email),
    )
    assert segundo.status_code == 400


async def test_un_codigo_caducado_no_sirve(
    client: AsyncClient, db: AsyncSession, world: World,
):
    code = (await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email))["code"]
    fila = (await db.execute(select(LinkCode))).scalar_one()
    fila.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()

    r = await client.post(
        CODES + "/redeem", json={"code": code}, headers=como(world.huerfano_email),
    )
    assert r.status_code == 400


async def test_un_codigo_revocado_no_sirve(client: AsyncClient, world: World):
    emitido = await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email)
    borrado = await client.delete(f"{CODES}/{emitido['id']}", headers=como(world.owner_email))
    assert borrado.status_code == 204

    r = await client.post(
        CODES + "/redeem", json={"code": emitido["code"]}, headers=como(world.huerfano_email),
    )
    assert r.status_code == 400


async def test_un_codigo_inventado_no_dice_que_no_existe(
    client: AsyncClient, world: World,
):
    """Mismo 400 y mismo texto que un código caducado: sondearlos no informa."""
    r = await client.post(
        CODES + "/redeem", json={"code": "ZZZZ-9999"}, headers=como(world.huerfano_email),
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Código inválido o caducado"


async def test_quien_ya_tiene_ficha_no_puede_canjear_otra(
    client: AsyncClient, world: World,
):
    code = (await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email))["code"]
    r = await client.post(
        CODES + "/redeem", json={"code": code}, headers=como(world.sofia_email),
    )
    assert r.status_code == 409


async def test_un_entrenador_no_puede_ligarse_a_una_ficha(
    client: AsyncClient, world: World,
):
    code = (await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email))["code"]
    r = await client.post(
        CODES + "/redeem", json={"code": code}, headers=como(world.assistant_email),
    )
    assert r.status_code == 409


async def test_una_cuenta_sin_equipo_entra_al_club_al_canjear(
    client: AsyncClient, db: AsyncSession, world: World,
):
    """El caso que justifica el pool global de nadadores.

    La persona ya tiene cuenta pero no es de ningún club, así que para el
    entrenador es como si no existiera. El código es su única puerta de entrada,
    y `POST /link-codes/redeem` es el único endpoint que no exige pertenencia.
    """
    suelto = User(
        email="suelto@test.dev", name="Nadador Del Pool",
        password_hash=hash_password("peakstroke-test"),
    )
    db.add(suelto)
    await db.commit()

    code = (await _emitir(client, world.sin_cuenta_swimmer_id, world.owner_email))["code"]
    r = await client.post(
        CODES + "/redeem", json={"code": code}, headers=como("suelto@test.dev"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["team_name"] == "Club de Prueba"

    membership = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == suelto.id)
    )).scalar_one()
    assert (membership.team_id, membership.role) == (world.team_id, "athlete")

    # Y a partir de aquí la ve el entrenador, que es lo que "ligar al equipo"
    # significa desde fuera.
    lista = (await client.get(f"{API}/swimmers/", headers=como(world.owner_email))).json()
    ficha = next(s for s in lista if s["id"] == world.sin_cuenta_swimmer_id)
    assert ficha["user_email"] == "suelto@test.dev"


# --- La frontera de siempre --------------------------------------------------

async def test_no_se_emite_codigo_para_una_ficha_de_otro_equipo(
    client: AsyncClient, db: AsyncSession, world: World,
):
    """404 y no 403: un 403 confirmaría que esa ficha existe en algún sitio."""
    from app.api.v1.auth.schemas import UserCreate
    from app.api.v1.auth.service import create_user
    from app.core.principal import Principal
    from app.persistencia.repositorios import (
        RepositorioDeAtletas,
        RepositorioDeEquipos,
    )

    equipos = RepositorioDeEquipos(db)
    otro = await equipos.crear("Otro Club")
    ajeno = await create_user(db, UserCreate(
        email="ajeno@test.dev", name="Entrenador Ajeno",
        password="peakstroke-test", role="coach",
    ), otro.id)
    otro.owner_id = ajeno.id
    await db.commit()
    ficha_ajena = await RepositorioDeAtletas(db, Principal(
        user=ajeno, membership=await equipos.pertenencia(ajeno.id), is_owner=True,
    )).crear(team_id=otro.id, nombre="Nadador Ajeno")

    r = await client.post(
        CODES + "/", json={"swimmer_id": ficha_ajena.id}, headers=como(world.owner_email),
    )
    assert r.status_code == 404

    # Y al revés: el código del otro club no aparece en la lista de este.
    await _emitir(client, ficha_ajena.id, "ajeno@test.dev")
    mios = (await client.get(CODES + "/", headers=como(world.owner_email))).json()
    assert mios == []
