"""C7: la sesión, lo que el atleta nadó cada día.

Lo que fija este archivo, en el orden en que importa:

  1. **La sesión guarda hechos y deriva el resto.** Metros, duración, RPE y
     fecha se guardan; el ritmo medio y la carga (sTSS) se calculan. Una hora
     entera al CSS vale 100 sTSS, por definición.
  2. **Las dos fronteras.** El atleta apunta, corrige y borra lo suyo, y lo del
     compañero le da 404; el entrenador llega a todo su equipo y a nada de otro.
  3. **Borrar es borrar** (decidido al arrancar C7): la fila desaparece.
"""
from __future__ import annotations

from datetime import date

import pytest
from conftest import API, World, como
from sqlalchemy import func, select

from app.dominio.entidades import Sesion
from app.dominio.valores import Ritmo, Tiempo
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeEquipos
from app.persistencia.tablas.sesiones import SwimSession

DIA = date(2026, 9, 21)


def _sesion(metros: int = 4000, segundos: float = 3600, **kw) -> Sesion:
    return Sesion(atleta_id=1, fecha=DIA, distancia_m=metros, duracion=Tiempo(segundos), **kw)


# ── 1. Dominio ───────────────────────────────────────────────────────────────

def test_el_ritmo_medio_cuenta_el_descanso():
    assert _sesion(4000, 3600).ritmo_medio() == Ritmo(90.0)


def test_una_hora_al_css_vale_100():
    assert _sesion(4000, 3600).carga(Ritmo(90.0)) == pytest.approx(100.0)


def test_la_carga_crece_con_el_cuadrado_de_la_intensidad():
    """Misma hora, un 10 % más rápido que el CSS: IF = 1.1 → 121."""
    assert _sesion(4000, 3600).carga(Ritmo(99.0)) == pytest.approx(121.0)
    # Media hora al CSS: la mitad.
    assert _sesion(2000, 1800).carga(Ritmo(90.0)) == pytest.approx(50.0)


@pytest.mark.parametrize("kw", [
    {"metros": 0}, {"metros": -100}, {"rpe": 0}, {"rpe": 11},
])
def test_lo_que_no_es_una_sesion_no_se_construye(kw):
    with pytest.raises(ValueError):
        _sesion(**kw)


@pytest.mark.parametrize("kw", [{"metros": 4000.5}, {"rpe": 7.5}, {"rpe": True}])
def test_metros_y_rpe_son_enteros(kw):
    with pytest.raises(TypeError):
        _sesion(**kw)


def test_una_duracion_no_positiva_no_es_un_tiempo():
    with pytest.raises(ValueError):
        _sesion(segundos=0)


# ── 2. El API y las fronteras ────────────────────────────────────────────────

def _cuerpo(swimmer_id: int, **kw) -> dict:
    return {"swimmer_id": swimmer_id, "session_date": DIA.isoformat(),
            "distance_m": 4200, "duration_s": 5400, "rpe": 6, **kw}


async def _apuntar(client, email: str, swimmer_id: int, **kw):
    return await client.post(f"{API}/sessions/", json=_cuerpo(swimmer_id, **kw),
                             headers=como(email))


async def test_el_atleta_apunta_lo_suyo_y_sale_con_el_ritmo_derivado(client, world: World):
    r = await _apuntar(client, world.sofia_email, world.sofia_swimmer_id)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["swimmer_id"] == world.sofia_swimmer_id
    assert (cuerpo["distance_m"], cuerpo["duration_s"], cuerpo["rpe"]) == (4200, 5400, 6)
    assert cuerpo["pace_100m"] == pytest.approx(5400 / 42, abs=0.01)


async def test_el_rpe_es_opcional_y_admite_dobles(client, world: World):
    for _ in range(2):
        r = await _apuntar(client, world.sofia_email, world.sofia_swimmer_id, rpe=None)
        assert r.status_code == 201
    lista = await client.get(f"{API}/sessions/", headers=como(world.sofia_email))
    assert [s["rpe"] for s in lista.json()] == [None, None]


async def test_el_atleta_no_apunta_a_nombre_de_otro(client, db, world: World):
    r = await _apuntar(client, world.sofia_email, world.carlos_swimmer_id)
    assert r.status_code == 404
    assert (await db.execute(select(func.count()).select_from(SwimSession))).scalar_one() == 0


async def test_el_entrenador_apunta_a_cualquiera_de_su_equipo(client, world: World):
    for swimmer in (world.sofia_swimmer_id, world.carlos_swimmer_id, world.sin_cuenta_swimmer_id):
        r = await _apuntar(client, world.owner_email, swimmer)
        assert r.status_code == 201


