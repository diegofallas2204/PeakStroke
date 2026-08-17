"""Lógica de negocio del módulo plans: el macrociclo en sí.

Las reglas de **acceso** (quién ve qué) no viven aquí sino en `access.py`, y la
de **inscripción** (un atleta, un macrociclo vivo) en `enrollment.py`. Este
módulo asume que las dos ya se comprobaron.

El módulo está repartido en cinco archivos y este tiene el plan como objeto —
crearlo, editarlo, borrarlo y presentarlo—. Los atletas inscritos están en
`roster.py` y sus semanas en `weeks.py`.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import Principal
from app.dominio.servicios.motor import fases_por_defecto

# Lecturas explícitas de modelos de otros módulos (permitido por las reglas
# del proyecto). No se importa lógica ajena.
from app.modules.aerobic_tests.models import AerobicTest
from app.modules.swimmers.models import Swimmer
from app.persistencia.mapeo import macrociclo_desde_fila

from .access import plan_unscoped
from .models import Competition, Plan, PlanCoach, PlanPhase
from .schemas import AthletePlanResponse, PlanCreate, PlanResponse, PlanUpdate


def current_week_of(plan: Plan, today: date | None = None) -> int | None:
    """En qué semana va el macrociclo. **Envoltorio en retirada.**

    La regla es `Macrociclo.semana_actual()` desde el paso 2 del rediseño
    (2026-08-16). Aquí queda la delegación mientras haya llamadores que tengan
    la fila y no la entidad — `dashboard` y `aerobic_tests/intervals` importan
    esta función, que es P5 en una línea: una vista importando la lógica de otro
    módulo para poder preguntarle algo a un plan.
    """
    return macrociclo_desde_fila(plan).semana_actual(today)


def effective_status(plan: Plan, today: date | None = None) -> str:
    """Estado mostrado al entrenador. **Envoltorio en retirada.**

    Suspendido / inactivo (draft) / completado (finished) son overrides manuales
    y mandan tal cual. Si el macrociclo está vigente (active) pero su última
    semana ya pasó, se auto-marca como completado por fecha.

    La regla es `Macrociclo.estado_efectivo()`, que devuelve un `EstadoDeMacro`;
    el `.value` se desenvuelve aquí porque los schemas de la API siguen hablando
    en cadenas.
    """
    return macrociclo_desde_fila(plan).estado_efectivo(today).value


async def _swimmer_map(db: AsyncSession, ids: list[int]) -> dict[int, Swimmer]:
    if not ids:
        return {}
    rows = (await db.execute(select(Swimmer).where(Swimmer.id.in_(ids)))).scalars()
    return {s.id: s for s in rows}


async def to_plan_response(
    db: AsyncSession, plan: Plan, principal: Principal,
) -> PlanResponse:
    """El macrociclo tal y como lo ve quien pregunta.

    El atleta ve el plan —fechas, fases, competencias, su propia inscripción—
    pero no con quién lo comparte. `plan.athlete_plans` trae el roster completo
    porque la relación no sabe de permisos; el recorte va aquí, que es el único
    sitio por el que ese roster sale hacia fuera.
    """
    resp = PlanResponse.model_validate(plan)
    resp.current_week = current_week_of(plan)
    resp.effective_status = effective_status(plan)
    inscripciones = [
        ap for ap in plan.athlete_plans
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


async def create_plan(db: AsyncSession, data: PlanCreate, team_id: int, coach_id: int) -> Plan:
    """El equipo y el entrenador NO vienen del cliente: salen de la sesión.

    Si el equipo fuese un campo del schema, cualquiera podría crear macrociclos
    dentro de un equipo ajeno con solo cambiar un número en la petición.
    """
    plan = Plan(**data.model_dump(exclude={"phases", "competitions"}), team_id=team_id)
    plan.coaches.append(PlanCoach(coach_id=coach_id, team_id=team_id))
    phases = [p.model_dump() for p in data.phases] or \
        fases_por_defecto(data.total_weeks)
    for i, p in enumerate(phases):
        plan.phases.append(PlanPhase(
            name=p["name"], type=p.get("type", "base"), color=p.get("color", "#8b5cf6"),
            week_start=p["week_start"], week_end=p["week_end"], sort=i,
        ))
    for c in data.competitions:
        plan.competitions.append(Competition(**c.model_dump()))
    db.add(plan)
    await db.commit()
    return (await plan_unscoped(db, plan.id))  # type: ignore[return-value]


async def update_plan(db: AsyncSession, plan: Plan, data: PlanUpdate) -> Plan:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    return (await plan_unscoped(db, plan.id))  # type: ignore[return-value]


async def delete_plan(db: AsyncSession, plan: Plan) -> int:
    """Borra el macrociclo. Devuelve **cuántos tests aeróbicos lo impidieron**.

    0 significa borrado. Cualquier otro número es la razón por la que no, y el
    router la convierte en un 409 que se puede leer.

    La comprobación existe porque `fk_aerobic_tests_plan_in_team` no lleva
    `ondelete`, así que la base de datos rechaza el borrado con un
    `IntegrityError`. Sin capturarlo el entrenador recibía un 500 con una traza,
    y el fallo depende del dato: un macrociclo sin tests se borra sin problema,
    con lo que aparecía en producción y no al desarrollar.

    Preguntar antes en vez de capturar la excepción es a propósito: el número de
    tests es lo que hace accionable el mensaje ("tiene 12 tests asociados"), y
    de un `IntegrityError` no se puede sacar.
    """
    bloqueantes = (await db.execute(
        select(func.count()).select_from(AerobicTest)
        .where(AerobicTest.plan_id == plan.id)
    )).scalar_one()
    if bloqueantes:
        return bloqueantes
    await db.delete(plan)
    await db.commit()
    return 0
