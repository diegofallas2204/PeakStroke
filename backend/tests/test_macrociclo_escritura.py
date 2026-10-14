"""C9 (REDISENO §5.4): el macrociclo se crea, se edita y se borra por su entidad.

Hasta el 2026-10-13 `api/v1/macrociclos/service.py` armaba la fila con
`Plan(**data.model_dump())` y la editaba con un `setattr` por campo.

Decisiones (opción recomendada, 2026-10-13):
- el equipo y el entrenador a cargo salen del `Principal` del repositorio;
- al editar se escribe solo lo editable: nombre, notas, estado, meta, piscina
  y número de macro;
- un `null` explícito en un campo que no puede quedar vacío no cambia nada
  (antes: 500);
- **sin** invariantes nuevas sobre fases y competencias: es una decisión
  aparte (TODO-24).
"""
from __future__ import annotations

from datetime import date

import pytest
from conftest import API, World, como
from sqlalchemy import select

from app.api.v1.auth.service import get_by_email
from app.api.v1.macrociclos.schemas import PlanCreate
from app.api.v1.macrociclos.service import nuevo_desde
from app.core.dependencies import _principal_for
from app.dominio.entidades import Competencia, FaseDelMacro, Macrociclo
from app.dominio.valores import EstadoDeMacro, Fase, Piscina
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.planes import Competition, Plan, PlanCoach, PlanPhase

# ── El dominio ───────────────────────────────────────────────────────────────


def _macro(**cambios) -> Macrociclo:
    base = {"nombre": "Temporada", "inicio": date(2027, 1, 4), "semanas": 12, "km_totales": 300.0}
    return Macrociclo.nuevo(**(base | cambios))


def test_un_macrociclo_nuevo_nace_activo_sin_equipo_y_con_la_piscina_como_valor():
    macro = _macro(piscina="25", n_mac=2, prueba_principal="Nacional")
    assert (macro.id, macro.equipo_id) == (None, None)
    assert (macro.estado, macro.piscina, macro.n_mac) == (EstadoDeMacro.ACTIVO, Piscina.CORTA, 2)
    assert (macro.nombre, macro.semanas, macro.km_totales) == ("Temporada", 12, 300.0)
    with pytest.raises(ValueError, match="Piscina"):
        _macro(piscina="33")
    with pytest.raises(ValueError):
        _macro(semanas=0)


def test_el_macrociclo_lleva_sus_fases_y_competencias_y_no_comparte_las_listas():
    fases = [FaseDelMacro(fase=Fase.TAPER, nombre="Afinar", semana_inicio=10, semana_fin=12)]
    macro = _macro(fases=fases, competencias=[Competencia(nombre="Final", semana=12)])
    fases.clear()
    assert [f.nombre for f in macro.fases] == ["Afinar"]
    assert macro.fase_de(11).fase is Fase.TAPER and macro.competencias[0].semana == 12


def test_lo_que_se_le_puede_editar_y_lo_que_no_admite():
    macro = _macro()
    macro.renombrar("Otro nombre")
    macro.anotar("Con parón en Semana Santa")
    macro.fijar_meta("Regional")
    macro.cambiar_estado(EstadoDeMacro.SUSPENDIDO)
    macro.cambiar_piscina(Piscina.CORTA)
    macro.numerar(3)
    assert (macro.nombre, macro.notas, macro.prueba_principal) == (
        "Otro nombre", "Con parón en Semana Santa", "Regional",
    )
    assert (macro.estado, macro.piscina, macro.n_mac) == (
        EstadoDeMacro.SUSPENDIDO, Piscina.CORTA, 3,
    )
    macro.anotar(None)
    macro.fijar_meta(None)
    assert (macro.notas, macro.prueba_principal) == (None, None)

    with pytest.raises(TypeError):
        macro.cambiar_estado("suspended")
    with pytest.raises(TypeError):
        macro.cambiar_piscina("25")
    with pytest.raises(ValueError):
        macro.numerar(0)
    with pytest.raises(TypeError):
        macro.numerar(True)
    assert macro.nombre == "Otro nombre"                 # nada de lo rechazado entró


def test_el_formulario_sin_fases_trae_las_cinco_por_defecto():
    macro = nuevo_desde(PlanCreate(
        name="Sin fases", start_date=date(2027, 1, 4), total_weeks=15, total_km=400,
    ))
    assert [f.fase for f in macro.fases] == list(Fase.secuencia())
    assert [f.orden for f in macro.fases] == [0, 1, 2, 3, 4]
    assert (macro.fases[0].semana_inicio, macro.fases[-1].semana_fin) == (1, 15)


