"""`Principal.scope_to_own_swimmer` y sus dos modos de fallo.

El helper acota una consulta al nadador propio desde un único sitio, para que
ningún servicio tenga que acordarse de la regla. Tiene dos formas de salir mal y
solo una es evidente:

  · **atleta sin ficha de nadador** — el caso documentado. Falla CERRADO: la
    consulta se vuelve imposible en vez de quedarse sin filtro.

  · **columna de una tabla que no está en el `stmt`** — el caso que la revisión
    independiente encontró el 2026-08-07. SQLAlchemy no protesta: añade la tabla
    al FROM y produce un producto cartesiano, con lo que el filtro deja de
    acotar. Falla ABIERTO.

El segundo no se comprueba en caliente porque cuesta 1,3 ms por consulta
(obliga a compilar el statement). Se comprueba aquí, y `pyproject.toml`
convierte el aviso de producto cartesiano de SQLAlchemy en un fallo de test, así
que cualquier consulta futura que caiga en el mismo error revienta su propio
test en vez de filtrar en silencio.
"""
from __future__ import annotations

import pytest
from conftest import World
from sqlalchemy import select
from sqlalchemy.exc import SAWarning

from app.core.dependencies import Principal
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, Plan, WeeklyPlan
from app.persistencia.tablas.tests_aerobicos import AerobicTest


async def _principal(db, email: str) -> Principal:
    from app.api.v1.auth.service import get_by_email
    from app.core.dependencies import _principal_for

    return await _principal_for(db, await get_by_email(db, email))


# ── El fallo cerrado, el que ya estaba documentado ───────────────────────────

async def test_un_atleta_sin_ficha_no_ve_nada(db, world: World):
    p = await _principal(db, world.huerfano_email)
    assert p.is_athlete and p.swimmer_id is None

    stmt = p.scope_to_own_swimmer(select(AerobicTest), AerobicTest.swimmer_id)
    assert (await db.execute(stmt)).scalars().all() == []


async def test_un_atleta_con_ficha_ve_lo_suyo(db, world: World):
    p = await _principal(db, world.sofia_email)
    stmt = p.scope_to_own_swimmer(select(AerobicTest), AerobicTest.swimmer_id)
    filas = (await db.execute(stmt)).scalars().all()
    assert {f.swimmer_id for f in filas} == {world.sofia_swimmer_id}


async def test_un_entrenador_pasa_sin_acotar(db, world: World):
    p = await _principal(db, world.owner_email)
    assert not p.is_athlete
    stmt = p.scope_to_own_swimmer(select(AerobicTest), AerobicTest.swimmer_id)
    filas = (await db.execute(stmt)).scalars().all()
    assert len({f.swimmer_id for f in filas}) > 1


# ── El fallo abierto, el que encontró la revisión ────────────────────────────

async def test_una_columna_ajena_al_stmt_revienta_en_vez_de_filtrar(db, world: World):
    """**El test que cierra TODO-12.**

    `Swimmer.id` no pertenece a `select(AerobicTest)`. Antes de que
    `pyproject.toml` convirtiera el aviso en error, esta consulta devolvía los
    12 tests del club para una atleta que solo debía ver 2.
    """
    p = await _principal(db, world.sofia_email)
    mal = p.scope_to_own_swimmer(select(AerobicTest), Swimmer.id)  # <- columna ajena

    with pytest.raises(SAWarning, match="cartesian product"):
        await db.execute(mal)


async def test_el_aviso_esta_configurado_como_error(db, world: World):
    """Sin esta configuración el test de arriba pasaría sin comprobar nada.

    Un `pytest.raises` sobre un aviso que nadie convierte en excepción no falla:
    simplemente no se lanza. Este test fija la configuración misma.
    """
    import warnings

    filtros = [f for f in warnings.filters if f[0] == "error"]
    assert any(
        f[1] is not None and "cartesian" in f[1].pattern for f in filtros
    ), "pyproject.toml dejó de convertir el producto cartesiano en error"


# ── Las cinco llamadas reales pasan una columna que sí pertenece ─────────────

@pytest.mark.parametrize(("nombre", "construir"), [
    ("swimmers.list", lambda p: p.scope_to_own_swimmer(select(Swimmer), Swimmer.id)),
    ("aerobic_tests", lambda p: p.scope_to_own_swimmer(
        select(AerobicTest), AerobicTest.swimmer_id)),
    ("plans.get_week", lambda p: p.scope_to_own_swimmer(
        select(WeeklyPlan)
        .join(AthleteEvent, AthleteEvent.id == WeeklyPlan.athlete_event_id)
        .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
        .join(Plan, Plan.id == AthletePlan.plan_id),
        AthletePlan.swimmer_id)),
    ("plans.get_event", lambda p: p.scope_to_own_swimmer(
        select(AthleteEvent)
        .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
        .join(Plan, Plan.id == AthletePlan.plan_id),
        AthletePlan.swimmer_id)),
    ("dashboard.events", lambda p: p.scope_to_own_swimmer(
        select(AthleteEvent)
        .join(AthletePlan, AthleteEvent.athlete_plan_id == AthletePlan.id),
        AthletePlan.swimmer_id)),
])
async def test_las_llamadas_reales_no_producen_producto_cartesiano(
    db, world: World, nombre, construir,
):
    """Una por cada forma de consulta que el código acota hoy."""
    p = await _principal(db, world.sofia_email)
    await db.execute(construir(p))  # revienta si hay producto cartesiano
