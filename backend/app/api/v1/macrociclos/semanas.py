"""Las semanas de una prueba: cómo se pintan y qué pasa al apuntar un tiempo.

Apuntar un tiempo real no cambia solo esa semana: reancla la curva restante al
último tiempo registrado (`_recalcular`). Por eso las tres funciones viven
juntas — leer `update_week` sin el recálculo debajo cuenta media historia.

**La curva ideal (`esperado`) no se toca nunca.** Lo que se reescribe es el
tiempo recalculado, que es otro campo: sin esa separación no habría contra qué
comparar el progreso. Desde C9 (2026-10-13) ya no es una regla que este archivo
tenga que respetar: `Semana` no deja reasignar su `esperado`, y el repositorio
no lo escribe.

**El tiempo real de una semana no es una columna suya** (C6, R2 enmendada). Es
el promedio de los `Resultado` del atleta en esa prueba y esos siete días,
convertidos a la piscina del macro (`Semana.real`). Por eso un tiempo que no cae
en ninguna semana del plan no reancla nada: nunca llega aquí.

**Este archivo ya no importa ninguna tabla** (C9 punto 4). Recibe un
`PlanDePrueba` —el macrociclo, la inscripción, la ficha, la prueba y sus
semanas, todo entidades—, les pide a las semanas que cambien y se las devuelve
al repositorio. Lo que sigue aquí y no en una entidad es la orquestación del
recálculo, porque llama al motor y las entidades no importan los servicios.
"""
from __future__ import annotations

from app.dominio.entidades import Semana
from app.dominio.servicios.kilometraje import km_por_zona
from app.dominio.servicios.motor import MOTOR, SemanaGenerada
from app.dominio.valores import Mejora, Tiempo
from app.persistencia.repositorios import (
    PlanDePrueba,
    RepositorioDeResultados,
    RepositorioDeSemanas,
)

from .schemas import WeekResponse, WeekUpdateRequest


def _sobre_el_plan(desviacion: Mejora) -> tuple[float, float]:
    """(segundos, %) de más sobre el plan: el signo que enseña la tabla.

    `Semana.desviacion` es positiva cuando se nadó más rápido; la tabla enseña
    lo contrario (+ es más lento). `0.0 - x` y no `-x`: clavar el tiempo
    esperado daría un `-0.0` en el JSON.
    """
    return round(0.0 - desviacion.segundos, 2), round(0.0 - desviacion.porcentaje, 2)


async def _reales(resultados: RepositorioDeResultados, plan: PlanDePrueba) -> dict[int, Tiempo]:
    return await resultados.reales_de(
        plan.inscripcion.atleta_id, plan.prueba.prueba, plan.semanas, plan.macro.piscina,
    )


async def event_weeks_response(
    resultados: RepositorioDeResultados, plan: PlanDePrueba,
) -> list[WeekResponse]:
    macro, prueba = plan.macro, plan.prueba.prueba
    especialidad = plan.atleta.especialidad.value
    reales = await _reales(resultados, plan)
    comp_weeks = {c.semana for c in macro.competencias}
    result = []
    for s in plan.semanas:
        # La semana guarda la clave de la fase; lo que se enseña es cómo llamó el
        # entrenador al tramo que la cubre, que es lo que la tabla pintó siempre.
        tramo = macro.fase_de(s.numero)
        phase = tramo.nombre if tramo is not None else s.fase.etiqueta
        pace = s.ritmo(prueba.distancia).segundos_por_100
        real = reales.get(s.id)
        status = diff_s = diff_p = None
        if real is not None:
            status = MOTOR.estado_de_rendimiento(real.segundos, s.esperado.segundos)
            diff_s, diff_p = _sobre_el_plan(s.desviacion(real))
        result.append(WeekResponse(
            id=s.id, week_number=s.numero, week_date=s.fecha,
            date_label=s.fecha.strftime("%d/%m"),
            planned_km=s.km_planificados, expected_time=s.esperado.segundos,
            recalc_time=s.recalculado.segundos if s.recalculado else None,
            pace_100m=round(pace, 2),
            zones=MOTOR.zonas(pace, prueba.distancia, prueba.estilo.value, macro.piscina.value),
            zone_km=km_por_zona(
                s.km_planificados, distancia=prueba.distancia, especialidad=especialidad,
            ),
            real_time=real.segundos if real is not None else None, status=status,
            diff_seconds=diff_s, diff_percent=diff_p,
            phase=phase, disabled=s.deshabilitada, disable_reason=s.razon,
            is_competition=s.numero in comp_weeks,
        ))
    return result


