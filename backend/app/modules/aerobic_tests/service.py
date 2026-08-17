"""Lógica de negocio de tests aeróbicos.

Las lecturas reciben el `Principal` entero, no un `team_id`: hay dos fronteras
que respetar y solo una cabe en un entero. Ver `core/dependencies.Principal`.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import Principal
from app.dominio.entidades import TestAerobico
from app.dominio.valores import ModoDeIngreso, TipoDeTest
from app.engine.aerobic import css_from_400_50

# Lectura explícita de la puerta de acceso de otro módulo (permitido por las
# reglas del proyecto): un test aeróbico puede colgar de un macrociclo, y quién
# ve qué macrociclo lo decide `plans`, no este módulo. Duplicar aquí la regla
# sería tener dos respuestas para la misma pregunta.
from app.modules.plans.access import get_plan
from app.persistencia.mapeo import test_desde_fila

from .models import AerobicSplit, AerobicTest
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


def _visible(principal: Principal, *, include_inactive: bool = False):
    """Base común de toda lectura: equipo, acotado al atleta, y de alta.

    Que las tres condiciones vivan juntas es el punto. Repartidas por cada
    consulta, tarde o temprano una se queda sin alguna — que es exactamente lo
    que pasó con el filtro por nadador.

    `include_inactive` es lo que hace que dar de baja no equivalga a borrar.
    Sin él, `set_active(..., True)` sería código muerto: un test retirado no se
    podría ni consultar para reactivarlo, y desde la aplicación el efecto sería
    idéntico al borrado que esta columna vino a evitar.
    """
    stmt = (
        select(AerobicTest).options(selectinload(AerobicTest.splits))
        .where(AerobicTest.team_id == principal.team_id)
    )
    if not include_inactive:
        stmt = stmt.where(AerobicTest.is_active.is_(True))
    return principal.scope_to_own_swimmer(stmt, AerobicTest.swimmer_id)


async def list_tests(
    db: AsyncSession, principal: Principal,
    swimmer_id: int | None = None, plan_id: int | None = None,
    *, include_inactive: bool = False,
) -> list[AerobicTest]:
    """`swimmer_id` filtra dentro de lo visible; nunca lo amplía.

    El parámetro llega del cliente, así que sin acotar antes por sesión bastaba
    con escribir el número de un compañero en la barra de direcciones.
    """
    stmt = _visible(principal, include_inactive=include_inactive).order_by(
        AerobicTest.test_date.desc(), AerobicTest.id.desc(),
    )
    if swimmer_id is not None:
        stmt = stmt.where(AerobicTest.swimmer_id == swimmer_id)
    if plan_id is not None:
        stmt = stmt.where(AerobicTest.plan_id == plan_id)
    return list((await db.execute(stmt)).scalars())


async def get_test(
    db: AsyncSession, test_id: int, principal: Principal,
) -> AerobicTest | None:
    """None si el test es de otro equipo o de otro atleta. El router lo traduce
    a 404 en ambos casos: distinguirlos confirmaría que ese id existe.

    **Sí devuelve los dados de baja**, igual que `swimmers.get_swimmer`. Es lo
    que permite que la ficha muestre "este test está retirado, ¿lo reactivas?"
    en vez de un 404 que no ofrece salida.
    """
    stmt = _visible(principal, include_inactive=True).where(AerobicTest.id == test_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_test(
    db: AsyncSession, data: AerobicTestCreate, principal: Principal,
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
    if data.plan_id is not None and await get_plan(db, data.plan_id, principal) is None:
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
    db.add(test)
    await db.commit()
    return await get_test(db, test.id, principal)


async def previous_test(
    db: AsyncSession, test: AerobicTest, principal: Principal,
) -> AerobicTest | None:
    """Test anterior del mismo atleta para el gráfico comparativo."""
    stmt = (
        _visible(principal)
        .where(
            AerobicTest.swimmer_id == test.swimmer_id,
            AerobicTest.id != test.id,
            AerobicTest.test_date <= test.test_date,
        )
        .order_by(AerobicTest.test_date.desc(), AerobicTest.id.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def set_active(db: AsyncSession, test: AerobicTest, active: bool) -> AerobicTest:
    """Da de baja (o reactiva) el test. **No lo borra.**

    Sustituye al `db.delete()` que había hasta el 2026-08-06, que iba contra la
    regla del CLAUDE.md ("nada se borra: se da de baja") que `swimmers.set_active`
    sí respetaba. Un test aeróbico es una medición del atleta en una fecha: se
    puede retirar de las listas, pero rehacerla es imposible.
    """
    test.is_active = active
    await db.commit()
    return test
