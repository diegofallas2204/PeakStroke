"""Endpoints del macrociclo.

Cada ruta resuelve el macrociclo a través del repositorio, que ya acota por
equipo y por entrenador asignado. Así el aislamiento no depende de que cada
endpoint se acuerde de comprobarlo.

Dos formas de pedir el mismo plan, y la diferencia es deliberada:
`repo.por_id()` devuelve el **`Macrociclo`** —lo que se usa para decidir—, y
`repo.fila_de()` devuelve la fila con la nómina cargada, que es lo que hace
falta para pintar la respuesta (`PlanResponse` se valida sobre las filas). La
nómina en sí está en `router_nomina.py`; las semanas, por `RepositorioDeSemanas`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import repo_de_macrociclos, repo_de_resultados, repo_de_semanas
from app.core.auditoria import TipoDeEvento, auditar
from app.core.database import get_db
from app.core.guards import exigir_o_bypass, require_coach, require_team_owner
from app.core.principal import Principal
from app.dominio.roles import Recurso
from app.dominio.servicios.motor import fases_por_defecto
from app.persistencia.repositorios import (
    RepositorioDeMacrociclos,
    RepositorioDeResultados,
    RepositorioDeSemanas,
)

from . import semanas, service
from .presentacion import to_plan_response
from .resolver import fila_o_404, macro_o_404
from .router_nomina import router as router_nomina
from .schemas import (
    PhaseInput,
    PlanCreate,
    PlanResponse,
    PlanUpdate,
    WeekResponse,
    WeekUpdateRequest,
)

router = APIRouter()


# La nómina (quién entra, sale y vuelve) vive en `router_nomina.py` desde el
# 2026-10-05; se incluye al final de este archivo con el mismo prefijo.


@router.get("/", response_model=list[PlanResponse])
async def list_plans(
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    return [
        await to_plan_response(db, f, repo.principal)
        for f in await repo.filas()
    ]


@router.post("/", response_model=PlanResponse, status_code=201)
async def create_plan(
    data: PlanCreate,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    # Quien lo crea queda automáticamente a cargo, y en su equipo: los dos
    # salen del `Principal` del repositorio, no de la petición.
    fila = await repo.guardar(service.nuevo_desde(data))
    return await to_plan_response(db, fila, coach)


@router.get("/default-phases", response_model=list[PhaseInput])
async def default_phases(
    weeks: int = Query(ge=4, le=30),
    _coach: Principal = Depends(require_coach),
):
    """Las fases con las que nace un macrociclo de `weeks` semanas.

    El asistente las pide aquí en vez de calcularlas: tenía su propia copia del
    reparto y de los colores, y los colores ya se habían separado de los del
    motor. Va antes de `/{plan_id}` porque si no esa ruta se la come.
    """
    return fases_por_defecto(weeks)


@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: int,
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    fila = await fila_o_404(repo, plan_id)
    return await to_plan_response(db, fila, repo.principal)


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: int, data: PlanUpdate,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    db: AsyncSession = Depends(get_db),
):
    macro = await macro_o_404(repo, plan_id)
    # Cambiar la meta del macro es de dueño (R4), el resto de la edición no:
    # un asistente activa, suspende y anota los macros que lleva. Se mira si el
    # valor CAMBIA, no si viaja, para que reenviar el formulario entero con la
    # meta intacta no le cueste un 403. Después del 404: un macro ajeno sigue
    # siendo ajeno antes que prohibido.
    cambia_la_meta = (
        "main_event" in data.model_fields_set and data.main_event != macro.prueba_principal
    )
    if cambia_la_meta and not coach.is_owner:
        exigir_o_bypass(coach, "dueño del equipo para cambiar la meta del macrociclo")
    service.aplicar(macro, data)
    return await to_plan_response(db, await repo.guardar(macro), coach)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: int,
    dueno: Principal = Depends(require_team_owner),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
):
    """Borra el macrociclo. **Solo el dueño** y **409 si tiene tests aeróbicos colgando.**

    Solo el dueño desde R4 (decidida el 2026-08-16, aplicada el 2026-09-24):
    `plan_coaches` dice quién **ve** un macro, no quién puede hacerlo
    desaparecer. Con `require_coach`, el asistente borraba el macro que llevaba.
    El 403 sale antes de buscar el plan, igual para cualquier id: dice que el
    rol no alcanza, no que el macro exista.

    No se borran en cascada a propósito: un test es una medición del atleta en
    una fecha, no una parte del macrociclo. Que el entrenador decida qué hacer
    con ellos es más barato que descubrir que se evaporaron.
    """
    bloqueantes = await service.delete_plan(repo, await macro_o_404(repo, plan_id))
    if bloqueantes:
        raise HTTPException(409, (
            f"Este macrociclo tiene {bloqueantes} test(s) aeróbico(s) asociados. "
            "Dales de baja o muévelos a otro macrociclo antes de borrarlo."
        ))
    # Es un borrado de verdad, no una baja: el registro es lo único que queda.
    auditar(TipoDeEvento.MACROCICLO_BORRADO, dueno, objetivo=("plan", plan_id))


@router.get("/events/{event_id}/weeks", response_model=list[WeekResponse])
async def event_weeks(
    event_id: int,
    repo: RepositorioDeSemanas = Depends(repo_de_semanas),
    resultados: RepositorioDeResultados = Depends(repo_de_resultados),
):
    plan = await repo.plan_de(event_id)
    if plan is None:
        raise HTTPException(404, "Prueba no encontrada")
    return await semanas.event_weeks_response(resultados, plan)


@router.patch("/weeks/{week_id}", response_model=list[WeekResponse])
async def update_week(
    week_id: int, data: WeekUpdateRequest,
    repo: RepositorioDeSemanas = Depends(repo_de_semanas),
    resultados: RepositorioDeResultados = Depends(repo_de_resultados),
):
    # Sin require_coach a propósito: registrar el tiempo real de la semana es una
    # de las cosas que el atleta puede hacer sobre SU plan, y
    # `repo.plan_de_la_semana` ya acota por visibilidad.
    #
    # Pero no todos los campos son suyos. Desde que el filtro por nadador existe,
    # la semana que toca ES la suya, así que sin esta comprobación escribir
    # `disabled` pasaría a ser legítimo — y eso es el parón del entrenador, que
    # redistribuye la mejora restante de todo el macrociclo. 403 y no 404: el
    # recurso sí es suyo, lo que no alcanza es el rol.
    principal = repo.macros.principal
    if data.touches_coach_only_fields() and not principal.rol.puede_escribir(
        Recurso.PARON_DE_SEMANA,
    ):
        exigir_o_bypass(principal, "entrenador para marcar el parón de una semana")

    plan = await semanas.update_week(repo, resultados, week_id, data)
    if plan is None:
        raise HTTPException(404, "Semana no encontrada")
    return await semanas.event_weeks_response(resultados, plan)


router.include_router(router_nomina)
