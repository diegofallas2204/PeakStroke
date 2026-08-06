"""Endpoints del módulo teams — sin lógica de negocio.

Todas las rutas operan sobre **el equipo de quien pregunta**, nunca sobre un id
recibido del cliente: así no existe forma de nombrar otro equipo en la petición.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import Principal, require_coach, require_team_owner

from . import service
from .schemas import CoachAthletes, OwnerTransfer, TeamResponse, TeamUpdate

router = APIRouter()


async def _mine(db: AsyncSession, principal: Principal):
    team = await service.get_team(db, principal.team_id)
    if team is None:  # pragma: no cover - imposible si la sesión es válida
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return team


async def _to_response(db: AsyncSession, team, principal: Principal) -> TeamResponse:
    coaches, athletes, swimmers = await service.team_counts(db, team.id)
    return TeamResponse(
        id=team.id, name=team.name, owner_id=team.owner_id,
        owner_name=await service.owner_name(db, team),
        is_owner=principal.is_owner,
        coaches=coaches, athletes=athletes, swimmers=swimmers,
    )


@router.get("/mine", response_model=TeamResponse)
async def my_team(
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    return await _to_response(db, await _mine(db, principal), principal)


@router.patch("/mine", response_model=TeamResponse)
async def rename_team(
    data: TeamUpdate,
    principal: Principal = Depends(require_team_owner),
    db: AsyncSession = Depends(get_db),
):
    team = await _mine(db, principal)
    team.name = data.name
    await db.commit()
    await db.refresh(team)
    return await _to_response(db, team, principal)


@router.post("/mine/transfer", response_model=TeamResponse)
async def transfer_ownership(
    data: OwnerTransfer,
    principal: Principal = Depends(require_team_owner),
    db: AsyncSession = Depends(get_db),
):
    """Cede la propiedad a otro entrenador del equipo.

    Es irreversible desde el punto de vista de quien la cede: a partir de aquí
    el nuevo dueño es el único que puede volver a transferirla.
    """
    team = await _mine(db, principal)
    try:
        team = await service.transfer_ownership(db, team, data.new_owner_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    # `is_owner` del principal ya no vale: quien pregunta acaba de dejar de serlo.
    return await _to_response(db, team, principal)


@router.get("/mine/coaches/{coach_id}/athletes", response_model=list[int])
async def coach_athletes(
    coach_id: int,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    return await service.athletes_of_coach(db, principal.team_id, coach_id)


@router.put("/mine/coaches/{coach_id}/athletes", response_model=list[int])
async def set_coach_athletes(
    coach_id: int,
    data: CoachAthletes,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await service.set_athletes_of_coach(
            db, principal.team_id, coach_id, data.swimmer_ids,
        )
    except Exception as exc:  # la FK compuesta rechaza atletas de otro equipo
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Algún atleta o entrenador no pertenece a este equipo",
        ) from exc
