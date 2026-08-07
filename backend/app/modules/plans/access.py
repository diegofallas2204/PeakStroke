"""Quién puede ver qué macrociclo, y por dónde se entra a sus semanas.

Este módulo es **la única puerta** a los macrociclos y a todo lo que cuelga de
ellos. Vive separado de `service.py` a propósito: el CRUD y el motor cambian a
menudo, las reglas de acceso casi nunca, y mezclarlos hacía que un diff de 300
líneas de negocio pudiera esconder un cambio de una línea en quién ve qué.

Dos filtros, y hay que pasar los dos:

    visible_to()             ──▶  ¿es un macrociclo que te toca?      (el club)
    scope_to_own_swimmer()   ──▶  ¿es TU fila dentro de él?           (el atleta)

El segundo se añadió el 2026-08-06. `visible_to` deja pasar el plan entero a
cualquiera inscrito en él, así que por sí solo permitía que un atleta leyera y
sobrescribiera las semanas de sus compañeros de macrociclo.

Se lleva la puerta **completa**, `get_plan` y `list_plans` incluidos. Un módulo
de acceso al que le falta la función de acceso principal organiza peor que no
haber extraído nada: quien venga a auditar quién ve qué tendría que leer los dos
archivos y adivinar cuál manda.
"""
from __future__ import annotations

from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import Principal

from .models import AthleteEvent, AthletePlan, Plan, PlanCoach, WeeklyPlan

_PLAN_LOAD = (
    selectinload(Plan.phases),
    selectinload(Plan.competitions),
    selectinload(Plan.athlete_plans).selectinload(AthletePlan.events),
)

_EVENT_LOAD = (
    selectinload(AthleteEvent.weeks),
    selectinload(AthleteEvent.athlete_plan).selectinload(AthletePlan.plan)
    .selectinload(Plan.competitions),
)


def visible_to(stmt, principal: Principal):
    """Acota una consulta de macrociclos a los que el solicitante puede ver.

    Tres casos, en este orden:
      · **Dueño del equipo** — todos los de su equipo. Sin esta excepción, los
        macrociclos de un entrenador que se va no los podría rescatar nadie.
      · **Entrenador** — solo aquellos en los que figura en `plan_coaches`.
      · **Atleta** — solo aquellos en los que está inscrito.

    Es la única puerta: `list_plans` y `get_plan` pasan por aquí, así que un
    macrociclo ajeno no se cuela ni listándolo ni pidiéndolo por id.
    """
    stmt = stmt.where(Plan.team_id == principal.team_id)
    if principal.sees_every_plan:
        return stmt

    if principal.is_coach:
        suyos = select(PlanCoach.plan_id).where(PlanCoach.coach_id == principal.id)
    elif principal.swimmer_id is None:
        # Atleta sin ficha de nadador: no está inscrito en ningún macrociclo, y
        # decirlo explícitamente evita una consulta que no puede devolver nada.
        return stmt.where(false())
    else:
        # Del `Principal`, que ya resolvió el nadador llevando el equipo en la
        # condición del join. Antes se derivaba aquí otra vez con
        # `Swimmer.user_id == principal.id` a secas: dos funciones respondiendo
        # la misma pregunta con semánticas distintas, que es el patrón que
        # produjo el agujero del scoping. Coincidían solo porque
        # `Swimmer.user_id` es UNIQUE global, y `teams/models.py` anticipa
        # quitar la restricción de un-usuario-un-equipo.
        suyos = select(AthletePlan.plan_id).where(
            AthletePlan.swimmer_id == principal.swimmer_id,
        )
    return stmt.where(Plan.id.in_(suyos))


async def list_plans(db: AsyncSession, principal: Principal) -> list[Plan]:
    stmt = visible_to(select(Plan).options(*_PLAN_LOAD), principal)
    return list((await db.execute(stmt.order_by(Plan.created_at.desc()))).scalars())


async def get_plan(db: AsyncSession, plan_id: int, principal: Principal) -> Plan | None:
    """None si no existe **o** si el solicitante no debe verlo.

    Ambos casos se responden con 404: un 403 confirmaría que ese macrociclo
    existe en algún equipo.
    """
    stmt = visible_to(select(Plan).options(*_PLAN_LOAD).where(Plan.id == plan_id), principal)
    return (await db.execute(stmt)).scalar_one_or_none()


async def plan_unscoped(db: AsyncSession, plan_id: int) -> Plan | None:
    """Recarga interna tras escribir, **cuando el acceso ya está comprobado**."""
    stmt = select(Plan).options(*_PLAN_LOAD).where(Plan.id == plan_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_event(
    db: AsyncSession, event_id: int, principal: Principal,
) -> AthleteEvent | None:
    """Prueba objetivo de un atleta dentro de un plan, solo si le es visible.

    Es la comprobación que impide el acceso directo por id: las pruebas y las
    semanas se piden por su propio identificador, sin mencionar el plan, así que
    sin esto bastaría con probar números para leer los datos de otro club.

    `principal` es obligatorio. Antes tenía default `None` (= sin filtrar), y un
    default inseguro solo hace falta olvidarlo una vez para abrir un agujero.
    Para las recargas internas, cuando el acceso YA está comprobado, está
    `event_unscoped()`, que dice en su nombre lo que hace.
    """
    stmt = visible_to(
        select(AthleteEvent).options(*_EVENT_LOAD)
        .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
        .join(Plan, Plan.id == AthletePlan.plan_id)
        .where(AthleteEvent.id == event_id),
        principal,
    )
    stmt = principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def event_unscoped(db: AsyncSession, event_id: int) -> AthleteEvent | None:
    """Recarga interna tras escribir, **cuando el acceso ya está comprobado**.

    Misma convención que `service._plan_unscoped`. No la llames desde un router:
    para eso está `get_event`.
    """
    stmt = select(AthleteEvent).options(*_EVENT_LOAD).where(AthleteEvent.id == event_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_week(
    db: AsyncSession, week_id: int, principal: Principal,
) -> WeeklyPlan | None:
    """Semana concreta, solo si su macrociclo **y su atleta** le corresponden.

    La segunda condición es la que faltaba, y es la que más caro salía: escribir
    el tiempo real de un compañero dispara `_recalculate_event`, que le reescribe
    la curva de progresión entera. El plan de entrenamiento de una persona,
    borrado por otra.
    """
    stmt = visible_to(
        select(WeeklyPlan)
        .join(AthleteEvent, AthleteEvent.id == WeeklyPlan.athlete_event_id)
        .join(AthletePlan, AthletePlan.id == AthleteEvent.athlete_plan_id)
        .join(Plan, Plan.id == AthletePlan.plan_id)
        .where(WeeklyPlan.id == week_id),
        principal,
    )
    stmt = principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)
    return (await db.execute(stmt)).scalar_one_or_none()
