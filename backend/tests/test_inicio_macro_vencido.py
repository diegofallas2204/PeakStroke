"""Inicio con un macrociclo cuyo calendario ya terminó (2026-11-10, `modulo/inicio`).

`Macrociclo.semana_actual()` se queda en la última semana a propósito —el
recálculo y el plan semanal la necesitan así—, y el resumen de Inicio la usaba
como si fuera «hoy». Con el macro vencido: la S12 salía como semana en curso,
la fase Taper como actual, la competencia de la S12 como «esta semana»
(`weeks_away == 0`) y la gráfica marcaba «Hoy» en la última semana. Lo que fija
este archivo:

- un macro en curso sigue igual (`is_over` falso, la semana actual marcada);
- uno vencido dice `is_over`, no marca ninguna semana ni fase como actual, y
  sus competencias quedan en el pasado (`weeks_away < 0`);
- `current_week` sigue siendo la última: la tabla de estado por atleta y el
  cumplimiento de registro se calculan sobre ella, como antes.
"""
from __future__ import annotations

from datetime import date, timedelta

from conftest import API, World
from sqlalchemy import update

from app.persistencia.tablas.planes import Plan


async def _resumen(client, plan_id: int) -> dict:
    r = await client.get(f"{API}/dashboard/summary?plan_id={plan_id}")
    assert r.status_code == 200, r.text
    return r.json()


async def test_un_macro_en_curso_marca_su_semana(client, world: World):
    s = await _resumen(client, world.plan_id)
    assert s["is_over"] is False
    assert s["current_week"] == 4
    assert [p["week_number"] for p in s["progression"] if p["is_current"]] == [4]
    assert [f["is_current"] for f in s["phases"]].count(True) == 1
    nacional = next(c for c in s["competitions"] if c["name"] == "Nacional")
    assert nacional["weeks_away"] == 8


async def test_un_macro_vencido_no_tiene_hoy_ni_proxima_competencia(client, db, world: World):
    lunes = date.today() - timedelta(days=date.today().weekday()) - timedelta(weeks=20)
    await db.execute(update(Plan).where(Plan.id == world.plan_id).values(start_date=lunes))
    await db.commit()

    s = await _resumen(client, world.plan_id)
    assert s["is_over"] is True
    assert s["current_week"] == 12, "la tabla de estado sigue usando la última semana"
    assert not any(p["is_current"] for p in s["progression"])
    assert not any(f["is_current"] for f in s["phases"])
    assert s["current_phase"] is None
    nacional = next(c for c in s["competitions"] if c["name"] == "Nacional")
    assert nacional["weeks_away"] == 12 - 21, "la S12 quedó nueve semanas atrás"


async def test_un_macro_que_aun_no_empieza(client, db, world: World):
    lunes = date.today() - timedelta(days=date.today().weekday()) + timedelta(weeks=2)
    await db.execute(update(Plan).where(Plan.id == world.plan_id).values(start_date=lunes))
    await db.commit()

    s = await _resumen(client, world.plan_id)
    assert s["is_over"] is False
    assert s["current_week"] is None
    nacional = next(c for c in s["competitions"] if c["name"] == "Nacional")
    assert nacional["weeks_away"] == 12 + 1, "faltan las dos de espera y once más"
