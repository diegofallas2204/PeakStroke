"""C8: la carga de entrenamiento (Banister), del cálculo a la tabla y al API.

Lo que fija este archivo, en el orden en que importa:

  1. **La recurrencia es la de la nota 05**: carga constante L → CTL y ATL
     tienden a L; tras τ días han recorrido 1 − 1/e del camino.
  2. **El CSS que vale es el de ese día**, y un T15 solo a falta de otro.
  3. **La tabla materializada es SIEMPRE el cálculo desde cero**, tras cualquier
     secuencia de escrituras (crear, mover de fecha, borrar, tests que entran y
     salen). Es lo que hace seguro guardar un derivado.
  4. **Alertas con los umbrales unificados**, y ninguna durante el calentamiento.
  5. **La serie arranca en equilibrio**: quien entrena a carga constante tiene
     TSB 0 desde el primer día, no −30 durante meses.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from conftest import API, World, como
from sqlalchemy import select

from app.dominio.entidades import Sesion
from app.dominio.servicios.banister import (
    DIAS_DE_CALENTAMIENTO,
    DIAS_PARA_EQUILIBRIO,
    RAMPA_MAXIMA_CTL_SEMANAL,
    TAU_ATL_DIAS,
    TAU_CTL_DIAS,
    CargaAcumulada,
    DiaDeCarga,
    EstadoDeCarga,
    MedicionDeCss,
    MotivoDeAlerta,
    NivelDeAlerta,
    alertas,
    carga_por_dia,
    css_vigente,
    estado_inicial,
    serie,
)
from app.dominio.valores import Ritmo, Tiempo, TipoDeTest
from app.persistencia.mapeo import medicion_desde_test, sesion_desde_fila
from app.persistencia.repositorios.carga import recalcular
from app.persistencia.tablas.carga import DailyLoad
from app.persistencia.tablas.sesiones import SwimSession
from app.persistencia.tablas.tests_aerobicos import AerobicTest

D0 = date(2026, 1, 5)


def _dias(n: int, desde: date = D0) -> list[date]:
    return [desde + timedelta(days=i) for i in range(n)]


# ── 1. La recurrencia ────────────────────────────────────────────────────────

def test_un_dia_es_la_formula_de_la_nota():
    e = EstadoDeCarga(50.0, 60.0).avanzar(100.0)
    assert e.ctl == pytest.approx(50 * math.exp(-1 / 42) + 100 * (1 - math.exp(-1 / 42)))
    assert e.atl == pytest.approx(60 * math.exp(-1 / 7) + 100 * (1 - math.exp(-1 / 7)))
    assert e.tsb == pytest.approx(e.ctl - e.atl)


def test_tras_tau_dias_de_carga_constante_se_ha_recorrido_1_menos_1_entre_e():
    dias = serie(dict.fromkeys(_dias(TAU_CTL_DIAS), 100.0), D0, D0 + timedelta(TAU_CTL_DIAS - 1))
    assert dias[-1].ctl == pytest.approx(100 * (1 - math.exp(-1)))
    assert dias[TAU_ATL_DIAS - 1].atl == pytest.approx(100 * (1 - math.exp(-1)))


def test_encadenar_dos_tramos_es_calcularlo_de_una_vez():
    cargas = {d: float(i % 5) * 30 for i, d in enumerate(_dias(60))}
    entera = serie(cargas, D0, D0 + timedelta(59))
    primera = serie(cargas, D0, D0 + timedelta(29))
    segunda = serie(cargas, D0 + timedelta(30), D0 + timedelta(59), primera[-1].estado)
    assert primera + segunda == entera


def test_sin_carga_solo_decae():
    dias = serie({}, D0, D0 + timedelta(9), EstadoDeCarga(70.0, 90.0))
    assert dias[-1].ctl == pytest.approx(70 * math.exp(-10 / 42))
    assert dias[-1].atl == pytest.approx(90 * math.exp(-10 / 7))


# ── 5. El arranque en equilibrio ─────────────────────────────────────────────

def test_el_equilibrio_es_la_media_de_la_ventana_con_los_descansos_en_cero():
    cargas = {D0: 140.0, D0 + timedelta(3): 140.0, D0 + timedelta(DIAS_PARA_EQUILIBRIO): 999.0}
    assert estado_inicial(cargas, D0) == EstadoDeCarga(20.0, 20.0)


def test_a_carga_constante_el_tsb_es_cero_desde_el_primer_dia():
    hora = Tiempo(3600)
    sesiones = [Sesion(atleta_id=1, fecha=d, distancia_m=4000, duracion=hora) for d in _dias(60)]
    dias, _ = CargaAcumulada.calcular(sesiones, [MedicionDeCss(D0, Ritmo(90.0))])
    assert all(d.ctl == pytest.approx(100.0) and d.tsb == pytest.approx(0.0) for d in dias)


# ── 2. El CSS de cada día ────────────────────────────────────────────────────

def test_vale_el_ultimo_test_anterior_y_el_t15_solo_a_falta_de_otro():
    t15 = MedicionDeCss(D0, Ritmo(70.0), preferente=False)
    t30 = MedicionDeCss(D0 + timedelta(10), Ritmo(75.0))
    t15_despues = MedicionDeCss(D0 + timedelta(20), Ritmo(69.0), preferente=False)
    medidas = [t15, t30, t15_despues]
    assert css_vigente(medidas, D0 - timedelta(1)) is None
    assert css_vigente(medidas, D0 + timedelta(5)) == Ritmo(70.0)
    assert css_vigente(medidas, D0 + timedelta(15)) == Ritmo(75.0)
    assert css_vigente(medidas, D0 + timedelta(25)) == Ritmo(75.0), "el T15 pisó al T30"


@pytest.mark.parametrize(("tipo", "mide"), [
    ("CSS", True), ("T30", True), ("DIRECT", True), ("T15", False), ("CUSTOM", False),
])
def test_que_test_mide_el_umbral(tipo, mide):
    assert TipoDeTest.desde_texto(tipo).mide_el_umbral is mide


def test_las_dobles_suman_y_lo_anterior_al_primer_test_no_entra():
    css = [MedicionDeCss(D0, Ritmo(90.0))]
    hora = Tiempo(3600)
    sesiones = [
        Sesion(atleta_id=1, fecha=D0 - timedelta(1), distancia_m=4000, duracion=hora),
        Sesion(atleta_id=1, fecha=D0, distancia_m=4000, duracion=hora),
        Sesion(atleta_id=1, fecha=D0, distancia_m=2000, duracion=Tiempo(1800)),
    ]
    cargas, sin_css = carga_por_dia(sesiones, css)
    assert cargas == {D0: pytest.approx(150.0)}
    assert sin_css == 1


# ── 4. Alertas ───────────────────────────────────────────────────────────────

def _con_tsb(tsbs: list[float], desde: date = D0) -> list[DiaDeCarga]:
    return [DiaDeCarga(d, 0.0, 50.0, 50.0 - t) for d, t in zip(_dias(len(tsbs), desde), tsbs, strict=True)]


def test_ninguna_alerta_durante_el_calentamiento():
    dias = _con_tsb([-60.0] * DIAS_DE_CALENTAMIENTO)
    assert alertas(dias, inicio_de_historia=D0) == []


@pytest.mark.parametrize(("tsb", "nivel"), [
    (-24.9, None), (-25.1, NivelDeAlerta.ADVERTENCIA), (-40.1, NivelDeAlerta.PELIGRO),
])
def test_umbrales_de_tsb(tsb, nivel):
    dias = _con_tsb([5.0, tsb])
    [*_, ultimo] = [None, *alertas(dias, inicio_de_historia=D0 - timedelta(100))]
    assert (ultimo.nivel if ultimo else None) == nivel


def test_subir_la_ctl_mas_de_7_en_una_semana_es_rampa():
    inicio = D0 - timedelta(100)

    def con_ctl(ctls: list[float]) -> list[DiaDeCarga]:
        return [DiaDeCarga(d, 0.0, c, c) for d, c in zip(_dias(len(ctls)), ctls, strict=True)]

    justo = con_ctl([50.0] + [50.0] * 6 + [50.0 + RAMPA_MAXIMA_CTL_SEMANAL])
    pasado = con_ctl([50.0] + [50.0] * 6 + [50.0 + RAMPA_MAXIMA_CTL_SEMANAL + 0.1])
    assert alertas(justo, inicio) == []
    [a] = alertas(pasado, inicio)
    assert (a.fecha, a.nivel, a.motivos) == (
        D0 + timedelta(7), NivelDeAlerta.ADVERTENCIA, (MotivoDeAlerta.RAMPA,))


def test_mas_de_14_dias_seguidos_negativos_es_fatiga_sostenida():
    inicio = D0 - timedelta(100)
    catorce = alertas(_con_tsb([-5.0] * 14), inicio)
    quince = alertas(_con_tsb([-5.0] * 15), inicio)
    assert catorce == []
    assert [(a.fecha, a.motivos) for a in quince] == [
        (D0 + timedelta(14), (MotivoDeAlerta.FATIGA_SOSTENIDA,)),
    ]
    # Un solo día en positivo corta la racha.
    assert alertas(_con_tsb([-5.0] * 10 + [1.0] + [-5.0] * 10), inicio) == []


# ── 3. La tabla es el cálculo desde cero ─────────────────────────────────────

async def _tabla(db, swimmer_id: int) -> list[tuple]:
    filas = (await db.execute(select(DailyLoad).where(DailyLoad.swimmer_id == swimmer_id)
                              .order_by(DailyLoad.load_date))).scalars()
    return [(f.load_date, round(f.stss, 9), round(f.ctl, 9), round(f.atl, 9)) for f in filas]


async def _desde_cero(db, swimmer_id: int) -> list[tuple]:
    sesiones = [sesion_desde_fila(f) for f in (await db.execute(
        select(SwimSession).where(SwimSession.swimmer_id == swimmer_id))).scalars()]
    medidas = [medicion_desde_test(f) for f in (await db.execute(select(AerobicTest).where(
        AerobicTest.swimmer_id == swimmer_id, AerobicTest.is_active.is_(True)))).scalars()]
    dias, _ = CargaAcumulada.calcular(sesiones, medidas)
    return [(d.fecha, round(d.stss, 9), round(d.ctl, 9), round(d.atl, 9)) for d in dias]


async def _apuntar(client, world: World, dia: date, metros: int = 4000, segundos: int = 4800):
    r = await client.post(f"{API}/sessions/", json={
        "swimmer_id": world.sofia_swimmer_id, "session_date": dia.isoformat(),
        "distance_m": metros, "duration_s": segundos,
    }, headers=como(world.owner_email))
    assert r.status_code == 201
    return r.json()["id"]


async def _cuadra(db, world: World) -> None:
    db.expire_all()
    assert await _tabla(db, world.sofia_swimmer_id) == await _desde_cero(db, world.sofia_swimmer_id)


async def test_la_tabla_es_el_calculo_desde_cero_tras_cualquier_escritura(client, db, world: World):
    [test] = (await db.execute(select(AerobicTest).where(
        AerobicTest.id == world.sofia_test_id))).scalars()
    lunes = test.test_date
    owner = como(world.owner_email)

    # Tres sesiones, una doble y una con un hueco de días detrás.
    a = await _apuntar(client, world, lunes + timedelta(1))
    await _apuntar(client, world, lunes + timedelta(1), 2000, 2400)
    b = await _apuntar(client, world, lunes + timedelta(9))
    await _cuadra(db, world)
    assert len(await _tabla(db, world.sofia_swimmer_id)) == 9, "días de carga 0 incluidos"

    # Dentro de la ventana de equilibrio: mueve el arranque, rehace la serie entera.
    await _apuntar(client, world, lunes + timedelta(3), 5000, 5400)
    await _cuadra(db, world)
    # Fuera de ella: incremental.
    ultima = await _apuntar(client, world, lunes + timedelta(20))
    await _cuadra(db, world)

    # Anterior al test: no tiene CSS, no mueve nada.
    await _apuntar(client, world, lunes - timedelta(2))
    await _cuadra(db, world)

    # Mover la primera hacia delante (cambia el inicio de la serie).
    await client.patch(f"{API}/sessions/{a}", json={"session_date": str(lunes + timedelta(4))},
                       headers=owner)
    await _cuadra(db, world)

    # Un test nuevo a mitad: cambia el CSS desde su fecha.
    creado = await client.post(f"{API}/aerobic-tests/", json={
        "swimmer_id": world.sofia_swimmer_id, "test_type": "DIRECT",
        "test_date": str(lunes + timedelta(6)), "direct_per100": 70.0,
    }, headers=owner)
    assert creado.status_code == 201
    await _cuadra(db, world)

    # Borrar una de en medio, y luego la última: la serie termina en la
    # anterior, no en un descanso que quedó colgando.
    await client.delete(f"{API}/sessions/{b}", headers=owner)
    await _cuadra(db, world)
    await client.delete(f"{API}/sessions/{ultima}", headers=owner)
    await _cuadra(db, world)
    assert (await _tabla(db, world.sofia_swimmer_id))[-1][0] == lunes + timedelta(4)

    # El test que sale se lleva su CSS.
    await client.delete(f"{API}/aerobic-tests/{creado.json()['id']}", headers=owner)
    await _cuadra(db, world)


async def test_recalcular_dos_veces_deja_lo_mismo(client, db, world: World):
    [test] = (await db.execute(select(AerobicTest).where(
        AerobicTest.id == world.sofia_test_id))).scalars()
    for i in (1, 2, 5, 12):
        await _apuntar(client, world, test.test_date + timedelta(i))
    antes = await _tabla(db, world.sofia_swimmer_id)
    for _ in range(2):
        await recalcular(db, team_id=world.team_id, swimmer_id=world.sofia_swimmer_id,
                         desde=date.min)
        await db.commit()
        assert await _tabla(db, world.sofia_swimmer_id) == antes


# ── El API ───────────────────────────────────────────────────────────────────

async def test_la_curva_llega_a_hasta_decayendo_y_avisa_del_calentamiento(client, db, world: World):
    [test] = (await db.execute(select(AerobicTest).where(
        AerobicTest.id == world.sofia_test_id))).scalars()
    dia = test.test_date + timedelta(1)
    await _apuntar(client, world, dia)
    await _apuntar(client, world, test.test_date - timedelta(1))   # sin CSS

    hasta = dia + timedelta(10)
    r = await client.get(
        f"{API}/training-load/{world.sofia_swimmer_id}?desde={dia}&hasta={hasta}",
        headers=como(world.sofia_email))
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["history_start"] == str(dia)
    assert cuerpo["warming_up"] is True
    assert cuerpo["sessions_without_css"] == 1
    dias = cuerpo["days"]
    assert [d["date"] for d in (dias[0], dias[-1])] == [str(dia), str(hasta)]
    assert all(d["stss"] == 0 for d in dias[1:])
    assert dias[-1]["ctl"] == pytest.approx(dias[0]["ctl"] * math.exp(-10 / 42), abs=0.01)
    assert all(d["alert"] is None for d in dias)


async def test_la_curva_ajena_da_404_y_sin_sesiones_sale_vacia(client, world: World):
    r = await client.get(f"{API}/training-load/{world.carlos_swimmer_id}",
                         headers=como(world.sofia_email))
    assert r.status_code == 404
    r = await client.get(f"{API}/training-load/{world.carlos_swimmer_id}",
                         headers=como(world.owner_email))
    assert r.status_code == 200
    assert (r.json()["days"], r.json()["history_start"]) == ([], None)


async def test_rango_invalido_da_422(client, world: World):
    base = f"{API}/training-load/{world.sofia_swimmer_id}"
    owner = como(world.owner_email)
    assert (await client.get(f"{base}?desde=2026-02-01&hasta=2026-01-01",
                             headers=owner)).status_code == 422
    assert (await client.get(f"{base}?desde=2020-01-01&hasta=2026-01-01",
                             headers=owner)).status_code == 422