# ── El repositorio ───────────────────────────────────────────────────────────


async def _repo(db, email: str) -> RepositorioDeMacrociclos:
    return RepositorioDeMacrociclos(db, await _principal_for(db, await get_by_email(db, email)))


async def test_al_crear_el_equipo_y_quien_lo_lleva_salen_de_quien_lo_crea(db, world: World):
    repo = await _repo(db, world.assistant_email)
    macro = _macro(
        fases=[FaseDelMacro(fase=Fase.BASE_GENERAL, nombre="Base", semana_inicio=1,
                            semana_fin=12, color="#123456")],
        competencias=[Competencia(nombre="Final", semana=12, dias=2, es_principal=True)],
    )
    macro.equipo_id = 999                                 # lo que diga la entidad no cuenta
    fila = await repo.guardar(macro)

    assert (macro.id, macro.equipo_id) == (fila.id, world.team_id)
    assert fila.team_id == world.team_id and fila.status == "active"
    a_cargo = (await db.execute(select(PlanCoach).where(PlanCoach.plan_id == fila.id))).scalars().all()
    assert [(c.coach_id, c.team_id) for c in a_cargo] == [(repo.principal.id, world.team_id)]
    fase = (await db.execute(select(PlanPhase).where(PlanPhase.plan_id == fila.id))).scalars().one()
    assert (fase.name, fase.type, fase.color, fase.week_start, fase.week_end, fase.sort) == (
        "Base", "base_general", "#123456", 1, 12, 0,
    )
    comp = (await db.execute(select(Competition).where(Competition.plan_id == fila.id))).scalars().one()
    assert (comp.name, comp.week_number, comp.days, comp.is_main) == ("Final", 12, 2, True)
    assert (macro.fases[0].id, macro.competencias[0].id) == (fase.id, comp.id)
    # Y quien lo creó lo ve; el dueño también; el otro atleta, no.
    assert await repo.por_id(fila.id) is not None
    assert await (await _repo(db, world.owner_email)).por_id(fila.id) is not None
    assert await (await _repo(db, world.sofia_email)).por_id(fila.id) is None


async def test_al_editar_solo_se_escribe_lo_editable(db, world: World):
    repo = await _repo(db, world.owner_email)
    antes = await repo.fila_de(world.plan_id)
    fijo = (antes.start_date, antes.total_weeks, antes.weeks_per_micro, antes.total_km, antes.team_id)
    fases = [(f.name, f.type, f.week_start, f.week_end) for f in antes.phases]

    macro = await repo.por_id(world.plan_id)
    macro.renombrar("Editado")
    macro.cambiar_estado(EstadoDeMacro.BORRADOR)
    # Lo que ninguna ruta edita: aunque la entidad lo traiga cambiado, no se escribe.
    macro.inicio, macro.semanas, macro.km_totales = date(2030, 1, 1), 20, 999.0
    macro.semanas_por_micro, macro.equipo_id = 6, 999
    macro.fases.clear()
    await repo.guardar(macro)

    # Columnas pedidas a la base, no atributos de un objeto que la sesión ya tenía.
    assert (await db.execute(
        select(Plan.name, Plan.status).where(Plan.id == world.plan_id)
    )).one() == ("Editado", "draft")
    assert (await db.execute(select(
        Plan.start_date, Plan.total_weeks, Plan.weeks_per_micro, Plan.total_km, Plan.team_id,
    ).where(Plan.id == world.plan_id))).one() == fijo
    assert [tuple(f) for f in (await db.execute(
        select(PlanPhase.name, PlanPhase.type, PlanPhase.week_start, PlanPhase.week_end)
        .where(PlanPhase.plan_id == world.plan_id).order_by(PlanPhase.sort)
    )).all()] == fases


async def test_un_macrociclo_que_no_se_ve_no_se_guarda_ni_se_borra(db, world: World):
    """El asistente no está en `plan_coaches`: con la entidad en la mano, tampoco."""
    macro = await (await _repo(db, world.owner_email)).por_id(world.plan_id)
    macro.renombrar("Del asistente")
    asistente = await _repo(db, world.assistant_email)
    with pytest.raises(LookupError):
        await asistente.guardar(macro)
    with pytest.raises(LookupError):
        await asistente.borrar(macro)
    db.expire_all()
    assert (await db.get(Plan, world.plan_id)).name == "Macrociclo de Prueba"


