"""La segunda frontera: dentro del club, un atleta solo ve y toca lo suyo.

La frontera entre clubes (`team_id`) lleva desde el principio y es sólida: FKs
compuestas reales, `visible_to`, 404 en vez de 403. La de dentro del club **no
existía**. Verificado en vivo contra la base de datos el 2026-08-06:

    Sofía (atleta, swimmer_id=1, inscrita en el plan 1 junto a otros 7)
      list_swimmers               -> 8 nadadores del club     (debería ser 1)
      list_tests                  -> 12 tests, 10 de otros
      get_week(semana de Carlos)  -> DEVUELVE LA SEMANA
      update_week(semana de Carlos, real_time=999)
          real_time antes=128.57  después=999.0     ESCRITURA AJENA ACEPTADA

Escribir el tiempo de otro no es un dato feo en una tabla: dispara
`_recalculate_event`, que le reescribe la curva de progresión entera. El plan de
entrenamiento de una persona, borrado por un compañero.

**Regla de todo el archivo: recurso ajeno = 404, nunca 403.** Un 403 confirmaría
que ese id existe, que es justo lo que no se quiere filtrar.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.modules.plans.models import WeeklyPlan
from conftest import API, World, como


async def semana_de(db, event_id: int, numero: int = 2) -> WeeklyPlan:
    return (await db.execute(
        select(WeeklyPlan).where(
            WeeklyPlan.athlete_event_id == event_id, WeeklyPlan.week_number == numero,
        )
    )).scalar_one()


# ── Las cuatro escrituras ajenas confirmadas en vivo ─────────────────────────

async def test_no_puede_escribir_la_semana_de_otro(client, db, world: World):
    """**El crítico.** Era la vía para borrarle a un compañero su plan entero."""
    semana = await semana_de(db, world.carlos_event_id)
    antes = semana.expected_time

    r = await client.patch(
        f"{API}/plans/weeks/{semana.id}", json={"real_time": 999.0},
        headers=como(world.sofia_email),
    )

    assert r.status_code == 404
    await db.refresh(semana)
    assert semana.real_time is None, "el tiempo ajeno se escribió de todos modos"
    assert semana.expected_time == antes, "la curva ajena se recalculó"


async def test_no_puede_leer_la_semana_de_otro(client, world: World):
    r = await client.get(
        f"{API}/plans/events/{world.carlos_event_id}/weeks",
        headers=como(world.sofia_email),
    )
    assert r.status_code == 404


async def test_no_puede_crear_un_test_a_nombre_de_otro(client, db, world: World):
    from app.modules.aerobic_tests.models import AerobicTest

    r = await client.post(f"{API}/aerobic-tests/", json={
        "swimmer_id": world.carlos_swimmer_id, "plan_id": world.plan_id,
        "test_type": "DIRECT", "test_date": "2026-08-06", "direct_per100": 60.0,
    }, headers=como(world.sofia_email))

    assert r.status_code == 404
    de_carlos = (await db.execute(
        select(AerobicTest).where(AerobicTest.swimmer_id == world.carlos_swimmer_id)
    )).scalars().all()
    assert len(de_carlos) == 1, "se creó un test a nombre de Carlos"


async def test_no_puede_borrar_el_test_de_otro(client, db, world: World):
    from app.modules.aerobic_tests.models import AerobicTest

    r = await client.delete(
        f"{API}/aerobic-tests/{world.carlos_test_id}", headers=como(world.sofia_email),
    )

    assert r.status_code == 404
    test = await db.get(AerobicTest, world.carlos_test_id)
    assert test is not None and test.is_active, "el test ajeno se dio de baja igual"


# ── Lecturas: solo lo suyo ───────────────────────────────────────────────────

async def test_solo_ve_su_propia_ficha_de_nadador(client, world: World):
    r = await client.get(f"{API}/swimmers/", headers=como(world.sofia_email))
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == [world.sofia_swimmer_id]


async def test_la_ficha_de_otro_no_existe_para_el(client, world: World):
    r = await client.get(
        f"{API}/swimmers/{world.carlos_swimmer_id}", headers=como(world.sofia_email),
    )
    assert r.status_code == 404


async def test_solo_ve_sus_propios_tests_aerobicos(client, world: World):
    r = await client.get(f"{API}/aerobic-tests/", headers=como(world.sofia_email))
    assert [t["id"] for t in r.json()] == [world.sofia_test_id]


async def test_el_test_de_otro_no_existe_para_el(client, world: World):
    r = await client.get(
        f"{API}/aerobic-tests/{world.carlos_test_id}", headers=como(world.sofia_email),
    )
    assert r.status_code == 404


async def test_el_filtro_por_swimmer_id_no_es_una_puerta_trasera(client, world: World):
    """Pedir explícitamente los tests de otro no los devuelve.

    El endpoint acepta `?swimmer_id=`, así que sin acotar por sesión bastaba con
    escribir el número del compañero en la barra de direcciones.
    """
    r = await client.get(
        f"{API}/aerobic-tests/?swimmer_id={world.carlos_swimmer_id}",
        headers=como(world.sofia_email),
    )
    assert r.json() == []


async def test_el_dashboard_solo_trae_sus_filas(client, world: World):
    r = await client.get(f"{API}/dashboard/summary", headers=como(world.sofia_email))
    assert r.status_code == 200
    assert [f["swimmer_id"] for f in r.json()["statuses"]] == [world.sofia_swimmer_id]


async def test_la_tabla_del_equipo_esta_fuera_de_su_alcance(client, world: World):
    """`/dashboard/team-week` es la puerta más ancha: nombres y tiempos de todos.

    403 y no una versión acotada: una tabla comparativa del equipo con una sola
    fila no es la versión personal de nada. El plan la marca ❌ explícito para el
    atleta, así que el backend lo dice en vez de fingir una pantalla.
    """
    r = await client.get(f"{API}/dashboard/team-week", headers=como(world.sofia_email))
    assert r.status_code == 403


async def test_el_entrenador_si_ve_la_tabla_del_equipo(client, world: World):
    r = await client.get(f"{API}/dashboard/team-week", headers=como(world.owner_email))
    assert r.status_code == 200
    assert len(r.json()["rows"]) == 3


# ── Autorización por campo: el parón es del entrenador ───────────────────────

async def test_no_puede_parar_su_propia_semana(client, db, world: World):
    """Su semana, sí; su curva de progresión, no.

    Desde que el filtro por nadador existe la fila ES suya, así que sin una
    comprobación por campo escribir `disabled` pasaría a ser legítimo. Y el
    parón no registra un resultado: redistribuye la mejora restante del
    macrociclo entero vía `_recalculate_event`.
    """
    semana = await semana_de(db, world.sofia_event_id)

    r = await client.patch(
        f"{API}/plans/weeks/{semana.id}",
        json={"disabled": True, "disable_reason": "me lo salto"},
        headers=como(world.sofia_email),
    )

    assert r.status_code == 403
    await db.refresh(semana)
    assert semana.disabled is False


async def test_tampoco_puede_reactivar_una_semana_parada(client, db, world: World):
    """`{"disabled": false}` es tanto una decisión de entrenamiento como `true`.

    Por eso la comprobación mira los campos *enviados* y no los que traen valor.
    """
    semana = await semana_de(db, world.sofia_event_id)
    semana.disabled = True
    await db.commit()

    r = await client.patch(
        f"{API}/plans/weeks/{semana.id}", json={"disabled": False},
        headers=como(world.sofia_email),
    )
    assert r.status_code == 403


async def test_el_entrenador_si_puede_parar_una_semana(client, db, world: World):
    semana = await semana_de(db, world.sofia_event_id)
    r = await client.patch(
        f"{API}/plans/weeks/{semana.id}",
        json={"disabled": True, "disable_reason": "lesión de hombro"},
        headers=como(world.owner_email),
    )
    assert r.status_code == 200
    await db.refresh(semana)
    assert semana.disabled is True
    assert semana.disable_reason == "lesión de hombro"


async def test_el_macrociclo_no_le_ensena_el_roster(client, world: World):
    """Ve su plan, pero no con quién lo comparte."""
    r = await client.get(f"{API}/plans/{world.plan_id}", headers=como(world.sofia_email))
    assert r.status_code == 200
    assert [a["swimmer_id"] for a in r.json()["athletes"]] == [world.sofia_swimmer_id]


# ── Lo propio sigue funcionando ──────────────────────────────────────────────

async def test_puede_registrar_su_propio_tiempo(client, db, world: World):
    """El scoping no puede convertirse en "el atleta no puede hacer nada"."""
    semana = await semana_de(db, world.sofia_event_id)

    r = await client.patch(
        f"{API}/plans/weeks/{semana.id}", json={"real_time": 131.5},
        headers=como(world.sofia_email),
    )

    assert r.status_code == 200
    await db.refresh(semana)
    assert semana.real_time == 131.5


async def test_puede_leer_sus_propias_semanas(client, world: World):
    r = await client.get(
        f"{API}/plans/events/{world.sofia_event_id}/weeks",
        headers=como(world.sofia_email),
    )
    assert r.status_code == 200
    assert len(r.json()) == 12


async def test_puede_crear_y_borrar_sus_propios_tests(client, world: World):
    creado = await client.post(f"{API}/aerobic-tests/", json={
        "swimmer_id": world.sofia_swimmer_id, "plan_id": world.plan_id,
        "test_type": "DIRECT", "test_date": "2026-08-06", "direct_per100": 74.0,
    }, headers=como(world.sofia_email))
    assert creado.status_code == 201

    borrado = await client.delete(
        f"{API}/aerobic-tests/{creado.json()['id']}", headers=como(world.sofia_email),
    )
    assert borrado.status_code == 204


# ── El entrenador sigue viéndolo todo ────────────────────────────────────────

async def test_el_entrenador_no_queda_acotado(client, world: World):
    """El arreglo no puede tocar al entrenador: su trabajo es ver a todo el mundo."""
    swimmers = await client.get(f"{API}/swimmers/", headers=como(world.owner_email))
    assert len(swimmers.json()) == 3

    tests = await client.get(f"{API}/aerobic-tests/", headers=como(world.owner_email))
    assert len(tests.json()) == 2

    semanas = await client.get(
        f"{API}/plans/events/{world.carlos_event_id}/weeks",
        headers=como(world.owner_email),
    )
    assert semanas.status_code == 200

    resumen = await client.get(f"{API}/dashboard/summary", headers=como(world.owner_email))
    assert len(resumen.json()["statuses"]) == 3


async def test_el_entrenador_si_puede_escribir_la_semana_de_un_atleta(client, db, world: World):
    semana = await semana_de(db, world.carlos_event_id)
    r = await client.patch(
        f"{API}/plans/weeks/{semana.id}", json={"real_time": 127.0},
        headers=como(world.owner_email),
    )
    assert r.status_code == 200
    await db.refresh(semana)
    assert semana.real_time == 127.0


# ── El modo de fallo cerrado ─────────────────────────────────────────────────

@pytest.mark.parametrize("ruta", [
    "/swimmers/", "/aerobic-tests/",
])
async def test_un_atleta_sin_nadador_ligado_no_ve_nada(client, world: World, ruta):
    """Fail-closed. Sin nadador resuelto, la respuesta es vacío, no "todo".

    Es el modo de fallo que decide si un bug de datos —una cuenta que se quedó
    sin ligar— filtra el club entero o simplemente no enseña nada.
    """
    r = await client.get(f"{API}{ruta}", headers=como(world.huerfano_email))
    assert r.status_code == 200
    assert r.json() == []


async def test_un_atleta_sin_nadador_ligado_tampoco_llega_por_id(client, world: World):
    r = await client.get(
        f"{API}/plans/events/{world.carlos_event_id}/weeks",
        headers=como(world.huerfano_email),
    )
    assert r.status_code == 404


async def test_no_puede_colgar_un_test_de_un_macrociclo_que_no_ve(client, db, world: World):
    """El `plan_id` del cuerpo pesa tanto como el `swimmer_id`.

    La FK compuesta solo impide cruzar EQUIPOS, no cruzar macrociclos dentro del
    equipo. Sin comprobarlo, una atleta que recibe 404 en `GET /plans/{otro}`
    podía colgar un test suyo de ese macrociclo y aparecer en la lista del
    entrenador que sí lo lleva.
    """
    otro = await client.post(f"{API}/plans/", json={
        "name": "Macrociclo Ajeno", "start_date": "2026-09-07",
        "total_weeks": 12, "total_km": 300,
    }, headers=como(world.owner_email))
    assert otro.status_code == 201
    otro_id = otro.json()["id"]

    # Sofía no está inscrita en ese macrociclo, así que para ella no existe.
    assert (await client.get(
        f"{API}/plans/{otro_id}", headers=como(world.sofia_email),
    )).status_code == 404

    r = await client.post(f"{API}/aerobic-tests/", json={
        "swimmer_id": world.sofia_swimmer_id, "plan_id": otro_id,
        "test_type": "DIRECT", "test_date": "2026-08-07", "direct_per100": 74.0,
    }, headers=como(world.sofia_email))
    assert r.status_code == 404

    del_otro = await client.get(
        f"{API}/aerobic-tests/?plan_id={otro_id}", headers=como(world.owner_email),
    )
    assert del_otro.json() == [], "el test se coló en el macrociclo ajeno"


async def test_puede_colgar_un_test_del_macrociclo_en_el_que_si_esta(client, world: World):
    r = await client.post(f"{API}/aerobic-tests/", json={
        "swimmer_id": world.sofia_swimmer_id, "plan_id": world.plan_id,
        "test_type": "DIRECT", "test_date": "2026-08-07", "direct_per100": 74.0,
    }, headers=como(world.sofia_email))
    assert r.status_code == 201


async def test_un_atleta_sin_ficha_no_ve_ningun_macrociclo(client, world: World):
    """`visible_to` deriva el nadador del `Principal`, que puede no tener ninguno.

    Antes lo derivaba por su cuenta con `Swimmer.user_id == principal.id`: dos
    funciones respondiendo la misma pregunta con semánticas distintas, que es el
    patrón que produjo el agujero del scoping.
    """
    r = await client.get(f"{API}/plans/", headers=como(world.huerfano_email))
    assert r.status_code == 200
    assert r.json() == []

    uno = await client.get(f"{API}/plans/{world.plan_id}", headers=como(world.huerfano_email))
    assert uno.status_code == 404


async def test_dar_de_baja_la_ficha_no_le_quita_su_historico(client, db, world: World):
    """Dar de baja a un nadador archiva su perfil; no le revoca el acceso.

    Son dos cosas distintas y es fácil confundirlas: revocar el acceso es
    `team_members.is_active`, y ese sí lo comprueba `_principal_for`. Si el
    scoping mirase también `swimmers.is_active`, un atleta dado de baja no
    podría ni consultar sus propios tiempos de las temporadas que sí nadó.
    """
    from app.modules.swimmers.models import Swimmer

    sofia_sw = await db.get(Swimmer, world.sofia_swimmer_id)
    sofia_sw.is_active = False
    await db.commit()

    semanas = await client.get(
        f"{API}/plans/events/{world.sofia_event_id}/weeks",
        headers=como(world.sofia_email),
    )
    assert semanas.status_code == 200
    assert len(semanas.json()) == 12

    tests = await client.get(f"{API}/aerobic-tests/", headers=como(world.sofia_email))
    assert [t["id"] for t in tests.json()] == [world.sofia_test_id]

    # Pero desaparece de los listados, que es lo que "dar de baja" significa.
    listado = await client.get(f"{API}/swimmers/", headers=como(world.owner_email))
    assert world.sofia_swimmer_id not in [s["id"] for s in listado.json()]
