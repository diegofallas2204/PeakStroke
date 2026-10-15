"""Endpoints de la nómina del macrociclo: quién puede entrar, meterlo, sacarlo y devolverlo.

Salieron de `router.py` el 2026-10-05 (C9 punto 2), cuando la inscripción pasó a
ser una entidad y el router pasaba de 300 líneas. Mismo prefijo, mismas rutas:
`router.py` incluye este.

Tres comprobaciones al inscribir, en este orden y cada una con su respuesta:
la ficha (visible, o 404; activa y del club, o 409, lo decide
`Macrociclo.inscribir`), la pareja (ya dentro, 409; dentro pero de baja, 409
que dice «devuélvelo») y la regla de «un atleta, un macrociclo vivo»
(`inscripcion.py`, 409).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import repo_de_atletas, repo_de_inscripciones, repo_de_macrociclos
from app.core.auditoria import TipoDeEvento, auditar
from app.core.database import get_db
from app.core.dates import age_at
from app.core.guards import require_coach
from app.core.principal import Principal
from app.dominio.entidades import InscripcionImposible
from app.persistencia.repositorios import (
    RepositorioDeAtletas,
    RepositorioDeInscripciones,
    RepositorioDeMacrociclos,
)

from . import inscripcion, nomina
from .presentacion import to_plan_response
from .resolver import fila_o_404, macro_o_404
from .schemas import AddAthleteRequest, AssignableAthlete, PlanResponse

router = APIRouter()


@router.get("/{plan_id}/assignable-athletes", response_model=list[AssignableAthlete])
async def assignable_athletes(
    plan_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    inscripciones: RepositorioDeInscripciones = Depends(repo_de_inscripciones),
    db: AsyncSession = Depends(get_db),
) -> list[AssignableAthlete]:
    """Los atletas que hoy pueden entrar en este macrociclo.

    Existe para que el formulario no ofrezca lo que el POST va a rechazar. La
    regla la impone `add_athlete` de todas formas: esto es la cortesía, no la
    cerradura (ver `inscripcion.py`).
    """
    macro = await macro_o_404(repo, plan_id)
    return [
        AssignableAthlete(
            id=s.id, name=s.name, specialty=s.specialty, main_stroke=s.main_stroke,
            age=age_at(s.birth_date, macro.inicio),
        )
        for s in await inscripcion.assignable_swimmers(db, inscripciones, macro)
    ]


@router.post("/{plan_id}/athletes", response_model=PlanResponse, status_code=201)
async def add_athlete(
    plan_id: int, data: AddAthleteRequest,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    inscripciones: RepositorioDeInscripciones = Depends(repo_de_inscripciones),
    atletas: RepositorioDeAtletas = Depends(repo_de_atletas),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    macro = await macro_o_404(repo, plan_id)
    # La ficha, por su repositorio: una inexistente o de otro club es 404. Hasta
    # el 2026-10-05 llegaba a la FK compuesta y salía como 500.
    atleta = await atletas.por_id(data.swimmer_id)
    if atleta is None:
        raise HTTPException(404, "Atleta no encontrado")
    previa = await inscripciones.de(plan_id, data.swimmer_id)
    if previa is not None and previa.activa:
        raise HTTPException(409, "El atleta ya está asignado a este macrociclo")
    if previa is not None:
        # La pareja (macrociclo, atleta) es única: volver a inscribirlo reventaba
        # en la UNIQUE con un 500. Lo que toca es devolverlo, con su histórico.
        raise HTTPException(409, (
            "Ese atleta está dado de baja en este macrociclo: devuélvelo en vez de "
            "inscribirlo de nuevo, así conserva lo que ya nadó."
        ))
    # Un atleta, un macrociclo vivo. El bloqueo aplica también al dueño del
    # equipo: no es una cuestión de permisos sino de que ese plan no existe.
    ocupado = await inscripcion.blocking_plan(
        inscripciones, data.swimmer_id, target_plan_id=plan_id,
    )
    if ocupado is not None:
        raise HTTPException(409, (
            f"Ese atleta ya está en el macrociclo «{ocupado.nombre}». "
            "Sácalo de ahí antes de inscribirlo en otro."
        ))
    try:
        await nomina.add_athlete(inscripciones, macro, atleta, data)
    except InscripcionImposible as exc:
        raise HTTPException(409, str(exc)) from exc
    return await to_plan_response(db, await fila_o_404(repo, plan_id), coach)


@router.delete("/{plan_id}/athletes/{athlete_plan_id}", status_code=204)
async def remove_athlete(
    plan_id: int, athlete_plan_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    inscripciones: RepositorioDeInscripciones = Depends(repo_de_inscripciones),
) -> None:
    """Saca al atleta del macrociclo. **No borra su histórico**: lo da de baja.

    Se mantiene el verbo DELETE porque es la acción que expresa el cliente
    ("quitar del macrociclo"), igual que en `swimmers`. Sus semanas y tiempos
    reales siguen en la base, y `POST .../restore` vuelve a inscribirlo con todo.
    Repetirla no falla y no se audita otra vez: no cambió nada.
    """
    await macro_o_404(repo, plan_id)
    cambio = await nomina.remove_athlete(inscripciones, plan_id, athlete_plan_id)
    if cambio is None:
        raise HTTPException(404, "Atleta no encontrado en este macrociclo")
    if cambio:
        auditar(
            TipoDeEvento.INSCRIPCION_BAJA, coach, objetivo=("athlete_plan", athlete_plan_id),
            detalle=f"del macrociclo {plan_id}",
        )


@router.post("/{plan_id}/athletes/{athlete_plan_id}/restore", status_code=204)
async def restore_athlete(
    plan_id: int, athlete_plan_id: int,
    coach: Principal = Depends(require_coach),
    repo: RepositorioDeMacrociclos = Depends(repo_de_macrociclos),
    inscripciones: RepositorioDeInscripciones = Depends(repo_de_inscripciones),
    atletas: RepositorioDeAtletas = Depends(repo_de_atletas),
) -> None:
    """Vuelve a inscribir a un atleta dado de baja, con su histórico intacto.

    Sacar a alguien de un macrociclo es la clase de clic que se da por error, y
    volver a inscribirlo desde cero no reconstruye lo que nadó. Repetirla no
    falla y no se audita otra vez.
    """
    await macro_o_404(repo, plan_id)
    ocupado = await inscripcion.blocking_plan_for(inscripciones, athlete_plan_id)
    if ocupado is not None:
        raise HTTPException(409, (
            f"Ese atleta entró mientras tanto en el macrociclo «{ocupado.nombre}». "
            "Sácalo de ahí antes de devolverlo a este."
        ))
    try:
        cambio = await nomina.restore_athlete(inscripciones, atletas, plan_id, athlete_plan_id)
    except InscripcionImposible as exc:
        raise HTTPException(409, str(exc)) from exc
    if cambio is None:
        raise HTTPException(404, "Atleta no encontrado en este macrociclo")
    if cambio:
        auditar(
            TipoDeEvento.INSCRIPCION_RESTAURADA, coach,
            objetivo=("athlete_plan", athlete_plan_id), detalle=f"al macrociclo {plan_id}",
        )
