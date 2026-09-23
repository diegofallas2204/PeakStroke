"""Los repositorios, como dependencia de FastAPI.

Un repositorio se construye con la sesión y la identidad de la petición, y esas
dos cosas ya las resuelve `core/`. Declararlo aquí evita que cada router repita
el `RepositorioDeMacrociclos(db, principal)` — y, sobre todo, que alguno lo
construya con un principal distinto del que su guard comprobó.

`get_current_principal` se pide una sola vez por petición aunque el endpoint
lleve además `require_coach`: FastAPI cachea las subdependencias, y el guard
cuelga de esta misma. El repositorio queda acotado a quien el guard dejó pasar.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_principal
from app.core.principal import Principal
from app.persistencia.repositorios import (
    RepositorioDeAtletas,
    RepositorioDeCodigos,
    RepositorioDeEquipos,
    RepositorioDeMacrociclos,
    RepositorioDeResultados,
    RepositorioDeSesiones,
    RepositorioDeTests,
    RepositorioDeUsuarios,
)


async def repo_de_macrociclos(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> RepositorioDeMacrociclos:
    return RepositorioDeMacrociclos(db, principal)


async def repo_de_resultados(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> RepositorioDeResultados:
    return RepositorioDeResultados(db, principal)


async def repo_de_sesiones(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> RepositorioDeSesiones:
    return RepositorioDeSesiones(db, principal)


async def repo_de_atletas(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> RepositorioDeAtletas:
    return RepositorioDeAtletas(db, principal)


async def repo_de_tests(
    db: AsyncSession = Depends(get_db),
    principal: Principal = Depends(get_current_principal),
) -> RepositorioDeTests:
    return RepositorioDeTests(db, principal)


async def repo_de_usuarios(db: AsyncSession = Depends(get_db)) -> RepositorioDeUsuarios:
    """Sin `Principal`: la cuenta es identidad pura, sin frontera de equipo."""
    return RepositorioDeUsuarios(db)


async def repo_de_codigos(db: AsyncSession = Depends(get_db)) -> RepositorioDeCodigos:
    """Sin `Principal`: la mitad de sus lectores no pertenece a ningún club."""
    return RepositorioDeCodigos(db)


async def repo_de_equipos(db: AsyncSession = Depends(get_db)) -> RepositorioDeEquipos:
    """Sin `Principal`, y a propósito: ver la cabecera del repositorio.

    El equipo es la frontera que los demás aplican, así que no puede acotarse
    por ella. Lo que la sostiene es que ningún endpoint acepta un `team_id` del
    cliente.
    """
    return RepositorioDeEquipos(db)
