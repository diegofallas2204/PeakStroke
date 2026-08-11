"""Endpoints del módulo plans.

Cada ruta resuelve el macrociclo a través de `service.get_plan`, que ya acota por
equipo y por entrenador asignado. Así el aislamiento no depende de que cada
endpoint se acuerde de comprobarlo.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    Principal, exigir_o_bypass, get_current_principal, require_coach,
)

from . import access, enrollment, service
from .schemas import (
    AddAthleteRequest, AssignableAthlete, PlanCreate, PlanResponse, PlanUpdate,
    WeekResponse, WeekUpdateRequest,
)

router = APIRouter()


async def _plan_or_404(db: AsyncSession, plan_id: int, principal: Principal):
    plan = await access.get_plan(db, plan_id, principal)
    if plan is None:
        raise HTTPException(404, "Macrociclo no encontrado")
    return plan


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return [
        await service.to_plan_response(db, p, principal)
        for p in await access.list_plans(db, principal)
    ]


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    data: PlanCreate,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    # Quien lo crea queda automáticamente a cargo: si no, nacería un macrociclo
    # que su propio autor no podría ver.
    plan = await service.create_plan(db, data, coach.team_id, coach.id)
    return await service.to_plan_response(db, plan, coach)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return await service.to_plan_response(db, await _plan_or_404(db, plan_id, principal), principal)


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int, data: PlanUpdate,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    plan = await _plan_or_404(db, plan_id, coach)
    return await service.to_plan_response(db, await service.update_plan(db, plan, data), coach)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Borra el macrociclo. **409 si tiene tests aeróbicos colgando.**

    No se borran en cascada a propósito: un test es una medición del atleta en
    una fecha, no una parte del macrociclo. Que el entrenador decida qué hacer
    con ellos es más barato que descubrir que se evaporaron.
    """
    bloqueantes = await service.delete_plan(db, await _plan_or_404(db, plan_id, coach))
    if bloqueantes:
        raise HTTPException(409, (
            f"Este macrociclo tiene {bloqueantes} test(s) aeróbico(s) asociados. "
            "Dales de baja o muévelos a otro macrociclo antes de borrarlo."
        ))


@router.get("/{plan_id}/assignable-athletes", response_model=list[AssignableAthlete])
async def assignable_athletes(
    plan_id: int,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Los atletas que hoy pueden entrar en este macrociclo.

    Existe para que el formulario no ofrezca lo que el POST va a rechazar. La
    regla la impone `add_athlete` de todas formas: esto es la cortesía, no la
    cerradura (ver `enrollment.py`).
    """
    plan = await _plan_or_404(db, plan_id, coach)
    return [
        AssignableAthlete(
            id=s.id, name=s.name, specialty=s.specialty, main_stroke=s.main_stroke,
            age=service.age_at(s.birth_date, plan.start_date),
        )
        for s in await enrollment.assignable_swimmers(db, plan)
    ]


@router.post("/{plan_id}/athletes", response_model=PlanResponse, status_code=201)
async def add_athlete(
    plan_id: int, data: AddAthleteRequest,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    plan = await _plan_or_404(db, plan_id, coach)
    if any(ap.swimmer_id == data.swimmer_id and ap.is_active for ap in plan.athlete_plans):
        raise HTTPException(409, "El atleta ya está asignado a este macrociclo")
    # Un atleta, un macrociclo vivo. El bloqueo aplica también al dueño del
    # equipo: no es una cuestión de permisos sino de que ese plan no existe.
    ocupado = await enrollment.blocking_plan(
        db, plan.team_id, data.swimmer_id, target_plan_id=plan_id,
    )
    if ocupado is not None:
        raise HTTPException(409, (
            f"Ese atleta ya está en el macrociclo «{ocupado.name}». "
            "Sácalo de ahí antes de inscribirlo en otro."
        ))
    await service.add_athlete(db, plan, data)
    return await service.to_plan_response(db, await _plan_or_404(db, plan_id, coach), coach)


@router.delete("/{plan_id}/athletes/{athlete_plan_id}", status_code=204)
async def remove_athlete(
    plan_id: int, athlete_plan_id: int,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Saca al atleta del macrociclo. **No borra su histórico**: lo da de baja.

    Se mantiene el verbo DELETE porque es la acción que expresa el cliente
    ("quitar del macrociclo"), igual que en `swimmers`. Sus semanas y tiempos
    reales siguen en la base, y `POST .../restore` vuelve a inscribirlo con todo.
    """
    await _plan_or_404(db, plan_id, coach)
    if not await service.remove_athlete(db, plan_id, athlete_plan_id):
        raise HTTPException(404, "Atleta no encontrado en este macrociclo")


@router.post("/{plan_id}/athletes/{athlete_plan_id}/restore", status_code=204)
async def restore_athlete(
    plan_id: int, athlete_plan_id: int,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Vuelve a inscribir a un atleta dado de baja, con su histórico intacto.

    Sacar a alguien de un macrociclo es la clase de clic que se da por error, y
    volver a inscribirlo desde cero no reconstruye lo que nadó.
    """
    plan = await _plan_or_404(db, plan_id, coach)
    ocupado = await enrollment.blocking_plan_for(db, athlete_plan_id, plan.team_id)
    if ocupado is not None:
        raise HTTPException(409, (
            f"Ese atleta entró mientras tanto en el macrociclo «{ocupado.name}». "
            "Sácalo de ahí antes de devolverlo a este."
        ))
    if not await service.restore_athlete(db, plan_id, athlete_plan_id):
        raise HTTPException(404, "No hay ninguna inscripción dada de baja con ese id")


@router.get("/events/{event_id}/weeks", response_model=list[WeekResponse])
async def event_weeks(
    event_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    event = await access.get_event(db, event_id, principal)
    if event is None:
        raise HTTPException(404, "Prueba no encontrada")
    return await service.event_weeks_response(db, event)


@router.patch("/weeks/{week_id}", response_model=list[WeekResponse])
async def update_week(
    week_id: int, data: WeekUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    # Sin require_coach a propósito: registrar el tiempo real de la semana es una
    # de las cosas que el atleta puede hacer sobre SU plan, y `update_week` ya
    # acota por visibilidad.
    #
    # Pero no todos los campos son suyos. Desde que el filtro por nadador existe,
    # la semana que toca ES la suya, así que sin esta comprobación escribir
    # `disabled` pasaría a ser legítimo — y eso es el parón del entrenador, que
    # redistribuye la mejora restante de todo el macrociclo. 403 y no 404: el
    # recurso sí es suyo, lo que no alcanza es el rol.
    if data.touches_coach_only_fields() and not principal.is_coach:
        exigir_o_bypass(principal, "entrenador para marcar el parón de una semana")

    event = await service.update_week(db, week_id, data, principal)
    if event is None:
        raise HTTPException(404, "Semana no encontrada")
    return await service.event_weeks_response(db, event)
