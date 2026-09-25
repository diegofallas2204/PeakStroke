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

    from app.persistencia.tablas.usuarios import User

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


# ── R4: borrar el macro y cambiar su meta son de dueño ───────────────────────
#
# `plan_coaches` decide quién VE un macrociclo, no quién puede hacerlo
# desaparecer ni moverle el objetivo. Hasta el 2026-09-24 las dos rutas pedían
# solo `require_coach`, así que el asistente borraba el macro que llevaba.

async def _macro_del_asistente(client, world: World) -> int:
    r = await client.post(f"{API}/plans/", json={
        "name": "Macro del Asistente", "start_date": "2026-09-07",
        "total_weeks": 12, "total_km": 300, "main_event": "Regional",
    }, headers=como(world.assistant_email))
    assert r.status_code == 201
    return r.json()["id"]


async def test_el_asistente_no_borra_el_macro_que_lleva(client, world: World):
    plan_id = await _macro_del_asistente(client, world)

    r = await client.delete(f"{API}/plans/{plan_id}", headers=como(world.assistant_email))
    assert r.status_code == 403
    # Sigue ahí, y el dueño sí puede.
    assert (await client.get(
        f"{API}/plans/{plan_id}", headers=como(world.assistant_email),
    )).status_code == 200
    r = await client.delete(f"{API}/plans/{plan_id}", headers=como(world.owner_email))
    assert r.status_code == 204


async def test_el_asistente_no_cambia_la_meta_del_macro(client, world: World):
    plan_id = await _macro_del_asistente(client, world)

    r = await client.patch(
        f"{API}/plans/{plan_id}", json={"main_event": "Nacional"},
        headers=como(world.assistant_email),
    )
    assert r.status_code == 403

    r = await client.patch(
        f"{API}/plans/{plan_id}", json={"main_event": "Nacional"},
        headers=como(world.owner_email),
    )
    assert r.status_code == 200
    assert r.json()["main_event"] == "Nacional"


async def test_el_asistente_sigue_editando_lo_demas(client, world: World):
    """El guard mira si la meta CAMBIA, no si viaja: reenviar el formulario
    entero con la misma meta no puede costarle un 403."""
    plan_id = await _macro_del_asistente(client, world)

    r = await client.patch(
        f"{API}/plans/{plan_id}",
        json={"status": "suspended", "notes": "Parón", "main_event": "Regional"},
        headers=como(world.assistant_email),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "suspended"


async def test_el_macro_ajeno_sigue_siendo_404_antes_que_403(client, world: World):
    """El asistente no lleva el macro del mundo: para él no existe. Cambiarle la
    meta tiene que decir eso, no que su rol no alcanza."""
    r = await client.patch(
        f"{API}/plans/{world.plan_id}", json={"main_event": "Otro"},
        headers=como(world.assistant_email),
    )
    assert r.status_code == 404


# ── R5: dos pertenencias activas son un error, no un club al azar ────────────

async def test_principal_falla_con_dos_pertenencias_activas(db, world: World):
    """La `UNIQUE` de `team_members.user_id` impide crear la segunda de verdad,
    así que se simula: la sesión devuelve la consulta de pertenencia duplicada.
    Con `.first()` esto atendía la petición en uno de los dos clubes sin avisar.
    """
    from sqlalchemy import select, union_all
    from sqlalchemy.exc import MultipleResultsFound

    from app.core.dependencies import _principal_for
    from app.persistencia.tablas.usuarios import User

    owner = (await db.execute(
        select(User).where(User.email == world.owner_email)
    )).scalar_one()

    class _SesionQueDuplica:
        def __init__(self, real) -> None:
            self._real = real
            self._primera = True

        async def execute(self, stmt, *args, **kwargs):
            if self._primera:
                self._primera = False
                return await self._real.execute(union_all(stmt, stmt))
            return await self._real.execute(stmt, *args, **kwargs)

    # Con una sola fila, la misma consulta resuelve como siempre.
    assert (await _principal_for(db, owner)).team_id == world.team_id
    with pytest.raises(MultipleResultsFound):
        await _principal_for(_SesionQueDuplica(db), owner)
