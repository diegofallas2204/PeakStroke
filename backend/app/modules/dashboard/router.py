"""Endpoints del dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.plans.service import current_week_of, get_plan

from . import service
from .schemas import DashboardSummary, TeamWeekResponse

router = APIRouter()


async def _resolve_plan(db: AsyncSession, plan_id: int | None):
    plan = await (get_plan(db, plan_id) if plan_id else service.active_plan(db))
    if plan is None:
        raise HTTPException(404, "No hay macrociclo activo")
    return plan


@router.get("/summary", response_model=DashboardSummary)
async def summary(plan_id: int | None = None, db: AsyncSession = Depends(get_db)):
    plan = await _resolve_plan(db, plan_id)
    return await service.build_summary(db, plan)


@router.get("/team-week", response_model=TeamWeekResponse)
async def team_week(
    plan_id: int | None = None, week: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    plan = await _resolve_plan(db, plan_id)
    week_number = week or current_week_of(plan) or 1
    week_number = max(1, min(week_number, plan.total_weeks))
    return await service.team_week(db, plan, week_number)
