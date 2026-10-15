"""De entidad de dominio a fila de SQLAlchemy: la otra dirección de `desde_modelos`.

Aquí está lo que un repositorio necesita para **escribir** un macrociclo: armar
la fila de uno nuevo y volcar sobre una existente lo que se puede editar. Vivía
en `api/v1/macrociclos/service.py` como `Plan(**data.model_dump())` y un
`setattr` por cada campo del formulario (C9, 2026-10-13).

Dos reglas, que son las de toda escritura:

* **El equipo no sale de la entidad.** Lo recibe quien llama —el repositorio,
  de su `Principal`— y es lo único que se escribe en `team_id`.
* **Se escribe la clave canónica** (`.value`) de cada catálogo, no el texto con
  que llegó.
"""
from __future__ import annotations

from app.dominio.entidades import Macrociclo
from app.persistencia.tablas.planes import Competition, Plan, PlanCoach, PlanPhase


def fila_de_macrociclo(macro: Macrociclo, *, equipo_id: int, entrenador_id: int) -> Plan:
    """La fila de un macrociclo nuevo, con sus fases, sus competencias y quien lo lleva.

    Quien lo crea queda a cargo (`plan_coaches`): si no, nacería un macrociclo
    que su propio autor no podría ver.
    """
    fila = Plan(
        team_id=equipo_id,
        name=macro.nombre, start_date=macro.inicio, total_weeks=macro.semanas,
        weeks_per_micro=macro.semanas_por_micro, total_km=macro.km_totales,
        pool=macro.piscina.value, n_mac=macro.n_mac,
        main_event=macro.prueba_principal, notes=macro.notas, status=macro.estado.value,
    )
    # Asignadas, no extendidas: una colección que solo se ha leído en un objeto
    # nuevo no queda cargada, y tocarla después del `flush` —para repartir los
    # `id`— dispararía una consulta fuera del contexto async cuando viene vacía
    # (un macrociclo sin competencias).
    fila.coaches = [PlanCoach(coach_id=entrenador_id, team_id=equipo_id)]
    fila.phases = [
        PlanPhase(
            name=f.nombre, type=f.fase.value, color=f.color,
            week_start=f.semana_inicio, week_end=f.semana_fin, sort=f.orden,
        )
        for f in macro.fases
    ]
    fila.competitions = [
        Competition(name=c.nombre, week_number=c.semana, days=c.dias, is_main=c.es_principal)
        for c in macro.competencias
    ]
    return fila


def volcar_macrociclo(macro: Macrociclo, fila: Plan) -> None:
    """Escribe en la fila **solo lo que un macrociclo puede cambiar** tras crearse.

    Nombre, notas, estado, meta, piscina y número de macro. Las fechas, las
    semanas, los kilómetros, las fases y las competencias no se tocan aunque la
    entidad llegara con otros: ninguna ruta los edita, y un plan ya generado se
    calculó con ellos.
    """
    fila.name = macro.nombre
    fila.notes = macro.notas
    fila.status = macro.estado.value
    fila.main_event = macro.prueba_principal
    fila.pool = macro.piscina.value
    fila.n_mac = macro.n_mac
