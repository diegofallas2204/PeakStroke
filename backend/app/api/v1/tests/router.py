"""Endpoints del test aeróbico.

El prefijo público sigue siendo `/api/v1/aerobic-tests`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import repo_de_macrociclos, repo_de_tests
from app.core.auditoria import TipoDeEvento, auditar
from app.core.database import get_db
from app.core.guards import require_coach
from app.core.principal import Principal
from app.engine.aerobic import analyze_splits
from app.persistencia.repositorios import RepositorioDeMacrociclos, RepositorioDeTests
from app.persistencia.tablas.tests_aerobicos import AerobicTest

from . import intervalos, service
from .schemas import (
    AerobicTestCreate,
    AerobicTestResponse,
    AnalyzePreviewRequest,
    AnalyzePreviewResponse,
    TrainingIntervalsResponse,
)

router = APIRouter()


async def _test_or_404(repo: RepositorioDeTests, test_id: int) -> AerobicTest:
    test = await repo.fila_de(test_id)
    if test is None:
        raise HTTPException(404, "Test no encontrado")
    return test


@router.get("/", response_model=list[AerobicTestResponse])
async def list_tests(
    swimmer_id: int | None = None, plan_id: int | None = None,
    include_inactive: bool = False,
    repo: RepositorioDeTests = Depends(repo_de_tests),
):
    filas = await repo.filas(
        swimmer_id=swimmer_id, plan_id=plan_id, incluir_de_baja=include_inactive,
    )
    return [service.to_response(f) for f in filas]


@router.post("/", response_model=AerobicTestResponse, status_code=201)
async def create_test(
    data: AerobicTestCreate,
    repo: RepositorioDeTests = Depends(repo_de_tests),
    macrociclos: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
):
    # Sin require_coach: registrar los propios tests aeróbicos es una de las
    # cosas que el atleta puede hacer. Que sea SUYO lo comprueba el service; que
    # el nadador sea de su equipo lo impone la FK compuesta del esquema.
    try:
        test = await service.create_test(repo, macrociclos, data, repo.principal)
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
    repo: RepositorioDeTests = Depends(repo_de_tests),
):
    return service.to_response(await _test_or_404(repo, test_id))


@router.get("/{test_id}/training-intervals", response_model=TrainingIntervalsResponse)
async def get_training_intervals(
    test_id: int,
    rep_distance: int = Query(default=100, ge=25, le=2000),
    repo: RepositorioDeTests = Depends(repo_de_tests),
    macrociclos: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    """Ritmo y salida por zona: la prescripción completa, no solo el ritmo.

    Sin `require_coach` a propósito: el atleta ya ve sus zonas en la semana, y
    saber cada cuánto sale es la misma información dicha entera. El test que
    puede pedir lo acota `_test_or_404`, que es donde vive el filtro.
    """
    test = await _test_or_404(repo, test_id)
    return await intervalos.training_intervals_for(db, macrociclos, test, rep_distance)


@router.get("/{test_id}/previous", response_model=AerobicTestResponse | None)
async def get_previous(
    test_id: int,
    repo: RepositorioDeTests = Depends(repo_de_tests),
):
    test = await _test_or_404(repo, test_id)
    prev = await repo.anterior_a(test)
    return service.to_response(prev) if prev else None


@router.delete("/{test_id}", status_code=204)
async def deactivate_test(
    test_id: int,
    repo: RepositorioDeTests = Depends(repo_de_tests),
):
    """Da de baja el test. **No borra nada**: la medición no se puede rehacer.

    Se mantiene el verbo DELETE porque es la acción que expresa el cliente
    ("quitar este test"), igual que en `swimmers`.
    """
    await repo.cambiar_alta(await _test_or_404(repo, test_id), False)
    # Sin `require_coach`: un atleta puede retirar su propio test, y el actor es él.
    auditar(TipoDeEvento.TEST_BAJA, repo.principal, objetivo=("aerobic_test", test_id))


@router.post("/{test_id}/reactivate", response_model=AerobicTestResponse)
async def reactivate_test(
    test_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeTests = Depends(repo_de_tests),
):
    """Vuelve a poner de alta un test retirado. Mismo patrón que `swimmers`.

    Sin esto, dar de baja y borrar eran indistinguibles desde la aplicación —y
    entonces la columna `is_active` no cumplía la regla que vino a cumplir.
    Solo entrenadores: retirar el propio test es una corrección; rescatarlo del
    archivo es una decisión sobre el histórico del club.
    """
    test = await _test_or_404(repo, test_id)
    respuesta = service.to_response(await repo.cambiar_alta(test, True))
    auditar(TipoDeEvento.TEST_RESTAURADO, coach, objetivo=("aerobic_test", test_id))
    return respuesta
