"""C6: el tiempo nadado es del atleta, no del plan.

Lo que fija este archivo, en el orden en que importa:

  1. **Sacar a un atleta de un macrociclo —y borrar el macrociclo— no toca sus
     tiempos.** Es lo que el cambio hace posible: antes la baja lógica de la
     inscripción era lo único que los protegía, y un macro sin tests aeróbicos se
     borraba con los tiempos de todo el equipo dentro.
  2. **La semana no guarda el tiempo: promedia los que caen en ella.** Uno,
     varios y ninguno son el mismo camino (R2 enmendada, §10.2).
  3. **Solo reancla la curva lo que cae en una semana del plan.** Un resultado
     de otra fecha u otra prueba es histórico y no toca la predicción. Uno de
     otra piscina SÍ entra, convertido con el factor corta/larga del motor.
  4. **El contrato del API no cambia**: `PATCH /weeks/{id}` sigue fijando *el*
     tiempo de la semana, y `real_time` sigue saliendo donde salía.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from conftest import API, World, como
from sqlalchemy import func, select

from app.dominio.entidades import Resultado, de_la_semana, promedio, real_de_la_semana
from app.dominio.valores import Piscina, Prueba, Tiempo
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, WeeklyPlan
from app.persistencia.tablas.resultados import Result

LUNES = date(2026, 9, 7)
P200 = Prueba(200, "libre")


def _r(segundos: float, fecha: date = LUNES, *, atleta: int = 1, prueba: Prueba = P200,
       piscina: Piscina = Piscina.LARGA) -> Resultado:
    return Resultado(atleta_id=atleta, prueba=prueba, tiempo=Tiempo(segundos),
                     fecha=fecha, piscina=piscina)


def _real(resultados: list[Resultado]) -> Tiempo | None:
    return real_de_la_semana(resultados, atleta_id=1, prueba=P200,
                             piscina=Piscina.LARGA, lunes=LUNES)


# ── Dominio: qué cae en una semana y cuánto vale ─────────────────────────────

@pytest.mark.parametrize(("tiempos", "esperado"), [
    ([], None), ([128.0], 128.0), ([128.0, 130.0], 129.0), ([127.0, 128.0, 132.0], 129.0),
])
def test_uno_varios_y_ninguno_son_el_mismo_promedio(tiempos, esperado):
    real = promedio((_r(t) for t in tiempos), Piscina.LARGA)
    assert (real.segundos if real else None) == esperado


def test_la_semana_va_de_lunes_a_domingo():
    dentro = [_r(128.0, LUNES), _r(130.0, LUNES + timedelta(days=6))]
    fuera = [_r(100.0, LUNES - timedelta(days=1)), _r(100.0, LUNES + timedelta(days=7))]
    assert _real(dentro + fuera) == Tiempo(129.0)


def test_otra_prueba_u_otro_atleta_no_entran():
    ajenos = [_r(60.0, prueba=Prueba(100, "libre")), _r(120.0, atleta=2)]
    assert de_la_semana(ajenos, atleta_id=1, prueba=P200, lunes=LUNES) == []
    assert _real(ajenos) is None


# Ratio corta/larga de medio fondo (200 m), calibrado con el pool el 2026-06-13.
_FACTOR_200 = 0.979


def test_en_su_piscina_el_tiempo_no_se_toca():
    assert _r(128.0).tiempo_en(Piscina.LARGA) == Tiempo(128.0)
    assert _r(125.0, piscina=Piscina.CORTA).tiempo_en(Piscina.CORTA) == Tiempo(125.0)


def test_un_tiempo_en_corta_entra_convertido_a_larga_y_viceversa():
    corta = _r(125.0, piscina=Piscina.CORTA)
    assert corta.tiempo_en(Piscina.LARGA).segundos == pytest.approx(125.0 / _FACTOR_200)
    assert _r(128.0).tiempo_en(Piscina.CORTA).segundos == pytest.approx(128.0 * _FACTOR_200)
    # Ida y vuelta: la conversión no pierde nada.
    ida = _r(corta.tiempo_en(Piscina.LARGA).segundos)
    assert ida.tiempo_en(Piscina.CORTA).segundos == pytest.approx(125.0)


def test_el_promedio_mezcla_piscinas_ya_convertidas():
    mezcla = [_r(128.0), _r(128.0 * _FACTOR_200, piscina=Piscina.CORTA)]
    assert _real(mezcla).segundos == pytest.approx(128.0)


def test_el_factor_depende_del_perfil_de_la_prueba():
    """Un 50 es velocidad (0,982); un 1500, fondo (0,968)."""
    p50, p1500 = Prueba(50, "libre"), Prueba(1500, "libre")
    r50 = _r(25.0, prueba=p50, piscina=Piscina.CORTA)
    r1500 = _r(900.0, prueba=p1500, piscina=Piscina.CORTA)
    assert r50.tiempo_en(Piscina.LARGA).segundos == pytest.approx(25.0 / 0.982)
    assert r1500.tiempo_en(Piscina.LARGA).segundos == pytest.approx(900.0 / 0.968)


def test_el_estilo_crudo_es_la_misma_prueba():
    """`"crol"` sigue guardado en filas viejas; tiene que casar con `"libre"`."""
    assert _real([_r(128.0, prueba=Prueba(200, "crol"))]) == Tiempo(128.0)


# ── Helpers de API ───────────────────────────────────────────────────────────

async def _semana(db, event_id: int, numero: int) -> WeeklyPlan:
    return (await db.execute(select(WeeklyPlan).where(
        WeeklyPlan.athlete_event_id == event_id, WeeklyPlan.week_number == numero,
    ))).scalar_one()


async def _resultados_de(db, swimmer_id: int, *, vivos: bool = True) -> list[Result]:
    stmt = select(Result).where(Result.swimmer_id == swimmer_id)
    if vivos:
        stmt = stmt.where(Result.is_active.is_(True))
    return list((await db.execute(stmt)).scalars())


async def _apuntar(client, world: World, week_id: int, cuerpo: dict) -> list[dict]:
    r = await client.patch(f"{API}/plans/weeks/{week_id}", json=cuerpo,
                           headers=como(world.owner_email))
    assert r.status_code == 200, r.text
    return r.json()


async def _semanas(client, world: World, event_id: int) -> dict[int, dict]:
    r = await client.get(f"{API}/plans/events/{event_id}/weeks",
                         headers=como(world.owner_email))
    assert r.status_code == 200
    return {w["week_number"]: w for w in r.json()}


def _meter(db, world: World, segundos: float, fecha: date, **extra) -> None:
    db.add(Result(
        team_id=world.team_id, swimmer_id=world.carlos_swimmer_id,
        distance=extra.get("distance", 200), stroke="libre", time=segundos,
        result_date=fecha, pool=extra.get("pool", "50"), context="control",
    ))


# ── 1. Lo que este cambio hace posible ───────────────────────────────────────

async def test_sacar_al_atleta_y_borrar_el_macro_no_toca_sus_tiempos(client, db, world: World):
    """**El test de C6.** Antes, la baja lógica era el único dique; y
    `DELETE /plans/{id}` sin tests aeróbicos se llevaba los tiempos en cascada."""
    semana = await _semana(db, world.carlos_event_id, 2)
    await _apuntar(client, world, semana.id, {"real_time": 128.0})
    assert [r.time for r in await _resultados_de(db, world.carlos_swimmer_id)] == [128.0]

    ap_id = (await db.execute(select(AthletePlan.id).where(
        AthletePlan.plan_id == world.plan_id,
        AthletePlan.swimmer_id == world.carlos_swimmer_id,
    ))).scalar_one()
    r = await client.delete(f"{API}/plans/{world.plan_id}/athletes/{ap_id}",
                            headers=como(world.owner_email))
    assert r.status_code == 204
    assert [r.time for r in await _resultados_de(db, world.carlos_swimmer_id)] == [128.0]

    # Un macro nuevo, sin tests aeróbicos: el que se borraba limpio.
    nuevo = await client.post(f"{API}/plans/", json={
        "name": "Macro que se borra", "start_date": (LUNES + timedelta(weeks=20)).isoformat(),
        "total_weeks": 12, "total_km": 300,
    }, headers=como(world.owner_email))
    plan_id = nuevo.json()["id"]
    r = await client.post(f"{API}/plans/{plan_id}/athletes", json={
        "swimmer_id": world.carlos_swimmer_id, "aerobic_base": 75.0,
        "events": [{"priority": 1, "distance": 200, "stroke": "libre",
                    "current_time": 130.0, "goal_time": 125.0}],
    }, headers=como(world.owner_email))
    assert r.status_code == 201, r.text
    # De la base y no de la respuesta: con la sesión compartida del harness, el
    # `Plan` recién creado puede salir del identity map con la nómina vacía.
    evento = (await db.execute(
        select(AthleteEvent.id).join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
        .where(AthletePlan.plan_id == plan_id)
    )).scalar_one()
    await _apuntar(client, world, (await _semana(db, evento, 1)).id, {"real_time": 127.5})

    r = await client.delete(f"{API}/plans/{plan_id}", headers=como(world.owner_email))
    assert r.status_code == 204
    tiempos = sorted(r.time for r in await _resultados_de(db, world.carlos_swimmer_id))
    assert tiempos == [127.5, 128.0], "borrar el macrociclo se llevó los tiempos"


# ── 2. El contrato de PATCH /weeks, sobre resultados ─────────────────────────

async def test_apuntar_crea_un_resultado_y_mantiene_la_sombra(client, db, world: World):
    semana = await _semana(db, world.carlos_event_id, 2)
    await _apuntar(client, world, semana.id, {"real_time": 128.0})

    [r] = await _resultados_de(db, world.carlos_swimmer_id)
    assert (r.time, r.result_date, r.pool, r.context) == (128.0, semana.week_date, "50", "control")
    assert (r.distance, r.stroke) == (200, "libre")
    await db.refresh(semana)
    assert semana.real_time == 128.0, "la sombra de la transición no se escribió"


async def test_reapuntar_reemplaza_y_borrar_retira(client, db, world: World):
    semana = await _semana(db, world.carlos_event_id, 2)
    await _apuntar(client, world, semana.id, {"real_time": 128.0})
    semanas = await _apuntar(client, world, semana.id, {"real_time": 127.0})

    assert next(w for w in semanas if w["id"] == semana.id)["real_time"] == 127.0
    assert [r.time for r in await _resultados_de(db, world.carlos_swimmer_id)] == [127.0]
    # Retirado, no borrado: el tiempo corregido sigue en la tabla.
    assert len(await _resultados_de(db, world.carlos_swimmer_id, vivos=False)) == 2

    semanas = await _apuntar(client, world, semana.id, {"clear_real_time": True})
    assert next(w for w in semanas if w["id"] == semana.id)["real_time"] is None
    assert await _resultados_de(db, world.carlos_swimmer_id) == []
    await db.refresh(semana)
    assert semana.real_time is None


async def test_el_conteo_de_retirada_cuadra(client, db, world: World):
    """El criterio para retirar `real_time`: resultados vivos == real_time no nulos."""
    for n, t in ((1, 129.0), (2, 128.5), (3, 128.0)):
        await _apuntar(client, world, (await _semana(db, world.carlos_event_id, n)).id,
                       {"real_time": t})
    await _apuntar(client, world, (await _semana(db, world.carlos_event_id, 2)).id,
                   {"real_time": 128.2})
    await _apuntar(client, world, (await _semana(db, world.carlos_event_id, 3)).id,
                   {"clear_real_time": True})

    vivos = (await db.execute(select(func.count()).select_from(Result)
                              .where(Result.is_active.is_(True)))).scalar_one()
    sombras = (await db.execute(select(func.count()).select_from(WeeklyPlan)
                                .where(WeeklyPlan.real_time.is_not(None)))).scalar_one()
    assert vivos == sombras == 2


# ── 3. Varios por semana se promedian, y el promedio es lo que reancla ───────

async def test_varios_tiempos_en_la_semana_se_promedian_y_reanclan(client, db, world: World):
    semana = await _semana(db, world.carlos_event_id, 2)
    _meter(db, world, 128.0, semana.week_date)
    _meter(db, world, 130.0, semana.week_date + timedelta(days=3))
    await db.commit()
    # Cualquier PATCH dispara el recálculo; este no toca el tiempo.
    otra = await _semana(db, world.carlos_event_id, 6)
    promediado = await _apuntar(client, world, otra.id, {"disabled": False})
    por_numero = {w["week_number"]: w for w in promediado}
    assert por_numero[2]["real_time"] == 129.0

    # Lo mismo que si el entrenador hubiera apuntado el promedio a mano.
    a_mano = {w["week_number"]: w for w in
              await _apuntar(client, world, semana.id, {"real_time": 129.0})}
    assert [por_numero[n]["recalc_time"] for n in range(1, 13)] == \
           [a_mano[n]["recalc_time"] for n in range(1, 13)]
    assert por_numero[3]["recalc_time"] is not None


# ── 4. Lo que no cae en ninguna semana no toca la predicción ─────────────────

async def test_un_resultado_fuera_de_las_semanas_no_toca_la_prediccion(client, db, world: World):
    antes = await _semanas(client, world, world.carlos_event_id)
    semana2 = antes[2]
    inicio = date.fromisoformat(antes[1]["week_date"])
    _meter(db, world, 110.0, inicio - timedelta(days=1))               # antes del macro
    _meter(db, world, 110.0, inicio + timedelta(weeks=12))             # después
    _meter(db, world, 58.0, date.fromisoformat(semana2["week_date"]), distance=100)
    await db.commit()

    otra = await _semana(db, world.carlos_event_id, 6)
    despues = {w["week_number"]: w for w in
               await _apuntar(client, world, otra.id, {"disabled": False})}
    for n in range(1, 13):
        assert despues[n]["real_time"] is None, f"semana {n} recogió un tiempo ajeno"
        assert despues[n]["recalc_time"] == antes[n]["recalc_time"]

    r = await client.get(f"{API}/dashboard/summary?plan_id={world.plan_id}",
                         headers=como(world.owner_email))
    fila = next(s for s in r.json()["statuses"] if s["event_id"] == world.carlos_event_id)
    assert fila["status"] == "pending"
    assert len(await _resultados_de(db, world.carlos_swimmer_id)) == 3, \
        "siguen en el histórico del atleta"


async def test_un_tiempo_en_corta_se_ve_convertido_en_el_macro_de_larga(
    client, db, world: World,
):
    """El macro del mundo es de larga; el tiempo se nadó en corta."""
    semana = await _semana(db, world.carlos_event_id, 2)
    _meter(db, world, 125.0, semana.week_date + timedelta(days=2), pool="25")
    await db.commit()
    semanas = await _semanas(client, world, world.carlos_event_id)
    assert semanas[2]["real_time"] == pytest.approx(125.0 / _FACTOR_200)

    # Apuntar en la celda lo reemplaza: la celda enseña el promedio de todos.
    await _apuntar(client, world, semana.id, {"real_time": 128.0})
    [vivo] = await _resultados_de(db, world.carlos_swimmer_id)
    assert (vivo.time, vivo.pool) == (128.0, "50")


# ── Aislamiento: el promedio de un atleta no se cuela en el de otro ──────────

async def test_el_tiempo_de_carlos_no_aparece_en_las_semanas_de_sofia(client, db, world: World):
    semana = await _semana(db, world.carlos_event_id, 2)
    await _apuntar(client, world, semana.id, {"real_time": 128.0})
    sofia = await _semanas(client, world, world.sofia_event_id)
    assert all(w["real_time"] is None for w in sofia.values())
