"""Endpoints del módulo aerobic_tests."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.engine.aerobic import analyze_splits

from . import service
from .schemas import (
    AerobicTestCreate, AerobicTestResponse,
    AnalyzePreviewRequest, AnalyzePreviewResponse,
)

router = APIRouter()


@router.get("/", response_model=list[AerobicTestResponse])
async def list_tests(
    swimmer_id: int | None = None, plan_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    return [service.to_response(t) for t in await service.list_tests(db, swimmer_id, plan_id)]


@router.post("/", response_model=AerobicTestResponse, status_code=201)
async def create_test(data: AerobicTestCreate, db: AsyncSession = Depends(get_db)):
    try:
        return service.to_response(await service.create_test(db, data))
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
async def get_test(test_id: int, db: AsyncSession = Depends(get_db)):
    test = await service.get_test(db, test_id)
    if test is None:
        raise HTTPException(404, "Test no encontrado")
    return service.to_response(test)


@router.get("/{test_id}/previous", response_model=AerobicTestResponse | None)
async def get_previous(test_id: int, db: AsyncSession = Depends(get_db)):
    test = await service.get_test(db, test_id)
    if test is None:
        raise HTTPException(404, "Test no encontrado")
    prev = await service.previous_test(db, test)
    return service.to_response(prev) if prev else None


@router.delete("/{test_id}", status_code=204)
async def delete_test(test_id: int, db: AsyncSession = Depends(get_db)):
    test = await service.get_test(db, test_id)
    if test is None:
        raise HTTPException(404, "Test no encontrado")
    await service.delete_test(db, test)
