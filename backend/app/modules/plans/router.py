"""Endpoints del módulo plans."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

from . import service
from .schemas import (
    AddAthleteRequest, PlanCreate, PlanResponse, PlanUpdate,
    WeekResponse, WeekUpdateRequest,
)

router = APIRouter()


async def _plan_or_404(db: AsyncSession, plan_id: int):
    plan = await service.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(404, "Macrociclo no encontrado")
    return plan


@router.get("/", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    return [await service.to_plan_response(db, p) for p in await service.list_plans(db)]


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(data: PlanCreate, db: AsyncSession = Depends(get_db)):
    plan = await service.create_plan(db, data)
    return await service.to_plan_response(db, plan)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    return await service.to_plan_response(db, await _plan_or_404(db, plan_id))


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(plan_id: int, data: PlanUpdate, db: AsyncSession = Depends(get_db)):
    plan = await _plan_or_404(db, plan_id)
    return await service.to_plan_response(db, await service.update_plan(db, plan, data))


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(plan_id: int, db: AsyncSession = Depends(get_db)):
    await service.delete_plan(db, await _plan_or_404(db, plan_id))


@router.post("/{plan_id}/athletes", response_model=PlanResponse, status_code=201)
async def add_athlete(plan_id: int, data: AddAthleteRequest, db: AsyncSession = Depends(get_db)):
    plan = await _plan_or_404(db, plan_id)
    if any(ap.swimmer_id == data.swimmer_id for ap in plan.athlete_plans):
        raise HTTPException(409, "El atleta ya está asignado a este macrociclo")
    await service.add_athlete(db, plan, data)
    return await service.to_plan_response(db, await _plan_or_404(db, plan_id))


@router.delete("/{plan_id}/athletes/{athlete_plan_id}", status_code=204)
async def remove_athlete(plan_id: int, athlete_plan_id: int, db: AsyncSession = Depends(get_db)):
    if not await service.remove_athlete(db, plan_id, athlete_plan_id):
        raise HTTPException(404, "Atleta no encontrado en este macrociclo")


@router.get("/events/{event_id}/weeks", response_model=list[WeekResponse])
async def event_weeks(event_id: int, db: AsyncSession = Depends(get_db)):
    event = await service.get_event(db, event_id)
    if event is None:
        raise HTTPException(404, "Prueba no encontrada")
    return await service.event_weeks_response(db, event)


@router.patch("/weeks/{week_id}", response_model=list[WeekResponse])
async def update_week(week_id: int, data: WeekUpdateRequest, db: AsyncSession = Depends(get_db)):
    event = await service.update_week(db, week_id, data)
    if event is None:
        raise HTTPException(404, "Semana no encontrada")
    event = await service.get_event(db, event.id)
    return await service.event_weeks_response(db, event)  # type: ignore[arg-type]
