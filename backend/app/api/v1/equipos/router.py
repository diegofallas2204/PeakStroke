"""Endpoints del equipo — sin lógica de negocio.

Todas las rutas operan sobre **el equipo de quien pregunta**, nunca sobre un id
recibido del cliente: así no existe forma de nombrar otro equipo en la petición.
Es lo que sostiene la frontera, porque el repositorio de equipos es el único que
no lleva `Principal` dentro (ver su cabecera).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import repo_de_equipos
from app.core.auditoria import TipoDeEvento, auditar
from app.core.database import get_db
from app.core.guards import require_coach, require_team_owner
from app.core.principal import Principal
from app.persistencia.repositorios import RepositorioDeEquipos
from app.persistencia.tablas.equipos import Team

from . import service
from .schemas import CoachAthletes, OwnerTransfer, TeamResponse, TeamUpdate

router = APIRouter()


async def _mio(repo: RepositorioDeEquipos, principal: Principal) -> Team:
    equipo = await repo.equipo(principal.team_id)
    if equipo is None:  # pragma: no cover - imposible si la sesión es válida
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return equipo


@router.get("/mine", response_model=TeamResponse)
async def my_team(
    principal: Principal = Depends(require_coach),
    repo: RepositorioDeEquipos = Depends(repo_de_equipos),
    db: AsyncSession = Depends(get_db),
):
    return await service.to_response(db, repo, await _mio(repo, principal), principal)


@router.patch("/mine", response_model=TeamResponse)
async def rename_team(
    data: TeamUpdate,
    principal: Principal = Depends(require_team_owner),
    repo: RepositorioDeEquipos = Depends(repo_de_equipos),
    db: AsyncSession = Depends(get_db),
):
    equipo = await service.rename_team(repo, await _mio(repo, principal), data.name)
    return await service.to_response(db, repo, equipo, principal)


@router.post("/mine/transfer", response_model=TeamResponse)
async def transfer_ownership(
    data: OwnerTransfer,
    principal: Principal = Depends(require_team_owner),
    repo: RepositorioDeEquipos = Depends(repo_de_equipos),
    db: AsyncSession = Depends(get_db),
):
    """Cede la propiedad a otro entrenador del equipo.

    Es irreversible desde el punto de vista de quien la cede: a partir de aquí
    el nuevo dueño es el único que puede volver a transferirla.
    """
    equipo = await _mio(repo, principal)
    try:
        equipo = await service.transfer_ownership(repo, equipo, data.new_owner_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    auditar(
        TipoDeEvento.PROPIEDAD_TRANSFERIDA, principal,
        objetivo=("user", data.new_owner_id),
        detalle=f"de la cuenta {principal.id} a la {data.new_owner_id}",
    )
    # `is_owner` sale del equipo ya transferido, no del `Principal` (que es de antes).
    return await service.to_response(db, repo, equipo, principal)


@router.get("/mine/coaches/{coach_id}/athletes", response_model=list[int])
async def coach_athletes(
    coach_id: int,
    principal: Principal = Depends(require_coach),
    repo: RepositorioDeEquipos = Depends(repo_de_equipos),
):
    return await repo.atletas_de(principal.team_id, coach_id)


@router.put("/mine/coaches/{coach_id}/athletes", response_model=list[int])
async def set_coach_athletes(
    coach_id: int,
    data: CoachAthletes,
    principal: Principal = Depends(require_coach),
    repo: RepositorioDeEquipos = Depends(repo_de_equipos),
):
    try:
        return await repo.fijar_atletas_de(
            principal.team_id, coach_id, data.swimmer_ids,
        )
    except Exception as exc:  # la FK compuesta rechaza atletas de otro equipo
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Algún atleta o entrenador no pertenece a este equipo",
        ) from exc
