"""Alta de atletas por correo y solicitudes de ingreso vistas por el atleta.

Ficha deportiva y cuenta eran dos altas separadas —dos formularios, dos listas,
dos momentos— para una sola persona. Aquí se fija el gesto único: el entrenador
escribe el correo con el que el atleta se registra en el sistema, y lo que sale
es la ficha, la cuenta si no la tenía, y el código que la persona tiene que
teclear para confirmar que es ella.

Las dos propiedades que estos tests protegen:

  1. **Invitar no mete a nadie en el club.** La cuenta nueva nace sin
     pertenencia; la crea el canje. Si invitar bastara, el código sería adorno.
  2. **Un código dirigido solo lo canjea su destinatario.** Tenerlo en la mano
     ya no alcanza: además hay que ser esa persona.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.link_codes.models import LinkCode
from app.modules.swimmers.models import Swimmer
from app.modules.teams.models import TeamMember

from conftest import API, World, como

pytestmark = pytest.mark.asyncio

CODES = f"{API}/link-codes"
NUEVO = "nueva.atleta@test.dev"


async def _invitar(client: AsyncClient, email: str, como_quien: str, **extra) -> dict:
    payload = {"email": email, "name": "Atleta Nueva"}
    payload.update(extra)
    return await client.post(
        CODES + "/invite", json=payload, headers=como(como_quien),
    )


# --- Invitar -----------------------------------------------------------------

async def test_invitar_crea_ficha_cuenta_y_codigo(
    client: AsyncClient, world: World, db: AsyncSession,
):
    r = await _invitar(client, NUEVO, world.owner_email)
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["account_created"] is True
    assert body["temporary_password"]
    assert body["link_code"]["invited_email"] == NUEVO
    assert body["link_code"]["swimmer_name"] == "Atleta Nueva"

    ficha = (await db.execute(
        select(Swimmer).where(Swimmer.name == "Atleta Nueva")
    )).scalar_one()
    assert ficha.team_id == world.team_id
    assert ficha.user_id is None       # todavía nadie ha confirmado nada


async def test_invitar_no_mete_a_nadie_en_el_equipo(
    client: AsyncClient, world: World, db: AsyncSession,
):
    """La cuenta nace en el pool global, sin club. La pertenencia la crea el canje."""
    await _invitar(client, NUEVO, world.owner_email)
    user = (await db.execute(select(User).where(User.email == NUEVO))).scalar_one()
    pertenencia = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )).scalar_one_or_none()
    assert pertenencia is None


async def test_el_correo_se_normaliza(client: AsyncClient, world: World, db: AsyncSession):
    r = await _invitar(client, "  MAYUSCULAS@Test.Dev  ", world.owner_email)
    assert r.status_code == 201
    assert r.json()["link_code"]["invited_email"] == "mayusculas@test.dev"


async def test_invitar_a_quien_ya_tiene_cuenta_no_crea_otra(
    client: AsyncClient, world: World, db: AsyncSession,
):
    """El caso del pool: la persona ya se registró, solo le falta el club."""
    await _invitar(client, NUEVO, world.owner_email)
    r = await _invitar(client, NUEVO, world.owner_email)
    assert r.status_code == 201
    assert r.json()["account_created"] is False
    assert r.json()["temporary_password"] is None

    cuentas = (await db.execute(select(User).where(User.email == NUEVO))).scalars().all()
    assert len(cuentas) == 1


async def test_reinvitar_no_duplica_la_ficha(
    client: AsyncClient, world: World, db: AsyncSession,
):
    """Reenviar la invitación reemite el código; no clona al atleta."""
    primero = (await _invitar(client, NUEVO, world.owner_email)).json()
    segundo = (await _invitar(client, NUEVO, world.owner_email)).json()
    assert segundo["link_code"]["swimmer_id"] == primero["link_code"]["swimmer_id"]
    assert segundo["link_code"]["code"] != primero["link_code"]["code"]

    fichas = (await db.execute(
        select(Swimmer).where(Swimmer.name == "Atleta Nueva")
    )).scalars().all()
    assert len(fichas) == 1


async def test_un_atleta_no_puede_invitar(client: AsyncClient, world: World):
    r = await _invitar(client, NUEVO, world.sofia_email)
    assert r.status_code == 403


async def test_no_se_invita_a_una_cuenta_ya_ligada(client: AsyncClient, world: World):
    r = await _invitar(client, world.sofia_email, world.owner_email)
    assert r.status_code == 409


async def test_no_se_invita_a_un_entrenador_del_equipo(client: AsyncClient, world: World):
    r = await _invitar(client, world.assistant_email, world.owner_email)
    assert r.status_code == 409


async def test_una_invitacion_rechazada_no_deja_ficha_huerfana(
    client: AsyncClient, world: World, db: AsyncSession,
):
    """La comprobación va antes de crear nada."""
    antes = len((await db.execute(select(Swimmer))).scalars().all())
    await _invitar(client, world.assistant_email, world.owner_email)
    despues = len((await db.execute(select(Swimmer))).scalars().all())
    assert antes == despues


# --- Solicitudes, desde el lado del atleta -----------------------------------

async def test_el_invitado_ve_su_solicitud(client: AsyncClient, world: World):
    await _invitar(client, NUEVO, world.owner_email)
    r = await client.get(CODES + "/mine", headers=como(NUEVO))
    assert r.status_code == 200
    solicitudes = r.json()
    assert len(solicitudes) == 1
    assert solicitudes[0]["team_name"] == "Club de Prueba"
    assert solicitudes[0]["swimmer_name"] == "Atleta Nueva"
    assert solicitudes[0]["invited_by"] == "Entrenadora Dueña"


async def test_la_solicitud_nunca_lleva_el_codigo(client: AsyncClient, world: World):
    """El código lo dicta el entrenador: es la prueba de identidad."""
    creado = (await _invitar(client, NUEVO, world.owner_email)).json()
    cuerpo = (await client.get(CODES + "/mine", headers=como(NUEVO))).text
    assert creado["link_code"]["code"] not in cuerpo
    assert "code" not in (await client.get(
        CODES + "/mine", headers=como(NUEVO),
    )).json()[0]


async def test_nadie_ve_las_solicitudes_de_otro(client: AsyncClient, world: World):
    await _invitar(client, NUEVO, world.owner_email)
    r = await client.get(CODES + "/mine", headers=como(world.huerfano_email))
    assert r.json() == []


async def test_un_codigo_sin_destinatario_no_aparece_como_solicitud(
    client: AsyncClient, world: World,
):
    """Emitir sobre una ficha suelta no va dirigido a nadie."""
    await client.post(
        CODES + "/", json={"swimmer_id": world.sin_cuenta_swimmer_id},
        headers=como(world.owner_email),
    )
    r = await client.get(CODES + "/mine", headers=como(world.huerfano_email))
    assert r.json() == []


async def test_canjear_vacia_la_lista_de_solicitudes(client: AsyncClient, world: World):
    creado = (await _invitar(client, NUEVO, world.owner_email)).json()
    r = await client.post(
        CODES + "/redeem", json={"code": creado["link_code"]["code"]},
        headers=como(NUEVO),
    )
    assert r.status_code == 200, r.text
    assert (await client.get(CODES + "/mine", headers=como(NUEVO))).json() == []


# --- El código dirigido es de quien es ---------------------------------------

async def test_otro_usuario_no_puede_canjear_un_codigo_dirigido(
    client: AsyncClient, world: World,
):
    """Tener el código ya no basta: además hay que ser esa persona."""
    creado = (await _invitar(client, NUEVO, world.owner_email)).json()
    r = await client.post(
        CODES + "/redeem", json={"code": creado["link_code"]["code"]},
        headers=como(world.huerfano_email),
    )
    assert r.status_code == 400
    # Mismo mensaje que un código inexistente: distinguirlos permitiría sondear.
    assert r.json()["detail"] == "Código inválido o caducado"


async def test_el_destinatario_entra_al_equipo_al_canjear(
    client: AsyncClient, world: World, db: AsyncSession,
):
    creado = (await _invitar(client, NUEVO, world.owner_email)).json()
    await client.post(
        CODES + "/redeem", json={"code": creado["link_code"]["code"]},
        headers=como(NUEVO),
    )
    user = (await db.execute(select(User).where(User.email == NUEVO))).scalar_one()
    pertenencia = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )).scalar_one()
    assert pertenencia.team_id == world.team_id
    assert pertenencia.role == "athlete"

    ficha = (await db.execute(
        select(Swimmer).where(Swimmer.id == creado["link_code"]["swimmer_id"])
    )).scalar_one()
    assert ficha.user_id == user.id


async def test_reinvitar_revoca_el_codigo_anterior(
    client: AsyncClient, world: World, db: AsyncSession,
):
    primero = (await _invitar(client, NUEVO, world.owner_email)).json()
    await _invitar(client, NUEVO, world.owner_email)
    viejo = (await db.execute(
        select(LinkCode).where(LinkCode.id == primero["link_code"]["id"])
    )).scalar_one()
    assert viejo.revoked_at is not None


# --- La cuenta sin club es un estado legítimo --------------------------------

async def test_la_cuenta_sin_equipo_puede_ver_su_perfil(client: AsyncClient, world: World):
    """Sin esto, el invitado recibiría 403 y no podría ni llegar al canje."""
    await _invitar(client, NUEVO, world.owner_email)
    r = await client.get(f"{API}/auth/me", headers=como(NUEVO))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == NUEVO
    assert body["role"] is None
    assert body["team_id"] is None


async def test_la_cuenta_sin_equipo_no_ve_datos_de_ningun_equipo(
    client: AsyncClient, world: World,
):
    """Puede entrar, pero solo a su perfil: sin `Principal` no hay frontera."""
    await _invitar(client, NUEVO, world.owner_email)
    for ruta in ("/swimmers/", "/plans/", "/aerobic-tests/"):
        r = await client.get(API + ruta, headers=como(NUEVO))
        assert r.status_code == 403, ruta


async def test_al_canjear_el_perfil_ya_tiene_equipo_y_rol(
    client: AsyncClient, world: World,
):
    creado = (await _invitar(client, NUEVO, world.owner_email)).json()
    await client.post(
        CODES + "/redeem", json={"code": creado["link_code"]["code"]},
        headers=como(NUEVO),
    )
    body = (await client.get(f"{API}/auth/me", headers=como(NUEVO))).json()
    assert body["role"] == "athlete"
    assert body["team_id"] == world.team_id
    assert body["swimmer_name"] == "Atleta Nueva"
