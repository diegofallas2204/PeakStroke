"""P3 — las fases del macrociclo son las cinco de la ciencia, y la base guarda su clave.

Convivían tres vocabularios de fase: las cinco claves de `F_FASE`, los cuatro
tramos que veía el entrenador (`Base/Construcción/Pico/Descenso`) y los cuatro
de `PlanPhase.type` (`base|build|peak|taper`). La base guardaba la etiqueta, así
que la ciencia no podía leer lo que la aplicación persistía, y ninguna regla
decía cómo se repartían cuatro tramos sobre cinco fases.

Se cerró quitando el vocabulario de cuatro, no traduciéndolo. Lo que se fija
aquí es lo que eso promete:

  · las fases por defecto **son** la forma de la curva científica, con las
    fronteras en las mismas semanas;
  · lo que se guarda es la clave (y un CHECK lo impone); lo que se enseña es el
    nombre que el entrenador le puso al tramo;
  · los tipos de antes de P3 ya no entran por ninguna puerta;
  · la migración convierte lo que había y su downgrade lo devuelve.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from conftest import API, World, como
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.api.v1.macrociclos.schemas import PhaseInput
from app.dominio.servicios.motor import COLOR_DE_FASE, MOTOR, fases_por_defecto
from app.dominio.servicios.tablas import MACRO_15_FASES
from app.dominio.valores import Fase
from app.persistencia.tablas.planes import PlanPhase, WeeklyPlan

CLAVES = [f.value for f in Fase.secuencia()]


# ── Las fases por defecto son la forma de la curva ──────────────────────────

class TestLasFasesPorDefecto:
    def test_con_15_semanas_son_exactamente_el_macro_de_la_ciencia(self):
        fases = fases_por_defecto(15)
        assert [(f["week_start"], f["week_end"], f["type"]) for f in fases] == \
            list(MACRO_15_FASES)

    @pytest.mark.parametrize("semanas", range(1, 31))
    def test_cubren_todas_las_semanas_en_orden_sin_huecos(self, semanas):
        fases = fases_por_defecto(semanas)
        assert fases[0]["week_start"] == 1
        assert fases[-1]["week_end"] == semanas
        for antes, despues in zip(fases, fases[1:], strict=False):
            assert despues["week_start"] == antes["week_end"] + 1
        assert all(f["week_start"] <= f["week_end"] for f in fases)
        # En orden cronológico, y ninguna repetida.
        orden = [Fase.desde_texto(f["type"]).orden for f in fases]
        assert orden == sorted(set(orden))
        assert [f["sort"] for f in fases] == list(range(len(fases)))

    @pytest.mark.parametrize("semanas", range(5, 31))
    def test_desde_cinco_semanas_estan_las_cinco(self, semanas):
        assert [f["type"] for f in fases_por_defecto(semanas)] == CLAVES

    @pytest.mark.parametrize("semanas", range(8, 31))
    def test_cada_frontera_es_la_semana_mas_cercana_al_cambio_de_la_curva(self, semanas):
        """`curvas.Cientifica` cambia de pendiente en `fin/15` del macro.

        Si la franja de fases cambiara en otra semana, el entrenador vería
        "Taper" mientras la curva del atleta todavía está en pre-competitivo.
        """
        total = MACRO_15_FASES[-1][1]
        for fase, (_, fin, _) in zip(fases_por_defecto(semanas), MACRO_15_FASES, strict=True):
            assert abs(fase["week_end"] - fin * semanas / total) <= 0.5

    def test_nacen_con_la_etiqueta_y_el_color_de_su_fase(self):
        for f in fases_por_defecto(12):
            fase = Fase.desde_texto(f["type"])
            assert f["name"] == fase.etiqueta
            assert f["color"] == COLOR_DE_FASE[fase]
        assert set(COLOR_DE_FASE) == set(Fase.secuencia())


# ── El plan: cada semana sabe su fase y cómo se llama ───────────────────────

class TestElPlanLlevaLaFase:
    def _plan(self, fases):
        from datetime import date
        return MOTOR.generar_plan(
            distancia=200, tiempo_actual=130.0, tiempo_meta=126.0, semanas=10,
            km_totales=250, curva="science", inicio=date(2026, 1, 5), fases=fases,
        )

    def test_la_clave_es_de_la_ciencia_y_el_nombre_del_entrenador(self):
        semanas = self._plan([
            {"name": "Aeróbico", "type": "base_general", "week_start": 1, "week_end": 6},
            {"name": "Afinamiento", "type": "taper", "week_start": 7, "week_end": 10},
        ])
        assert (semanas[2].fase, semanas[2].nombre_fase) == (Fase.BASE_GENERAL, "Aeróbico")
        assert (semanas[7].fase, semanas[7].nombre_fase) == (Fase.TAPER, "Afinamiento")

    @pytest.mark.parametrize("viejo", ["build", "Construcción", "extension"])
    def test_un_tramo_con_un_tipo_que_no_es_fase_del_macro_no_genera_plan(self, viejo):
        with pytest.raises(ValueError):
            self._plan([{"name": "X", "type": viejo, "week_start": 1, "week_end": 10}])


# ── La puerta del API ────────────────────────────────────────────────────────

class TestElTipoDeUnTramo:
    def _tramo(self, **cambios):
        return {"name": "Tramo", "week_start": 1, "week_end": 4, **cambios}

    def test_acepta_la_clave_y_la_normaliza(self):
        assert PhaseInput(**self._tramo(type=" Umbral_CSS ")).type == "umbral_css"

    @pytest.mark.parametrize("viejo", ["base", "build", "peak", "Construcción", "Descenso"])
    def test_los_tipos_de_antes_de_p3_no_entran(self, viejo):
        with pytest.raises(ValidationError):
            PhaseInput(**self._tramo(type=viejo))

    def test_la_extension_no_es_un_tramo(self):
        with pytest.raises(ValidationError, match="extensión"):
            PhaseInput(**self._tramo(type="extension"))

    def test_sin_tipo_no_hay_tramo(self):
        # Antes caía en "base" en silencio: adivinar la fase es lo que P3 cierra.
        with pytest.raises(ValidationError):
            PhaseInput(**self._tramo())


async def test_crear_un_macro_con_un_tipo_viejo_da_422(client, world: World):
    r = await client.post(f"{API}/plans/", json={
        "name": "Viejo", "start_date": "2026-01-05", "total_weeks": 12, "total_km": 300,
        "phases": [{"name": "Construcción", "type": "build", "week_start": 1, "week_end": 12}],
    }, headers=como(world.owner_email))
    assert r.status_code == 422


async def test_el_macro_nace_con_las_cinco_fases_por_clave(client, world: World):
    r = await client.get(f"{API}/plans/{world.plan_id}", headers=como(world.owner_email))
    assert r.status_code == 200
    fases = r.json()["phases"]
    assert [f["type"] for f in fases] == CLAVES
    assert [f["name"] for f in fases] == [Fase.desde_texto(c).etiqueta for c in CLAVES]


async def test_las_semanas_guardan_la_clave_y_ensenan_el_nombre_del_tramo(
    client, db, world: World,
):
    guardadas = (await db.execute(
        select(WeeklyPlan.week_number, WeeklyPlan.phase)
        .where(WeeklyPlan.athlete_event_id == world.sofia_event_id)
        .order_by(WeeklyPlan.week_number)
    )).all()
    esperadas = {
        s: f["type"] for f in fases_por_defecto(12)
        for s in range(f["week_start"], f["week_end"] + 1)
    }
    assert dict(guardadas) == esperadas

    # El entrenador renombra el primer tramo: la tabla enseña SU nombre, que se
    # lee de `plan_phases` y no de una copia en la semana.
    await db.execute(
        update(PlanPhase)
        .where(PlanPhase.plan_id == world.plan_id, PlanPhase.sort == 0)
        .values(name="Aeróbico")
    )
    await db.commit()
    r = await client.get(
        f"{API}/plans/events/{world.sofia_event_id}/weeks", headers=como(world.owner_email),
    )
    assert r.status_code == 200
    por_semana = {w["week_number"]: w["phase"] for w in r.json()}
    assert por_semana[1] == "Aeróbico"
    assert por_semana[12] == Fase.TAPER.etiqueta


async def test_la_base_no_admite_una_etiqueta_como_fase(db, world: World):
    with pytest.raises(IntegrityError, match="ck_plan_phases_type"):
        await db.execute(
            update(PlanPhase).where(PlanPhase.plan_id == world.plan_id).values(type="build")
        )
    await db.rollback()
    with pytest.raises(IntegrityError, match="ck_weekly_plans_phase"):
        await db.execute(
            update(WeeklyPlan)
            .where(WeeklyPlan.athlete_event_id == world.sofia_event_id)
            .values(phase="Construcción")
        )
    await db.rollback()


async def test_el_asistente_pide_las_fases_por_defecto_al_motor(client, world: World):
    r = await client.get(
        f"{API}/plans/default-phases", params={"weeks": 12}, headers=como(world.owner_email),
    )
    assert r.status_code == 200
    campos = ("name", "type", "week_start", "week_end", "color")
    assert r.json() == [{k: f[k] for k in campos} for f in fases_por_defecto(12)]


async def test_las_fases_por_defecto_son_cosa_del_entrenador(client, world: World):
    r = await client.get(
        f"{API}/plans/default-phases", params={"weeks": 12}, headers=como(world.sofia_email),
    )
    assert r.status_code == 403


async def test_las_fases_por_defecto_piden_un_largo_de_macro_con_sentido(client, world: World):
    r = await client.get(
        f"{API}/plans/default-phases", params={"weeks": 3}, headers=como(world.owner_email),
    )
    assert r.status_code == 422


# ── El frontend conoce las mismas cinco claves ──────────────────────────────

_TIPOS_DEL_FRONTEND = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "types" / "plans.ts"
)


def test_el_tipo_del_frontend_tiene_las_mismas_claves():
    assert _TIPOS_DEL_FRONTEND.exists(), f"No se encontró {_TIPOS_DEL_FRONTEND}"
    texto = _TIPOS_DEL_FRONTEND.read_text(encoding="utf-8")
    union = re.search(r"export type ClaveDeFase\s*=([^\n]+(?:\n\s*\|[^\n]+)*)", texto)
    assert union, "ClaveDeFase no está declarado en lib/types/plans.ts"
    assert re.findall(r"'([a-z_]+)'", union.group(1)) == CLAVES


# ── La migración ─────────────────────────────────────────────────────────────

_ANTES_DE_P3 = "22f704975e94"
_P3 = "a3f1c2d4e5b6"

# Plan 1: los cuatro tramos por defecto de antes, 12 semanas. Plan 2: tipos que
# la API aceptaba sin validar (se deciden por posición). Plan 3: sin tramos.
_TRAMOS_1 = [
    (1, "Base", "base", 1, 4), (2, "Construcción", "build", 5, 9),
    (3, "Pico", "peak", 10, 11), (4, "Descenso", "taper", 12, 12),
]
_TRAMOS_2 = [(5, "Inicio", "xyz", 1, 3), (6, "Medio", "base", 4, 8), (7, "Final", "xyz", 9, 10)]


def _nombre_en(semana: int, tramos) -> str:
    return next(nombre for _, nombre, _, ini, fin in tramos if ini <= semana <= fin)


def _sembrar_antes_de_p3(ruta: Path) -> None:
    con = sqlite3.connect(ruta)
    for plan_id, semanas in ((1, 12), (2, 10), (3, 12)):
        con.execute(
            "INSERT INTO plans (id, team_id, name, start_date, total_weeks, weeks_per_micro, "
            "total_km, progression_curve, pool, n_mac, status) "
            "VALUES (?, 1, 'P', '2026-01-05', ?, 4, 300, 'science', '50', 1, 'active')",
            (plan_id, semanas),
        )
        con.execute(
            "INSERT INTO athlete_plans (id, team_id, plan_id, swimmer_id, is_active) "
            "VALUES (?, 1, ?, 1, 1)", (plan_id, plan_id),
        )
        con.execute(
            "INSERT INTO athlete_events (id, athlete_plan_id, priority, distance, stroke, "
            '"current_time", goal_time) VALUES (?, ?, 1, 200, \'libre\', 130, 125)',
            (plan_id, plan_id),
        )
    for plan_id, tramos in ((1, _TRAMOS_1), (2, _TRAMOS_2)):
        for orden, (tid, nombre, tipo, ini, fin) in enumerate(tramos):
            con.execute(
                "INSERT INTO plan_phases (id, plan_id, name, type, week_start, week_end, "
                "color, sort) VALUES (?, ?, ?, ?, ?, ?, '#22d3ee', ?)",
                (tid, plan_id, nombre, tipo, ini, fin, orden),
            )
    fases_viejas = {
        1: [_nombre_en(s, _TRAMOS_1) for s in range(1, 13)],
        2: [_nombre_en(s, _TRAMOS_2) for s in range(1, 11)],
        3: ["—"] * 12,
    }
    for evento, nombres in fases_viejas.items():
        for semana, nombre in enumerate(nombres, start=1):
            con.execute(
                "INSERT INTO weekly_plans (athlete_event_id, week_number, week_date, "
                "planned_km, expected_time, phase, disabled) "
                "VALUES (?, ?, '2026-01-05', 20, 128, ?, 0)",
                (evento, semana, nombre),
            )
    con.commit()
    con.close()


def _leer(ruta: Path) -> tuple[dict, dict]:
    con = sqlite3.connect(ruta)
    tramos = {r[0]: (r[1], r[2]) for r in con.execute("SELECT id, name, type FROM plan_phases")}
    semanas = {
        (r[0], r[1]): r[2]
        for r in con.execute("SELECT athlete_event_id, week_number, phase FROM weekly_plans")
    }
    con.close()
    return tramos, semanas


def test_la_migracion_convierte_y_el_downgrade_devuelve_lo_de_antes(tmp_path, monkeypatch):
    """Se ejecuta de verdad, contra una base desechable, en las dos direcciones."""
    from alembic.config import Config

    from alembic import command
    from app.core.config import settings

    ruta = tmp_path / "migracion.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{ruta.as_posix()}")
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    command.upgrade(cfg, _ANTES_DE_P3)
    _sembrar_antes_de_p3(ruta)
    tramos_antes, semanas_antes = _leer(ruta)

    command.upgrade(cfg, _P3)
    tramos, semanas = _leer(ruta)
    # Cada tramo va a la fase con la que más se solapa en la forma de 15 semanas;
    # los que no eran ninguno de los cuatro, por su posición en el macro.
    assert {tid: tipo for tid, (_, tipo) in tramos.items()} == {
        1: "base_general", 2: "umbral_css", 3: "pre_competitivo", 4: "taper",
        5: "base_general", 6: "base_general", 7: "taper",
    }
    # Los nombres del entrenador no se tocan.
    assert {tid: nombre for tid, (nombre, _) in tramos.items()} == \
        {tid: nombre for tid, (nombre, _) in tramos_antes.items()}
    # La semana lleva la clave del tramo que la cubre…
    assert [semanas[(1, s)] for s in (1, 4, 5, 9, 10, 11, 12)] == [
        "base_general", "base_general", "umbral_css", "umbral_css",
        "pre_competitivo", "pre_competitivo", "taper",
    ]
    # …y sin tramos, la de la ciencia en esa posición del macro.
    assert [semanas[(3, s)] for s in (1, 6, 12)] == ["base_general", "base_especifica", "taper"]
    assert set(semanas.values()) <= set(CLAVES)

    con = sqlite3.connect(ruta)
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE plan_phases SET type = 'build' WHERE id = 1")
    con.close()

    command.downgrade(cfg, _ANTES_DE_P3)
    tramos, semanas = _leer(ruta)
    # El macro con los cuatro tramos de antes vuelve exactamente como estaba.
    assert {tid: tramos[tid] for tid in (1, 2, 3, 4)} == \
        {tid: tramos_antes[tid] for tid in (1, 2, 3, 4)}
    assert {k: v for k, v in semanas.items() if k[0] in (1, 2, 3)} == semanas_antes
    # El esquema también: sin CHECK y con los largos de antes.
    con = sqlite3.connect(ruta)
    con.execute("UPDATE plan_phases SET type = 'build' WHERE id = 1")
    largos = {
        r[1]: r[2] for r in con.execute("PRAGMA table_info(plan_phases)")
    } | {r[1]: r[2] for r in con.execute("PRAGMA table_info(weekly_plans)")}
    con.close()
    assert (largos["type"], largos["phase"]) == ("VARCHAR(12)", "VARCHAR(60)")
