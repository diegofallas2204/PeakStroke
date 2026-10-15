"""§7.2 fila 6 (C9, 2026-10-14): la base impone los vocabularios cerrados.

Cuatro listas tienen que decir lo mismo, y este archivo las compara:

    dominio (enums)  ──  tablas/vocabulario.py  ──  la migración c9e1a4d7b2f6
                                 │
                       el API (`Literal` / `pattern`)

Si el API aceptara un valor que el CHECK rechaza, la petición daría **500 y no
422** (no hay manejador del `IntegrityError`): por eso se comparan también los
schemas, y se prueban los valores límite que un `pattern` podría dejar pasar.
"""
from __future__ import annotations

import importlib.util
import re
import sqlite3
import typing
from pathlib import Path

import pytest
from conftest import API, World, como
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api import vocabulario as api
from app.api.v1.macrociclos.schemas import PlanCreate, PlanUpdate
from app.api.v1.tests.schemas import AerobicTestCreate
from app.persistencia.tablas import vocabulario as tablas

_MIGRACION = next(
    (Path(__file__).resolve().parents[1] / "alembic" / "versions").glob("*_c9e1a4d7b2f6_*.py"),
)


def _migracion():
    spec = importlib.util.spec_from_file_location("migracion_checks", _MIGRACION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_ESPERADOS = {
    ("swimmers", "gender"): tablas.GENEROS,
    ("swimmers", "specialty"): tablas.ESPECIALIDADES,
    ("swimmers", "main_stroke"): tablas.ESTILOS,
    ("plans", "pool"): tablas.PISCINAS,
    ("plans", "status"): tablas.ESTADOS_DE_MACRO,
    ("athlete_events", "stroke"): tablas.ESTILOS,
    ("resultados", "stroke"): tablas.ESTILOS,
    ("aerobic_tests", "test_type"): tablas.TIPOS_DE_TEST,
    ("aerobic_tests", "input_mode"): tablas.MODOS_DE_INGRESO,
}


def test_la_migracion_lleva_los_vocabularios_del_dominio():
    checks = {(t, c): set(v) for t, _, c, v, _ in _migracion().CHECKS}
    assert checks == {k: set(v) for k, v in _ESPERADOS.items()}


def test_el_api_acepta_exactamente_lo_que_la_base_admite():
    assert set(typing.get_args(api.Gender)) == set(tablas.GENEROS)
    assert set(typing.get_args(api.Specialty)) == set(tablas.ESPECIALIDADES)
    assert set(typing.get_args(api.MainStroke)) == set(tablas.ESTILOS)
    pool = PlanCreate.model_fields["pool"].annotation
    assert set(typing.get_args(pool)) == set(tablas.PISCINAS)
    estado = typing.get_args(PlanUpdate.model_fields["status"].annotation)[0]
    assert set(typing.get_args(estado)) == set(tablas.ESTADOS_DE_MACRO)
    for campo, valores in (("test_type", tablas.TIPOS_DE_TEST), ("input_mode", tablas.MODOS_DE_INGRESO)):
        patron = next(m.pattern for m in AerobicTestCreate.model_fields[campo].metadata if hasattr(m, "pattern"))
        assert set(re.fullmatch(r"\^\((.*)\)\$", patron).group(1).split("|")) == set(valores)


@pytest.mark.parametrize(("tabla", "columna"), list(_ESPERADOS))
async def test_la_base_rechaza_un_valor_fuera_de_vocabulario(db, world: World, tabla, columna):
    if tabla == "resultados":   # el mundo de prueba no trae ninguno: uno válido primero
        await db.execute(text(
            "INSERT INTO resultados (team_id, swimmer_id, distance, stroke, time, result_date, "
            "pool, context, is_active) VALUES (:t, :s, 200, 'libre', 130.0, '2026-10-01', '50', "
            "'control', TRUE)"), {"t": world.team_id, "s": world.sofia_swimmer_id})
    assert (await db.execute(text(f"SELECT COUNT(*) FROM {tabla}"))).scalar_one() > 0
    with pytest.raises(IntegrityError):
        await db.execute(text(f"UPDATE {tabla} SET {columna} = 'otra_cosa'"))
    await db.rollback()


async def test_el_genero_puede_quedar_vacio(db, world: World):
    await db.execute(text("UPDATE swimmers SET gender = NULL"))
    await db.rollback()


@pytest.mark.parametrize("tipo", ["T30\n", " T30", "t30", "T30 "])
async def test_un_tipo_de_test_casi_valido_da_422_y_no_500(client, world: World, tipo):
    """El `pattern` es la única barrera antes del CHECK: un `$` que dejara pasar
    el salto de línea convertiría esto en un 500."""
    r = await client.post(f"{API}/aerobic-tests/", json={
        "swimmer_id": world.sofia_swimmer_id, "test_type": tipo, "test_date": "2026-10-01",
        "splits": [80.0, 80.5, 81.0],
    }, headers=como(world.owner_email))
    assert r.status_code == 422, r.text


def test_la_migracion_sube_y_baja_en_sqlite(tmp_path, monkeypatch):
    """Sube hasta aquí, baja uno y vuelve a subir, con datos; y en cada paso el
    CHECK está o no está de verdad (se intenta violar)."""
    from alembic.config import Config

    from alembic import command
    from app.core.config import settings

    ruta = tmp_path / "checks.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{ruta.as_posix()}")
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    def acepta_basura() -> bool:
        con = sqlite3.connect(ruta)
        try:
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("INSERT INTO teams (name, is_active) VALUES ('t', 1)")
            equipo = con.execute("SELECT max(id) FROM teams").fetchone()[0]
            con.execute(
                "INSERT INTO plans (team_id, name, start_date, total_weeks, weeks_per_micro, "
                "total_km, pool, n_mac, status) VALUES (?, 'p', '2026-01-05', 12, 4, 1, '33', 1, 'raro')",
                (equipo,),
            )
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            con.rollback()
            con.close()

    def forma() -> dict:
        """FKs, índices y CHECK de las tablas que el modo batch recrea en SQLite."""
        con = sqlite3.connect(ruta)
        out = {}
        for t in ("swimmers", "plans", "athlete_events", "resultados", "aerobic_tests"):
            sql = con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (t,)).fetchone()[0]
            out[t] = (
                sorted(tuple(r[2:5]) for r in con.execute(f"PRAGMA foreign_key_list({t})")),
                sorted(r[1] for r in con.execute(f"PRAGMA index_list({t})") if not r[1].startswith("sqlite_")),
                sorted(c.split()[0] for c in sql.split("CONSTRAINT ")[1:] if "CHECK" in c[:120]),
            )
        con.close()
        return out

    command.upgrade(cfg, "head")
    assert not acepta_basura()
    arriba = forma()
    # Los CHECK de antes sobreviven al batch: si Alembic dejara de reflejarlos,
    # los recrearía sin ellos en silencio (lo apuntó el revisor de C9).
    assert {"ck_resultados_context", "ck_resultados_pool", "ck_resultados_time_positive",
            "ck_resultados_stroke"} <= set(arriba["resultados"][2])
    # Hasta la revisión de antes de C9, no `-1`: desde D1 (`d1a7c3e9f5b2`) el head
    # ya no es esta migración, y `-1` solo deshacía la de las vistas.
    command.downgrade(cfg, "b2d7f5a8c1e4")
    assert acepta_basura()
    abajo = forma()
    assert "ck_resultados_context" in abajo["resultados"][2] and "ck_resultados_stroke" not in abajo["resultados"][2]
    assert {t: v[:2] for t, v in abajo.items()} == {t: v[:2] for t, v in arriba.items()}   # FKs e índices
    # Una ficha de antes de C9 con un alias: subir la convierte a su clave.
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO teams (id, name, is_active) VALUES (77, 'Viejo', 1)")
    con.execute("INSERT INTO swimmers (team_id, name, specialty, main_stroke, is_active) "
                "VALUES (77, 'De antes', 'fondo', ' Crol ', 1)")
    con.commit()
    con.close()
    command.upgrade(cfg, "head")
    assert not acepta_basura()
    assert forma() == arriba
    con = sqlite3.connect(ruta)
    assert con.execute("SELECT main_stroke FROM swimmers WHERE team_id = 77").fetchone() == ("libre",)
    con.close()
