"""La retirada de `weekly_plans.real_time` (C7), contra una base desechable.

Subir borra la columna solo si `resultados` respalda cada tiempo que guarda;
bajar la rellena con lo que la semana enseña: el promedio de sus resultados
vivos, convertido a la piscina del macrociclo.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

_ANTES = "82135c6cb2d8"
_C7 = "c7a1e0d5b2f4"

# Ratio corta/larga de medio fondo (200 m), el mismo que usan las zonas.
_FACTOR_200 = 0.979


def _sembrar(ruta: Path, *, huerfana: bool = False) -> None:
    """Un macro de larga, 200 libre, tres semanas desde el 2026-01-05.

    S1: dos controles (128 y 130) → 129. S2: uno en corta → convertido. S3: nada.
    Con `huerfana`, la S3 tiene `real_time` sin resultado que lo respalde.
    """
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO plans (id, team_id, name, start_date, total_weeks, weeks_per_micro, "
        "total_km, pool, n_mac, status) "
        "VALUES (1, 7, 'P', '2026-01-05', 12, 4, 300, '50', 1, 'active')")
    con.execute(
        "INSERT INTO athlete_plans (id, team_id, plan_id, swimmer_id, is_active) "
        "VALUES (1, 7, 1, 41, 1)")
    con.execute(
        "INSERT INTO athlete_events (id, athlete_plan_id, priority, distance, stroke, "
        "\"current_time\", goal_time) VALUES (1, 1, 1, 200, 'libre', 131, 125)")
    for numero, lunes, real in ((1, "2026-01-05", 129.0),
                                (2, "2026-01-12", round(125.0 / _FACTOR_200, 2)),
                                (3, "2026-01-19", 127.0 if huerfana else None)):
        con.execute(
            "INSERT INTO weekly_plans (id, athlete_event_id, week_number, week_date, "
            "planned_km, expected_time, real_time, phase, disabled) "
            "VALUES (?, 1, ?, ?, 20, 129, ?, 'base_general', 0)", (numero, numero, lunes, real))
    for tiempo, fecha, piscina, estilo, vivo in (
        (128.0, "2026-01-05", "50", "libre", 1),
        # Alias crudo: sigue siendo la misma prueba.
        (130.0, "2026-01-09", "50", "crol", 1),
        # Retirado: una corrección, no cuenta.
        (100.0, "2026-01-06", "50", "libre", 0),
        (125.0, "2026-01-14", "25", "libre", 1),
        # Fuera de toda semana del plan: histórico, no tiene fila a la que volver.
        (126.0, "2026-06-01", "50", "libre", 1),
    ):
        con.execute(
            "INSERT INTO resultados (team_id, swimmer_id, distance, stroke, time, "
            "result_date, pool, context, is_active) "
            "VALUES (7, 41, 200, ?, ?, ?, ?, 'control', ?)", (estilo, tiempo, fecha, piscina, vivo))
    con.commit()
    con.close()


def _columnas(ruta: Path) -> set[str]:
    con = sqlite3.connect(ruta)
    cols = {c[1] for c in con.execute("PRAGMA table_info(weekly_plans)")}
    con.close()
    return cols


def _reales(ruta: Path) -> list[float | None]:
    con = sqlite3.connect(ruta)
    filas = [r for (r,) in con.execute("SELECT real_time FROM weekly_plans ORDER BY id")]
    con.close()
    return filas


def _conteo(ruta: Path, tabla: str) -> int:
    con = sqlite3.connect(ruta)
    n = con.execute(f"SELECT count(*) FROM {tabla}").fetchone()[0]
    con.close()
    return n


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    from alembic.config import Config

    from app.core.config import settings

    ruta = tmp_path / "c7.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{ruta.as_posix()}")
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), ruta


def test_sube_quita_la_columna_y_baja_la_rellena_desde_resultados(cfg):
    from alembic import command

    config, ruta = cfg
    command.upgrade(config, _ANTES)
    _sembrar(ruta)

    command.upgrade(config, _C7)
    assert "real_time" not in _columnas(ruta)
    assert _conteo(ruta, "weekly_plans") == 3, "recrear la tabla perdió semanas"
    assert _conteo(ruta, "resultados") == 5, "la migración tocó resultados"

    command.downgrade(config, _ANTES)
    s1, s2, s3 = _reales(ruta)
    assert s1 == pytest.approx(129.0), "el promedio de la semana no volvió"
    assert s2 == pytest.approx(125.0 / _FACTOR_200), "el de corta no volvió convertido"
    assert s3 is None

    command.upgrade(config, _C7)
    assert "real_time" not in _columnas(ruta)


def test_no_sube_si_la_columna_guarda_un_tiempo_que_resultados_no(cfg):
    from alembic import command

    config, ruta = cfg
    command.upgrade(config, _ANTES)
    _sembrar(ruta, huerfana=True)

    with pytest.raises(RuntimeError, match="no se sigue"):
        command.upgrade(config, _C7)
    assert "real_time" in _columnas(ruta)
    assert _reales(ruta)[2] == 127.0
