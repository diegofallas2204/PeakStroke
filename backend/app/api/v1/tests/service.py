"""Lo que el test decide al escribirse, y cómo se pinta hacia fuera.

Las consultas están en `persistencia/repositorios/tests_aerobicos.py`. Lo que
queda aquí es lo que **no** es una consulta: construir la entidad —que es lo que
aplica la conversión reloj→nadado— y dar forma a la respuesta.

Un test aeróbico puede colgar de un macrociclo, y quién ve qué macrociclo lo
decide **su** repositorio, no este archivo. Duplicar aquí la regla sería tener
dos respuestas para la misma pregunta.
"""
from __future__ import annotations

from app.core.principal import Principal
from app.dominio.entidades import TestAerobico
from app.dominio.valores import ModoDeIngreso, TipoDeTest
from app.engine.aerobic import css_from_400_50
from app.persistencia.mapeo import test_desde_fila
from app.persistencia.repositorios import RepositorioDeMacrociclos, RepositorioDeTests
from app.persistencia.tablas.tests_aerobicos import AerobicSplit, AerobicTest

from .schemas import AerobicTestCreate, AerobicTestResponse


def to_response(test: AerobicTest) -> AerobicTestResponse:
    resp = AerobicTestResponse.model_validate(test)
    # Los parciales guardados son SIEMPRE tiempos nadados: la conversión desde
    # las llegadas de reloj la hizo el constructor una sola vez, al escribir. Por
    # eso el mapeo relee en modo `rep` — el modo de ingreso se guarda por
    # trazabilidad, no porque el cálculo dependa de él.
    analizado = test_desde_fila(test)
    if analizado is None:
        return resp

    resp.per100_splits = [r.segundos_por_100 for r in analizado.parciales_por_100()]
    if not analizado.se_nado_sobre_intervalo():
        return resp

    resp.rest_per_rep = [d.segundos for d in analizado.descansos()]
    resp.avg_rest = analizado.descanso_medio().segundos    # type: ignore[union-attr]
    resp.work_rest_ratio = analizado.ratio_descanso_trabajo()
    resp.density = analizado.densidad()
    resp.missed_intervals = analizado.intervalos_perdidos()
    return resp


async def create_test(
    tests: RepositorioDeTests, macrociclos: RepositorioDeMacrociclos,
    data: AerobicTestCreate, principal: Principal,
) -> AerobicTest | None:
    """Crea el test. **None si el nadador o el macrociclo no le corresponden.**

    Los dos destinatarios llegan en el cuerpo y no en la URL, así que aquí no
    hay consulta que acotar: hay que preguntarlo. Crear a nombre de alguien que
    para ti no existe no es un error de validación, es un recurso que no existe
    — y el router responde 404, igual que en todas las demás puertas.

    El `plan_id` importa tanto como el `swimmer_id`, y se olvidó hasta el
    2026-08-07: la FK compuesta solo impide cruzar EQUIPOS, no cruzar
    macrociclos dentro del equipo. Sin esta comprobación, una atleta que recibe
    404 en `GET /plans/2` podía colgar un test suyo de ese macrociclo y aparecer
    en la lista del entrenador que sí lo lleva.

    El equipo sigue saliendo de la sesión.
    """
    if not principal.owns_swimmer(data.swimmer_id):
        return None
    if data.plan_id is not None and await macrociclos.por_id(data.plan_id) is None:
        return None

    test = AerobicTest(
        team_id=principal.team_id, swimmer_id=data.swimmer_id, plan_id=data.plan_id,
        test_type=data.test_type, test_date=data.test_date, notes=data.notes,
        input_mode=data.input_mode,
    )
    if data.test_type == "DIRECT":
        if data.direct_per100 is None:
            raise ValueError("Ingreso directo requiere el parcial por 100m")
        test.avg_per100 = data.direct_per100
    elif data.test_type == "CSS":
        if data.t400 is None or data.t50 is None:
            raise ValueError("El test CSS requiere los tiempos de 400m y 50m")
        css = css_from_400_50(data.t400, data.t50)
        test.avg_per100 = css.t_pace_100
        test.css_ms = css.css_ms
    else:  # T30 | T15 | CUSTOM
        if not data.splits:
            raise ValueError("Se requieren los parciales del test")
        # Construir la entidad **es** aplicar la conversión reloj→nadado: no hay
        # forma de tener un `TestAerobico` cuyos parciales sigan siendo llegadas
        # del reloj. Hasta 2026-08-16 eso era una regla que este bloque tenía que
        # acordarse de aplicar, y olvidarla infló una base aeróbica un 114 %.
        analizado = TestAerobico(
            tipo=TipoDeTest.desde_texto(data.test_type),
            fecha=data.test_date,
            numeros=data.splits,
            distancia_rep=data.rep_distance,
            salida=data.send_off,
            modo=ModoDeIngreso.desde_texto(data.input_mode),
        )
        test.rep_count = analizado.repeticiones
        test.rep_distance = analizado.distancia_rep
        test.send_off = data.send_off
        test.avg_per100 = analizado.base_aerobica().segundos_por_100
        test.std_dev = analizado.consistencia()
        test.trend = analizado.tendencia().value
        # Se guarda el tiempo NADADO, venga como venga en la petición. Las
        # llegadas de reloj son una comodidad del formulario, no un formato de
        # almacenamiento: dejarlas crudas obligaría a cada lectura a saber en qué
        # modo se escribió, y basta que una se olvide para que la base aeróbica
        # de ese test salga con el doble de segundos.
        for parcial in analizado.parciales:
            test.splits.append(AerobicSplit(
                rep_number=parcial.numero,
                split_time=round(parcial.tiempo_nadado.segundos, 2),
                send_off_time=parcial.inicio.segundos if parcial.inicio is not None else None,
            ))
    await tests.guardar(test)
    return await tests.fila_de(test.id)
