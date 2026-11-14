"""El test de lactato por el API: lo que se guarda, lo que vuelve y a quién.

Tres promesas que importan más que la aritmética (que ya fija
`test_test_de_lactato.py`):

1. **No es una base aeróbica.** No aparece en `/aerobic-tests`, no toca la
   carga y no es candidato a base por defecto al inscribir. Es la trampa del
   prompt: un 10×400 en R1 colado ahí contamina el motor entero.
2. **Datos de salud.** El atleta ve solo los suyos; el de otro club es 404.
3. **Se apunta; no se calcula a mano.** Lo derivado vuelve en la respuesta y no
   hay forma de mandarlo.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest
from conftest import API, World, como
from lactato_22_09 import A01, A06
from sqlalchemy import func, select

from app.core.auditoria import TipoDeEvento
from app.persistencia.tablas import vocabulario as voc
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.carga import DailyLoad
from app.persistencia.tablas.equipos import Team

RUTA = f"{API}/lactate-tests/"


def _cuerpo(swimmer_id: int, datos=A01, **extra) -> dict:
    cuerpo = {
        "swimmer_id": swimmer_id, "test_date": "2026-09-22", "target_zone": "R1",
        "rep_distance": 400, "rest_type": "pausa", "rest_s": 30,
        "proposed_min": datos["propuesto"][0], "proposed_max": datos["propuesto"][1],
        "reference_time": datos["referencia"], "counted_segment_m": 50,
        "sample_site": "lobulo", "analyzer": "Lactate Pro 2", "sample_minute": 1,
        "hr_method": "palpacion",
        "reps": [
            {"swim_time": t, "lactate": lac, "heart_rate": fc, "effort": rpe, "stroke_counts": list(b)}
            for t, lac, fc, rpe, b in datos["reps"]
        ],
    }
    cuerpo.update(extra)
    return cuerpo


async def _crear(client, world: World, **extra):
    return await client.post(
        RUTA, json=_cuerpo(world.sofia_swimmer_id, **extra), headers=como(world.owner_email),
    )


class TestGuardarYLeer:
    async def test_lo_derivado_vuelve_y_cuadra_con_la_serie_real(self, client, world: World):
        r = await _crear(client, world)
        assert r.status_code == 201, r.text
        body = r.json()
        s = body["summary"]
        assert s["mean_time"] == pytest.approx(292.5)
        assert round(s["cv_pct"], 1) == 0.7
        assert s["diff_proposed"] == pytest.approx(-12.5)
        assert s["pct_reference"] == pytest.approx(83.8)
        assert s["stroke_drift_pct"] == pytest.approx(33.6)
        assert s["stroke_index"] == pytest.approx(3.98, abs=0.01)
        assert (s["lactate_median"], s["lactate_zone"], s["steady_state"]) == (3.0, "dentro", True)
        assert body["zone_range"] == [2.0, 3.5]
        assert body["warnings"] == []
        primera = body["reps"][0]
        assert primera["m_per_stroke"] == pytest.approx(1.64)
        assert primera["cycle_rate_estimated"] is True
        assert body["reps"][1]["lactate_zone"] == "dentro"
        assert (body["sample_site"], body["hr_method"]) == ("lobulo", "palpacion")

    async def test_releerlo_da_lo_mismo(self, client, world: World):
        creado = (await _crear(client, world)).json()
        leido = (await client.get(f"{RUTA}{creado['id']}", headers=como(world.owner_email))).json()
        assert leido == creado

    async def test_lo_derivado_no_se_puede_mandar(self, client, world: World):
        # Un campo derivado en la petición se ignora: el que vuelve es el calculado.
        cuerpo = _cuerpo(world.sofia_swimmer_id)
        cuerpo["reps"][0]["speed"] = 99
        r = await client.post(RUTA, json=cuerpo, headers=como(world.owner_email))
        assert r.json()["reps"][0]["speed"] == pytest.approx(400 / 291, abs=1e-3)


class TestNoEsUnaBaseAerobica:
    async def test_no_aparece_entre_los_tests_aerobicos(self, client, world: World):
        antes = (await client.get(f"{API}/aerobic-tests/", headers=como(world.owner_email))).json()
        assert (await _crear(client, world)).status_code == 201
        despues = (await client.get(f"{API}/aerobic-tests/", headers=como(world.owner_email))).json()
        assert despues == antes

    async def test_no_toca_la_carga(self, client, db, world: World):
        contar = select(func.count()).select_from(DailyLoad).where(
            DailyLoad.swimmer_id == world.sofia_swimmer_id)
        antes = (await db.execute(contar)).scalar_one()
        assert (await _crear(client, world)).status_code == 201
        assert (await db.execute(contar)).scalar_one() == antes


class TestQuienVeQue:
    async def test_el_atleta_ve_los_suyos_y_no_los_de_un_companero(self, client, world: World):
        suyo = (await _crear(client, world)).json()
        ajeno = (await client.post(
            RUTA, json=_cuerpo(world.carlos_swimmer_id), headers=como(world.owner_email),
        )).json()
        lista = (await client.get(RUTA, headers=como(world.sofia_email))).json()
        assert [t["id"] for t in lista] == [suyo["id"]]
        # Pedir la lista del compañero no la amplía.
        filtrada = await client.get(RUTA, params={"swimmer_id": world.carlos_swimmer_id},
                                    headers=como(world.sofia_email))
        assert filtrada.json() == []
        assert (await client.get(f"{RUTA}{ajeno['id']}", headers=como(world.sofia_email))).status_code == 404

    async def test_el_atleta_no_apunta_ni_analiza_ni_da_de_baja(self, client, world: World):
        cuerpo = _cuerpo(world.sofia_swimmer_id)
        assert (await client.post(RUTA, json=cuerpo, headers=como(world.sofia_email))).status_code == 403
        assert (await client.post(f"{RUTA}analyze", json=cuerpo,
                                  headers=como(world.sofia_email))).status_code == 403
        creado = (await _crear(client, world)).json()
        r = await client.delete(f"{RUTA}{creado['id']}", headers=como(world.sofia_email))
        assert r.status_code == 403

    async def test_un_nadador_de_otro_club_es_404(self, client, db, world: World):
        otro = Team(name="Otro club", is_active=True)
        db.add(otro)
        await db.flush()
        ajeno = Swimmer(team_id=otro.id, name="Ajeno", specialty="fondo", main_stroke="libre", is_active=True)
        db.add(ajeno)
        await db.commit()
        for swimmer_id in (ajeno.id, 999_999):
            r = await client.post(RUTA, json=_cuerpo(swimmer_id), headers=como(world.owner_email))
            assert r.status_code == 404, swimmer_id


class TestLoQueSeRechaza:
    @pytest.mark.parametrize("cambio", [
        {"counted_segment_m": None},                 # brazadas sin tramo
        {"mode": "escalonado"},                      # en el modelo, no en la v1
        {"target_zone": "Z9"},
        {"proposed_min": 306, "proposed_max": 304},  # propuesto al revés
        {"proposed_max": None},                      # un solo extremo
        {"reps": []},
    ])
    async def test_422(self, client, world: World, cambio):
        r = await _crear(client, world, **cambio)
        assert r.status_code == 422, r.text

    async def test_un_lactato_imposible_es_422(self, client, world: World):
        cuerpo = _cuerpo(world.sofia_swimmer_id)
        cuerpo["reps"][1]["lactate"] = 45.0
        r = await client.post(RUTA, json=cuerpo, headers=como(world.owner_email))
        assert r.status_code == 422


class TestAvisosYBaja:
    async def test_el_analisis_en_vivo_avisa_sin_guardar(self, client, db, world: World):
        r = await client.post(f"{RUTA}analyze", json=_cuerpo(world.sofia_swimmer_id, datos=A06),
                              headers=como(world.owner_email))
        assert r.status_code == 200, r.text
        assert {(a["rep_number"], a["field"]) for a in r.json()["warnings"]} == {(2, "lactato"), (6, "tiempo")}
        assert (await client.get(RUTA, headers=como(world.owner_email))).json() == []

    async def test_dar_de_baja_lo_saca_de_la_lista_y_se_audita(self, client, db, world: World):
        creado = (await _crear(client, world)).json()
        r = await client.delete(f"{RUTA}{creado['id']}", headers=como(world.owner_email))
        assert r.status_code == 204
        assert (await client.get(RUTA, headers=como(world.owner_email))).json() == []
        # No se borra: la ficha sigue y dice que está de baja.
        leido = (await client.get(f"{RUTA}{creado['id']}", headers=como(world.owner_email))).json()
        assert leido["is_active"] is False
        db.expire_all()
        [evento] = (await db.execute(select(EventoDeAuditoria).where(
            EventoDeAuditoria.event_type == str(TipoDeEvento.TEST_DE_LACTATO_BAJA),
        ))).scalars().all()
        assert (evento.target_type, evento.target_id) == ("lactate_test", creado["id"])


# ── Vocabularios y migración ────────────────────────────────────────────────

_MIGRACION = next(
    (Path(__file__).resolve().parents[1] / "alembic" / "versions").glob("*_a7d3e5f1c9b4_*.py"),
)


def _migracion():
    spec = importlib.util.spec_from_file_location("migracion_lactato", _MIGRACION)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_la_migracion_lleva_los_vocabularios_del_dominio():
    assert {c: set(v) for c, v, _ in _migracion().CHECKS} == {
        "mode": set(voc.MODOS_DE_LACTATO), "target_zone": set(voc.ZONAS),
        "rest_type": set(voc.TIPOS_DE_DESCANSO), "sample_site": set(voc.SITIOS_DE_MUESTRA),
        "hr_method": set(voc.METODOS_DE_FC),
    }


def test_la_migracion_sube_y_baja_en_sqlite(tmp_path, monkeypatch):
    from alembic.config import Config

    from alembic import command
    from app.core.config import settings

    ruta = tmp_path / "lactato.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{ruta.as_posix()}")
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))

    def tablas() -> set[str]:
        con = sqlite3.connect(ruta)
        try:
            return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            con.close()

    command.upgrade(cfg, "head")
    assert {"lactate_tests", "lactate_test_reps"} <= tablas()
    con = sqlite3.connect(ruta)
    con.execute("INSERT INTO teams (id, name, is_active) VALUES (1, 't', 1)")
    con.execute("INSERT INTO swimmers (id, team_id, name, specialty, main_stroke, is_active) "
                "VALUES (1, 1, 'a', 'fondo', 'libre', 1)")
    con.commit()
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO lactate_tests (team_id, swimmer_id, test_date, mode, target_zone, "
                    "rep_distance) VALUES (1, 1, '2026-09-22', 'control', 'Z9', 400)")
    con.close()
    command.downgrade(cfg, "f4c2a9d7e1b3")
    assert not {"lactate_tests", "lactate_test_reps"} & tablas()
    command.upgrade(cfg, "head")
    assert {"lactate_tests", "lactate_test_reps"} <= tablas()
