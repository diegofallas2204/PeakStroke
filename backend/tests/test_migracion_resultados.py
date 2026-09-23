"""La migración de C6, ejecutada de verdad contra una base desechable.

Sube, comprueba fila a fila, baja, comprueba que `real_time` quedó intacta y
vuelve a subir. Y fija las dos guardas: el downgrade se niega a tirar tiempos que
la columna vieja no sabe guardar.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

_ANTES_DE_C6 = "a3f1c2d4e5b6"
_C6 = "bae825334065"

# (plan, piscina, inscripción viva, [(semana, lunes, real_time)])
_PLANES = (
    (1, "50", 1, [(1, "2026-01-05", 130.0), (2, "2026-01-12", None), (3, "2026-01-19", 128.4)]),
    # Dado de baja del macro: lo que nadó sigue siendo suyo y se migra igual.
    (2, "50", 0, [(1, "2026-03-02", 129.1), (2, "2026-03-09", 128.9)]),
    # Corta: la piscina sale del plan.
    (3, "25", 1, [(1, "2026-05-04", 126.0), (2, "2026-05-11", None)]),
)


def _sembrar(ruta: Path) -> None:
    con = sqlite3.connect(ruta)
    for plan_id, pool, viva, semanas in _PLANES:
        con.execute(
            "INSERT INTO plans (id, team_id, name, start_date, total_weeks, weeks_per_micro, "
            "total_km, progression_curve, pool, n_mac, status) "
            "VALUES (?, 7, 'P', ?, 12, 4, 300, 'science', ?, 1, 'active')",
            (plan_id, semanas[0][1], pool),
        )
        con.execute(
            "INSERT INTO athlete_plans (id, team_id, plan_id, swimmer_id, is_active) "
            "VALUES (?, 7, ?, 40 + ?, ?)", (plan_id, plan_id, plan_id, viva),
        )
        con.execute(
            "INSERT INTO athlete_events (id, athlete_plan_id, priority, distance, stroke, "
            '"current_time", goal_time) VALUES (?, ?, 1, 200, \'libre\', 131, 125)',
            (plan_id, plan_id),
        )
        for numero, lunes, real in semanas:
            con.execute(
                "INSERT INTO weekly_plans (athlete_event_id, week_number, week_date, "
                "planned_km, expected_time, real_time, phase, disabled) "
                "VALUES (?, ?, ?, 20, 129, ?, 'base_general', 0)",
                (plan_id, numero, lunes, real),
            )
    con.commit()
    con.close()


def _real_times(ruta: Path) -> list[tuple]:
    con = sqlite3.connect(ruta)
    filas = con.execute(
        "SELECT id, real_time FROM weekly_plans ORDER BY id").fetchall()
    con.close()
    return filas


def _resultados(ruta: Path) -> list[tuple] | None:
    con = sqlite3.connect(ruta)
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'resultados'").fetchone():
        return None
    filas = con.execute(
        "SELECT team_id, swimmer_id, distance, stroke, time, result_date, pool, context, "
        "competition_id, is_active FROM resultados ORDER BY result_date").fetchall()
    con.close()
    return filas


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    from alembic.config import Config

    from app.core.config import settings

    ruta = tmp_path / "c6.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{ruta.as_posix()}")
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), ruta


def test_sube_copia_cada_real_time_y_baja_sin_perder_nada(cfg):
    from alembic import command

    config, ruta = cfg
    command.upgrade(config, _ANTES_DE_C6)
    _sembrar(ruta)
    antes = _real_times(ruta)
    assert sum(r is not None for _, r in antes) == 5

    command.upgrade(config, _C6)
    assert _resultados(ruta) == [
        (7, 41, 200, "libre", 130.0, "2026-01-05", "50", "control", None, 1),
        (7, 41, 200, "libre", 128.4, "2026-01-19", "50", "control", None, 1),
        (7, 42, 200, "libre", 129.1, "2026-03-02", "50", "control", None, 1),
        (7, 42, 200, "libre", 128.9, "2026-03-09", "50", "control", None, 1),
        (7, 43, 200, "libre", 126.0, "2026-05-04", "25", "control", None, 1),
    ]
    assert _real_times(ruta) == antes, "la migración tocó real_time"

    command.downgrade(config, _ANTES_DE_C6)
    assert _resultados(ruta) is None
    assert _real_times(ruta) == antes

    command.upgrade(config, _C6)
    assert len(_resultados(ruta)) == 5


def test_el_downgrade_no_tira_tiempos_que_real_time_no_sabe_guardar(cfg):
    """Un segundo tiempo en la misma semana es justo lo que R2 enmendada permite."""
    from alembic import command

    config, ruta = cfg
    command.upgrade(config, _ANTES_DE_C6)
    _sembrar(ruta)
    command.upgrade(config, _C6)
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO resultados (team_id, swimmer_id, distance, stroke, time, result_date, "
        "pool, context, is_active) VALUES (7, 41, 200, 'libre', 129.0, '2026-01-08', "
        "'50', 'control', 1)")
    con.commit()
    con.close()

    with pytest.raises(RuntimeError, match="no se baja"):
        command.downgrade(config, _ANTES_DE_C6)
    assert len(_resultados(ruta)) == 6, "tiró la tabla aun negándose"
