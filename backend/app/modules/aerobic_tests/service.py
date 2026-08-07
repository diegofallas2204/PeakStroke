"""Lógica de negocio de tests aeróbicos.

Las lecturas reciben el `Principal` entero, no un `team_id`: hay dos fronteras
que respetar y solo una cabe en un entero. Ver `core/dependencies.Principal`.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import Principal
from app.engine.aerobic import analyze_splits, css_from_400_50

from .models import AerobicSplit, AerobicTest
from .schemas import AerobicTestCreate, AerobicTestResponse


def to_response(test: AerobicTest) -> AerobicTestResponse:
    resp = AerobicTestResponse.model_validate(test)
    if test.splits and test.rep_distance:
        factor = test.rep_distance / 100.0
        resp.per100_splits = [round(s.split_time / factor, 2) for s in test.splits]
    return resp


def _visible(principal: Principal):
    """Base común de toda lectura: equipo, no dado de baja, y acotado al atleta.

    Que las tres condiciones vivan juntas es el punto. Repartidas por cada
    consulta, tarde o temprano una se queda sin alguna — que es exactamente lo
    que pasó con el filtro por nadador.
    """
    stmt = (
        select(AerobicTest).options(selectinload(AerobicTest.splits))
        .where(
            AerobicTest.team_id == principal.team_id,
            AerobicTest.is_active.is_(True),
        )
    )
    return principal.scope_to_own_swimmer(stmt, AerobicTest.swimmer_id)


async def list_tests(
    db: AsyncSession, principal: Principal,
    swimmer_id: int | None = None, plan_id: int | None = None,
) -> list[AerobicTest]:
    """`swimmer_id` filtra dentro de lo visible; nunca lo amplía.

    El parámetro llega del cliente, así que sin acotar antes por sesión bastaba
    con escribir el número de un compañero en la barra de direcciones.
    """
    stmt = _visible(principal).order_by(
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
    """None si el test es de otro equipo, de otro atleta o está de baja.

    El router lo traduce a 404 en los tres casos: distinguirlos confirmaría que
    ese id existe.
    """
    stmt = _visible(principal).where(AerobicTest.id == test_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_test(
    db: AsyncSession, data: AerobicTestCreate, principal: Principal,
) -> AerobicTest | None:
    """Crea el test. **None si `swimmer_id` no le corresponde a quien lo pide.**

    El destinatario llega en el cuerpo, no en la URL, así que aquí no hay
    consulta que acotar: hay que preguntarlo. Un atleta creando un test a nombre
    de otro no es un error de validación, es un recurso que para él no existe —
    y el router responde 404, igual que en todas las demás puertas.

    El equipo sigue saliendo de la sesión. Las FKs compuestas del esquema
    rechazan el test si el nadador o el macrociclo indicados son de otro club.
    """
    if not principal.owns_swimmer(data.swimmer_id):
        return None

    test = AerobicTest(
        team_id=principal.team_id, swimmer_id=data.swimmer_id, plan_id=data.plan_id,
        test_type=data.test_type, test_date=data.test_date, notes=data.notes,
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
        rep_distance = 100 if data.test_type in ("T30", "T15") else data.rep_distance
        analysis = analyze_splits(data.splits, rep_distance)
        test.rep_count = len(data.splits)
        test.rep_distance = rep_distance
        test.avg_per100 = analysis.avg_per100
        test.std_dev = analysis.std_dev
        test.trend = analysis.trend
        for i, split in enumerate(data.splits):
            test.splits.append(AerobicSplit(rep_number=i + 1, split_time=split))
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
