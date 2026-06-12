"""Endpoints del módulo swimmers — sin lógica de negocio."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

from . import service
from .schemas import SwimmerCreate, SwimmerResponse, SwimmerUpdate

router = APIRouter()


@router.get("/", response_model=list[SwimmerResponse])
async def list_swimmers(search: str | None = None, db: AsyncSession = Depends(get_db)):
    return [service.to_response(s) for s in await service.list_swimmers(db, search)]


@router.post("/", response_model=SwimmerResponse, status_code=201)
async def create_swimmer(data: SwimmerCreate, db: AsyncSession = Depends(get_db)):
    return service.to_response(await service.create_swimmer(db, data))


@router.get("/{swimmer_id}", response_model=SwimmerResponse)
async def get_swimmer(swimmer_id: int, db: AsyncSession = Depends(get_db)):
    swimmer = await service.get_swimmer(db, swimmer_id)
    if swimmer is None:
        raise HTTPException(404, "Atleta no encontrado")
    return service.to_response(swimmer)


@router.put("/{swimmer_id}", response_model=SwimmerResponse)
async def update_swimmer(swimmer_id: int, data: SwimmerUpdate, db: AsyncSession = Depends(get_db)):
    swimmer = await service.get_swimmer(db, swimmer_id)
    if swimmer is None:
        raise HTTPException(404, "Atleta no encontrado")
    return service.to_response(await service.update_swimmer(db, swimmer, data))


@router.delete("/{swimmer_id}", status_code=204)
async def delete_swimmer(swimmer_id: int, db: AsyncSession = Depends(get_db)):
    swimmer = await service.get_swimmer(db, swimmer_id)
    if swimmer is None:
        raise HTTPException(404, "Atleta no encontrado")
    await service.delete_swimmer(db, swimmer)
