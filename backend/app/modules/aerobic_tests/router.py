"""Endpoints del módulo aerobic_tests."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal
from app.engine.aerobic import analyze_splits

from . import service
from .schemas import (
    AerobicTestCreate, AerobicTestResponse,
    AnalyzePreviewRequest, AnalyzePreviewResponse,
)

router = APIRouter()


async def _test_or_404(db: AsyncSession, test_id: int, team_id: int):
    test = await service.get_test(db, test_id, team_id)
    if test is None:
        raise HTTPException(404, "Test no encontrado")
    return test


@router.get("/", response_model=list[AerobicTestResponse])
async def list_tests(
    swimmer_id: int | None = None, plan_id: int | None = None,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    tests = await service.list_tests(db, principal.team_id, swimmer_id, plan_id)
    return [service.to_response(t) for t in tests]


@router.post("/", response_model=AerobicTestResponse, status_code=201)
async def create_test(
    data: AerobicTestCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    # Sin require_coach: registrar los propios tests aeróbicos es una de las
    # cosas que el atleta puede hacer. Que el nadador sea de su equipo lo impone
    # la FK compuesta del esquema.
    try:
        return service.to_response(await service.create_test(db, data, principal.team_id))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/analyze", response_model=AnalyzePreviewResponse)
async def analyze_preview(data: AnalyzePreviewRequest):
    """Análisis en vivo de parciales sin persistir (preview del formulario)."""
    a = analyze_splits(data.splits, data.rep_distance)
    return AnalyzePreviewResponse(
        per100_splits=a.per100_splits, avg_per100=a.avg_per100,
        std_dev=a.std_dev, trend=a.trend, trend_slope=a.trend_slope,
    )


@router.get("/{test_id}", response_model=AerobicTestResponse)
async def get_test(
    test_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return service.to_response(await _test_or_404(db, test_id, principal.team_id))


@router.get("/{test_id}/previous", response_model=AerobicTestResponse | None)
async def get_previous(
    test_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    test = await _test_or_404(db, test_id, principal.team_id)
    prev = await service.previous_test(db, test)
    return service.to_response(prev) if prev else None


@router.delete("/{test_id}", status_code=204)
async def delete_test(
    test_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_test(db, await _test_or_404(db, test_id, principal.team_id))
