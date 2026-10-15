"""C9 punto 4 (REDISENO §5.8): las escrituras de la semana pasan por `Semana`.

La entidad está en `test_semana.py`. Aquí, lo que se ve desde fuera: el parón, el
tiempo real y el recálculo se escriben por `RepositorioDeSemanas`, la curva
ideal no se mueve por ningún camino y `api/v1/macrociclos/semanas.py` ya no
importa ninguna tabla.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from conftest import API, World, como
from sqlalchemy import select

from app.api.v1.auth.service import get_by_email
from app.core.dependencies import _principal_for
from app.dominio.valores import Tiempo
from app.persistencia.repositorios import RepositorioDeMacrociclos, RepositorioDeSemanas
from app.persistencia.tablas.planes import WeeklyPlan
from app.persistencia.tablas.resultados import Result


async def _filas(db, event_id: int) -> list[WeeklyPlan]:
    db.expire_all()
    return list((await db.execute(
        select(WeeklyPlan).where(WeeklyPlan.athlete_event_id == event_id)
        .order_by(WeeklyPlan.week_number)
    )).scalars())


async def _repo(db, email: str) -> RepositorioDeSemanas:
    principal = await _principal_for(db, await get_by_email(db, email))
    return RepositorioDeSemanas(RepositorioDeMacrociclos(db, principal))


def _patch(client, world: World, week_id: int, cuerpo: dict, quien: str | None = None):
    return client.patch(f"{API}/plans/weeks/{week_id}", json=cuerpo,
                        headers=como(quien or world.owner_email))


# ── La curva ideal ───────────────────────────────────────────────────────────


async def test_ni_el_tiempo_ni_el_paron_ni_el_recalculo_mueven_la_curva_ideal(
    client, db, world: World,
):
    antes = await _filas(db, world.carlos_event_id)
    ideal = [f.expected_time for f in antes]
    ids = {f.week_number: f.id for f in antes}

    for cuerpo, semana in [
        ({"real_time": round(ideal[3] * 0.99, 2)}, 4),
        ({"disabled": True, "disable_reason": "Lesión"}, 6),
        ({"real_time": round(ideal[7] * 1.01, 2)}, 8),
        ({"disabled": False}, 6),
        ({"clear_real_time": True}, 8),
    ]:
        r = await _patch(client, world, ids[semana], cuerpo)
        assert r.status_code == 200, r.text
        assert [w["expected_time"] for w in r.json()] == ideal

    despues = await _filas(db, world.carlos_event_id)
    assert [f.expected_time for f in despues] == ideal
    # Queda anclada en la semana 4: de la 5 en adelante hay tiempo recalculado.
    assert [f.recalc_time is not None for f in despues] == [False] * 4 + [True] * 8


async def test_guardar_una_semana_no_escribe_su_tiempo_esperado(db, world: World):
    """Aunque la entidad llegara con otro `esperado`, la base conserva el suyo."""
    repo = await _repo(db, world.owner_email)
    plan = await repo.plan_de(world.carlos_event_id)
    original = plan.semanas[2]
    trucada = type(original)(
        id=original.id, prueba_id=original.prueba_id, numero=original.numero,
        fecha=original.fecha, km_planificados=99.0, esperado=Tiempo(60.0), fase=original.fase,
        recalculado=Tiempo(127.0), deshabilitada=True, razon="Vacaciones",
    )
    await repo.guardar([trucada])

    fila = (await _filas(db, world.carlos_event_id))[2]
    assert (fila.expected_time, fila.planned_km) == (original.esperado.segundos, original.km_planificados)
    assert (fila.recalc_time, fila.disabled, fila.disable_reason) == (127.0, True, "Vacaciones")


# ── El parón ─────────────────────────────────────────────────────────────────


async def test_el_paron_guarda_su_razon_y_reanudar_la_borra(client, db, world: World):
    semana = (await _filas(db, world.carlos_event_id))[5]
    r = await _patch(client, world, semana.id, {"disabled": True, "disable_reason": "Lesión"})
    parada = next(w for w in r.json() if w["id"] == semana.id)
    assert (parada["disabled"], parada["disable_reason"]) == (True, "Lesión")

    r = await _patch(client, world, semana.id, {"disabled": False, "disable_reason": "da igual"})
    libre = next(w for w in r.json() if w["id"] == semana.id)
    assert (libre["disabled"], libre["disable_reason"]) == (False, None)
    fila = (await _filas(db, world.carlos_event_id))[5]
    assert (fila.disabled, fila.disable_reason) == (False, None)


async def test_una_razon_sin_paron_no_para_la_semana(client, db, world: World):
    """`disable_reason` suelto no dice si parar o reanudar: la semana se queda como estaba."""
    semana = (await _filas(db, world.carlos_event_id))[5]
    r = await _patch(client, world, semana.id, {"disable_reason": "solo la razón"})
    assert r.status_code == 200, r.text
    fila = (await _filas(db, world.carlos_event_id))[5]
    assert (fila.disabled, fila.disable_reason) == (False, None)


# ── El tiempo real ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("tiempo", [0, -3, -0.01])
async def test_un_tiempo_que_no_es_positivo_es_un_422(client, db, world: World, tiempo):
    """Hasta C9 llegaba al CHECK de `resultados` y salía como un 500."""
    semana = (await _filas(db, world.carlos_event_id))[2]
    r = await _patch(client, world, semana.id, {"real_time": tiempo})
    assert r.status_code == 422, r.text
    assert (await db.execute(select(Result))).scalars().first() is None


async def test_el_resultado_apuntado_es_del_equipo_de_quien_escribe_y_de_la_prueba(
    client, db, world: World,
):
    semana = (await _filas(db, world.carlos_event_id))[2]
    r = await _patch(client, world, semana.id, {"real_time": 128.4}, world.carlos_email)
    assert r.status_code == 200, r.text
    resultado = (await db.execute(select(Result))).scalars().one()
    assert (resultado.team_id, resultado.swimmer_id) == (world.team_id, world.carlos_swimmer_id)
    assert (resultado.distance, resultado.stroke, resultado.time) == (200, "libre", 128.4)
    assert resultado.result_date == semana.week_date


async def test_el_resultado_de_una_semana_sale_con_el_estilo_canonico(
    client, db, world: World,
):
    """Antes partía de una prueba que guardaba «crol» (fila de antes de C9). Desde
    `c9e1a4d7b2f6` esa fila no puede existir (la migración convirtió los alias y
    un CHECK lo impide): queda lo que importa, que el resultado sale canónico y
    la semana lo encuentra."""
    semana = (await _filas(db, world.carlos_event_id))[2]
    r = await _patch(client, world, semana.id, {"real_time": 128.4})
    assert r.status_code == 200, r.text
    assert next(w for w in r.json() if w["id"] == semana.id)["real_time"] == 128.4
    assert (await db.execute(select(Result))).scalars().one().stroke == "libre"


# ── Lo que enseña la tabla ───────────────────────────────────────────────────


async def test_la_tabla_ensena_cuanto_se_nado_por_encima_o_por_debajo_del_plan(
    client, db, world: World,
):
    """`diff_seconds` y `diff_percent`: positivo es más LENTO que el plan.

    Es el signo contrario al de `Semana.desviacion` (una `Mejora`, positiva si se
    nadó más rápido), y la inversión vive en `semanas._sobre_el_plan`.
    """
    filas = await _filas(db, world.carlos_event_id)
    rapida, lenta, clavada = filas[2], filas[4], filas[6]
    casos = [
        (rapida, round(rapida.expected_time - 2.0, 2), "ahead"),
        (lenta, round(lenta.expected_time + 1.5, 2), "behind"),
        (clavada, clavada.expected_time, "on_track"),
    ]
    for fila, tiempo, _ in casos:
        r = await _patch(client, world, fila.id, {"real_time": tiempo})
        assert r.status_code == 200, r.text

    por_id = {w["id"]: w for w in r.json()}
    for fila, tiempo, estado in casos:
        w = por_id[fila.id]
        assert w["real_time"] == tiempo and w["status"] == estado
        assert w["diff_seconds"] == round(tiempo - fila.expected_time, 2)
        assert w["diff_percent"] == round((tiempo - fila.expected_time) / fila.expected_time * 100, 2)
    assert por_id[rapida.id]["diff_seconds"] < 0 < por_id[lenta.id]["diff_seconds"]
    assert por_id[rapida.id]["diff_percent"] < 0 < por_id[lenta.id]["diff_percent"]
    # Clavar el tiempo esperado es un cero, no un «-0.0» en el JSON.
    assert por_id[clavada.id]["diff_seconds"] == 0.0 and '"diff_seconds":-0.0' not in r.text
    assert por_id[clavada.id]["diff_percent"] == 0.0 and '"diff_percent":-0.0' not in r.text
    # Una semana sin tiempo no enseña ninguna de las tres cosas.
    vacia = por_id[filas[9].id]
    assert (vacia["real_time"], vacia["status"], vacia["diff_seconds"], vacia["diff_percent"]) == (
        None, None, None, None,
    )


# ── El repositorio ───────────────────────────────────────────────────────────


async def test_el_plan_de_una_prueba_esta_acotado(db, world: World):
    async def ve(email: str) -> bool:
        return await (await _repo(db, email)).plan_de(world.carlos_event_id) is not None

    assert await ve(world.owner_email)
    assert await ve(world.carlos_email)
    assert not await ve(world.sofia_email)          # la del compañero, no
    assert not await ve(world.assistant_email)      # no está en plan_coaches


async def test_el_plan_trae_las_semanas_en_orden_y_su_contexto(db, world: World):
    plan = await (await _repo(db, world.owner_email)).plan_de(world.carlos_event_id)
    assert [s.numero for s in plan.semanas] == list(range(1, 13))
    assert plan.inscripcion.atleta_id == plan.atleta.id == world.carlos_swimmer_id
    assert plan.prueba.id == world.carlos_event_id and plan.macro.id == world.plan_id
    assert plan.semana(plan.semanas[4].id) is plan.semanas[4]
    assert plan.semana(-1) is None


async def test_guardar_semanas_ajenas_no_se_salta_en_silencio(db, world: World):
    """Sofía con las semanas de Carlos en la mano: no se escriben, y se nota."""
    de_carlos = await (await _repo(db, world.owner_email)).plan_de(world.carlos_event_id)
    semana = de_carlos.semanas[0]
    semana.parar("no debería")
    with pytest.raises(LookupError):
        await (await _repo(db, world.sofia_email)).guardar([semana])
    assert (await _filas(db, world.carlos_event_id))[0].disabled is False


# ── La estructura ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("archivo", ["semanas.py", "nomina.py", "service.py"])
def test_las_escrituras_del_macrociclo_no_arman_filas_del_orm(archivo: str):
    ruta = Path(__file__).resolve().parent.parent / "app/api/v1/macrociclos" / archivo
    importados: list[str] = []
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            importados += [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados += [f"{nodo.module}.{alias.name}" for alias in nodo.names]
    assert importados, "no se leyó ningún import: el test estaría pasando en vacío"
    assert not [m for m in importados if m.startswith("app.persistencia.tablas")]
