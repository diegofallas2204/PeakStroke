"""Lógica de negocio de tests aeróbicos."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.engine.aerobic import analyze_splits, css_from_400_50

from .models import AerobicSplit, AerobicTest
from .schemas import AerobicTestCreate, AerobicTestResponse


def to_response(test: AerobicTest) -> AerobicTestResponse:
    resp = AerobicTestResponse.model_validate(test)
    if test.splits and test.rep_distance:
        factor = test.rep_distance / 100.0
        resp.per100_splits = [round(s.split_time / factor, 2) for s in test.splits]
    return resp


async def list_tests(
    db: AsyncSession, team_id: int,
    swimmer_id: int | None = None, plan_id: int | None = None,
) -> list[AerobicTest]:
    stmt = select(AerobicTest).options(selectinload(AerobicTest.splits)) \
        .where(AerobicTest.team_id == team_id) \
        .order_by(AerobicTest.test_date.desc(), AerobicTest.id.desc())
    if swimmer_id is not None:
        stmt = stmt.where(AerobicTest.swimmer_id == swimmer_id)
    if plan_id is not None:
        stmt = stmt.where(AerobicTest.plan_id == plan_id)
    return list((await db.execute(stmt)).scalars())


async def get_test(db: AsyncSession, test_id: int, team_id: int) -> AerobicTest | None:
    """None si el test es de otro equipo; el router lo traduce a 404."""
    stmt = select(AerobicTest).options(selectinload(AerobicTest.splits)) \
        .where(AerobicTest.id == test_id, AerobicTest.team_id == team_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_test(db: AsyncSession, data: AerobicTestCreate, team_id: int) -> AerobicTest:
    """El equipo sale de la sesión. Las FKs compuestas del esquema rechazan el
    test si el nadador o el macrociclo indicados son de otro club."""
    test = AerobicTest(
        team_id=team_id, swimmer_id=data.swimmer_id, plan_id=data.plan_id,
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
    return (await get_test(db, test.id, team_id))  # type: ignore[return-value]


async def previous_test(db: AsyncSession, test: AerobicTest) -> AerobicTest | None:
    """Test anterior del mismo atleta para el gráfico comparativo."""
    stmt = (
        select(AerobicTest).options(selectinload(AerobicTest.splits))
        .where(
            AerobicTest.swimmer_id == test.swimmer_id,
            AerobicTest.id != test.id,
            AerobicTest.test_date <= test.test_date,
        )
        .order_by(AerobicTest.test_date.desc(), AerobicTest.id.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def delete_test(db: AsyncSession, test: AerobicTest) -> None:
    await db.delete(test)
    await db.commit()