# ── El API ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cuerpo", [
    {"name": None}, {"status": None}, {"pool": None}, {"n_mac": None},
    {"name": None, "status": None, "pool": None, "n_mac": None},
])
async def test_un_null_en_lo_que_no_puede_quedar_vacio_no_cambia_nada(
    client, db, world: World, cuerpo,
):
    """Medido en db56a20: los cuatro daban 500 (NOT NULL)."""
    jefe = como(world.owner_email)
    antes = (await client.get(f"{API}/plans/{world.plan_id}", headers=jefe)).json()
    r = await client.patch(f"{API}/plans/{world.plan_id}", json=cuerpo, headers=jefe)
    assert r.status_code == 200, r.text
    assert r.json() == antes


async def test_un_nombre_que_el_formulario_acepta_no_lo_rechaza_la_entidad(
    client, world: World,
):
    """El formulario pide de 2 a 120 caracteres y no recorta: dos espacios valen.

    Es feo y está apuntado (TODO-24), pero una entidad más estricta que su
    formulario no da un 422: da un 500, en una petición que antes devolvía 200.
    Lo cazó el revisor de este bloque con `renombrar` rechazando los espacios.
    """
    jefe = como(world.owner_email)
    for nombre in ("  ", "\t\t", "a" * 120):
        r = await client.patch(f"{API}/plans/{world.plan_id}", json={"name": nombre}, headers=jefe)
        assert r.status_code == 200, r.text
        assert r.json()["name"] == nombre
    r = await client.post(f"{API}/plans/", json={
        "name": "  ", "start_date": "2027-03-01", "total_weeks": 10, "total_km": 250,
    }, headers=jefe)
    assert r.status_code == 201 and r.json()["name"] == "  "


async def test_un_null_en_las_notas_o_en_la_meta_las_borra(client, world: World):
    jefe = como(world.owner_email)
    url = f"{API}/plans/{world.plan_id}"
    r = await client.patch(url, json={"notes": "algo", "main_event": "Nacional"}, headers=jefe)
    assert (r.json()["notes"], r.json()["main_event"]) == ("algo", "Nacional")
    r = await client.patch(url, json={"notes": None, "main_event": None}, headers=jefe)
    assert r.status_code == 200, r.text
    assert (r.json()["notes"], r.json()["main_event"]) == (None, None)


async def test_editar_cambia_lo_enviado_y_deja_lo_demas(client, world: World):
    jefe = como(world.owner_email)
    url = f"{API}/plans/{world.plan_id}"
    antes = (await client.get(url, headers=jefe)).json()
    r = await client.patch(url, json={"pool": "25", "n_mac": 2, "status": "suspended"}, headers=jefe)
    assert r.status_code == 200, r.text
    despues = r.json()
    cambiado = {"pool": "25", "n_mac": 2, "status": "suspended", "effective_status": "suspended"}
    assert {k: despues[k] for k in cambiado} == cambiado
    assert {k: v for k, v in despues.items() if k not in cambiado} == {
        k: v for k, v in antes.items() if k not in cambiado
    }
    assert (await client.get(url, headers=jefe)).json() == despues


async def test_crear_responde_lo_mismo_que_leer_despues(client, world: World):
    jefe = como(world.owner_email)
    r = await client.post(f"{API}/plans/", json={
        "name": "Recién creado", "start_date": "2027-03-01", "total_weeks": 10,
        "total_km": 250, "pool": "25", "n_mac": 2, "main_event": "Copa", "notes": "n",
        "phases": [
            {"name": "Uno", "type": "base_general", "week_start": 1, "week_end": 5},
            {"name": "Dos", "type": "taper", "week_start": 6, "week_end": 10, "color": "#010203"},
        ],
        "competitions": [{"name": "Copa", "week_number": 10, "days": 2, "is_main": True}],
    }, headers=jefe)
    assert r.status_code == 201, r.text
    creado = r.json()
    assert [(f["name"], f["type"], f["sort"], f["color"]) for f in creado["phases"]] == [
        ("Uno", "base_general", 0, "#8b5cf6"), ("Dos", "taper", 1, "#010203"),
    ]
    assert (creado["status"], creado["effective_status"], creado["athletes"]) == ("active", "active", [])
    assert (await client.get(f"{API}/plans/{creado['id']}", headers=jefe)).json() == creado
