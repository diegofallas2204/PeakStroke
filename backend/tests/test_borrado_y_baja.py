"""Nada se borra: se da de baja. Y lo que no se puede borrar, lo dice.

Dos reglas del `CLAUDE.md` que se sostienen mutuamente:

  · **Nada se borra: se da de baja.** El histórico de entrenamiento es el activo
    más valioso de la aplicación. Un test aeróbico es una medición del atleta en
    una fecha concreta: se puede retirar de las listas, pero rehacerla no.

  · **Dar de baja no puede equivaler a borrar.** Si un test retirado no se puede
    ni consultar ni reactivar, la columna `is_active` cumple la regla en la tabla
    y la incumple en la aplicación, que es donde se nota.

Y la consecuencia que la revisión independiente destapó el 2026-08-07: desde que
los tests se dan de baja en vez de borrarse, sus filas **nunca** salen de
`aerobic_tests`, así que un macrociclo con tests pasó a ser indestructible — y
`DELETE /plans/{id}` devolvía un 500 con una traza en vez de explicarlo.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.modules.aerobic_tests.models import AerobicSplit, AerobicTest
from conftest import API, World, como


# ── Dar de baja conserva el dato ─────────────────────────────────────────────

async def test_dar_de_baja_un_test_no_borra_la_fila(client, db, world: World):
    r = await client.delete(
        f"{API}/aerobic-tests/{world.sofia_test_id}", headers=como(world.owner_email),
    )
    assert r.status_code == 204

    fila = await db.get(AerobicTest, world.sofia_test_id)
    assert fila is not None, "el test se borró de verdad"
    assert fila.is_active is False
    assert fila.avg_per100 is not None, "la medición sigue ahí"


async def test_los_parciales_sobreviven_a_la_baja(client, db, world: World):
    """Un T30 son 30 mediciones. El borrado físico se las llevaba todas."""
    creado = await client.post(f"{API}/aerobic-tests/", json={
        "swimmer_id": world.sofia_swimmer_id, "test_type": "T30",
        "test_date": "2026-08-07", "splits": [75.0 + i * 0.1 for i in range(30)],
    }, headers=como(world.owner_email))
    assert creado.status_code == 201
    test_id = creado.json()["id"]

    await client.delete(f"{API}/aerobic-tests/{test_id}", headers=como(world.owner_email))

    parciales = (await db.execute(
        select(func.count()).select_from(AerobicSplit).where(AerobicSplit.test_id == test_id)
    )).scalar_one()
    assert parciales == 30


async def test_un_test_de_baja_desaparece_de_los_listados(client, world: World):
    await client.delete(
        f"{API}/aerobic-tests/{world.sofia_test_id}", headers=como(world.owner_email),
    )
    listado = await client.get(f"{API}/aerobic-tests/", headers=como(world.owner_email))
    assert world.sofia_test_id not in [t["id"] for t in listado.json()]


async def test_pero_se_puede_pedir_y_reactivar(client, world: World):
    """**El test que cierra TODO-13.**

    Si un test retirado no se pudiera ni consultar, `set_active(..., True)`
    sería código muerto y "dar de baja" sería un borrado con otro nombre.
    """
    await client.delete(
        f"{API}/aerobic-tests/{world.sofia_test_id}", headers=como(world.owner_email),
    )

    ficha = await client.get(
        f"{API}/aerobic-tests/{world.sofia_test_id}", headers=como(world.owner_email),
    )
    assert ficha.status_code == 200, "no se puede ni mirar lo que se retiró"

    con_bajas = await client.get(
        f"{API}/aerobic-tests/?include_inactive=true", headers=como(world.owner_email),
    )
    assert world.sofia_test_id in [t["id"] for t in con_bajas.json()]

    vuelta = await client.post(
        f"{API}/aerobic-tests/{world.sofia_test_id}/reactivate",
        headers=como(world.owner_email),
    )
    assert vuelta.status_code == 200

    listado = await client.get(f"{API}/aerobic-tests/", headers=como(world.owner_email))
    assert world.sofia_test_id in [t["id"] for t in listado.json()]


async def test_reactivar_es_cosa_del_entrenador(client, world: World):
    """Retirar el propio test es una corrección; rescatarlo, una decisión."""
    await client.delete(
        f"{API}/aerobic-tests/{world.sofia_test_id}", headers=como(world.sofia_email),
    )
    r = await client.post(
        f"{API}/aerobic-tests/{world.sofia_test_id}/reactivate",
        headers=como(world.sofia_email),
    )
    assert r.status_code == 403


async def test_un_atleta_no_ve_las_bajas_ajenas_ni_pidiendolas(client, world: World):
    """`include_inactive` filtra dentro de lo visible; nunca lo amplía."""
    await client.delete(
        f"{API}/aerobic-tests/{world.carlos_test_id}", headers=como(world.owner_email),
    )
    r = await client.get(
        f"{API}/aerobic-tests/?include_inactive=true", headers=como(world.sofia_email),
    )
    assert world.carlos_test_id not in [t["id"] for t in r.json()]


# ── Borrar un macrociclo con tests: 409, no 500 ──────────────────────────────

async def test_borrar_un_macrociclo_con_tests_lo_explica(client, world: World):
    """**El test que cierra TODO-9.**

    Antes: `sqlite3.IntegrityError: FOREIGN KEY constraint failed` → 500 con
    traza. Y el fallo dependía del dato, así que aparecía en producción y no al
    desarrollar.
    """
    r = await client.delete(f"{API}/plans/{world.plan_id}", headers=como(world.owner_email))

    assert r.status_code == 409
    detalle = r.json()["detail"]
    assert "2" in detalle, "el mensaje no dice cuántos tests lo impiden"
    assert "test" in detalle.lower()


async def test_un_macrociclo_sin_tests_se_borra(client, db, world: World):
    from app.modules.plans.models import Plan

    nuevo = await client.post(f"{API}/plans/", json={
        "name": "Macrociclo Vacío", "start_date": "2026-09-07",
        "total_weeks": 12, "total_km": 300,
    }, headers=como(world.owner_email))
    plan_id = nuevo.json()["id"]

    r = await client.delete(f"{API}/plans/{plan_id}", headers=como(world.owner_email))
    assert r.status_code == 204
    assert await db.get(Plan, plan_id) is None


async def test_dar_de_baja_los_tests_no_desbloquea_el_borrado(client, world: World):
    """La baja lógica no saca la fila de la tabla, y la FK mira filas.

    Es la consecuencia incómoda de TODO-7 y merece estar fijada: quien lea el
    mensaje de error va a intentar exactamente esto.
    """
    for test_id in (world.sofia_test_id, world.carlos_test_id):
        await client.delete(f"{API}/aerobic-tests/{test_id}", headers=como(world.owner_email))

    r = await client.delete(f"{API}/plans/{world.plan_id}", headers=como(world.owner_email))
    assert r.status_code == 409
