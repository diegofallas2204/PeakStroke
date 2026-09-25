"""Endpoints del atleta — sin lógica de negocio.

El prefijo público sigue siendo `/api/v1/swimmers`: el contrato no cambia con
el paso 5.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencias import repo_de_atletas, repo_de_usuarios
from app.core.auditoria import TipoDeEvento, auditar
from app.core.guards import require_coach
from app.core.principal import Principal
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeUsuarios
from app.persistencia.tablas.atletas import Swimmer

from . import service
from .schemas import SwimmerCreate, SwimmerResponse, SwimmerUpdate

router = APIRouter()


async def _fila_o_404(repo: RepositorioDeAtletas, swimmer_id: int) -> Swimmer:
    fila = await repo.fila_de(swimmer_id)
    if fila is None:
        raise HTTPException(404, "Atleta no encontrado")
    return fila


@router.get("/", response_model=list[SwimmerResponse])
async def list_swimmers(
    search: str | None = None,
    include_inactive: bool = False,
    repo: RepositorioDeAtletas = Depends(repo_de_atletas),
    usuarios: RepositorioDeUsuarios = Depends(repo_de_usuarios),
):
    filas = await repo.filas(busqueda=search, incluir_de_baja=include_inactive)
    return await service.with_accounts(usuarios, filas)


@router.post("/", response_model=SwimmerResponse, status_code=201)
async def create_swimmer(
    data: SwimmerCreate,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeAtletas = Depends(repo_de_atletas),
):
    return service.to_response(await repo.crear(
        team_id=coach.team_id, nombre=data.name, nacimiento=data.birth_date,
        genero=data.gender, especialidad=data.specialty,
        estilo_principal=data.main_stroke, peso_kg=data.weight_kg,
        altura_cm=data.height_cm, notas=data.notes,
    ))


@router.get("/{swimmer_id}", response_model=SwimmerResponse)
async def get_swimmer(
    swimmer_id: int,
    repo: RepositorioDeAtletas = Depends(repo_de_atletas),
):
    return service.to_response(await _fila_o_404(repo, swimmer_id))


@router.put("/{swimmer_id}", response_model=SwimmerResponse)
async def update_swimmer(
    swimmer_id: int,
    data: SwimmerUpdate,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeAtletas = Depends(repo_de_atletas),
):
    fila = await _fila_o_404(repo, swimmer_id)
    return service.to_response(
        await repo.actualizar(fila, data.model_dump(exclude_unset=True)),
    )


@router.delete("/{swimmer_id}", response_model=SwimmerResponse)
async def deactivate_swimmer(
    swimmer_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeAtletas = Depends(repo_de_atletas),
):
    """Da de baja al atleta. **No borra nada**: su histórico se conserva.

    Se mantiene el verbo DELETE porque es la acción que expresa el cliente
    ("quitar del equipo"), pero la respuesta devuelve el atleta actualizado en
    vez de 204 para que la UI pueda reflejar el nuevo estado.
    """
    fila = await _fila_o_404(repo, swimmer_id)
    respuesta = service.to_response(await repo.cambiar_alta(fila, False))
    auditar(TipoDeEvento.NADADOR_BAJA, coach, objetivo=("swimmer", swimmer_id))
    return respuesta


@router.post("/{swimmer_id}/reactivate", response_model=SwimmerResponse)
async def reactivate_swimmer(
    swimmer_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeAtletas = Depends(repo_de_atletas),
):
    fila = await _fila_o_404(repo, swimmer_id)
    respuesta = service.to_response(await repo.cambiar_alta(fila, True))
    auditar(TipoDeEvento.NADADOR_RESTAURADO, coach, objetivo=("swimmer", swimmer_id))
    return respuesta
