"""Endpoints del módulo plans.

Cada ruta resuelve el macrociclo a través de `service.get_plan`, que ya acota por
equipo y por entrenador asignado. Así el aislamiento no depende de que cada
endpoint se acuerde de comprobarlo.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal, require_coach

from . import service
from .schemas import (
    AddAthleteRequest, PlanCreate, PlanResponse, PlanUpdate,
    WeekResponse, WeekUpdateRequest,
)

router = APIRouter()


async def _plan_or_404(db: AsyncSession, plan_id: int, principal: Principal):
    plan = await service.get_plan(db, plan_id, principal)
    if plan is None:
        raise HTTPException(404, "Macrociclo no encontrado")
    return plan


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return [
        await service.to_plan_response(db, p)
        for p in await service.list_plans(db, principal)
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
    return await service.to_plan_response(db, plan)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return await service.to_plan_response(db, await _plan_or_404(db, plan_id, principal))


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int, data: PlanUpdate,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    plan = await _plan_or_404(db, plan_id, coach)
    return await service.to_plan_response(db, await service.update_plan(db, plan, data))


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_plan(db, await _plan_or_404(db, plan_id, coach))


@router.post("/{plan_id}/athletes", response_model=PlanResponse, status_code=201)
async def add_athlete(
    plan_id: int, data: AddAthleteRequest,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    plan = await _plan_or_404(db, plan_id, coach)
    if any(ap.swimmer_id == data.swimmer_id for ap in plan.athlete_plans):
        raise HTTPException(409, "El atleta ya está asignado a este macrociclo")
    await service.add_athlete(db, plan, data)
    return await service.to_plan_response(db, await _plan_or_404(db, plan_id, coach))


@router.delete("/{plan_id}/athletes/{athlete_plan_id}", status_code=204)
async def remove_athlete(
    plan_id: int, athlete_plan_id: int,
    coach: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    await _plan_or_404(db, plan_id, coach)
    if not await service.remove_athlete(db, plan_id, athlete_plan_id):
        raise HTTPException(404, "Atleta no encontrado en este macrociclo")


@router.get("/events/{event_id}/weeks", response_model=list[WeekResponse])
async def event_weeks(
    event_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    event = await service.get_event(db, event_id, principal)
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
    event = await service.update_week(db, week_id, data, principal)
    if event is None:
        raise HTTPException(404, "Semana no encontrada")
    event = await service.get_event(db, event.id)
    return await service.event_weeks_response(db, event)  # type: ignore[arg-type]
