"""La auditoría (D0): qué se registra, qué no se puede borrar y qué no se guarda.

Cuatro grupos:

1. **Cada evento de seguridad deja su fila**, con actor, equipo y objetivo. Se
   prueba por el API, igual que se producen en la realidad.
2. **Append-only de verdad**: la base rechaza el `UPDATE` y el `DELETE` de lo
   reciente, y solo la purga borra lo que ya cumplió 24 meses.
3. **Una IP nunca llega entera al disco** (R11, opción C).
4. **Si la auditoría falla, la petición sigue** y el log lo dice.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import pytest
from conftest import API, PASSWORD, World, como
from sqlalchemy import select, text
from sqlalchemy.exc import DatabaseError

from app.core import auditoria as mod_auditoria
from app.core.anonimizacion import familia_de, huella_de, red_de
from app.core.auditoria import TipoDeEvento, contexto_de_auditoria
from app.core.config import settings
from app.core.dev_identity import DEV_BYPASS_HEADER
from app.persistencia.repositorios import RepositorioDeAuditoria
from app.persistencia.tablas.auditoria import ClaveDeAuditoria, EventoDeAuditoria
from app.persistencia.tablas.usuarios import User


async def _eventos(db, tipo: TipoDeEvento | None = None) -> list[EventoDeAuditoria]:
    stmt = select(EventoDeAuditoria).order_by(EventoDeAuditoria.id)
    if tipo is not None:
        stmt = stmt.where(EventoDeAuditoria.event_type == str(tipo))
    db.expire_all()
    return list((await db.execute(stmt)).scalars())


async def _uno(db, tipo: TipoDeEvento) -> EventoDeAuditoria:
    eventos = await _eventos(db, tipo)
    assert len(eventos) == 1, f"{tipo}: {[(e.outcome, e.detail) for e in eventos]}"
    return eventos[0]


async def _user_id(db, email: str) -> int:
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


async def _login(client, email: str, password: str = PASSWORD):
    return await client.post(f"{API}/auth/login", json={"email": email, "password": password})


# ── 1. Acceso y sesión ───────────────────────────────────────────────────────

async def test_login_correcto(client, db, world: World):
    assert (await _login(client, world.sofia_email)).status_code == 200

    e = await _uno(db, TipoDeEvento.LOGIN)
    assert (e.outcome, e.actor_email, e.team_id) == ("ok", world.sofia_email, world.team_id)
    assert e.actor_user_id == await _user_id(db, world.sofia_email)
    assert e.occurred_at is not None


@pytest.mark.parametrize(("email", "password", "motivo"), [
    ("nadie@test.dev", PASSWORD, "cuenta_inexistente"),
    ("sofia@test.dev", "no-es-esta", "password_incorrecta"),
])
async def test_login_fallido_dice_por_que(client, db, world: World, email, password, motivo):
    """La respuesta es el mismo 401 en los dos casos; el registro no.

    Se guarda el correo tecleado (normalizado), no un id: un fallo no atribuye
    la acción a una cuenta, solo dice contra qué correo se intentó.
    """
    r = await _login(client, email.upper(), password)
    assert r.status_code == 401

    e = await _uno(db, TipoDeEvento.LOGIN)
    assert (e.outcome, e.detail, e.actor_email) == ("fallo", motivo, email)
    assert e.actor_user_id is None


async def test_login_con_acceso_revocado(client, db, world: World):
    r = await client.patch(
        f"{API}/auth/members/{await _user_id(db, world.sofia_email)}",
        json={"is_active": False}, headers=como(world.owner_email),
    )
    assert r.status_code == 200
    assert (await _login(client, world.sofia_email)).status_code == 401

    e = await _uno(db, TipoDeEvento.LOGIN)
    assert (e.outcome, e.detail, e.actor_email) == ("fallo", "acceso_revocado", world.sofia_email)


async def test_refresh_reusado_queda_registrado(client, db, world: World, auth_on):
    """**El evento más importante del registro**: una cookie copiada."""
    await _login(client, world.sofia_email)
    robada = client.cookies.get(settings.refresh_cookie_name)
    assert (await client.post(f"{API}/auth/refresh")).status_code == 200

    client.cookies.set(settings.refresh_cookie_name, robada, path="/api/v1/auth")
    assert (await client.post(f"{API}/auth/refresh")).status_code == 401

    e = await _uno(db, TipoDeEvento.REFRESH_REUSADO)
    assert (e.outcome, e.actor_email) == ("fallo", world.sofia_email)
    assert "se revocan todas las sesiones" in e.detail


async def test_logout(client, db, world: World, auth_on):
    await _login(client, world.sofia_email)
    assert (await client.post(f"{API}/auth/logout")).status_code == 204
    assert (await _uno(db, TipoDeEvento.LOGOUT)).actor_email == world.sofia_email


async def test_cambio_de_contrasena_bueno_y_malo(client, db, world: World):
    ruta, quien = f"{API}/auth/me/password", como(world.sofia_email)
    r = await client.post(ruta, json={
        "current_password": "mala", "new_password": "otra-contrasena-larga",
    }, headers=quien)
    assert r.status_code == 400
    r = await client.post(ruta, json={
        "current_password": PASSWORD, "new_password": "otra-contrasena-larga",
    }, headers=quien)
    assert r.status_code == 200

    eventos = await _eventos(db, TipoDeEvento.PASSWORD_CAMBIADA)
    assert [(e.outcome, e.detail) for e in eventos] == [
        ("fallo", "password_actual_incorrecta"), ("ok", "se revocan las demás sesiones"),
    ]


async def test_el_bypass_de_desarrollo_deja_rastro(client, db, world: World):
    r = await client.post(
        f"{API}/swimmers/", json={"name": "Colado"},
        headers={**como(world.sofia_email), DEV_BYPASS_HEADER: "true"},
    )
    assert r.status_code == 201
    e = await _uno(db, TipoDeEvento.DEV_BYPASS)
    assert e.actor_email == world.sofia_email
    assert "athlete se salta el guard" in e.detail


# ── 1. Actividad ─────────────────────────────────────────────────────────────

async def test_rol_revocacion_y_restauracion(client, db, world: World):
    carlos = await _user_id(db, world.carlos_email)
    ruta, jefe = f"{API}/auth/members/{carlos}", como(world.owner_email)
    await client.patch(ruta, json={"role": "coach"}, headers=jefe)
    await client.patch(ruta, json={"is_active": False}, headers=jefe)
    await client.patch(ruta, json={"is_active": True}, headers=jefe)
    await client.patch(ruta, json={"name": "Carlos Renombrado"}, headers=jefe)

    eventos = await _eventos(db)
    assert [e.event_type for e in eventos] == [
        "miembro.rol_cambiado", "miembro.revocado", "miembro.restaurado",
    ], "renombrar no es un evento de seguridad"
    assert eventos[0].detail == f"{world.carlos_email}: athlete → coach"
    assert {(e.target_type, e.target_id, e.actor_email) for e in eventos} == {
        ("user", carlos, world.owner_email),
    }


async def test_transferencia_de_propiedad(client, db, world: World):
    asistente = await _user_id(db, world.assistant_email)
    r = await client.post(
        f"{API}/teams/mine/transfer", json={"new_owner_id": asistente},
        headers=como(world.owner_email),
    )
    assert r.status_code == 200
    e = await _uno(db, TipoDeEvento.PROPIEDAD_TRANSFERIDA)
    assert (e.target_type, e.target_id, e.team_id) == ("user", asistente, world.team_id)


async def test_codigos_emitido_revocado_y_canjes(client, db, world: World):
    jefe, huerfano = como(world.owner_email), como(world.huerfano_email)
    ficha = world.sin_cuenta_swimmer_id
    primero = (await client.post(
        f"{API}/link-codes/", json={"swimmer_id": ficha}, headers=jefe,
    )).json()
    await client.delete(f"{API}/link-codes/{primero['id']}", headers=jefe)
    await client.post(f"{API}/link-codes/redeem", json={"code": "ZZZZ-9999"}, headers=huerfano)
    segundo = (await client.post(
        f"{API}/link-codes/", json={"swimmer_id": ficha}, headers=jefe,
    )).json()
    r = await client.post(
        f"{API}/link-codes/redeem", json={"code": segundo["code"]}, headers=huerfano,
    )
    assert r.status_code == 200

    eventos = await _eventos(db)
    assert [(e.event_type, e.outcome) for e in eventos] == [
        ("codigo.emitido", "ok"), ("codigo.revocado", "ok"), ("codigo.canjeado", "fallo"),
        ("codigo.emitido", "ok"), ("codigo.canjeado", "ok"),
    ]
    canje = eventos[-1]
    assert (canje.actor_email, canje.team_id) == (world.huerfano_email, world.team_id)
    assert (canje.target_type, canje.target_id) == ("swimmer", ficha)
    # El código en sí no se guarda en ningún sitio del registro.
    assert all(segundo["code"] not in (e.detail or "") for e in eventos)


async def test_bajas_y_restauraciones(client, db, world: World):
    jefe = como(world.owner_email)
    nadador, test = world.carlos_swimmer_id, world.carlos_test_id
    await client.delete(f"{API}/aerobic-tests/{test}", headers=jefe)
    await client.post(f"{API}/aerobic-tests/{test}/reactivate", headers=jefe)
    await client.delete(f"{API}/swimmers/{nadador}", headers=jefe)
    await client.post(f"{API}/swimmers/{nadador}/reactivate", headers=jefe)

    plan = (await client.get(f"{API}/plans/{world.plan_id}", headers=jefe)).json()
    ap = next(a["id"] for a in plan["athletes"] if a["swimmer_id"] == nadador)
    await client.delete(f"{API}/plans/{world.plan_id}/athletes/{ap}", headers=jefe)
    await client.post(f"{API}/plans/{world.plan_id}/athletes/{ap}/restore", headers=jefe)

    eventos = await _eventos(db)
    assert [(e.event_type, e.target_type, e.target_id) for e in eventos] == [
        ("test_aerobico.baja", "aerobic_test", test),
        ("test_aerobico.restaurado", "aerobic_test", test),
        ("nadador.baja", "swimmer", nadador),
        ("nadador.restaurado", "swimmer", nadador),
        ("inscripcion.baja", "athlete_plan", ap),
        ("inscripcion.restaurada", "athlete_plan", ap),
    ]
    assert {e.team_id for e in eventos} == {world.team_id}


async def test_lo_que_falla_antes_de_confirmar_no_se_anota_como_hecho(
    client, db, world: World,
):
    """Un 404 no es una baja: se audita lo que pasó, no lo que se pidió."""
    r = await client.delete(f"{API}/swimmers/999999", headers=como(world.owner_email))
    assert r.status_code == 404
    assert await _eventos(db) == []


# ── 2. Append-only ───────────────────────────────────────────────────────────

async def _un_evento(db, hace: timedelta = timedelta(0)) -> int:
    fila = EventoDeAuditoria(
        occurred_at=datetime.now(UTC) - hace, event_type="sesion.login", outcome="ok",
        detail="",
    )
    db.add(fila)
    await db.commit()
    return fila.id


async def test_la_base_rechaza_modificar_un_evento(db, world: World):
    evento = await _un_evento(db)
    with pytest.raises(DatabaseError, match="append-only"):
        await db.execute(text("UPDATE auditoria SET outcome = 'fallo' WHERE id = :i"), {"i": evento})
    await db.rollback()


async def test_la_base_rechaza_borrar_lo_reciente(db, world: World):
    evento = await _un_evento(db, hace=timedelta(days=700))  # 23 meses: aún dentro
    with pytest.raises(DatabaseError, match="24 meses"):
        await db.execute(text("DELETE FROM auditoria WHERE id = :i"), {"i": evento})
    await db.rollback()


async def test_la_purga_solo_se_lleva_lo_caducado(db, world: World):
    viejo = await _un_evento(db, hace=timedelta(days=760))  # 25 meses
    nuevo = await _un_evento(db, hace=timedelta(days=1))

    assert await RepositorioDeAuditoria(db).purgar_caducados() == 1
    await db.commit()
    assert [e.id for e in await _eventos(db)] == [nuevo]
    assert viejo != nuevo


# ── 3. Privacidad ────────────────────────────────────────────────────────────

async def test_la_ip_nunca_se_guarda_entera(client, db, world: World):
    await _login(client, world.sofia_email)
    e = await _uno(db, TipoDeEvento.LOGIN)
    # `ASGITransport` presenta la petición como 127.0.0.1.
    assert e.ip_network == "127.0.0.0/24"
    assert len(e.ip_hash) == 32
    assert e.user_agent == "httpx"
    fila = (await db.execute(text("SELECT * FROM auditoria"))).one()
    assert not any("127.0.0.1" in str(valor) for valor in fila)


def test_red_truncada():
    assert red_de("203.0.113.77") == "203.0.113.0/24"
    assert red_de("::ffff:203.0.113.77") == "203.0.113.0/24"  # IPv4 envuelta
    assert red_de("2001:db8:abcd:12::1") == "2001:db8:abcd::/48"
    assert red_de("testclient") is None
    assert red_de(None) is None


def test_la_huella_depende_de_la_clave():
    """Misma IP y misma clave, misma huella; al rotar la clave, otra."""
    a, b = b"a" * 32, b"b" * 32
    assert huella_de("203.0.113.77", a) == huella_de("::ffff:203.0.113.77", a)
    assert huella_de("203.0.113.77", a) != huella_de("203.0.113.78", a)
    assert huella_de("203.0.113.77", a) != huella_de("203.0.113.77", b)


@pytest.mark.parametrize(("ua", "familia"), [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/128.0.0.0 Safari/537.36", "Chrome · Windows"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0", "Edge · Windows"),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
     "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1", "Safari · iOS"),
    ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/128.0 Mobile Safari/537.36", "Chrome · Android"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:129.0) Gecko/20100101 Firefox/129.0",
     "Firefox · macOS"),
    ("curl/8.7.1", "curl"),
    (None, None),
])
def test_familia_del_user_agent(ua, familia):
    assert familia_de(ua) == familia


async def test_rotar_la_clave_borra_la_anterior(db, world: World):
    repo = RepositorioDeAuditoria(db)
    vieja = await repo.clave_del_periodo(1000)
    assert await repo.clave_del_periodo(1000) == vieja
    nueva = await repo.clave_del_periodo(1001)
    await db.commit()
    assert nueva != vieja
    periodos = (await db.execute(select(ClaveDeAuditoria.period))).scalars().all()
    assert periodos == [1001]


# ── 4. Una tabla de log no tumba la aplicación ───────────────────────────────

async def test_si_la_auditoria_falla_la_peticion_sigue(
    client, db, world: World, monkeypatch, caplog,
):
    def rota(self, eventos):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(RepositorioDeAuditoria, "anotar", rota)
    with caplog.at_level(logging.ERROR, logger="app.core.auditoria"):
        r = await _login(client, world.sofia_email)

    assert r.status_code == 200
    assert await _eventos(db) == []
    aviso = next(m for m in caplog.messages if "AUDITORÍA" in m)
    assert "no se pudieron guardar 1 evento(s)" in aviso
    assert f"sesion.login ok {world.sofia_email}" in aviso


async def test_fuera_de_una_peticion_se_avisa_y_no_se_guarda(db, world: World, caplog):
    with caplog.at_level(logging.WARNING, logger="app.core.auditoria"):
        mod_auditoria.auditar(TipoDeEvento.LOGIN, correo="x@test.dev")
    assert any("fuera de una petición" in m for m in caplog.messages)
    assert await _eventos(db) == []


async def test_un_script_abre_su_propio_contexto(db, world: World):
    async with contexto_de_auditoria(user_agent="curl/8.7.1"):
        mod_auditoria.auditar(TipoDeEvento.AUDITORIA_PURGADA, detalle="0 eventos")
    e = await _uno(db, TipoDeEvento.AUDITORIA_PURGADA)
    assert (e.user_agent, e.ip_network, e.ip_hash) == ("curl", None, None)
