"""Endpoints del módulo aerobic_tests."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal
from app.core.guards import require_coach
from app.engine.aerobic import analyze_splits

from . import intervals, service
from .schemas import (
    AerobicTestCreate,
    AerobicTestResponse,
    AnalyzePreviewRequest,
    AnalyzePreviewResponse,
    TrainingIntervalsResponse,
)

router = APIRouter()


async def _test_or_404(db: AsyncSession, test_id: int, principal: Principal):
    test = await service.get_test(db, test_id, principal)
    if test is None:
        raise HTTPException(404, "Test no encontrado")
    return test


@router.get("/", response_model=list[AerobicTestResponse])
async def list_tests(
    swimmer_id: int | None = None, plan_id: int | None = None,
    include_inactive: bool = False,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    tests = await service.list_tests(
        db, principal, swimmer_id, plan_id, include_inactive=include_inactive,
    )
    return [service.to_response(t) for t in tests]


@router.post("/", response_model=AerobicTestResponse, status_code=201)
async def create_test(
    data: AerobicTestCreate,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    # Sin require_coach: registrar los propios tests aeróbicos es una de las
    # cosas que el atleta puede hacer. Que sea SUYO lo comprueba el service; que
    # el nadador sea de su equipo lo impone la FK compuesta del esquema.
    try:
        test = await service.create_test(db, data, principal)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if test is None:
        raise HTTPException(404, "Atleta no encontrado")
    return service.to_response(test)


@router.post("/analyze", response_model=AnalyzePreviewResponse)
async def analyze_preview(data: AnalyzePreviewRequest):
    """Análisis en vivo de parciales sin persistir (preview del formulario)."""
    try:
        a = analyze_splits(
            data.splits, data.rep_distance,
            send_off=data.send_off, input_mode=data.input_mode,
        )
    except ValueError as exc:
        # El preview corre mientras se escribe: unas llegadas a medio teclear son
        # incoherentes casi siempre, y un 500 dejaría el formulario en rojo por
        # una respuesta que todavía no se ha terminado de dar.
        raise HTTPException(422, str(exc)) from exc
    return AnalyzePreviewResponse(
        per100_splits=a.per100_splits, avg_per100=a.avg_per100,
        std_dev=a.std_dev, trend=a.trend, trend_slope=a.trend_slope,
        rep_times=a.rep_times, rest_per_rep=a.rest_per_rep, avg_rest=a.avg_rest,
        work_rest_ratio=a.work_rest_ratio, density=a.density,
        missed_intervals=a.missed_intervals,
    )


@router.get("/{test_id}", response_model=AerobicTestResponse)
async def get_test(
    test_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return service.to_response(await _test_or_404(db, test_id, principal))


@router.get("/{test_id}/training-intervals", response_model=TrainingIntervalsResponse)
async def get_training_intervals(
    test_id: int,
    rep_distance: int = Query(default=100, ge=25, le=2000),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Ritmo y salida por zona: la prescripción completa, no solo el ritmo.

    Sin `require_coach` a propósito: el atleta ya ve sus zonas en la semana, y
    saber cada cuánto sale es la misma información dicha entera. El test que
    puede pedir lo acota `_test_or_404`, que es donde vive el filtro.
    """
    test = await _test_or_404(db, test_id, principal)
    return await intervals.training_intervals_for(db, test, principal, rep_distance)


@router.get("/{test_id}/previous", response_model=AerobicTestResponse | None)
async def get_previous(
    test_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    test = await _test_or_404(db, test_id, principal)
    prev = await service.previous_test(db, test, principal)
    return service.to_response(prev) if prev else None


@router.delete("/{test_id}", status_code=204)
async def deactivate_test(
    test_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Da de baja el test. **No borra nada**: la medición no se puede rehacer.

    Se mantiene el verbo DELETE porque es la acción que expresa el cliente
    ("quitar este test"), igual que en `swimmers`.
    """
    await service.set_active(db, await _test_or_404(db, test_id, principal), False)


@router.post("/{test_id}/reactivate", response_model=AerobicTestResponse)
async def reactivate_test(
    test_id: int,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Vuelve a poner de alta un test retirado. Mismo patrón que `swimmers`.

    Sin esto, dar de baja y borrar eran indistinguibles desde la aplicación —y
    entonces la columna `is_active` no cumplía la regla que vino a cumplir.
    Solo entrenadores: retirar el propio test es una corrección; rescatarlo del
    archivo es una decisión sobre el histórico del club.
    """
    test = await _test_or_404(db, test_id, principal)
    return service.to_response(await service.set_active(db, test, True))
