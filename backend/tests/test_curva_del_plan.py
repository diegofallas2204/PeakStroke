"""R7: la curva de un plan real es la científica; elegirla es cosa del simulador.

Por qué importa (§10.4 de `REDISENO.md`): a mitad de macro las cinco curvas se
separan hasta 1,30 s contra una tolerancia de estado de ±0,4 %, así que el mismo
nado salía «adelantado» con una y «atrasado» con otra. La curva era una casilla
del asistente; ahora no es de nadie.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest
from conftest import API, World, como

from app.dominio.entidades import Macrociclo
from app.dominio.entidades.macrociclo import CURVA_DEL_PLAN
from app.dominio.servicios.curvas import Cientifica, Curva

_ANTES_DE_R7 = "bae825334065"
_R7 = "82135c6cb2d8"


# ── Dominio ──────────────────────────────────────────────────────────────────

def test_la_curva_del_plan_es_la_cientifica_viva():
    """La clave está copiada en la entidad (el dominio no importa de lado): este
    test es lo que impide que las dos se separen."""
    assert Cientifica.clave == CURVA_DEL_PLAN
    assert isinstance(Curva.desde_clave(Macrociclo(inicio=date(2026, 1, 5), semanas=12).curva),
                      Cientifica)


def test_no_se_puede_construir_un_macro_con_otra_curva():
    with pytest.raises(TypeError):
        Macrociclo(inicio=date(2026, 1, 5), semanas=12, curva="exponential")  # type: ignore[call-arg]


# ── API ──────────────────────────────────────────────────────────────────────

async def test_el_plan_ya_no_lleva_curva_en_la_respuesta(client, world: World):
    r = await client.get(f"{API}/plans/{world.plan_id}", headers=como(world.owner_email))
    assert r.status_code == 200
    assert "progression_curve" not in r.json()


async def test_un_cliente_viejo_que_manda_la_curva_no_rompe(client, world: World):
    """Pydantic ignora el campo de más: el frontend de antes sigue pudiendo crear."""
    r = await client.post(f"{API}/plans/", json={
        "name": "Macro de cliente viejo", "start_date": "2026-11-02",
        "total_weeks": 12, "total_km": 300, "progression_curve": "exponential",
    }, headers=como(world.owner_email))
    assert r.status_code == 201, r.text
    assert "progression_curve" not in r.json()


async def test_el_simulador_sigue_eligiendo_curva(client, world: World):
    cuerpo = {"distance": 200, "stroke": "libre", "current_time": 160.0,
              "goal_time": 157.0, "total_weeks": 15, "total_km": 450}
    sims = {}
    for curva in ("science", "exponential"):
        r = await client.post(f"{API}/simulator/run", json={**cuerpo, "curve": curva},
                              headers=como(world.owner_email))
        assert r.status_code == 200, r.text
        sims[curva] = [w["expected_time"] for w in r.json()["weeks"]]
    assert sims["science"] != sims["exponential"], "el simulador ignoró la curva"


# ── Migración ────────────────────────────────────────────────────────────────

def test_la_migracion_quita_la_columna_y_el_downgrade_la_devuelve(tmp_path, monkeypatch, capfd):
    from alembic.config import Config

    from alembic import command
    from app.core.config import settings

    ruta = tmp_path / "r7.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{ruta.as_posix()}")
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    command.upgrade(cfg, _ANTES_DE_R7)
    con = sqlite3.connect(ruta)
    for plan_id, curva in ((1, "science"), (2, "exponential")):
        con.execute(
            "INSERT INTO plans (id, team_id, name, start_date, total_weeks, weeks_per_micro, "
            "total_km, progression_curve, pool, n_mac, status) "
            "VALUES (?, 1, 'P', '2026-01-05', 12, 4, 300, ?, '50', 1, 'active')",
            (plan_id, curva),
        )
    con.execute("INSERT INTO plan_phases (plan_id, name, type, week_start, week_end, color, sort) "
                "VALUES (2, 'Base', 'base_general', 1, 12, '#22d3ee', 0)")
    con.commit()
    con.close()

    capfd.readouterr()
    command.upgrade(cfg, _R7)
    # Por la salida y no por `caplog`: `env.py` reconfigura el logging con
    # `fileConfig` y el aviso va directo al handler de consola de alembic.ini.
    aviso = capfd.readouterr().err
    assert "1 plan(es)" in aviso and "exponential" in aviso

    con = sqlite3.connect(ruta)
    columnas = {r[1] for r in con.execute("PRAGMA table_info(plans)")}
    assert "progression_curve" not in columnas
    # Recrear `plans` no arrastró lo que cuelga de ella.
    assert con.execute("SELECT count(*) FROM plan_phases").fetchone()[0] == 1
    con.close()

    command.downgrade(cfg, _ANTES_DE_R7)
    con = sqlite3.connect(ruta)
    assert con.execute("SELECT id, progression_curve FROM plans ORDER BY id").fetchall() == \
        [(1, "science"), (2, "science")], "solo 'science' es recuperable"
    columna = next(r for r in con.execute("PRAGMA table_info(plans)") if r[1] == "progression_curve")
    assert (columna[3], columna[4]) == (1, None), "debe volver NOT NULL y sin server_default"
    con.close()
