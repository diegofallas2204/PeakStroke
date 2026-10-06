"""El macrociclo de la URL, o 404. Lo comparten los dos routers de la rebanada.

Los dos piden al repositorio, que ya acota por equipo y por entrenador
asignado: un macrociclo que no te toca y uno que no existe son el mismo 404.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.dominio.entidades import Macrociclo
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.planes import Plan


async def fila_o_404(repo: RepositorioDeMacrociclos, plan_id: int) -> Plan:
    fila = await repo.fila_de(plan_id)
    if fila is None:
        raise HTTPException(404, "Macrociclo no encontrado")
    return fila


async def macro_o_404(repo: RepositorioDeMacrociclos, plan_id: int) -> Macrociclo:
    macro = await repo.por_id(plan_id)
    if macro is None:
        raise HTTPException(404, "Macrociclo no encontrado")
    return macro
