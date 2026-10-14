"""El macrociclo tal y como sale por el API.

Se separó de `service.py` el 2026-10-13 (C9): presentar **lee** filas —la
respuesta se valida sobre ellas— y crear o editar ya no las toca. Con las dos
cosas en el mismo archivo no se podía decir, ni comprobar, que las escrituras
del macrociclo hubieran dejado de armar filas del ORM.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.dominio.entidades import Macrociclo
from app.persistencia.mapeo import macrociclo_desde_fila
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import Plan

from .schemas import AthletePlanResponse, PlanResponse


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
    la **fila** aporta lo que se valida tal cual: el plan, sus fases, sus
    competencias y la nómina con sus pruebas.

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
