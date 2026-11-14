"""Endpoints del test de lactato: `/api/v1/lactate-tests`.

Apuntarlo, analizarlo en vivo y darlo de baja es del entrenador: la muestra la
toma el equipo técnico con su analizador. Leerlo, cualquiera del club con lo
suyo —el atleta, solo sus tests (lactato y FC son datos de salud)—.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencias import repo_de_atletas, repo_de_tests_de_lactato
from app.core.auditoria import TipoDeEvento, auditar
from app.core.guards import require_coach
from app.core.principal import Principal
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeTestsDeLactato
from app.persistencia.tablas.tests_de_lactato import LactateTest

from . import lactato_service as service
from .lactato_schemas import LactateAnalysis, LactateTestCreate, LactateTestResponse

router = APIRouter()


async def _test_or_404(repo: RepositorioDeTestsDeLactato, test_id: int) -> LactateTest:
    fila = await repo.fila_de(test_id)
    if fila is None:
        raise HTTPException(404, "Test no encontrado")
    return fila


@router.get("/", response_model=list[LactateTestResponse])
async def list_tests(
    swimmer_id: int | None = None,
    repo: RepositorioDeTestsDeLactato = Depends(repo_de_tests_de_lactato),
) -> list[LactateTestResponse]:
    return [service.to_response(f) for f in await repo.filas(swimmer_id=swimmer_id)]


@router.post("/", response_model=LactateTestResponse, status_code=201)
async def create_test(
    data: LactateTestCreate,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeTestsDeLactato = Depends(repo_de_tests_de_lactato),
    atletas: RepositorioDeAtletas = Depends(repo_de_atletas),
) -> LactateTestResponse:
    try:
        fila = await service.crear(repo, atletas, data, coach)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if fila is None:
        raise HTTPException(404, "Atleta no encontrado")
    return service.to_response(fila)


@router.post("/analyze", response_model=LactateAnalysis, dependencies=[Depends(require_coach)])
async def analyze_preview(data: LactateTestCreate) -> LactateAnalysis:
    """Lo mismo que daría guardarlo, sin guardar: los avisos mientras se escribe."""
    try:
        return service.analizar(service.entidad_desde_peticion(data))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/{test_id}", response_model=LactateTestResponse)
async def get_test(
    test_id: int,
    repo: RepositorioDeTestsDeLactato = Depends(repo_de_tests_de_lactato),
) -> LactateTestResponse:
    return service.to_response(await _test_or_404(repo, test_id))


@router.delete("/{test_id}", status_code=204)
async def deactivate_test(
    test_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeTestsDeLactato = Depends(repo_de_tests_de_lactato),
) -> None:
    """Da de baja el test. **No borra nada**: la medición no se puede rehacer."""
    await repo.dar_de_baja(await _test_or_404(repo, test_id))
    auditar(TipoDeEvento.TEST_DE_LACTATO_BAJA, coach, objetivo=("lactate_test", test_id))
