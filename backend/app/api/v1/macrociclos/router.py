"""Endpoints del macrociclo.

Cada ruta resuelve el macrociclo a través del repositorio, que ya acota por
equipo y por entrenador asignado. Así el aislamiento no depende de que cada
endpoint se acuerde de comprobarlo.

Dos formas de pedir el mismo plan, y la diferencia es deliberada:
`repo.por_id()` devuelve el **`Macrociclo`** —lo que se usa para decidir—, y
`repo.fila_de()` devuelve la fila con la nómina cargada, que es lo que hace
falta para pintar la respuesta mientras `Inscripcion` no sea una entidad.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import repo_de_macrociclos
from app.core.database import get_db
from app.core.dates import age_at
from app.core.guards import exigir_o_bypass, require_coach
from app.core.principal import Principal
from app.dominio.entidades import Macrociclo
from app.dominio.roles import Recurso
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.planes import Plan

from . import inscripcion, nomina, semanas, service
from .schemas import (
    AddAthleteRequest,
    AssignableAthlete,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    WeekResponse,
    WeekUpdateRequest,
)

router = APIRouter()


async def _fila_o_404(repo: RepositorioDeMacrociclos, plan_id: int) -> Plan:
    fila = await repo.fila_de(plan_id)
    if fila is None:
        raise HTTPException(404, "Macrociclo no encontrado")
    return fila


async def _macro_o_404(repo: RepositorioDeMacrociclos, plan_id: int) -> Macrociclo:
    macro = await repo.por_id(plan_id)
    if macro is None:
        raise HTTPException(404, "Macrociclo no encontrado")
    return macro


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    return [
        await service.to_plan_response(db, f, repo.principal)
        for f in await repo.filas()
    ]


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    data: PlanCreate,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    # Quien lo crea queda automáticamente a cargo: si no, nacería un macrociclo
    # que su propio autor no podría ver.
    fila = await service.create_plan(repo, data, coach.team_id, coach.id)
    return await service.to_plan_response(db, fila, coach)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: int,
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    fila = await _fila_o_404(repo, plan_id)
    return await service.to_plan_response(db, fila, repo.principal)


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int, data: PlanUpdate,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    fila = await _fila_o_404(repo, plan_id)
    return await service.to_plan_response(db, await service.update_plan(repo, fila, data), coach)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
):
    """Borra el macrociclo. **409 si tiene tests aeróbicos colgando.**

    No se borran en cascada a propósito: un test es una medición del atleta en
    una fecha, no una parte del macrociclo. Que el entrenador decida qué hacer
    con ellos es más barato que descubrir que se evaporaron.
    """
    bloqueantes = await service.delete_plan(repo, await _fila_o_404(repo, plan_id))
    if bloqueantes:
        raise HTTPException(409, (
            f"Este macrociclo tiene {bloqueantes} test(s) aeróbico(s) asociados. "
            "Dales de baja o muévelos a otro macrociclo antes de borrarlo."
        ))


@router.get("/{plan_id}/assignable-athletes", response_model=list[AssignableAthlete])
async def assignable_athletes(
    plan_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    """Los atletas que hoy pueden entrar en este macrociclo.

    Existe para que el formulario no ofrezca lo que el POST va a rechazar. La
    regla la impone `add_athlete` de todas formas: esto es la cortesía, no la
    cerradura (ver `inscripcion.py`).
    """
    macro = await _macro_o_404(repo, plan_id)
    return [
        AssignableAthlete(
            id=s.id, name=s.name, specialty=s.specialty, main_stroke=s.main_stroke,
            age=age_at(s.birth_date, macro.inicio),
        )
        for s in await inscripcion.assignable_swimmers(db, repo, macro)
    ]


@router.post("/{plan_id}/athletes", response_model=PlanResponse, status_code=201)
async def add_athlete(
    plan_id: int, data: AddAthleteRequest,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    macro = await _macro_o_404(repo, plan_id)
    if data.swimmer_id in await repo.inscritos_en(plan_id):
        raise HTTPException(409, "El atleta ya está asignado a este macrociclo")
    # Un atleta, un macrociclo vivo. El bloqueo aplica también al dueño del
    # equipo: no es una cuestión de permisos sino de que ese plan no existe.
    ocupado = await inscripcion.blocking_plan(repo, data.swimmer_id, target_plan_id=plan_id)
    if ocupado is not None:
        raise HTTPException(409, (
            f"Ese atleta ya está en el macrociclo «{ocupado.nombre}». "
            "Sácalo de ahí antes de inscribirlo en otro."
        ))
    await nomina.add_athlete(db, repo, macro, data)
    return await service.to_plan_response(db, await _fila_o_404(repo, plan_id), coach)


@router.delete("/{plan_id}/athletes/{athlete_plan_id}", status_code=204)
async def remove_athlete(
    plan_id: int, athlete_plan_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
):
    """Saca al atleta del macrociclo. **No borra su histórico**: lo da de baja.

    Se mantiene el verbo DELETE porque es la acción que expresa el cliente
    ("quitar del macrociclo"), igual que en `swimmers`. Sus semanas y tiempos
    reales siguen en la base, y `POST .../restore` vuelve a inscribirlo con todo.
    """
    await _macro_o_404(repo, plan_id)
    if not await nomina.remove_athlete(repo, plan_id, athlete_plan_id):
        raise HTTPException(404, "Atleta no encontrado en este macrociclo")


@router.post("/{plan_id}/athletes/{athlete_plan_id}/restore", status_code=204)
async def restore_athlete(
    plan_id: int, athlete_plan_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
):
    """Vuelve a inscribir a un atleta dado de baja, con su histórico intacto.

    Sacar a alguien de un macrociclo es la clase de clic que se da por error, y
    volver a inscribirlo desde cero no reconstruye lo que nadó.
    """
    await _macro_o_404(repo, plan_id)
    ocupado = await inscripcion.blocking_plan_for(repo, athlete_plan_id)
    if ocupado is not None:
        raise HTTPException(409, (
            f"Ese atleta entró mientras tanto en el macrociclo «{ocupado.nombre}». "
            "Sácalo de ahí antes de devolverlo a este."
        ))
    if not await nomina.restore_athlete(repo, plan_id, athlete_plan_id):
        raise HTTPException(404, "No hay ninguna inscripción dada de baja con ese id")


@router.get("/events/{event_id}/weeks", response_model=list[WeekResponse])
async def event_weeks(
    event_id: int,
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    event = await repo.prueba(event_id)
    if event is None:
        raise HTTPException(404, "Prueba no encontrada")
    return await semanas.event_weeks_response(db, event)


@router.patch("/weeks/{week_id}", response_model=list[WeekResponse])
async def update_week(
    week_id: int, data: WeekUpdateRequest,
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    # Sin require_coach a propósito: registrar el tiempo real de la semana es una
    # de las cosas que el atleta puede hacer sobre SU plan, y `repo.semana` ya
    # acota por visibilidad.
    #
    # Pero no todos los campos son suyos. Desde que el filtro por nadador existe,
    # la semana que toca ES la suya, así que sin esta comprobación escribir
    # `disabled` pasaría a ser legítimo — y eso es el parón del entrenador, que
    # redistribuye la mejora restante de todo el macrociclo. 403 y no 404: el
    # recurso sí es suyo, lo que no alcanza es el rol.
    if data.touches_coach_only_fields() and not repo.principal.rol.puede_escribir(
        Recurso.PARON_DE_SEMANA,
    ):
        exigir_o_bypass(repo.principal, "entrenador para marcar el parón de una semana")

    event = await semanas.update_week(db, repo, week_id, data)
    if event is None:
        raise HTTPException(404, "Semana no encontrada")
    return await semanas.event_weeks_response(db, event)
