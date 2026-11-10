"""Endurecimiento antes del primer release (auditoría del 2026-11-09).

Tres cosas que el /cso de esa fecha encontró abiertas:

- **El secreto de desarrollo no firma tokens de verdad.** `_check_production`
  solo miraba el secreto con `PEAKSTROKE_ENVIRONMENT=production`. Un despliegue
  que encendiera el login y se olvidara de esa variable firmaba con una cadena
  que está en el repositorio: cualquiera fabricaba el token del dueño.
- **TODO-28**: un nombre de solo espacios se aceptaba en el club, en la cuenta y
  en la ficha.
- **TODO-29**: la purga de la auditoría salía con 0 aunque su evento se perdiera.
"""
from __future__ import annotations

import pytest
from conftest import API, World

from app.core.config import DEV_JWT_SECRET, Settings

# --- El secreto de desarrollo -------------------------------------------------


def test_con_login_y_sin_secreto_propio_no_se_firma_con_el_del_repositorio():
    """Fuera de producción no se niega a arrancar (probar el login en local no
    debe pedir configuración): firma con un secreto aleatorio del proceso."""
    s = Settings(environment="development", auth_enabled=True, jwt_secret=DEV_JWT_SECRET)
    assert s.jwt_secret != DEV_JWT_SECRET
    assert len(s.jwt_secret) >= 43            # como mínimo 32 bytes de azar
    otro = Settings(environment="development", auth_enabled=True, jwt_secret=DEV_JWT_SECRET)
    assert otro.jwt_secret != s.jwt_secret    # aleatorio, no otra constante


def test_un_secreto_propio_se_respeta():
    s = Settings(environment="development", auth_enabled=True, jwt_secret="x" * 64)
    assert s.jwt_secret == "x" * 64


def test_sin_login_el_secreto_de_desarrollo_se_queda():
    """Con el login apagado no se emite ningún token: no hay nada que proteger,
    y cambiarlo rompería a quien lo lee en los tests."""
    s = Settings(environment="development", auth_enabled=False, jwt_secret=DEV_JWT_SECRET)
    assert s.jwt_secret == DEV_JWT_SECRET


def test_en_produccion_sigue_negandose_a_arrancar():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            environment="production", auth_enabled=True,
            jwt_secret=DEV_JWT_SECRET, refresh_cookie_secure=True,
        )


# --- TODO-28: nombres en blanco ----------------------------------------------

EN_BLANCO = ["  ", "   \t ", " a "]   # el último: un solo carácter tras recortar


@pytest.mark.parametrize("nombre", EN_BLANCO)
async def test_el_club_no_acepta_un_nombre_en_blanco(client, world: World, nombre):
    r = await client.patch(f"{API}/teams/mine", json={"name": nombre})
    assert r.status_code == 422
    assert (await client.get(f"{API}/teams/mine")).json()["name"].strip() != ""


@pytest.mark.parametrize("nombre", EN_BLANCO)
async def test_una_cuenta_no_acepta_un_nombre_en_blanco(client, world: World, nombre):
    r = await client.post(
        f"{API}/auth/members",
        json={"email": "blanco@test.dev", "name": nombre, "role": "coach"},
    )
    assert r.status_code == 422


@pytest.mark.parametrize("nombre", EN_BLANCO)
async def test_una_ficha_no_acepta_un_nombre_en_blanco(client, world: World, nombre):
    antes = len((await client.get(f"{API}/swimmers/")).json())
    r = await client.post(
        f"{API}/swimmers/",
        json={"name": nombre, "birth_date": "2008-01-01", "gender": "F",
              "specialty": "velocidad", "main_stroke": "libre"},
    )
    assert r.status_code == 422
    assert len((await client.get(f"{API}/swimmers/")).json()) == antes


@pytest.mark.parametrize("nombre", EN_BLANCO)
async def test_una_invitacion_no_acepta_un_nombre_en_blanco(client, world: World, nombre):
    antes = len((await client.get(f"{API}/swimmers/")).json())
    r = await client.post(
        f"{API}/link-codes/invite", json={"email": "blanco@test.dev", "name": nombre},
    )
    assert r.status_code == 422
    assert len((await client.get(f"{API}/swimmers/")).json()) == antes


@pytest.mark.parametrize(("argv", "que"), [
    (("--nombre-equipo", "   ", "--correo", "x@test.dev", "--nombre", "Ana Mora"), "club"),
    (("--nombre-equipo", "Club Nuevo", "--correo", "x@test.dev", "--nombre", "   "), "persona"),
])
async def test_el_cli_hereda_la_regla_del_nombre(db, world: World, argv, que):
    """`ops.py` valida con los schemas del API: no tiene una regla propia que
    pudiera quedarse atrás. Sale con error y no crea ni club ni cuenta."""
    import io

    from sqlalchemy import func, select

    from app.persistencia.tablas.equipos import Team
    from app.persistencia.tablas.usuarios import User
    from tools.operaciones import Consola, ejecutar

    async def cuenta(tabla):
        return (await db.execute(select(func.count()).select_from(tabla))).scalar_one()

    antes = (await cuenta(Team), await cuenta(User))
    consola = Consola(entrada=io.StringIO(""), salida=io.StringIO(),
                      errores=io.StringIO(), terminal=False)
    codigo = await ejecutar(("crear-equipo", *argv), consola, db)
    assert codigo != 0, que
    assert (await cuenta(Team), await cuenta(User)) == antes


async def test_el_nombre_se_guarda_recortado(client, world: World):
    r = await client.patch(f"{API}/teams/mine", json={"name": "  Club del Agua  "})
    assert r.status_code == 200
    assert r.json()["name"] == "Club del Agua"


# --- TODO-29: la purga no calla un evento perdido ------------------------------


async def test_la_purga_sale_distinto_de_cero_si_su_evento_se_pierde(monkeypatch, capsys):
    from tools import purgar_auditoria

    class _Contexto:
        perdidos = 1

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class _Repo:
        def __init__(self, _db): ...
        async def purgar_caducados(self): return 0
        async def retirar_claves_anteriores_a(self, _periodo): ...

    monkeypatch.setattr(purgar_auditoria, "contexto_de_auditoria", lambda **_: _Contexto())
    monkeypatch.setattr(purgar_auditoria, "RepositorioDeAuditoria", _Repo)
    monkeypatch.setattr(purgar_auditoria, "auditar", lambda *a, **k: None)

    assert await purgar_auditoria.main() == 3
    assert "no se guardó" in capsys.readouterr().err