async def update_week(
    semanas: RepositorioDeSemanas, resultados: RepositorioDeResultados,
    week_id: int, data: WeekUpdateRequest,
) -> PlanDePrueba | None:
    """None —y el router lo traduce a 404— si esa semana no le corresponde.

    `semanas.plan_de_la_semana()` es la única comprobación de acceso de todo el
    camino. Devuelve el plan con las semanas ya cambiadas: quien pinta la
    respuesta no tiene que releer nada.
    """
    plan = await semanas.plan_de_la_semana(week_id)
    if plan is None:
        return None
    semana = plan.semana(week_id)
    assert semana is not None   # el plan se leyó a partir de ella
    if data.clear_real_time or data.real_time is not None:
        await resultados.apuntar_en_semana(
            semana, atleta_id=plan.inscripcion.atleta_id, prueba=plan.prueba.prueba,
            piscina=plan.macro.piscina,
            tiempo=None if data.clear_real_time else Tiempo(data.real_time),
        )
    if data.disabled is True:
        semana.parar(data.disable_reason)
    elif data.disabled is False:
        semana.reanudar()
    # Confirma también el resultado apuntado: comparten la sesión de la petición.
    await semanas.guardar([semana])

    await _recalcular(semanas, plan, await _reales(resultados, plan))
    return plan


async def _recalcular(
    semanas: RepositorioDeSemanas, plan: PlanDePrueba, reales: dict[int, Tiempo],
) -> None:
    """Recalcula la curva restante anclada al último tiempo real registrado.

    Las semanas con parón no progresan; la mejora restante se redistribuye
    entre las semanas activas. La curva ideal original no se modifica.

    `reales` son los promedios por semana: el ancla es el de la última semana
    que tenga alguno. Un resultado que no cae en ninguna semana no está en el
    diccionario, así que no puede mover la curva.
    """
    con_real = [s for s in plan.semanas if s.id in reales]
    paradas = {s.numero for s in plan.semanas if s.deshabilitada}

    if not con_real and not paradas:
        for s in plan.semanas:
            s.reanclar(None)
        await semanas.guardar(plan.semanas)
        return

    if con_real:
        ancla: Semana = max(con_real, key=lambda s: s.numero)
        semana_ancla, tiempo_ancla = ancla.numero, reales[ancla.id].segundos
    else:
        semana_ancla, tiempo_ancla = 0, plan.prueba.actual.segundos

    macro, prueba, base = plan.macro, plan.prueba, plan.inscripcion.base_aerobica
    # El recálculo solo mueve tiempos: la fase entra porque la semana la lleva,
    # y el nombre del tramo no lo lee nadie en este camino.
    entradas = [
        SemanaGenerada(
            numero=s.numero, fecha=s.fecha,
            tiempo_esperado=s.esperado.segundos, ritmo_100=0.0, km=s.km_planificados,
            fase=s.fase, nombre_fase="",
            mejora_vs_anterior=0.0, mejora_acumulada=0.0,
        )
        for s in plan.semanas
    ]
    MOTOR.recalcular_desde(
        entradas, desde_semana=semana_ancla + 1, tiempo_ancla=float(tiempo_ancla),
        tiempo_meta=prueba.meta.segundos, curva=macro.curva,
        distancia=prueba.prueba.distancia, deshabilitadas=paradas,
        estilo=prueba.prueba.estilo.value, piscina=macro.piscina.value,
        # La edad al inicio del macro, como al generar el plan.
        n_mac=macro.n_mac, edad=plan.atleta.edad_en(macro.inicio),
        # Misma clasificación que al generar el plan: si el recálculo derivara
        # el nivel del ritmo mientras el alta lo tomó del test, el mismo atleta
        # tendría dos niveles según por qué puerta se entre.
        base_aerobica=base.segundos_por_100 if base is not None else None,
    )
    recalculados = {e.numero: e.tiempo_esperado for e in entradas if e.numero > semana_ancla}
    for s in plan.semanas:
        tiempo = recalculados.get(s.numero)
        s.reanclar(Tiempo(tiempo) if tiempo is not None else None)
    await semanas.guardar(plan.semanas)
