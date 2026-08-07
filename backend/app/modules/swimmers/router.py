"""Endpoints del módulo swimmers — sin lógica de negocio."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal, require_coach

from . import service
from .schemas import SwimmerCreate, SwimmerResponse, SwimmerUpdate

router = APIRouter()


async def _swimmer_or_404(db: AsyncSession, swimmer_id: int, principal: Principal):
    swimmer = await service.get_swimmer(db, swimmer_id, principal)
    if swimmer is None:
        raise HTTPException(404, "Atleta no encontrado")
    return swimmer


@router.get("/", response_model=list[SwimmerResponse])
async def list_swimmers(
    search: str | None = None,
    include_inactive: bool = False,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    swimmers = await service.list_swimmers(
        db, principal, search, include_inactive=include_inactive,
    )
    return [service.to_response(s) for s in swimmers]


@router.post("/", response_model=SwimmerResponse, status_code=201)
async def create_swimmer(
    data: SwimmerCreate,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    return service.to_response(await service.create_swimmer(db, data, principal.team_id))


@router.get("/{swimmer_id}", response_model=SwimmerResponse)
async def get_swimmer(
    swimmer_id: int,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return service.to_response(await _swimmer_or_404(db, swimmer_id, principal))


@router.put("/{swimmer_id}", response_model=SwimmerResponse)
async def update_swimmer(
    swimmer_id: int,
    data: SwimmerUpdate,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    swimmer = await _swimmer_or_404(db, swimmer_id, principal)
    return service.to_response(await service.update_swimmer(db, swimmer, data))


@router.delete("/{swimmer_id}", response_model=SwimmerResponse)
async def deactivate_swimmer(
    swimmer_id: int,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Da de baja al atleta. **No borra nada**: su histórico se conserva.

    Se mantiene el verbo DELETE porque es la acción que expresa el cliente
    ("quitar del equipo"), pero la respuesta devuelve el atleta actualizado en
    vez de 204 para que la UI pueda reflejar el nuevo estado.
    """
    swimmer = await _swimmer_or_404(db, swimmer_id, principal)
    return service.to_response(await service.set_active(db, swimmer, False))


@router.post("/{swimmer_id}/reactivate", response_model=SwimmerResponse)
async def reactivate_swimmer(
    swimmer_id: int,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    swimmer = await _swimmer_or_404(db, swimmer_id, principal)
    return service.to_response(await service.set_active(db, swimmer, True))
