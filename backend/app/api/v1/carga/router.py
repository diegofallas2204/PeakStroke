"""Endpoints de la carga de entrenamiento. Prefijo público: `/api/v1/training-load`.

Solo lectura: la carga se deriva de las sesiones y los tests y no se edita. Sin
`require_coach`: el atleta ve la suya; la ajena, 404.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencias import repo_de_atletas, repo_de_carga
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeCarga

from . import service
from .schemas import TrainingLoadResponse

router = APIRouter()

# Lo que se enseña si no se pide rango: un trimestre, algo más que un macro.
_RANGO_POR_DEFECTO = timedelta(days=90)
# Tope del rango: dos años de días. Más es una consulta que nadie va a pintar.
_RANGO_MAXIMO = timedelta(days=731)


@router.get("/{swimmer_id}", response_model=TrainingLoadResponse)
async def get_training_load(
    swimmer_id: int, desde: date | None = None, hasta: date | None = None,
    repo: RepositorioDeCarga = Depends(repo_de_carga),
    atletas: RepositorioDeAtletas = Depends(repo_de_atletas),
):
    """CTL, ATL y TSB día a día en `[desde, hasta]` (por defecto, los últimos 90 días)."""
    if await atletas.fila_de(swimmer_id) is None:
        raise HTTPException(404, "Atleta no encontrado")
    hasta = hasta or date.today()
    desde = desde or hasta - _RANGO_POR_DEFECTO
    if desde > hasta:
        raise HTTPException(422, "`desde` no puede ser posterior a `hasta`")
    if hasta - desde > _RANGO_MAXIMO:
        raise HTTPException(422, "El rango no puede pasar de dos años")
    return await service.curva(repo, swimmer_id, desde, hasta)
