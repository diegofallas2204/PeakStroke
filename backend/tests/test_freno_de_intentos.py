"""TODO-33 y TODO-18: el freno de intentos en el login y en el canje de códigos.

Decidido por la persona el 2026-11-10: **freno por correo + origen y por
origen, sin bloquear cuentas**. Lo que fija este archivo:

- cinco fallos contra un correo desde un origen → 429 con `Retry-After`, también
  con la contraseña buena y también si el correo no existe (no enumera);
- la espera crece con cada fallo nuevo, y un intento frenado **no** la alarga;
- el mismo correo desde otro origen entra: nadie deja fuera a otro escribiendo
  mal su contraseña;
- veinte fallos desde un origen contra correos distintos frenan ese origen;
- el canje de códigos tiene el suyo, por cuenta.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import API, PASSWORD, World
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import freno
from app.core.auditoria import TipoDeEvento
from app.main import app
from app.persistencia.tablas.auditoria import EventoDeAuditoria


async def _login(cliente, correo: str, password: str = PASSWORD):
    return await cliente.post(f"{API}/auth/login", json={"email": correo, "password": password})


async def _fallar(cliente, correo: str, veces: int) -> None:
    for _ in range(veces):
        assert (await _login(cliente, correo, "no-es-esta")).status_code == 401


def _dentro_de(monkeypatch, segundos: int) -> None:
    """Adelanta el reloj del freno (los eventos ya escritos se quedan donde están)."""
    monkeypatch.setattr(freno, "_ahora", lambda: datetime.now(UTC) + timedelta(seconds=segundos))


def _cliente_desde(ip: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, client=(ip, 50000)), base_url="http://test")


@pytest.fixture
async def desde_otro_origen(client):
    """Un segundo cliente con otra IP. Depende de `client`, que pone la base."""
    transporte = ASGITransport(app=app, client=("203.0.113.9", 50000))
    async with AsyncClient(transport=transporte, base_url="http://test") as otro:
        yield otro


# --- La regla, sin base de datos ----------------------------------------------

@pytest.mark.parametrize(("fallos", "espera"), [
    (0, 0), (4, 0), (5, 30), (6, 60), (7, 120), (9, 480), (10, 900), (40, 900),
])
def test_la_espera_crece_y_tiene_tope(fallos, espera):
    assert freno.espera_tras(fallos, umbral=5) == timedelta(seconds=espera)


# --- Login ---------------------------------------------------------------------

async def test_cinco_fallos_frenan_aunque_la_contrasena_sea_buena(client, db, world: World):
    await _fallar(client, world.sofia_email, 5)

    r = await _login(client, world.sofia_email)            # la buena
    assert r.status_code == 429
    assert 1 <= int(r.headers["Retry-After"]) <= 30
    assert "access_token" not in r.text

    db.expire_all()
    frenados = (await db.execute(
        select(EventoDeAuditoria).where(
            EventoDeAuditoria.event_type == str(TipoDeEvento.LOGIN),
            EventoDeAuditoria.detail == freno.FRENADO,
        ),
    )).scalars().all()
    assert [(e.outcome, e.actor_email) for e in frenados] == [("fallo", world.sofia_email)]


async def test_cuatro_fallos_no_frenan(client, world: World):
    await _fallar(client, world.sofia_email, 4)
    assert (await _login(client, world.sofia_email)).status_code == 200


async def test_pasada_la_espera_se_entra_y_los_frenados_no_la_alargan(
    client, world: World, monkeypatch,
):
    await _fallar(client, world.sofia_email, 5)
    for _ in range(4):                                       # insistir no cuenta
        assert (await _login(client, world.sofia_email)).status_code == 429

    _dentro_de(monkeypatch, 31)
    assert (await _login(client, world.sofia_email)).status_code == 200


async def test_otro_fallo_tras_la_espera_dobla_la_siguiente(client, world: World, monkeypatch):
    """Los eventos se sellan con el reloj de verdad; solo se adelanta el del
    freno. El sexto fallo cae «ahora», así que su espera de 60 s se mide desde
    aquí: a los 31 s todavía frena (con cinco habría pasado) y a los 61 no."""
    await _fallar(client, world.sofia_email, 5)
    _dentro_de(monkeypatch, 31)
    assert (await _login(client, world.sofia_email, "tampoco")).status_code == 401   # el sexto

    r = await _login(client, world.sofia_email)
    assert r.status_code == 429
    assert 20 <= int(r.headers["Retry-After"]) <= 30

    _dentro_de(monkeypatch, 61)
    assert (await _login(client, world.sofia_email)).status_code == 200


async def test_un_correo_que_no_existe_se_frena_igual(client, world: World):
    """Si solo se frenaran las cuentas reales, el 429 diría cuáles existen."""
    await _fallar(client, "nadie@test.dev", 5)
    assert (await _login(client, "nadie@test.dev", "da-igual")).status_code == 429


async def test_el_freno_de_un_correo_no_toca_a_los_demas(client, world: World):
    await _fallar(client, world.sofia_email, 5)
    assert (await _login(client, world.carlos_email)).status_code == 200


async def test_el_mismo_correo_desde_otro_origen_entra(client, desde_otro_origen, world: World):
    """Lo que separa esto de un bloqueo de cuenta: quien falla a propósito la
    contraseña de un entrenador solo se frena a sí mismo."""
    await _fallar(client, world.sofia_email, 5)
    assert (await _login(client, world.sofia_email)).status_code == 429
    assert (await _login(desde_otro_origen, world.sofia_email)).status_code == 200


async def test_veinte_fallos_contra_correos_distintos_frenan_el_origen(
    client, desde_otro_origen, world: World,
):
    for i in range(20):
        assert (await _login(client, f"barrido{i}@test.dev", "x")).status_code == 401

    assert (await _login(client, world.carlos_email)).status_code == 429
    assert (await _login(desde_otro_origen, world.carlos_email)).status_code == 200


async def test_en_ipv6_cambiar_de_direccion_no_esquiva_el_freno(client, world: World):
    """Cinco direcciones distintas de la misma /64 son el mismo origen."""
    for i in range(5):
        async with _cliente_desde(f"2001:db8:abcd:12::{i + 1}") as c:
            assert (await _login(c, world.sofia_email, "no-es-esta")).status_code == 401
    async with _cliente_desde("2001:db8:abcd:12::99") as c:
        assert (await _login(c, world.sofia_email)).status_code == 429
    async with _cliente_desde("2001:db8:abcd:13::1") as c:          # otra /64
        assert (await _login(c, world.sofia_email)).status_code == 200


async def test_sin_origen_no_se_frena_nunca(client, world: World, monkeypatch):
    """Sin huella (sin IP, o antes del primer evento del periodo de clave) el
    freno no cuenta solo por correo: eso sería el bloqueo de cuenta que se
    descartó. Diez fallos seguidos y la buena sigue entrando."""
    async def sin_huella(_db):
        return None

    monkeypatch.setattr(freno, "huella_del_origen", sin_huella)
    for _ in range(10):
        assert (await _login(client, world.sofia_email, "no-es-esta")).status_code == 401
    assert (await _login(client, world.sofia_email)).status_code == 200


# --- Canje de códigos (TODO-18) -------------------------------------------------

async def test_cinco_canjes_fallidos_frenan_el_sexto(client, world: World):
    for i in range(5):
        r = await client.post(f"{API}/link-codes/redeem", json={"code": f"ZZZZ-ZZZ{i}"})
        assert r.status_code != 429, i

    r = await client.post(f"{API}/link-codes/redeem", json={"code": "ZZZZ-ZZZZ"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
