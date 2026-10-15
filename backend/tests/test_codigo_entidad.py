"""C9 (REDISENO §5.13): el ciclo de vida del código de vinculación es de la entidad.

Hasta el 2026-10-14 eran tres columnas que cada sitio comprobaba a mano:
`sigue_vivo` en el repositorio, `revoked_at = ahora` en el service y en el
repositorio, y `used_at`/`used_by` en el canje, con la cadena de `elif` de quién
puede canjear en `api/v1/codigos/service.redeem`. Lo que fija este archivo:

- `es_servible`, `es_para`, `canjear` y `revocar` (idempotente);
- `admite`, **en el orden de siempre**: otro club, entrenador, revocado. R5.3
  queda como decisión: invertirlo trataría «revocado» como «sin club»;
- fuera del mapeo nadie asigna `used_at`, `used_by` ni `revoked_at` (AST).

El comportamiento de cara al API lo fijan `test_link_codes.py` y
`test_invitaciones.py`, que no cambian.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import API, World, como
from escrituras_ast import escrituras
from sqlalchemy import select, update

from app.core.security import hash_password
from app.dominio.entidades import CanjeImposible, CodigoDeVinculacion, Pertenencia
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import User

AHORA = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)


def _codigo(**cambios) -> CodigoDeVinculacion:
    base = {"equipo_id": 1, "ficha_id": 3, "emitido_por": 1, "codigo": "ABCD2345", "ahora": AHORA}
    return CodigoDeVinculacion.emitir(**(base | cambios))


def _p(equipo_id: int = 1, rol: str = "athlete", activa: bool = True) -> Pertenencia:
    return Pertenencia(usuario_id=9, equipo_id=equipo_id, rol=rol, activa=activa, id=9)


def test_emitir_caduca_a_las_72_horas():
    c = _codigo()
    assert c.caduca == AHORA + timedelta(hours=72)
    assert c.es_servible(AHORA + timedelta(hours=71, minutes=59))
    assert not c.es_servible(AHORA + timedelta(hours=72))


def test_una_fecha_sin_zona_se_lee_como_utc():
    """SQLite devuelve `expires_at` sin zona: compararlo no revienta."""
    c = _codigo()
    c.caduca = c.caduca.replace(tzinfo=None)
    assert c.es_servible(AHORA) and not c.es_servible(AHORA + timedelta(days=4))


def test_un_codigo_dirigido_solo_es_de_su_destinatario():
    assert _codigo().es_para("cualquiera@x.dev")
    dirigido = _codigo(correo_invitado="ana@x.dev")
    assert dirigido.es_para("ana@x.dev") and not dirigido.es_para("otra@x.dev")


def test_canjear_lo_gasta_una_sola_vez():
    c = _codigo()
    c.canjear(9, AHORA)
    assert (c.usado_en, c.usado_por) == (AHORA, 9)
    assert not c.es_servible(AHORA)
    with pytest.raises(CanjeImposible, match="inválido o caducado"):
        c.canjear(10, AHORA)
    assert c.usado_por == 9


def test_no_se_canjea_uno_revocado_ni_uno_caducado():
    revocado = _codigo()
    assert revocado.revocar(AHORA) is True
    with pytest.raises(CanjeImposible):
        revocado.canjear(9, AHORA)
    with pytest.raises(CanjeImposible):
        _codigo().canjear(9, AHORA + timedelta(days=3, seconds=1))


def test_revocar_es_idempotente_y_conserva_la_primera_fecha():
    c = _codigo()
    assert c.revocar(AHORA) is True
    assert c.revocar(AHORA + timedelta(hours=1)) is False
    assert c.revocado_en == AHORA


def test_sin_club_entra_y_hay_que_crear_la_pertenencia():
    assert _codigo().admite(None) is True


def test_un_atleta_activo_del_mismo_club_entra_sin_crear_nada():
    assert _codigo().admite(_p()) is False


@pytest.mark.parametrize(("pertenencia", "mensaje"), [
    (_p(equipo_id=2), "otro equipo"),
    (_p(rol="coach"), "entrenador"),
    (_p(activa=False), "revocado"),
    # El orden de siempre: el club se mira antes que el acceso. Una cuenta
    # revocada en OTRO club no es una cuenta del pool (R5.3 queda como decisión).
    (_p(equipo_id=2, activa=False), "otro equipo"),
    (_p(equipo_id=2, rol="coach", activa=False), "otro equipo"),
    (_p(rol="coach", activa=False), "entrenador"),
])
def test_lo_que_no_admite_y_en_que_orden(pertenencia, mensaje):
    with pytest.raises(CanjeImposible, match=mensaje):
        _codigo().admite(pertenencia)



@pytest.mark.parametrize("campo", ["usado_en", "usado_por", "revocado_en"])
def test_el_ciclo_de_vida_no_se_asigna_a_mano(campo):
    c = _codigo()
    with pytest.raises(AttributeError, match="solo cambia por sus métodos"):
        setattr(c, campo, AHORA)
    assert c.es_servible(AHORA)


# ── Nadie más escribe el ciclo de vida ───────────────────────────────────────



def test_fuera_del_mapeo_nadie_gasta_ni_revoca_un_codigo():
    assert escrituras(
        {"used_at", "used_by", "revoked_at"},
        {"app/persistencia/mapeo/identidad.py"},
    ) == []


# ── Por el API: las ramas de `admite` que solo se veían en el dominio ────────
#
# Lo señaló el revisor del bloque: por HTTP solo pasaba la rama «entrenador».
# Las dos de abajo son las de R5.3: una cuenta de OTRO club y una revocada en
# ESTE. Las dos con un código vivo y sin ficha ligada, que es el camino real por
# el que se llega aquí (una cuenta de atleta dada de alta por `POST
# /auth/members` no tiene ficha, y un access token emitido antes de revocar
# sigue valiendo hasta que caduca).

_CODES = f"{API}/link-codes"


async def _codigo_del_club(client, world: World) -> str:
    r = await client.post(_CODES + "/", json={"swimmer_id": world.sin_cuenta_swimmer_id},
                          headers=como(world.owner_email))
    assert r.status_code == 201, r.text
    return r.json()["code"]


async def test_una_cuenta_de_otro_club_no_entra_por_un_codigo(client, db, world: World):
    otro = Team(name="Otro Club")
    db.add(otro)
    cuenta = User(email="de-otro@test.dev", name="De Otro Club", password_hash=hash_password("x" * 12))
    db.add(cuenta)
    await db.flush()
    db.add(TeamMember(team_id=otro.id, user_id=cuenta.id, role="athlete"))
    await db.commit()

    r = await client.post(_CODES + "/redeem", json={"code": await _codigo_del_club(client, world)},
                          headers=como("de-otro@test.dev"))
    assert r.status_code == 409 and r.json()["detail"] == "Tu cuenta ya pertenece a otro equipo"


async def test_una_cuenta_revocada_en_este_club_no_vuelve_por_un_codigo(client, db, world: World):
    """«Revocado ≠ sin equipo»: un código no deshace la revocación."""
    huerfano = (await db.execute(select(User.id).where(User.email == world.huerfano_email))).scalar_one()
    await db.execute(update(TeamMember).where(TeamMember.user_id == huerfano).values(is_active=False))
    await db.commit()

    r = await client.post(_CODES + "/redeem", json={"code": await _codigo_del_club(client, world)},
                          headers=como(world.huerfano_email))
    assert r.status_code == 409 and r.json()["detail"] == "Tu acceso a este equipo está revocado"
    activa = (await db.execute(select(TeamMember.is_active).where(TeamMember.user_id == huerfano))).scalar_one()
    assert activa is False
