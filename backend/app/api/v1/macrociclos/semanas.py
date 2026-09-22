"""Las semanas de una prueba: cómo se pintan y qué pasa al apuntar un tiempo.

Apuntar un tiempo real no cambia solo esa semana: reancla la curva restante al
último tiempo registrado (`_recalculate_event`). Por eso las tres funciones
viven juntas — leer `update_week` sin el recálculo debajo cuenta media historia.

**La curva ideal (`expected_time`) no se toca nunca.** Lo que se reescribe es
`recalc_time`, que es una segunda columna: sin esa separación no habría contra
qué comparar el progreso.

Los datos del macrociclo —piscina, curva, n_mac, fecha de inicio— salen de la
entidad, no de la fila: `event.athlete_plan.plan.pool` ata este archivo a la
forma de la tabla, y la piscina de la entidad es un `Piscina`, no una cadena que
haya que recordar cómo se escribe.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dates import age_at
from app.dominio.servicios.kilometraje import km_por_zona
from app.dominio.servicios.motor import MOTOR, SemanaGenerada
from app.dominio.valores import Fase
from app.persistencia.mapeo import macrociclo_desde_fila
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import AthleteEvent

from .schemas import WeekResponse, WeekUpdateRequest


async def event_weeks_response(db: AsyncSession, event: AthleteEvent) -> list[WeekResponse]:
    swimmer = await db.get(Swimmer, event.athlete_plan.swimmer_id)
    specialty = swimmer.specialty if swimmer else "medio_fondo"
    macro = macrociclo_desde_fila(event.athlete_plan.plan)
    comp_weeks = {c.semana for c in macro.competencias}
    result = []
    for w in sorted(event.weeks, key=lambda x: x.week_number):
        # La semana guarda la clave de la fase; lo que se enseña es cómo llamó el
        # entrenador al tramo que la cubre, que es lo que la tabla pintó siempre.
        tramo = macro.fase_de(w.week_number)
        phase = tramo.nombre if tramo is not None else Fase.desde_texto(w.phase).etiqueta
        effective = w.recalc_time if w.recalc_time is not None else w.expected_time
        pace = effective / (event.distance / 100)
        status = diff_s = diff_p = None
        if w.real_time is not None:
            status = MOTOR.estado_de_rendimiento(w.real_time, w.expected_time)
            diff_s = round(w.real_time - w.expected_time, 2)
            diff_p = round((w.real_time - w.expected_time) / w.expected_time * 100, 2)
        result.append(WeekResponse(
            id=w.id, week_number=w.week_number, week_date=w.week_date,
            date_label=w.week_date.strftime("%d/%m"),
            planned_km=w.planned_km, expected_time=w.expected_time,
            recalc_time=w.recalc_time, pace_100m=round(pace, 2),
            zones=MOTOR.zonas(pace, event.distance, event.stroke, macro.piscina.value),
            zone_km=km_por_zona(w.planned_km, distancia=event.distance, especialidad=specialty),
            real_time=w.real_time, status=status,
            diff_seconds=diff_s, diff_percent=diff_p,
            phase=phase, disabled=w.disabled, disable_reason=w.disable_reason,
            is_competition=w.week_number in comp_weeks,
        ))
    return result


async def update_week(
    db: AsyncSession, repo: RepositorioDeMacrociclos,
    week_id: int, data: WeekUpdateRequest,
) -> AthleteEvent | None:
    """None —y el router lo traduce a 404— si esa semana no le corresponde.

    `repo.semana()` es la única comprobación de acceso de todo el camino: a
    partir de ahí las recargas son `prueba_sin_acotar`, porque volver a filtrar
    lo que ya se autorizó solo añade sitios donde equivocarse.
    """
    week = await repo.semana(week_id)
    if week is None:
        return None
    if data.clear_real_time:
        week.real_time = None
    elif data.real_time is not None:
        week.real_time = data.real_time
    if data.disabled is not None:
        week.disabled = data.disabled
        week.disable_reason = data.disable_reason if data.disabled else None
    await repo.confirmar()

    event = await repo.prueba_sin_acotar(week.athlete_event_id)
    if event is None:
        return None
    await _recalculate_event(db, repo, event)
    # Segunda recarga: `_recalculate_event` reescribe `recalc_time` de todas las
    # semanas, y la respuesta tiene que salir con esos valores ya puestos.
    return await repo.prueba_sin_acotar(event.id)


async def _recalculate_event(
    db: AsyncSession, repo: RepositorioDeMacrociclos, event: AthleteEvent,
) -> None:
    """Recalcula la curva restante anclada al último tiempo real registrado.

    Las semanas con parón no progresan; la mejora restante se redistribuye
    entre las semanas activas. La curva ideal original no se modifica.
    """
    weeks = sorted(event.weeks, key=lambda w: w.week_number)
    real_weeks = [w for w in weeks if w.real_time is not None]
    disabled = {w.week_number for w in weeks if w.disabled}

    if not real_weeks and not disabled:
        for w in weeks:
            w.recalc_time = None
        await repo.confirmar()
        return

    if real_weeks:
        anchor = max(real_weeks, key=lambda w: w.week_number)
        anchor_week, anchor_time = anchor.week_number, anchor.real_time
    else:
        anchor_week, anchor_time = 0, event.current_time

    macro = macrociclo_desde_fila(event.athlete_plan.plan)
    swimmer = await db.get(Swimmer, event.athlete_plan.swimmer_id)
    age = age_at(swimmer.birth_date, macro.inicio) if swimmer else None
    # El recálculo solo mueve tiempos: la fase entra porque la semana la lleva,
    # y el nombre del tramo no lo lee nadie en este camino.
    entradas = [
        SemanaGenerada(
            numero=w.week_number, fecha=w.week_date,
            tiempo_esperado=w.expected_time, ritmo_100=0.0, km=w.planned_km,
            fase=Fase.desde_texto(w.phase), nombre_fase="",
            mejora_vs_anterior=0.0, mejora_acumulada=0.0,
        )
        for w in weeks
    ]
    MOTOR.recalcular_desde(
        entradas, desde_semana=anchor_week + 1, tiempo_ancla=float(anchor_time),
        tiempo_meta=event.goal_time, curva=macro.curva,
        distancia=event.distance, deshabilitadas=disabled, estilo=event.stroke,
        piscina=macro.piscina.value, n_mac=macro.n_mac, edad=age,
        # Misma clasificación que al generar el plan: si el recálculo derivara
        # el nivel del ritmo mientras el alta lo tomó del test, el mismo atleta
        # tendría dos niveles según por qué puerta se entre.
        base_aerobica=event.athlete_plan.aerobic_base,
    )
    recalc_map = {e.numero: e.tiempo_esperado for e in entradas
                  if e.numero > anchor_week}
    for w in weeks:
        w.recalc_time = recalc_map.get(w.week_number)
    await repo.confirmar()
