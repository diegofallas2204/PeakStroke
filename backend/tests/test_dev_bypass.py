"""El modo desarrollador: saltarse los guards de rol sin dejar de ser quien eres.

El conmutador de identidad existe para revisar la aplicación con los ojos de cada
rol. Eso solo sirve si la interfaz que ves es **la de verdad**: un atleta tiene
que recibir 403 donde un atleta recibe 403, o no estarías revisando nada.

Pero depurar así te deja atascado en cuanto necesitas montar datos, y cambiar de
identidad, hacer la acción y volver es el tipo de fricción que hace que nadie use
la herramienta. De ahí el segundo eje:

    X-PeakStroke-Dev-User    ──▶  QUIÉN eres     (fiel: 403 donde toca)
    X-PeakStroke-Dev-Bypass  ──▶  puedes SALTARTE los guards de rol

El bypass levanta **lo que puedes hacer**, no **lo que ves**. El filtro por
nadador sigue puesto, así que sigues mirando la aplicación de Sofía mientras te
desatascas. Si quisieras verlo todo, para eso está suplantar al entrenador.

Los tests de abajo fijan las dos mitades: que el bypass funcione, y que no exista
en cuanto el login se enciende o el entorno es producción.
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.dependencies import DEV_BYPASS_HEADER
from conftest import API, World, como


def con_bypass(email: str) -> dict[str, str]:
    return {**como(email), DEV_BYPASS_HEADER: "true"}


# ── Sin bypass: la identidad se comporta como su rol, fielmente ──────────────

@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), [
    ("post", "/swimmers/", {"name": "Nadador Nuevo"}),
    ("get", "/auth/members", None),
    ("get", "/teams/mine", None),
    ("get", "/dashboard/team-week", None),
])
async def test_sin_bypass_el_atleta_sigue_siendo_atleta(client, world: World, metodo, ruta, cuerpo):
    """Lo que hace revisable la UI de atleta: que no todo responda 200."""
    r = await getattr(client, metodo)(
        f"{API}{ruta}", headers=como(world.sofia_email),
        **({"json": cuerpo} if cuerpo is not None else {}),
    )
    assert r.status_code == 403


# ── Con bypass: los guards dejan pasar ───────────────────────────────────────

@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), [
    ("post", "/swimmers/", {"name": "Nadador de Depuración"}),
    ("get", "/auth/members", None),
    ("get", "/teams/mine", None),
    ("get", "/dashboard/team-week", None),
])
async def test_con_bypass_pasa_los_guards_de_entrenador(client, world: World, metodo, ruta, cuerpo):
    r = await getattr(client, metodo)(
        f"{API}{ruta}", headers=con_bypass(world.sofia_email),
        **({"json": cuerpo} if cuerpo is not None else {}),
    )
    assert r.status_code in (200, 201), f"{metodo.upper()} {ruta} bloqueó al desarrollador"


async def test_con_bypass_pasa_los_guards_de_dueno(client, world: World):
    """Incluso `require_owner`, que es el guard más estrecho."""
    r = await client.patch(
        f"{API}/teams/mine", json={"name": "Club Renombrado"},
        headers=con_bypass(world.assistant_email),
    )
    assert r.status_code == 200


async def test_con_bypass_puede_marcar_el_paron_de_una_semana(client, db, world: World):
    """La autorización por campo también lo honra, no solo las dependencias."""
    from sqlalchemy import select

    from app.modules.plans.models import WeeklyPlan

    semana = (await db.execute(
        select(WeeklyPlan).where(
            WeeklyPlan.athlete_event_id == world.sofia_event_id, WeeklyPlan.week_number == 2,
        )
    )).scalar_one()

    r = await client.patch(
        f"{API}/plans/weeks/{semana.id}", json={"disabled": True},
        headers=con_bypass(world.sofia_email),
    )
    assert r.status_code == 200


# ── Lo que el bypass NO hace: seguir viendo lo de Sofía ──────────────────────

async def test_el_bypass_no_levanta_el_filtro_de_datos(client, world: World):
    """**La mitad que da valor a la herramienta.**

    Si el bypass enseñara los 3 nadadores del club, estarías mirando la pantalla
    del entrenador y no la del atleta — y entonces no habrías revisado la UI de
    atleta, que era el motivo de suplantarla. Levanta lo que puedes HACER; lo que
    VES sigue siendo lo de Sofía.
    """
    r = await client.get(f"{API}/swimmers/", headers=con_bypass(world.sofia_email))
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [world.sofia_swimmer_id]

    tests = await client.get(f"{API}/aerobic-tests/", headers=con_bypass(world.sofia_email))
    assert [t["id"] for t in tests.json()] == [world.sofia_test_id]

    resumen = await client.get(f"{API}/dashboard/summary", headers=con_bypass(world.sofia_email))
    assert {f["swimmer_id"] for f in resumen.json()["statuses"]} == {world.sofia_swimmer_id}


async def test_el_bypass_no_da_acceso_a_datos_ajenos(client, world: World):
    """Un recurso de otro atleta sigue siendo 404, con bypass o sin él.

    El bypass es una llave para los guards de rol, no un pase para los datos: si
    abriera también el scoping, "modo desarrollador" y "modo entrenador" serían
    lo mismo y la distinción no compraría nada.
    """
    r = await client.get(
        f"{API}/plans/events/{world.carlos_event_id}/weeks",
        headers=con_bypass(world.sofia_email),
    )
    assert r.status_code == 404


# ── Lo que apaga el bypass ───────────────────────────────────────────────────

async def test_con_auth_encendida_el_bypass_no_existe(client, world: World, monkeypatch):
    """**El test crítico.** Con login real la cabecera es texto que nadie lee."""
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)

    r = await client.post(
        f"{API}/swimmers/", json={"name": "Intruso"}, headers=con_bypass(world.sofia_email),
    )
    assert r.status_code == 401, "el bypass sobrevivió al login real"


@pytest.mark.parametrize("entorno", ["production", "PROD"])
async def test_en_produccion_las_dos_cabeceras_se_ignoran(client, world: World, monkeypatch, entorno):
    """Segunda barrera, la que aguanta si algo muta `auth_enabled` en caliente.

    Se comprueba que **ninguna de las dos** cabeceras se lea, no que la petición
    acabe en 403: con el conmutador apagado la identidad cae al usuario por
    defecto —un entrenador— así que un 403 sería la respuesta equivocada por el
    motivo equivocado. Lo que fija el test es que no eres Sofía y que no llevas
    bypass.
    """
    monkeypatch.setattr(settings, "environment", entorno, raising=False)
    assert settings.dev_identity_enabled is False

    quien = await client.get(f"{API}/auth/me", headers=con_bypass(world.sofia_email))
    assert quien.json()["email"] == settings.dev_user_email, "la cabecera de identidad se leyó"

    cfg = (await client.get(f"{API}/auth/config", headers=con_bypass(world.sofia_email))).json()
    assert cfg["dev_bypass_active"] is False, "la cabecera de bypass se leyó"
    assert cfg["dev_identities_enabled"] is False


@pytest.mark.parametrize("valor", ["", "0", "false", "no", "quiza", "  "])
async def test_solo_un_valor_afirmativo_activa_el_bypass(client, world: World, valor):
    """Una cabecera presente pero sin decir que sí no cuenta como que sí."""
    r = await client.post(
        f"{API}/swimmers/", json={"name": "Intruso"},
        headers={**como(world.sofia_email), DEV_BYPASS_HEADER: valor},
    )
    assert r.status_code == 403


@pytest.mark.parametrize("valor", ["1", "true", "TRUE", "yes", "on", "si", "Si"])
async def test_los_valores_afirmativos_habituales_valen(client, world: World, valor):
    r = await client.get(
        f"{API}/teams/mine", headers={**como(world.sofia_email), DEV_BYPASS_HEADER: valor},
    )
    assert r.status_code == 200


async def test_el_bypass_no_se_puede_persistir(db, world: World):
    """`is_developer` no existe en la base de datos, y ese es el punto.

    Ninguna columna, ningún campo de usuario, ningún rol. Solo una cabecera que
    `dev_identity_enabled` puede apagar entera. Si algún día alguien lo hace
    persistible, este test se lo dice.
    """
    from app.core.database import Base

    columnas = {
        c.name for t in Base.metadata.sorted_tables for c in t.columns
    }
    assert "is_developer" not in columnas
    assert "is_dev" not in columnas

    from app.modules.teams.models import ROLES
    assert "developer" not in ROLES and "dev" not in ROLES


# ── El contrato que consume el frontend ──────────────────────────────────────

async def test_auth_config_anuncia_el_modo(client, world: World):
    sin = (await client.get(f"{API}/auth/config")).json()
    assert sin["auth_enabled"] is False
    assert sin["dev_identities_enabled"] is True
    assert sin["dev_bypass_active"] is False
    assert sin["dev_user_header"] == "X-PeakStroke-Dev-User"
    assert sin["dev_bypass_header"] == DEV_BYPASS_HEADER

    con = (await client.get(f"{API}/auth/config", headers=con_bypass(world.sofia_email))).json()
    assert con["dev_bypass_active"] is True


async def test_auth_config_no_anuncia_nada_con_auth_encendida(client, monkeypatch):
    """El frontend no debe dibujar la barra si el conmutador no existe."""
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    cfg = (await client.get(f"{API}/auth/config")).json()
    assert cfg["auth_enabled"] is True
    assert cfg["dev_identities_enabled"] is False
    assert cfg["dev_bypass_active"] is False
    assert cfg["dev_user_header"] is None
    assert cfg["dev_bypass_header"] is None
