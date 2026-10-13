"""C9 punto 3 (REDISENO §5.7): el alta de un atleta pasa por `PruebaObjetivo`.

La entidad y su traducción están en `test_prueba_objetivo.py`. Aquí, lo que se
ve desde fuera: `api/v1/macrociclos/nomina.py` construye entidades, el
repositorio arma las filas y el estilo se guarda canónico.
"""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest
from conftest import API, World, como
from sqlalchemy import select

from app.dominio.entidades import PruebaObjetivo, Semana
from app.dominio.servicios.motor import MOTOR
from app.dominio.valores import Tiempo
from app.persistencia.mapeo import prueba_objetivo_desde_fila
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, WeeklyPlan

# ── El API ───────────────────────────────────────────────────────────────────


async def _ficha_nueva(client, world: World) -> int:
    r = await client.post(f"{API}/swimmers/", json={"name": "Nueva Nadadora"},
                          headers=como(world.owner_email))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _plan_nuevo(client, world: World) -> int:
    r = await client.post(f"{API}/plans/", json={
        "name": "Otro macro", "start_date": "2027-01-04", "total_weeks": 12,
        "weeks_per_micro": 4, "total_km": 300, "competitions": [],
    }, headers=como(world.owner_email))
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_el_alta_guarda_cada_prueba_con_sus_semanas_y_el_estilo_canonico(
    client, db, world: World,
):
    plan_id, nueva = await _plan_nuevo(client, world), await _ficha_nueva(client, world)
    r = await client.post(f"{API}/plans/{plan_id}/athletes", json={
        "swimmer_id": nueva, "aerobic_base": 76.0, "aerobic_base_source": "t30",
        "events": [
            {"priority": 2, "distance": 100, "stroke": "crol",
             "current_time": 62.0, "goal_time": 60.5},
            {"priority": 1, "distance": 200, "stroke": "espalda",
             "current_time": 150.0, "goal_time": 146.0},
        ],
    }, headers=como(world.owner_email))
    assert r.status_code == 201, r.text

    inscrita = next(a for a in r.json()["athletes"] if a["swimmer_id"] == nueva)
    assert [(e["priority"], e["distance"], e["stroke"], e["current_time"], e["goal_time"])
            for e in inscrita["events"]] == [
        (1, 200, "espalda", 150.0, 146.0), (2, 100, "libre", 62.0, 60.5),
    ]

    db.expire_all()
    filas = list((await db.execute(
        select(AthleteEvent).join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
        .where(AthletePlan.plan_id == plan_id, AthletePlan.swimmer_id == nueva)
        .order_by(AthleteEvent.priority)
    )).scalars())
    assert [f.stroke for f in filas] == ["espalda", "libre"]
    for fila in filas:
        semanas = list((await db.execute(
            select(WeeklyPlan).where(WeeklyPlan.athlete_event_id == fila.id)
            .order_by(WeeklyPlan.week_number)
        )).scalars())
        assert [s.week_number for s in semanas] == list(range(1, 13))
        # La curva baja de la marca hacia la meta (sin pasarla: el techo del
        # macro puede quedarse antes) y cada semana lleva su fase y sus km.
        assert fila.goal_time - 0.01 <= semanas[-1].expected_time < fila.current_time
        assert all(s.phase and s.planned_km > 0 for s in semanas)


async def test_la_respuesta_del_alta_no_depende_del_recolector_de_basura(client, world: World):
    """El alta responde con el macrociclo, y el recién inscrito tiene que estar.

    Hasta el 2026-10-13 estaba **solo si el recolector había pasado**. La ruta
    lee el macrociclo, inscribe y lo vuelve a leer; la inscripción entra por su
    `plan_id`, no por la relación, así que la nómina del `Plan` ya cargado se
    quedaba como estaba, y SQLAlchemy no repuebla una colección cargada de un
    objeto que sigue vivo. Seguía vivo o no según el recolector: `Plan` y sus
    fases se referencian en ciclo. Medido en HEAD con `gc.disable()`: la
    respuesta salía con `athletes: []`.
    """
    import gc

    plan_id, nueva = await _plan_nuevo(client, world), await _ficha_nueva(client, world)
    gc.disable()
    try:
        r = await client.post(f"{API}/plans/{plan_id}/athletes", json={
            "swimmer_id": nueva,
            "events": [{"priority": 1, "distance": 200, "stroke": "libre",
                        "current_time": 130.0, "goal_time": 126.0}],
        }, headers=como(world.owner_email))
    finally:
        gc.enable()
    assert r.status_code == 201, r.text
    assert [a["swimmer_id"] for a in r.json()["athletes"]] == [nueva]


async def test_una_prueba_imposible_sigue_sin_entrar(client, world: World):
    plan_id, nueva = await _plan_nuevo(client, world), await _ficha_nueva(client, world)
    r = await client.post(f"{API}/plans/{plan_id}/athletes", json={
        "swimmer_id": nueva,
        "events": [{"priority": 1, "distance": 50, "stroke": "combinado",
                    "current_time": 30.0, "goal_time": 29.0}],
    }, headers=como(world.owner_email))
    assert r.status_code == 422
    assert "No existe la prueba 50 combinado" in r.text


