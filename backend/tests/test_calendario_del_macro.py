"""TODO-24 (C9, 2026-10-14): qué rechaza un macrociclo al crearlo o renombrarlo.

Hasta hoy nada impedía guardar fases solapadas, con huecos o fuera del macro,
competencias después de la última semana o un nombre de solo espacios. Lo que
se rompía después era silencioso: el plan generado manda una semana sin tramo
al último (el taper).

Decisiones (opción recomendada, apuntadas en la bitácora):
- las fases, si vienen, cubren de la semana 1 a la N **sin solapes ni huecos**,
  en cualquier orden;
- una competencia cae entre la semana 1 y la N;
- el nombre no puede ser solo espacios, al crear **y** al renombrar;
- **se valida al escribir, nunca al leer**: un macrociclo ya guardado que lo
  incumpla se sigue abriendo. El mapeo fila → entidad usa el constructor, no
  `nuevo()`.
"""
from __future__ import annotations

from datetime import date

import pytest
from conftest import API, World, como
from sqlalchemy import func, select, text

from app.dominio.entidades import Competencia, FaseDelMacro, Macrociclo
from app.dominio.valores import Fase
from app.persistencia.tablas.planes import Plan


def _fase(inicio: int, fin: int, fase: Fase = Fase.BASE_GENERAL) -> FaseDelMacro:
    return FaseDelMacro(fase=fase, nombre=f"S{inicio}-{fin}", semana_inicio=inicio, semana_fin=fin)


def _nuevo(**cambios) -> Macrociclo:
    base = {"nombre": "Temporada", "inicio": date(2027, 1, 4), "semanas": 12, "km_totales": 300.0}
    return Macrociclo.nuevo(**(base | cambios))


