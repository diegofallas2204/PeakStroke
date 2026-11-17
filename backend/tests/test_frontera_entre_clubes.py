"""TODO-2: la frontera ENTRE clubes, ruta por ruta (2026-11-16).

Es la promesa más cara del producto: nada de un club se ve ni se toca desde
otro. Hasta hoy había tests sueltos; este archivo **barre todas las rutas** del
API (las saca de `app.openapi()`, así que una ruta nueva entra sola) con tres
comprobaciones:

1. **Un id del otro club responde exactamente igual que uno que no existe**
   —mismo código y mismo cuerpo— y nunca con éxito. Ni siquiera se filtra que
   el recurso existe (la regla del 404 y no 403).
2. **Ninguna respuesta lleva la marca** con la que se crean los datos del otro
   club (`ZETA`), por ninguna puerta: listado, id directo, filtro por query o id
   en el cuerpo.
3. **Los datos del otro club siguen intactos** después del barrido: cada
   escritura con sus ids (borrar, editar, reactivar, apuntar) se comprueba
   contra una foto tomada antes.

El club ajeno se monta **por el API**, como lo haría su entrenador, y el
barrido se hace como la dueña del club A (lo máximo que se puede ser) y como una
atleta de A.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from conftest import API, PASSWORD, World, como

from app.api.v1.auth.schemas import UserCreate
from app.api.v1.auth.service import create_user
from app.main import app
from app.persistencia.repositorios import RepositorioDeEquipos

MARCA = "ZETA"
INEXISTENTE = 987_654
CORREO_B = "dueno.zeta@otro.dev"

# Rutas que no se barren, cada una con su porqué.
EXCLUIDAS = {
    # Lista TODAS las cuentas a propósito: es el conmutador de desarrollo, y con
    # el login encendido responde 404 (`test_dev_identity.py`).
    ("GET", "/api/v1/auth/dev-identities"),
    # Sin ids ni datos de nadie: login, refresh, salir y la salud del servidor.
    ("POST", "/api/v1/auth/login"), ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"), ("POST", "/api/v1/auth/logout-all"),
    ("GET", "/health"),
}


async def _club_ajeno(db, client) -> dict:
    """El club B, completo y montado por su entrenador a través del API."""
    equipo = await RepositorioDeEquipos(db).crear(f"{MARCA} Club Ajeno")
    dueno = await create_user(db, UserCreate(
        email=CORREO_B, name=f"{MARCA} Entrenador", password=PASSWORD, role="coach",
    ), equipo.id)
    equipo.owner_id = dueno.id
    await db.commit()
    b = como(CORREO_B)

    async def post(ruta: str, cuerpo: dict) -> dict:
        r = await client.post(f"{API}{ruta}", json=cuerpo, headers=b)
        assert r.status_code in (200, 201), (ruta, r.text)
        return r.json()

    nadador = await post("/swimmers/", {"name": f"{MARCA} Nadadora Ajena"})
    atleta = await post("/auth/members", {
        "email": "atleta.zeta@otro.dev", "name": f"{MARCA} Atleta", "role": "athlete",
    })
    lunes = date.today() - timedelta(days=date.today().weekday()) - timedelta(weeks=3)
    plan = await post("/plans/", {
        "name": f"{MARCA} Macro Ajeno", "start_date": lunes.isoformat(),
        "total_weeks": 12, "total_km": 300,
    })
    await post(f"/plans/{plan['id']}/athletes", {
        "swimmer_id": nadador["id"], "aerobic_base": 75.0,
        "events": [{"priority": 1, "distance": 200, "stroke": "libre",
                    "current_time": 130.0, "goal_time": 125.0}],
    })
    plan = (await client.get(f"{API}/plans/{plan['id']}", headers=b)).json()
    inscripcion = plan["athletes"][0]
    evento = inscripcion["events"][0]
    semanas = (await client.get(f"{API}/plans/events/{evento['id']}/weeks", headers=b)).json()
    aerobico = await post("/aerobic-tests/", {
        "swimmer_id": nadador["id"], "plan_id": plan["id"], "test_type": "DIRECT",
        "test_date": lunes.isoformat(), "direct_per100": 75.0, "notes": MARCA,
    })
    lactato = await post("/lactate-tests/", {
        "swimmer_id": nadador["id"], "test_date": lunes.isoformat(), "target_zone": "R1",
        "rep_distance": 400, "reps": [{"swim_time": 300.0, "lactate": 2.5}], "notes": MARCA,
    })
    sesion = await post("/sessions/", {
        "swimmer_id": nadador["id"], "session_date": lunes.isoformat(),
        "distance_m": 4000, "duration_s": 3600, "notes": MARCA,
    })
    codigo = await post("/link-codes/", {"swimmer_id": nadador["id"]})
    return {
        "swimmer_id": nadador["id"], "user_id": atleta["member"]["id"],
        "coach_id": dueno.id, "plan_id": plan["id"],
        "athlete_plan_id": inscripcion["id"], "event_id": evento["id"],
        "week_id": semanas[3]["id"], "session_id": sesion["id"], "code_id": codigo["id"],
        "aerobic_test_id": aerobico["id"], "lactate_test_id": lactato["id"],
    }


async def _foto(client, ids: dict) -> dict:
    """Todo lo del club B, visto por su entrenador."""
    b = como(CORREO_B)
    rutas = [
        f"/swimmers/{ids['swimmer_id']}", "/swimmers/?include_inactive=true",
        f"/plans/{ids['plan_id']}", f"/plans/events/{ids['event_id']}/weeks",
        f"/aerobic-tests/{ids['aerobic_test_id']}", f"/lactate-tests/{ids['lactate_test_id']}",
        f"/sessions/{ids['session_id']}", "/link-codes/", "/auth/members", "/teams/mine",
    ]
    return {r: (await client.get(f"{API}{r}", headers=b)).json() for r in rutas}


def _ids_de_la_ruta(ruta: str, ids: dict) -> dict:
    """Qué id del club B va en cada parámetro de esta ruta."""
    test_id = ids["lactate_test_id"] if "lactate" in ruta else ids["aerobic_test_id"]
    return {**ids, "test_id": test_id}


def _cuerpo(metodo: str, ruta: str, ids_a: dict) -> dict | None:
    """El cuerpo mínimo válido: sin él, el 422 llegaría antes que la frontera."""
    cuerpos = {
        ("PATCH", "/api/v1/auth/members/{user_id}"): {"is_active": False},
        ("PATCH", "/api/v1/plans/weeks/{week_id}"): {"real_time": 100.0},
        ("PATCH", "/api/v1/plans/{plan_id}"): {"name": "secuestrado"},
        ("POST", "/api/v1/plans/{plan_id}/athletes"): {
            "swimmer_id": ids_a["swimmer_id"],
            "events": [{"priority": 1, "distance": 100, "stroke": "libre",
                        "current_time": 70.0, "goal_time": 68.0}],
        },
        ("PATCH", "/api/v1/sessions/{session_id}"): {"distance_m": 1},
        ("PUT", "/api/v1/swimmers/{swimmer_id}"): {"name": "secuestrado"},
        ("PUT", "/api/v1/teams/mine/coaches/{coach_id}/athletes"): {
            "coach_id": 0, "swimmer_ids": [],
        },
    }
    return cuerpos.get((metodo, ruta))


def _rutas_con_ids():
    for ruta, ops in app.openapi()["paths"].items():
        for metodo in ops:
            metodo = metodo.upper()
            if "{" in ruta and (metodo, ruta) not in EXCLUIDAS:
                yield metodo, ruta


async def _pedir(client, metodo: str, ruta: str, cuerpo: dict | None, quien: str):
    return await client.request(metodo, ruta, json=cuerpo, headers=como(quien))


def _rellenar(ruta: str, valores: dict) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(valores[m.group(1)]), ruta)


async def test_ninguna_ruta_con_ids_distingue_lo_ajeno_de_lo_inexistente(client, db, world: World):
    ids_b = await _club_ajeno(db, client)
    antes = await _foto(client, ids_b)
    ids_a = {"swimmer_id": world.sofia_swimmer_id, "plan_id": world.plan_id}
    nada = dict.fromkeys((*ids_b, "test_id"), INEXISTENTE)

    revisadas, fallos = 0, []
    for metodo, ruta in _rutas_con_ids():
        ajeno = _rellenar(ruta, _ids_de_la_ruta(ruta, ids_b))
        inexistente = _rellenar(ruta, nada)
        cuerpo = _cuerpo(metodo, ruta, ids_a)
        if cuerpo and "coach_id" in cuerpo:
            cuerpo = {**cuerpo, "coach_id": ids_b["coach_id"]}
        for quien in (world.owner_email, world.sofia_email):
            r_ajeno = await _pedir(client, metodo, ajeno, cuerpo, quien)
            r_nada = await _pedir(client, metodo, inexistente, cuerpo, quien)
            revisadas += 1
            if r_ajeno.is_success or MARCA in r_ajeno.text:
                fallos.append(f"{metodo} {ruta} como {quien}: {r_ajeno.status_code} {r_ajeno.text[:120]}")
            elif (r_ajeno.status_code, r_ajeno.text) != (r_nada.status_code, r_nada.text):
                fallos.append(
                    f"{metodo} {ruta} como {quien}: ajeno {r_ajeno.status_code} {r_ajeno.text[:80]} "
                    f"≠ inexistente {r_nada.status_code} {r_nada.text[:80]}"
                )
    assert revisadas >= 50, "el barrido no vio las rutas"
    assert not fallos, "Fugas entre clubes:\n  " + "\n  ".join(fallos)
    assert await _foto(client, ids_b) == antes, "Una escritura desde A cambió algo de B"


async def test_mezclar_un_id_propio_con_uno_ajeno_tampoco_pasa(client, db, world: World):
    """La inscripción de B colgada del macrociclo de A."""
    ids_b = await _club_ajeno(db, client)
    antes = await _foto(client, ids_b)
    base = f"{API}/plans/{world.plan_id}/athletes"
    for metodo, sufijo in (("DELETE", ""), ("POST", "/restore")):
        r_ajeno = await client.request(metodo, f"{base}/{ids_b['athlete_plan_id']}{sufijo}",
                                       headers=como(world.owner_email))
        r_nada = await client.request(metodo, f"{base}/{INEXISTENTE}{sufijo}",
                                      headers=como(world.owner_email))
        assert not r_ajeno.is_success
        assert (r_ajeno.status_code, r_ajeno.text) == (r_nada.status_code, r_nada.text)
    assert await _foto(client, ids_b) == antes


async def test_un_id_ajeno_en_el_cuerpo_o_en_la_query_es_como_uno_que_no_existe(
    client, db, world: World,
):
    ids_b = await _club_ajeno(db, client)
    antes = await _foto(client, ids_b)
    hoy = date.today().isoformat()
    a = world.sofia_swimmer_id

    def escrituras(
        nadador: int, plan: int, coach: int, dueno: int, propio: int,
    ) -> list[tuple[str, str, dict]]:
        return [
            ("POST", "/aerobic-tests/", {"swimmer_id": nadador, "test_type": "DIRECT",
                                          "test_date": hoy, "direct_per100": 80.0}),
            ("POST", "/aerobic-tests/", {"swimmer_id": a, "plan_id": plan, "test_type": "DIRECT",
                                          "test_date": hoy, "direct_per100": 80.0}),
            ("POST", "/lactate-tests/", {"swimmer_id": nadador, "test_date": hoy, "target_zone": "R1",
                                          "rep_distance": 400, "reps": [{"swim_time": 300.0}]}),
            ("POST", "/sessions/", {"swimmer_id": nadador, "session_date": hoy,
                                     "distance_m": 1000, "duration_s": 900}),
            ("POST", "/link-codes/", {"swimmer_id": nadador}),
            ("POST", f"/plans/{world.plan_id}/athletes", {
                "swimmer_id": nadador, "events": [{"priority": 1, "distance": 100, "stroke": "libre",
                                                   "current_time": 70.0, "goal_time": 68.0}]}),
            ("PUT", f"/teams/mine/coaches/{coach}/athletes", {"coach_id": coach, "swimmer_ids": [a]}),
            ("PUT", f"/teams/mine/coaches/{propio}/athletes", {"coach_id": propio, "swimmer_ids": [nadador]}),
            ("POST", "/teams/mine/transfer", {"new_owner_id": dueno}),
        ]

    lecturas = [
        "/aerobic-tests/?swimmer_id={s}", "/aerobic-tests/?plan_id={p}",
        "/lactate-tests/?swimmer_id={s}", "/sessions/?swimmer_id={s}",
        "/training-load/{s}", "/dashboard/summary?plan_id={p}",
        "/dashboard/team-week?plan_id={p}",
    ]

    fallos = []
    miembros = (await client.get(f"{API}/auth/members", headers=como(world.owner_email))).json()
    asistente = next(m["id"] for m in miembros if m["email"] == world.assistant_email)
    ajenas = escrituras(ids_b["swimmer_id"], ids_b["plan_id"], ids_b["coach_id"], ids_b["coach_id"], asistente)
    nulas = escrituras(INEXISTENTE, INEXISTENTE, INEXISTENTE, INEXISTENTE, asistente)
    for quien in (world.owner_email, world.sofia_email):
        for (metodo, ruta, ajeno), (_, ruta_nula, nulo) in zip(ajenas, nulas, strict=True):
            r_a = await client.request(metodo, f"{API}{ruta}", json=ajeno, headers=como(quien))
            r_n = await client.request(metodo, f"{API}{ruta_nula}", json=nulo, headers=como(quien))
            if r_a.is_success or MARCA in r_a.text or (r_a.status_code, r_a.text) != (r_n.status_code, r_n.text):
                fallos.append(f"{metodo} {ruta} {ajeno} como {quien}: {r_a.status_code} {r_a.text[:100]}"
                              f" | inexistente {r_n.status_code} {r_n.text[:100]}")
        for plantilla in lecturas:
            r_a = await client.get(f"{API}{plantilla.format(s=ids_b['swimmer_id'], p=ids_b['plan_id'])}",
                                   headers=como(quien))
            r_n = await client.get(f"{API}{plantilla.format(s=INEXISTENTE, p=INEXISTENTE)}",
                                   headers=como(quien))
            if MARCA in r_a.text or (r_a.status_code, r_a.text) != (r_n.status_code, r_n.text):
                fallos.append(f"GET {plantilla} como {quien}: {r_a.status_code} {r_a.text[:100]}"
                              f" | inexistente {r_n.status_code} {r_n.text[:100]}")
    assert not fallos, "Fugas entre clubes:\n  " + "\n  ".join(fallos)
    assert await _foto(client, ids_b) == antes


async def test_ningun_listado_sin_filtro_trae_nada_del_otro_club(client, db, world: World):
    await _club_ajeno(db, client)
    listados = [
        (m.upper(), ruta) for ruta, ops in app.openapi()["paths"].items() for m in ops
        if m == "get" and "{" not in ruta and ("GET", ruta) not in EXCLUIDAS
    ]
    assert len(listados) >= 12
    fallos = []
    for quien in (world.owner_email, world.assistant_email, world.sofia_email, world.huerfano_email):
        for _, ruta in listados:
            r = await client.get(ruta, headers=como(quien))
            if MARCA in r.text:
                fallos.append(f"GET {ruta} como {quien}")
    assert not fallos, "Datos del otro club en un listado:\n  " + "\n  ".join(fallos)


@pytest.mark.parametrize("ruta", ["/auth/dev-identities"])
def test_lo_excluido_esta_escrito(ruta):
    """Cada exclusión del barrido tiene su porqué en `EXCLUIDAS`."""
    assert ("GET", f"{API}{ruta}") in EXCLUIDAS