async def test_guardar_da_identidad_a_las_pruebas_y_solo_las_admite_al_crear(db, world: World):
    from app.api.v1.auth.service import get_by_email
    from app.core.dependencies import _principal_for
    from app.dominio.entidades import Atleta
    from app.persistencia.repositorios import (
        RepositorioDeAtletas,
        RepositorioDeInscripciones,
        RepositorioDeMacrociclos,
    )

    jefe = await _principal_for(db, await get_by_email(db, world.owner_email))
    macros = RepositorioDeMacrociclos(db, jefe)
    repo = RepositorioDeInscripciones(macros)
    # Un macrociclo terminado: no ocupa el calendario de nadie y admite al atleta.
    from app.api.v1.macrociclos.schemas import PlanCreate
    from app.api.v1.macrociclos.service import create_plan
    plan = await create_plan(macros, PlanCreate(
        name="Macro pasado", start_date=date(2025, 1, 6), total_weeks=12, total_km=300,
    ), world.team_id, jefe.id)
    macro = await macros.recargar(plan.id)
    atleta = Atleta.nueva("Recién Llegada")
    await RepositorioDeAtletas(db, jefe).guardar(atleta)

    principal = PruebaObjetivo.nueva(200, "libre", 130.0, 126.0)
    segunda = PruebaObjetivo.nueva(100, "mariposa", 68.0, 66.5, prioridad=2)
    def semanas() -> list[Semana]:
        return [
            Semana(numero=s.numero, fecha=s.fecha, km_planificados=s.km,
                   esperado=Tiempo(s.tiempo_esperado), fase=s.fase)
            for s in MOTOR.generar_plan(
                distancia=200, tiempo_actual=130.0, tiempo_meta=126.0, semanas=12,
                km_totales=300.0, curva=macro.curva, inicio=macro.inicio,
            )
        ]

    de_la_principal, de_la_segunda = semanas(), semanas()
    inscripcion = macro.inscribir(atleta)
    await repo.guardar(
        inscripcion, pruebas=[(principal, de_la_principal), (segunda, de_la_segunda)],
    )

    assert inscripcion.id is not None
    # Cada semana sale con su identidad y la de SU prueba, no la de la otra.
    assert len({s.id for s in de_la_principal + de_la_segunda}) == 24
    assert {s.prueba_id for s in de_la_principal} == {principal.id}
    assert {s.prueba_id for s in de_la_segunda} == {segunda.id}
    # Y la de SU número: el `id` de cada semana es el de la fila de esa semana.
    for prueba, suyas in ((principal, de_la_principal), (segunda, de_la_segunda)):
        filas = (await db.execute(
            select(WeeklyPlan.id, WeeklyPlan.week_number)
            .where(WeeklyPlan.athlete_event_id == prueba.id)
        )).all()
        assert {s.id: s.numero for s in suyas} == dict(filas)
    assert principal.id is not None and segunda.id is not None and principal.id != segunda.id
    assert principal.inscripcion_id == segunda.inscripcion_id == inscripcion.id
    releida = prueba_objetivo_desde_fila(await db.get(AthleteEvent, segunda.id))
    assert releida == segunda
    assert (releida.prueba, releida.actual, releida.meta, releida.prioridad) == (
        segunda.prueba, segunda.actual, segunda.meta, 2,
    )

    # Con la inscripción ya guardada, las pruebas no entran por esta puerta.
    inscripcion.dar_de_baja()
    with pytest.raises(ValueError, match="solo entran al crear"):
        await repo.guardar(inscripcion, pruebas=[(PruebaObjetivo.nueva(50, "libre", 28.0, 27.5), [])])


async def test_una_fila_de_antes_con_alias_se_sigue_leyendo_igual(client, db, world: World):
    """Las filas viejas no se tocan: una que guarda «crol» pinta su tabla y su tablero."""
    fila = await db.get(AthleteEvent, world.carlos_event_id)
    jefe = como(world.owner_email)
    antes = (await client.get(f"{API}/plans/events/{fila.id}/weeks", headers=jefe)).json()
    fila.stroke = "crol"
    await db.commit()

    r = await client.get(f"{API}/plans/events/{fila.id}/weeks", headers=jefe)
    assert r.status_code == 200, r.text
    assert r.json() == antes                      # mismas zonas, mismos tiempos
    for ruta in ("/dashboard/summary", "/dashboard/team-week"):
        assert (await client.get(f"{API}{ruta}", headers=jefe)).status_code == 200
    assert (await db.get(AthleteEvent, fila.id)).stroke == "crol"   # leer no la reescribe


# ── La estructura ────────────────────────────────────────────────────────────


def test_el_alta_ya_no_arma_filas_del_orm():
    """`nomina.py` construye entidades; las filas las arma el repositorio."""
    archivo = Path(__file__).resolve().parent.parent / "app/api/v1/macrociclos/nomina.py"
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    # Las tres formas de traerse una tabla: `from app.persistencia.tablas.x import Y`,
    # `import app.persistencia.tablas.x` y `from app.persistencia import tablas`.
    importados: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            importados += [alias.name for alias in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importados += [f"{nodo.module}.{alias.name}" for alias in nodo.names]
    assert importados, "no se leyó ningún import: el test estaría pasando en vacío"
    assert not [m for m in importados if m.startswith("app.persistencia.tablas")]
