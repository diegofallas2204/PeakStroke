"""D1: los comandos de acceso del CLI (`tools/ops.py`), contra la base de pruebas.

Cada comando que escribe, cuatro veces: lo que hace, lo que audita (tipo,
actor `os:` y objetivo), que `--dry-run` no escribe ni audita, y que si lo
escrito para confirmar no es el nombre del recurso no cambia nada. Y el caso que
motivó «liberar» (TODO-26): un atleta echado de un club entra en otro.
"""
from __future__ import annotations

import io

import pytest
from conftest import API, PASSWORD, World, como
from sqlalchemy import select

from app.core.config import settings
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.equipos import TeamMember
from app.persistencia.tablas.usuarios import User
from tools.operaciones import Consola, ejecutar


def _consola(entrada: str = "") -> Consola:
    return Consola(entrada=io.StringIO(entrada), salida=io.StringIO(),
                   errores=io.StringIO(), terminal=False)


async def _ops(db, *argv: str, entrada: str = "") -> tuple[int, Consola]:
    consola = _consola(entrada)
    return await ejecutar(argv, consola, db), consola


async def _eventos(db, tipo: str) -> list[EventoDeAuditoria]:
    return list((await db.execute(
        select(EventoDeAuditoria).where(EventoDeAuditoria.event_type == tipo),
    )).scalars())


async def _fila(db, correo: str) -> tuple[int, int, TeamMember | None]:
    """(id, token_version, pertenencia) leídos de la base, no de la sesión."""
    db.expire_all()
    uid, version = (await db.execute(
        select(User.id, User.token_version).where(User.email == correo),
    )).one()
    miembro = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == uid),
    )).scalar_one_or_none()
    return uid, version, miembro


def _es_del_operador(evento: EventoDeAuditoria, objetivo_id: int, equipo: int | None) -> None:
    assert evento.actor_email.startswith("os:") and "@" in evento.actor_email
    assert evento.actor_user_id is None
    assert (evento.target_type, evento.target_id, evento.team_id) == ("user", objetivo_id, equipo)
    assert "tools/ops.py" in evento.detail
    assert evento.user_agent == "otro"


# ── revocar / restaurar ──────────────────────────────────────────────────────

async def test_revocar_quita_el_acceso_corta_y_audita(db, world: World):
    uid, version, _ = await _fila(db, world.carlos_email)
    codigo, consola = await _ops(db, "revocar", "--correo", world.carlos_email,
                                 entrada=world.carlos_email + "\n")
    assert codigo == 0, consola.errores.getvalue()
    _, version_despues, miembro = await _fila(db, world.carlos_email)
    assert miembro.is_active is False and version_despues == version + 1
    [evento] = await _eventos(db, "miembro.revocado")
    _es_del_operador(evento, uid, world.team_id)


async def test_revocar_otra_vez_no_corta_ni_audita(db, world: World):
    await _ops(db, "revocar", "--correo", world.carlos_email, entrada=world.carlos_email + "\n")
    _, version, _ = await _fila(db, world.carlos_email)
    codigo, consola = await _ops(db, "revocar", "--correo", world.carlos_email)
    assert codigo == 0 and "ya tenía el acceso revocado" in consola.salida.getvalue()
    assert (await _fila(db, world.carlos_email))[1] == version
    assert len(await _eventos(db, "miembro.revocado")) == 1


@pytest.mark.parametrize("escrito", ["", "s", "CARLOS@test.dev", "carlos@test.dev x"])
async def test_revocar_sin_escribir_el_correo_no_cambia_nada(db, world: World, escrito):
    codigo, consola = await _ops(db, "revocar", "--correo", world.carlos_email,
                                 entrada=escrito + "\n")
    assert codigo == 1 and "Cancelado" in consola.errores.getvalue()
    assert (await _fila(db, world.carlos_email))[2].is_active is True
    assert await _eventos(db, "miembro.revocado") == []


async def test_revocar_en_dry_run_no_escribe_ni_audita(db, world: World):
    _, version, _ = await _fila(db, world.carlos_email)
    codigo, consola = await _ops(db, "revocar", "--correo", world.carlos_email, "--dry-run")
    assert codigo == 0 and consola.salida.getvalue().startswith("[dry-run]")
    _, version_despues, miembro = await _fila(db, world.carlos_email)
    assert miembro.is_active is True and version_despues == version
    assert await _eventos(db, "miembro.revocado") == []


async def test_al_dueno_no_se_le_revoca_tampoco_por_el_cli(db, world: World):
    codigo, consola = await _ops(db, "revocar", "--correo", world.owner_email,
                                 entrada=world.owner_email + "\n")
    assert codigo == 1 and "Transfiere la propiedad" in consola.errores.getvalue()
    assert (await _fila(db, world.owner_email))[2].is_active is True


async def test_restaurar_devuelve_el_acceso_sin_cortar(db, world: World):
    await _ops(db, "revocar", "--correo", world.sofia_email, entrada=world.sofia_email + "\n")
    uid, version, _ = await _fila(db, world.sofia_email)
    codigo, _ = await _ops(db, "restaurar", "--correo", world.sofia_email)
    assert codigo == 0
    _, version_despues, miembro = await _fila(db, world.sofia_email)
    assert miembro.is_active is True and version_despues == version
    [evento] = await _eventos(db, "miembro.restaurado")
    _es_del_operador(evento, uid, world.team_id)


