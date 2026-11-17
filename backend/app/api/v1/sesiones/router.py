"""Endpoints de las sesiones. Prefijo público: `/api/v1/sessions`.

**Sin `require_coach` en ninguno, a propósito.** Apuntar lo que nadó es lo
primero que tiene que poder hacer el atleta —el RPE es suyo—, igual que sus
tiempos y sus tests. Lo que le impide tocar lo de un compañero es el
repositorio, que acota cada consulta: lo ajeno da 404, nunca 403.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencias import repo_de_atletas, repo_de_sesiones
from app.core.auditoria import TipoDeEvento, auditar
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeSesiones

from . import service
from .schemas import TrainingSessionCreate, TrainingSessionResponse, TrainingSessionUpdate

router = APIRouter()


@router.get("/", response_model=list[TrainingSessionResponse])
async def list_sessions(
    swimmer_id: int | None = None, desde: date | None = None, hasta: date | None = None,
    repo: RepositorioDeSesiones = Depends(repo_de_sesiones),
):
    """Las visibles, de la más reciente a la más antigua; fechas inclusivas."""
    return [service.to_response(s) for s in await repo.listar(
        atleta_id=swimmer_id, desde=desde, hasta=hasta,
    )]


@router.post("/", response_model=TrainingSessionResponse, status_code=201)
async def create_session(
    data: TrainingSessionCreate,
    repo: RepositorioDeSesiones = Depends(repo_de_sesiones),
    atletas: RepositorioDeAtletas = Depends(repo_de_atletas),
):
    sesion = await service.crear(repo, atletas, data)
    if sesion is None:
        raise HTTPException(404, "Atleta no encontrado")
    return service.to_response(sesion)


@router.get("/{session_id}", response_model=TrainingSessionResponse)
async def get_session(
    session_id: int, repo: RepositorioDeSesiones = Depends(repo_de_sesiones),
):
    sesion = await repo.por_id(session_id)
    if sesion is None:
        raise HTTPException(404, "Sesión no encontrada")
    return service.to_response(sesion)


@router.patch("/{session_id}", response_model=TrainingSessionResponse)
async def update_session(
    session_id: int, data: TrainingSessionUpdate,
    repo: RepositorioDeSesiones = Depends(repo_de_sesiones),
):
    try:
        sesion = await service.actualizar(repo, session_id, data)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if sesion is None:
        raise HTTPException(404, "Sesión no encontrada")
    return service.to_response(sesion)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: int, repo: RepositorioDeSesiones = Depends(repo_de_sesiones),
):
    """Borra de verdad: ver `persistencia/tablas/sesiones.py`.

    Se audita cuando quien borra **no** es el atleta dueño (TODO-20, 2026-11-16):
    el entrenador quitando el registro de otro es un borrado de verdad sobre un
    dato ajeno, y CLAUDE.md pide `TipoDeEvento` para esos. Que el atleta corrija
    lo suyo no es un evento de seguridad.
    """
    borrada = await repo.borrar(session_id)
    if borrada is None:
        raise HTTPException(404, "Sesión no encontrada")
    principal = repo.principal
    if not (principal.is_athlete and principal.swimmer_id == borrada.swimmer_id):
        auditar(
            TipoDeEvento.SESION_DE_ENTRENAMIENTO_BORRADA, principal,
            objetivo=("swim_session", session_id),
            detalle=f"nadador {borrada.swimmer_id} · {borrada.session_date.isoformat()} · {borrada.distance_m} m",
        )
