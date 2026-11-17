"""Lo que el despliegue necesita del código (TODO-34, 2026-11-16).

- El proxy de confianza: la IP real del cliente detrás del balanceador, sin
  creer un `X-Forwarded-For` que cualquiera puede escribir.
- Las cabeceras de seguridad en cada respuesta del API.
- No arrancar sin login contra una base remota, aunque falte `ENVIRONMENT`.
"""
from __future__ import annotations

import pytest
from conftest import API, World, como
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, settings
from app.core.proxy import ip_del_cliente, redes
from app.main import app
from app.persistencia.tablas.auditoria import EventoDeAuditoria

PROXY = redes(["10.0.0.0/8", "fd00::/8"])


class TestElProxyDeConfianza:
    def test_sin_proxies_declarados_la_cabecera_no_se_cree(self):
        assert ip_del_cliente("10.1.2.3", "203.0.113.7", ()) == "10.1.2.3"

    def test_desde_un_proxy_propio_se_lee_la_cabecera(self):
        assert ip_del_cliente("10.1.2.3", "203.0.113.7", PROXY) == "203.0.113.7"

    def test_desde_fuera_la_cabecera_se_ignora(self):
        # Un cliente cualquiera que se inventa el X-Forwarded-For.
        assert ip_del_cliente("198.51.100.9", "203.0.113.7", PROXY) == "198.51.100.9"

    def test_lo_que_escribe_el_cliente_a_la_izquierda_no_se_cree(self):
        # El cliente mandó «1.2.3.4»; su proxy añadió su IP real, y el nuestro, la suya.
        cadena = "1.2.3.4, 203.0.113.7, 10.0.0.5"
        assert ip_del_cliente("10.0.0.9", cadena, PROXY) == "203.0.113.7"

    def test_basura_en_la_cabecera_cae_a_la_conexion(self):
        assert ip_del_cliente("10.0.0.9", "no-es-ip", PROXY) == "10.0.0.9"

    def test_ipv6(self):
        assert ip_del_cliente("fd00::1", "2001:db8::42", PROXY) == "2001:db8::42"

    def test_una_red_mal_escrita_no_arranca(self):
        with pytest.raises(ValidationError):
            Settings(proxies_de_confianza=["10.0.0.0/33"])


async def test_el_freno_y_la_auditoria_ven_la_ip_real(db, world: World, monkeypatch):
    """Detrás del proxy, dos clientes distintos no comparten origen."""
    monkeypatch.setattr(settings, "proxies_de_confianza", ["10.0.0.0/8"])
    transporte = ASGITransport(app=app, client=("10.0.0.5", 4242))
    async with AsyncClient(transport=transporte, base_url="http://test") as cliente:
        r = await cliente.post(f"{API}/auth/login", json={"email": "nadie@test.dev", "password": "x"},
                               headers={"X-Forwarded-For": "203.0.113.7"})
    assert r.status_code == 401
    db.expire_all()
    [evento] = (await db.execute(select(EventoDeAuditoria))).scalars().all()
    assert evento.ip_network.startswith("203.0.113.")


class TestLasCabecerasDeSeguridad:
    async def test_cada_respuesta_del_api_las_lleva(self, client, world: World):
        r = await client.get(f"{API}/swimmers/", headers=como(world.owner_email))
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        # Datos personales: que ningún intermediario los guarde.
        assert r.headers["cache-control"] == "no-store"

    async def test_tambien_los_errores(self, client):
        r = await client.get(f"{API}/no-existe")
        assert r.status_code == 404
        assert r.headers["x-content-type-options"] == "nosniff"

    async def test_hsts_solo_en_produccion(self, client, monkeypatch):
        r = await client.get("/health")
        assert "strict-transport-security" not in r.headers
        monkeypatch.setattr(settings, "environment", "production")
        r = await client.get("/health")
        assert r.headers["strict-transport-security"].startswith("max-age=")


class TestArrancarSinLogin:
    def test_contra_una_base_remota_no_arranca(self):
        with pytest.raises(ValidationError, match="login"):
            Settings(database_url="postgresql+asyncpg://u:p@db.ejemplo.com:5432/ps", auth_enabled=False)

    def test_contra_postgres_local_si(self):
        """El `docker-compose.yml` de desarrollo: PostgreSQL en localhost, sin login."""
        Settings(database_url="postgresql+asyncpg://u:p@localhost:5432/ps", auth_enabled=False)

    def test_con_login_contra_una_base_remota_si(self):
        Settings(database_url="postgresql+asyncpg://u:p@db.ejemplo.com:5432/ps", auth_enabled=True)
