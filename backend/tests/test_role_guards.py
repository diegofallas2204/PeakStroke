"""Los guards de rol comprueban el rol **siempre**, también con el login apagado.

Hasta el 2026-08-06 `require_role` y `require_owner` devolvían el principal sin
mirar nada cuando `auth_enabled=false`. El comentario lo justificaba así: "en modo
bypass no hay rol real que comprobar: el usuario de desarrollo es siempre el mismo".

Esa premisa murió el mismo día, con la cabecera `X-PeakStroke-Dev-User`. Ahora sí
hay un rol real —el de la identidad suplantada— y el atajo se convirtió en un
agujero. Reproducido en vivo contra la base sembrada:

    PATCH /auth/members/2  {"role":"coach"}  como sofia@peakstroke.dev  ->  200
    rol de Sofía después: coach
    nadadores que ve:     10   (antes: 1)

Una petición y toda la frontera del atleta deja de aplicarse, porque
`scope_to_own_swimmer` solo actúa cuando el rol es `athlete`. Estos tests fijan
que ya no se puede.
"""
from __future__ import annotations

import pytest
from conftest import API, World, como

# ── Un atleta no hace cosas de entrenador ────────────────────────────────────

@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), [
    ("post", "/swimmers/", {"name": "Nadador Nuevo"}),
    ("post", "/plans/", {
        "name": "Plan Intruso", "start_date": "2026-09-07", "total_weeks": 12,
        "total_km": 300,
    }),
    ("get", "/auth/members", None),
    ("get", "/teams/mine", None),
])
async def test_un_atleta_no_pasa_los_guards_de_entrenador(
    client, world: World, metodo, ruta, cuerpo,
):
    r = await getattr(client, metodo)(
        f"{API}{ruta}", headers=como(world.sofia_email),
        **({"json": cuerpo} if cuerpo is not None else {}),
    )
    assert r.status_code == 403, f"{metodo.upper()} {ruta} dejó pasar a un atleta"


async def test_un_atleta_no_puede_ascenderse_a_entrenador(client, db, world: World):
    """**El crítico.** Era la vía para anular el scoping entero en una petición.

    403 y no 404 a propósito: aquí el problema no es que el recurso sea ajeno
    —Sofía se está editando a sí misma— sino que su rol no alcanza para la
    acción. Ese es exactamente el caso en el que 403 es la respuesta correcta.
    """
    from sqlalchemy import select

    from app.modules.auth.models import User

    sofia = (await db.execute(
        select(User).where(User.email == world.sofia_email)
    )).scalar_one()

    r = await client.patch(
        f"{API}/auth/members/{sofia.id}", json={"role": "coach"},
        headers=como(world.sofia_email),
    )

    assert r.status_code == 403
    me = await client.get(f"{API}/auth/me", headers=como(world.sofia_email))
    assert me.json()["role"] == "athlete"
    # Y el scoping sigue en pie, que es lo que la promoción desactivaba.
    swimmers = await client.get(f"{API}/swimmers/", headers=como(world.sofia_email))
    assert [s["id"] for s in swimmers.json()] == [world.sofia_swimmer_id]


# ── Un entrenador que no es dueño no hace cosas de dueño ─────────────────────

async def test_un_coach_asistente_no_pasa_los_guards_de_dueno(client, world: World):
    r = await client.patch(
        f"{API}/teams/mine", json={"name": "Club Renombrado"},
        headers=como(world.assistant_email),
    )
    assert r.status_code == 403


async def test_un_atleta_tampoco(client, world: World):
    r = await client.patch(
        f"{API}/teams/mine", json={"name": "Club Secuestrado"},
        headers=como(world.sofia_email),
    )
    assert r.status_code == 403


# ── Y el trabajo normal sigue funcionando ────────────────────────────────────

async def test_el_entrenador_sigue_pudiendo_hacer_su_trabajo(client, world: World):
    """El arreglo no puede convertirse en "ahora no se puede desarrollar"."""
    nadador = await client.post(
        f"{API}/swimmers/", json={"name": "Nadadora Nueva"},
        headers=como(world.owner_email),
    )
    assert nadador.status_code == 201

    plan = await client.post(f"{API}/plans/", json={
        "name": "Plan del Entrenador", "start_date": "2026-09-07",
        "total_weeks": 12, "total_km": 300,
    }, headers=como(world.owner_email))
    assert plan.status_code == 201

    miembros = await client.get(f"{API}/auth/members", headers=como(world.owner_email))
    assert miembros.status_code == 200


async def test_el_dueno_sigue_siendo_dueno(client, world: World):
    r = await client.patch(
        f"{API}/teams/mine", json={"name": "Club Renombrado"},
        headers=como(world.owner_email),
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Club Renombrado"


async def test_el_coach_asistente_si_hace_cosas_de_coach(client, world: World):
    """Owner y coach se distinguen; asistente no es un rol de segunda."""
    r = await client.post(
        f"{API}/swimmers/", json={"name": "Fichaje del Asistente"},
        headers=como(world.assistant_email),
    )
    assert r.status_code == 201