async def test_nadie_apunta_a_un_nadador_de_otro_equipo(client, db, world: World):
    otro = await RepositorioDeEquipos(db).crear("Club Rival")
    # `crear` recibe el equipo explícito: el principal no interviene.
    rival = await RepositorioDeAtletas(db, None).crear(team_id=otro.id, nombre="Rival")  # type: ignore[arg-type]
    r = await _apuntar(client, world.owner_email, rival.id)
    assert r.status_code == 404


async def test_el_atleta_solo_ve_lo_suyo_aunque_lo_pida(client, world: World):
    await _apuntar(client, world.owner_email, world.carlos_swimmer_id)
    await _apuntar(client, world.owner_email, world.sofia_swimmer_id)

    r = await client.get(f"{API}/sessions/?swimmer_id={world.carlos_swimmer_id}",
                         headers=como(world.sofia_email))
    assert r.json() == []
    r = await client.get(f"{API}/sessions/", headers=como(world.sofia_email))
    assert [s["swimmer_id"] for s in r.json()] == [world.sofia_swimmer_id]
    r = await client.get(f"{API}/sessions/", headers=como(world.owner_email))
    assert len(r.json()) == 2


async def test_el_rango_de_fechas_es_inclusivo_y_ordena_de_reciente_a_antigua(client, world: World):
    for dia in ("2026-09-20", "2026-09-21", "2026-09-22", "2026-09-23"):
        await _apuntar(client, world.owner_email, world.sofia_swimmer_id, session_date=dia)
    r = await client.get(f"{API}/sessions/?desde=2026-09-21&hasta=2026-09-22",
                         headers=como(world.owner_email))
    assert [s["session_date"] for s in r.json()] == ["2026-09-22", "2026-09-21"]


async def test_lo_ajeno_da_404_en_leer_corregir_y_borrar(client, db, world: World):
    ajena = (await _apuntar(client, world.carlos_email, world.carlos_swimmer_id)).json()["id"]
    url = f"{API}/sessions/{ajena}"
    sofia = como(world.sofia_email)

    assert (await client.get(url, headers=sofia)).status_code == 404
    assert (await client.patch(url, json={"rpe": 1}, headers=sofia)).status_code == 404
    assert (await client.delete(url, headers=sofia)).status_code == 404
    fila = await db.get(SwimSession, ajena)
    assert fila is not None and fila.rpe == 6, "lo ajeno se tocó de todos modos"


async def test_corregir_cambia_solo_lo_que_llega(client, world: World):
    creada = (await _apuntar(client, world.sofia_email, world.sofia_swimmer_id)).json()
    r = await client.patch(f"{API}/sessions/{creada['id']}", json={"duration_s": 4200},
                           headers=como(world.sofia_email))
    assert r.status_code == 200
    assert (r.json()["duration_s"], r.json()["distance_m"], r.json()["rpe"]) == (4200, 4200, 6)
    assert r.json()["pace_100m"] == pytest.approx(100.0)

    r = await client.patch(f"{API}/sessions/{creada['id']}", json={"rpe": None},
                           headers=como(world.sofia_email))
    assert r.json()["rpe"] is None


@pytest.mark.parametrize("cambio", [
    {"distance_m": None}, {"duration_s": 0}, {"rpe": 11}, {"session_date": None},
])
async def test_corregir_no_admite_lo_que_no_es_una_sesion(client, world: World, cambio):
    creada = (await _apuntar(client, world.sofia_email, world.sofia_swimmer_id)).json()
    r = await client.patch(f"{API}/sessions/{creada['id']}", json=cambio,
                           headers=como(world.sofia_email))
    assert r.status_code == 422


@pytest.mark.parametrize("cuerpo", [
    {"rpe": 0}, {"rpe": 11}, {"distance_m": 0}, {"duration_s": -60},
    {"distance_m": 300_000},
])
async def test_crear_no_admite_lo_que_no_es_una_sesion(client, world: World, cuerpo):
    r = await _apuntar(client, world.sofia_email, world.sofia_swimmer_id, **cuerpo)
    assert r.status_code == 422


# ── 3. Borrar es borrar ──────────────────────────────────────────────────────

async def test_borrar_quita_la_fila(client, db, world: World):
    creada = (await _apuntar(client, world.sofia_email, world.sofia_swimmer_id)).json()
    r = await client.delete(f"{API}/sessions/{creada['id']}", headers=como(world.sofia_email))
    assert r.status_code == 204
    assert await db.get(SwimSession, creada["id"]) is None
    r = await client.get(f"{API}/sessions/{creada['id']}", headers=como(world.sofia_email))
    assert r.status_code == 404
