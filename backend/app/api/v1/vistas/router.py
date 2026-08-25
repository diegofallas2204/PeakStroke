"""Endpoints de las vistas: el tablero y la tabla del equipo.

El prefijo público sigue siendo `/api/v1/dashboard`. El contrato del API no
cambia con el paso 5 — lo que cambia es de dónde salen los datos.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import repo_de_macrociclos
from app.core.database import get_db
from app.core.guards import require_coach
from app.core.principal import Principal
from app.dominio.entidades import Macrociclo
from app.persistencia.repositorios import RepositorioDeMacrociclos

from . import tablero
from .schemas import DashboardSummary, TeamWeekResponse

router = APIRouter()


async def _resolver_macro(
    repo: RepositorioDeMacrociclos, plan_id: int | None,
) -> Macrociclo:
    """El macrociclo pedido, o el activo — siempre dentro de lo que el usuario ve.

    `plan_id` llega del cliente, así que pasa por el repositorio, que acota por
    equipo y por asignación. Sin eso, el tablero sería la puerta trasera para
    leer el macrociclo de otro club.
    """
    macro = await (repo.por_id(plan_id) if plan_id else repo.activo())
    if macro is None:
        raise HTTPException(404, "No hay macrociclo activo")
    return macro


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    plan_id: int | None = None,
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    macro = await _resolver_macro(repo, plan_id)
    return await tablero.build_summary(db, repo, macro)


@router.get("/team-week", response_model=TeamWeekResponse)
async def team_week(
    plan_id: int | None = None, week: int | None = None,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    """La semana de **todo el equipo**: una herramienta de entrenador.

    Fuera del alcance del atleta por decisión explícita del plan, y por eso el
    guard va aquí y no un filtro de filas: una tabla comparativa con una sola
    fila no es una versión personal de nada, es una pantalla sin sentido. Que
    responda 403 dice lo que pasa; devolver una fila fingiría que la pantalla es
    para él.

    `require_coach` sirve para esto desde que comprueba el rol también con el
    login apagado (hallazgo CSO-1 del 2026-08-06). Antes no habría servido.
    """
    macro = await _resolver_macro(repo, plan_id)
    week_number = week or macro.semana_actual() or 1
    week_number = max(1, min(week_number, macro.semanas))
    return await tablero.team_week(db, repo, macro, week_number)