async def test_una_cuenta_que_no_existe_es_un_error_claro(db, world: World):
    codigo, consola = await _ops(db, "cortar-sesiones", "--correo", "nadie@test.dev")
    assert codigo == 1 and "No hay ninguna cuenta" in consola.errores.getvalue()


# ── liberar (TODO-26) ────────────────────────────────────────────────────────

async def test_liberar_exige_revocar_antes_y_solo_atletas(db, world: World):
    codigo, consola = await _ops(db, "liberar", "--correo", world.carlos_email,
                                 entrada=world.carlos_email + "\n")
    assert codigo == 1 and "Primero revoca" in consola.errores.getvalue()
    await _ops(db, "revocar", "--correo", world.assistant_email,
               entrada=world.assistant_email + "\n")
    codigo, consola = await _ops(db, "liberar", "--correo", world.assistant_email,
                                 entrada=world.assistant_email + "\n")
    assert codigo == 1 and "Solo se libera a un atleta" in consola.errores.getvalue()
    assert (await _fila(db, world.assistant_email))[2] is not None
    assert await _eventos(db, "miembro.liberado") == []


async def test_liberar_en_dry_run_no_borra(db, world: World):
    await _ops(db, "revocar", "--correo", world.carlos_email, entrada=world.carlos_email + "\n")
    codigo, _ = await _ops(db, "liberar", "--correo", world.carlos_email, "--dry-run")
    assert codigo == 0 and (await _fila(db, world.carlos_email))[2] is not None
    assert await _eventos(db, "miembro.liberado") == []


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


async def test_liberado_entra_en_otro_club(client, db, world: World, monkeypatch):
    """El caso de TODO-26 entero: echado de A, liberado, invitado y dentro de B."""
    await _ops(db, "revocar", "--correo", world.carlos_email, entrada=world.carlos_email + "\n")
    uid, version, _ = await _fila(db, world.carlos_email)
    codigo, consola = await _ops(db, "liberar", "--correo", world.carlos_email,
                                 entrada=world.carlos_email + "\n")
    assert codigo == 0, consola.errores.getvalue()
    _, version_despues, miembro = await _fila(db, world.carlos_email)
    assert miembro is None and version_despues == version + 1
    ficha = (await db.execute(
        select(Swimmer.user_id, Swimmer.team_id).where(Swimmer.id == world.carlos_swimmer_id),
    )).one()
    assert ficha == (None, world.team_id)               # la ficha se queda en A, sin cuenta
    [evento] = await _eventos(db, "miembro.liberado")
    _es_del_operador(evento, uid, world.team_id)
    assert f"#{world.carlos_swimmer_id} desligada" in evento.detail

    assert (await _ops(db, "crear-equipo", "--nombre-equipo", "Club B",
                       "--correo", "dueno-b@test.dev", "--nombre", "Dueña B"))[0] == 0
    r = await client.post(f"{API}/link-codes/invite", headers=como("dueno-b@test.dev"),
                          json={"email": world.carlos_email, "name": "Carlos en B"})
    assert r.status_code == 201, r.text
    assert r.json()["account_created"] is False
    codigo_b = r.json()["link_code"]["code"]

    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)
    r = await client.post(f"{API}/auth/login",
                          json={"email": world.carlos_email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    token = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = await client.post(f"{API}/link-codes/redeem", json={"code": codigo_b}, headers=token)
    assert r.status_code == 200, r.text
    assert r.json()["team_name"] == "Club B"


# ── cortar sesiones y restablecer la contraseña ──────────────────────────────

async def test_cortar_sesiones_sube_la_generacion_y_es_de_acceso(db, world: World):
    uid, version, _ = await _fila(db, world.sofia_email)
    assert (await _ops(db, "cortar-sesiones", "--correo", world.sofia_email, "--dry-run"))[0] == 0
    assert (await _fila(db, world.sofia_email))[1] == version
    codigo, _ = await _ops(db, "cortar-sesiones", "--correo", world.sofia_email,
                           entrada=world.sofia_email + "\n")
    assert codigo == 0 and (await _fila(db, world.sofia_email))[1] == version + 1
    [evento] = await _eventos(db, "sesion.cortadas")
    _es_del_operador(evento, uid, world.team_id)


async def test_restablecer_emite_una_temporal_que_sirve_una_sola_vez(client, db, world: World,
                                                                     auth_on):
    uid, version, _ = await _fila(db, world.sofia_email)
    codigo, consola = await _ops(db, "restablecer-password", "--correo", world.sofia_email,
                                 entrada=world.sofia_email + "\n")
    assert codigo == 0
    salida = consola.salida.getvalue()
    [linea] = [x for x in salida.splitlines() if x.startswith("Contraseña temporal: ")]
    temporal = linea.removeprefix("Contraseña temporal: ")
    assert salida.count(temporal) == 1 and len(temporal) >= 12
    assert (await _fila(db, world.sofia_email))[1] == version + 1

    vieja = await client.post(f"{API}/auth/login",
                              json={"email": world.sofia_email, "password": PASSWORD})
    nueva = await client.post(f"{API}/auth/login",
                              json={"email": world.sofia_email, "password": temporal})
    assert (vieja.status_code, nueva.status_code) == (401, 200)
    [evento] = await _eventos(db, "cuenta.password_restablecida")
    _es_del_operador(evento, uid, world.team_id)
    assert temporal not in evento.detail