# ── El dominio ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("fases", "mensaje"), [
    ([_fase(1, 7), _fase(7, 12)], "solapa"),
    ([_fase(1, 5), _fase(8, 12)], "hueco"),
    ([_fase(1, 13)], "se sale"),
    ([_fase(2, 12)], "semana 1"),
    ([_fase(1, 11)], "semana 12"),
    ([_fase(9, 3), _fase(1, 12)], "acaba antes"),
    ([_fase(0, 12)], "semana 1"),
])
def test_las_fases_tienen_que_cubrir_el_macro_entero_sin_solaparse(fases, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        _nuevo(fases=fases)


@pytest.mark.parametrize("fases", [
    [],
    [_fase(1, 12)],
    [_fase(1, 4), _fase(5, 9), _fase(10, 12, Fase.TAPER)],
    [_fase(10, 12, Fase.TAPER), _fase(1, 9)],             # en cualquier orden
    [_fase(i, i) for i in range(1, 13)],                   # una por semana
])
def test_fases_que_cubren_el_macro_valen_y_se_guardan_en_el_orden_en_que_llegan(fases):
    macro = _nuevo(fases=fases)
    assert [(f.semana_inicio, f.semana_fin) for f in macro.fases] == [
        (f.semana_inicio, f.semana_fin) for f in fases
    ]


@pytest.mark.parametrize("semana", [0, 13, 99])
def test_una_competencia_fuera_del_macro_no_vale(semana):
    with pytest.raises(ValueError, match="competencia"):
        _nuevo(competencias=[Competencia(nombre="Fuera", semana=semana)])


def test_competencias_en_la_primera_y_la_ultima_semana_valen():
    macro = _nuevo(competencias=[Competencia(nombre="Una", semana=1),
                                 Competencia(nombre="Otra", semana=12, dias=10)])
    assert [c.semana for c in macro.competencias] == [1, 12]


@pytest.mark.parametrize("nombre", ["", " ", "  ", "\t\n ", "　"])
def test_un_nombre_en_blanco_no_vale_ni_al_crear_ni_al_renombrar(nombre):
    with pytest.raises(ValueError, match="nombre"):
        _nuevo(nombre=nombre)
    macro = _nuevo()
    with pytest.raises(ValueError, match="nombre"):
        macro.renombrar(nombre)
    assert macro.nombre == "Temporada"                     # lo rechazado no entró


def test_un_nombre_con_texto_se_guarda_tal_cual_sin_recortar():
    assert _nuevo(nombre="  x  ").nombre == "  x  "
    macro = _nuevo()
    macro.renombrar(" ok ")
    assert macro.nombre == " ok "


def test_leer_no_valida_un_macrociclo_construido_desde_la_fila():
    """El mapeo usa el constructor: uno guardado antes de la regla se abre igual."""
    macro = Macrociclo(
        inicio=date(2027, 1, 4), semanas=12, nombre="  ",
        fases=[_fase(1, 7), _fase(7, 20)], competencias=[Competencia(nombre="x", semana=30)],
    )
    assert macro.fase_de(7).semana_inicio == 1


# ── El API ───────────────────────────────────────────────────────────────────

_BASE = {"name": "Macro", "start_date": "2027-03-01", "total_weeks": 12, "total_km": 300}


def _f(inicio: int, fin: int, tipo: str = "base_general") -> dict:
    return {"name": f"S{inicio}", "type": tipo, "week_start": inicio, "week_end": fin}


async def _planes(db) -> int:
    return (await db.execute(select(func.count()).select_from(Plan))).scalar_one()


@pytest.mark.parametrize("cambios", [
    {"name": "  "},
    {"name": "\t\t"},
    {"phases": [_f(1, 7), _f(7, 12)]},
    {"phases": [_f(1, 5), _f(8, 12)]},
    {"phases": [_f(1, 13)]},
    {"phases": [_f(2, 12)]},
    {"phases": [_f(1, 11)]},
    {"phases": [_f(9, 3), _f(1, 12)]},
    {"competitions": [{"name": "Tarde", "week_number": 13}]},
])
async def test_crear_un_macrociclo_que_no_cabe_da_422_y_no_guarda_nada(
    client, db, world: World, cambios,
):
    antes = await _planes(db)
    r = await client.post(f"{API}/plans/", json=_BASE | cambios, headers=como(world.owner_email))
    assert r.status_code == 422, r.text
    assert await _planes(db) == antes


async def test_crear_en_los_limites_que_valen_da_201(client, world: World):
    jefe = como(world.owner_email)
    for cambios in (
        {"name": "  x  "},
        {"name": "y" * 120},
        {"phases": [_f(10, 12, "taper"), _f(1, 9)]},
        {"phases": [_f(1, 12)]},
        {"competitions": [{"name": "A", "week_number": 1}, {"name": "B", "week_number": 12, "days": 10}]},
        {"total_weeks": 8, "phases": [_f(1, 8)], "competitions": [{"name": "C", "week_number": 8}]},
        {"total_weeks": 24, "competitions": [{"name": "D", "week_number": 24}]},
    ):
        r = await client.post(f"{API}/plans/", json=_BASE | cambios, headers=jefe)
        assert r.status_code == 201, (cambios, r.text)


async def test_renombrar_a_blanco_da_422_y_no_cambia_nada(client, world: World):
    jefe = como(world.owner_email)
    url = f"{API}/plans/{world.plan_id}"
    antes = (await client.get(url, headers=jefe)).json()
    for nombre in ("  ", "\t\t", " \n "):
        r = await client.patch(url, json={"name": nombre}, headers=jefe)
        assert r.status_code == 422, r.text
    assert (await client.get(url, headers=jefe)).json() == antes
    r = await client.patch(url, json={"name": " ok "}, headers=jefe)
    assert r.status_code == 200 and r.json()["name"] == " ok "


async def test_un_macrociclo_guardado_que_incumple_se_sigue_abriendo(client, db, world: World):
    """Validar al leer convertiría cualquier macro viejo que incumpla en un 500."""
    await db.execute(text(
        "UPDATE plan_phases SET week_start = 1, week_end = 30 WHERE plan_id = :p"
    ), {"p": world.plan_id})
    await db.execute(text("UPDATE plans SET name = '  ' WHERE id = :p"), {"p": world.plan_id})
    await db.commit()
    jefe = como(world.owner_email)
    r = await client.get(f"{API}/plans/{world.plan_id}", headers=jefe)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "  "
    # Y se puede seguir editando lo que no toca la regla.
    r = await client.patch(f"{API}/plans/{world.plan_id}", json={"notes": "sigue"}, headers=jefe)
    assert r.status_code == 200, r.text


def test_las_competencias_quedan_por_semana_y_las_fases_como_llegaron():
    macro = _nuevo(
        fases=[_fase(10, 12, Fase.TAPER), _fase(1, 9)],
        competencias=[Competencia(nombre="Final", semana=12), Competencia(nombre="A", semana=4),
                      Competencia(nombre="B", semana=4)],
    )
    assert [c.nombre for c in macro.competencias] == ["A", "B", "Final"]
    assert [f.semana_inicio for f in macro.fases] == [10, 1]
