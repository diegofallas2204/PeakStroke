"""El macrociclo como objeto del API: crearlo, editarlo y presentarlo.

Las reglas de **acceso** (quién ve qué) están en
`persistencia/repositorios/macrociclos.py`, y la de **inscripción** (un atleta,
un macrociclo vivo) en `inscripcion.py`. Este módulo asume que las dos ya se
comprobaron.

**Lo que este archivo ya no tiene.** Hasta el paso 5 vivían aquí
`current_week_of()` y `effective_status()`: dos reglas puras, sin base de datos,
que el tablero y `aerobic_tests` importaban de un módulo hermano para poder
preguntarle algo a un plan. Eran P5 del §0 en dos líneas. Hoy la respuesta viaja
dentro del `Macrociclo` que devuelve el repositorio (`semana_actual()`,
`estado_efectivo()`) y no queda ni el envoltorio: un envoltorio que delega sigue
siendo un import que cruza.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.dominio.entidades import Macrociclo
from app.dominio.servicios.motor import fases_por_defecto
from app.persistencia.mapeo import macrociclo_desde_fila
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import Competition, Plan, PlanCoach, PlanPhase

from .schemas import AthletePlanResponse, PlanCreate, PlanResponse, PlanUpdate


async def _swimmer_map(db: AsyncSession, ids: list[int]) -> dict[int, Swimmer]:
    if not ids:
        return {}
    rows = (await db.execute(select(Swimmer).where(Swimmer.id.in_(ids)))).scalars()
    return {s.id: s for s in rows}


async def to_plan_response(
    db: AsyncSession, fila: Plan, principal: Principal,
) -> PlanResponse:
    """El macrociclo tal y como lo ve quien pregunta.

    Entran las dos caras del mismo plan y cada una hace lo suyo: la **entidad**
    contesta lo que se deriva (en qué semana va, qué estado tiene de verdad) y
    la **fila** aporta la nómina, que todavía no es entidad (§5.6). Cuando
    `Inscripcion` exista, el segundo argumento desaparece.

    El atleta ve el plan —fechas, fases, competencias, su propia inscripción—
    pero no con quién lo comparte. `fila.athlete_plans` trae la nómina completa
    porque la relación no sabe de permisos; el recorte va aquí, que es el único
    sitio por el que esa nómina sale hacia fuera.
    """
    macro: Macrociclo = macrociclo_desde_fila(fila)
    resp = PlanResponse.model_validate(fila)
    resp.current_week = macro.semana_actual()
    resp.effective_status = macro.estado_efectivo().value
    inscripciones = [
        ap for ap in fila.athlete_plans
        if ap.is_active and principal.owns_swimmer(ap.swimmer_id)
    ]
    swimmers = await _swimmer_map(db, [ap.swimmer_id for ap in inscripciones])
    athletes = []
    for ap in inscripciones:
        item = AthletePlanResponse.model_validate(ap)
        swimmer = swimmers.get(ap.swimmer_id)
        if swimmer:
            item.swimmer_name = swimmer.name
            item.specialty = swimmer.specialty
        athletes.append(item)
    resp.athletes = athletes
    return resp


async def create_plan(
    repo: RepositorioDeMacrociclos, data: PlanCreate, team_id: int, coach_id: int,
) -> Plan:
    """El equipo y el entrenador NO vienen del cliente: salen de la sesión.

    Si el equipo fuese un campo del schema, cualquiera podría crear macrociclos
    dentro de un equipo ajeno con solo cambiar un número en la petición.
    """
    fila = Plan(**data.model_dump(exclude={"phases", "competitions"}), team_id=team_id)
    fila.coaches.append(PlanCoach(coach_id=coach_id, team_id=team_id))
    phases = [p.model_dump() for p in data.phases] or \
        fases_por_defecto(data.total_weeks)
    for i, p in enumerate(phases):
        fila.phases.append(PlanPhase(
            name=p["name"], type=p.get("type", "base"), color=p.get("color", "#8b5cf6"),
            week_start=p["week_start"], week_end=p["week_end"], sort=i,
        ))
    for c in data.competitions:
        fila.competitions.append(Competition(**c.model_dump()))
    await repo.guardar(fila)
    return await repo.fila_sin_acotar(fila.id)


async def update_plan(
    repo: RepositorioDeMacrociclos, fila: Plan, data: PlanUpdate,
) -> Plan:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(fila, field, value)
    await repo.confirmar()
    return await repo.fila_sin_acotar(fila.id)


async def delete_plan(repo: RepositorioDeMacrociclos, fila: Plan) -> int:
    """Borra el macrociclo. Devuelve **cuántos tests aeróbicos lo impidieron**.

    0 significa borrado. Cualquier otro número es la razón por la que no, y el
    router la convierte en un 409 que se puede leer. El porqué de preguntar
    antes en vez de capturar el `IntegrityError` está en el repositorio, que es
    quien cuenta.
    """
    bloqueantes = await repo.tests_que_bloquean_el_borrado(fila.id)
    if bloqueantes:
        return bloqueantes
    await repo.borrar(fila)
    return 0
