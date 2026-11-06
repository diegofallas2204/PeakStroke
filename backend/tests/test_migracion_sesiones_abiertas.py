"""`e3b8f1a6c4d2` (TODO-30) contra una base desechable: sube y baja.

Subir crea `sesiones_abiertas` y quita `users.refresh_rotation` en modo batch,
que en SQLite **copia** `users`: las cuentas tienen que sobrevivir enteras, las
FKs que la apuntan seguir apuntándola y las vistas `v_admin_*` —que leen
`users`— seguir abriéndose (por eso el `legacy_alter_table`). Bajar devuelve la
columna en 0 y borra la tabla. PostgreSQL se prueba a mano contra
`peakstroke_c9` (bitácora del bloque).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

_ANTES = "d1a7c3e9f5b2"
_TODO30 = "e3b8f1a6c4d2"
_VISTAS = ("v_admin_accesos", "v_admin_actividad", "v_admin_cuentas", "v_admin_equipos")


def _sembrar(ruta: Path) -> None:
    con = sqlite3.connect(ruta)
    con.execute(
        "INSERT INTO users (id, email, password_hash, name, is_active, token_version, "
        "refresh_rotation) VALUES (1, 'ana@x.dev', 'h', 'Ana', 1, 2, 5)")
    con.execute("INSERT INTO teams (id, name, owner_id, is_active) VALUES (1, 'Club', 1, 1)")
    con.execute(
        "INSERT INTO team_members (team_id, user_id, role, is_active) VALUES (1, 1, 'coach', 1)")
    con.commit()
    con.close()


def _consulta(ruta: Path, sql: str) -> list[tuple]:
    con = sqlite3.connect(ruta)
    filas = con.execute(sql).fetchall()
    con.close()
    return filas


def _columnas(ruta: Path) -> set[str]:
    return {c[1] for c in _consulta(ruta, "PRAGMA table_info(users)")}


def _tablas(ruta: Path) -> set[str]:
    return {n for (n,) in _consulta(ruta, "SELECT name FROM sqlite_master WHERE type = 'table'")}


def _intacta(ruta: Path) -> None:
    assert _consulta(ruta, "SELECT id, email, token_version, is_active FROM users") == [
        (1, "ana@x.dev", 2, 1)]
    assert _consulta(ruta, "PRAGMA foreign_key_check") == []
    for vista in _VISTAS:
        _consulta(ruta, f"SELECT * FROM {vista}")   # revienta si la vista quedó rota


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    from alembic.config import Config

    from app.core.config import settings

    ruta = tmp_path / "todo30.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{ruta.as_posix()}")
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), ruta


def test_sube_crea_la_tabla_quita_la_columna_y_baja_la_devuelve(cfg):
    from alembic import command

    config, ruta = cfg
    command.upgrade(config, _ANTES)
    _sembrar(ruta)

    command.upgrade(config, _TODO30)
    assert "refresh_rotation" not in _columnas(ruta)
    assert "sesiones_abiertas" in _tablas(ruta)
    _intacta(ruta)
    indices = {n for (n,) in _consulta(
        ruta, "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'sesiones_abiertas'")}
    assert {"ix_sesiones_abiertas_user_id", "ix_sesiones_abiertas_expires_at"} <= indices

    command.downgrade(config, _ANTES)
    assert "sesiones_abiertas" not in _tablas(ruta)
    assert _consulta(ruta, "SELECT refresh_rotation FROM users") == [(0,)], (
        "la rotación vuelve en 0: los tokens con sid no llevan la de la cuenta"
    )
    _intacta(ruta)

    command.upgrade(config, _TODO30)
    assert "refresh_rotation" not in _columnas(ruta)
    _intacta(ruta)


def test_borrar_la_cuenta_borra_sus_sesiones(cfg):
    from alembic import command

    config, ruta = cfg
    command.upgrade(config, _TODO30)
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute(
        "INSERT INTO users (id, email, password_hash, name, is_active, token_version) "
        "VALUES (9, 'b@x.dev', 'h', 'B', 1, 0)")
    con.execute(
        "INSERT INTO sesiones_abiertas (id, user_id, refresh_rotation, expires_at) "
        "VALUES ('s', 9, 0, '2030-01-01 00:00:00')")
    con.execute("DELETE FROM users WHERE id = 9")
    con.commit()
    assert con.execute("SELECT count(*) FROM sesiones_abiertas").fetchone() == (0,)
    con.close()
