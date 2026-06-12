"""Genera datos de demostración realistas para PeakStroke.

Uso:  python seed.py        (borra la base local y la repuebla)

Crea: 8 atletas, un macrociclo activo de 12 semanas cursando la semana 7,
tests aeróbicos y tiempos reales de las semanas 1-6 con ruido plausible.
"""
from __future__ import annotations

import asyncio
import random
from datetime import date, timedelta
from pathlib import Path

from app.core.database import AsyncSessionLocal, engine, Base
from app.modules.aerobic_tests.schemas import AerobicTestCreate
from app.modules.aerobic_tests.service import create_test
from app.modules.plans.schemas import (
    AddAthleteRequest, CompetitionInput, EventInput, PlanCreate,
)
from app.modules.plans.service import add_athlete, create_plan, update_week
from app.modules.plans.schemas import WeekUpdateRequest
from app.modules.plans.models import WeeklyPlan, AthleteEvent, AthletePlan
from app.modules.swimmers.schemas import SwimmerCreate
from app.modules.swimmers.service import create_swimmer
from sqlalchemy import select

random.seed(7)

SWIMMERS = [
    ("Sofía Ramírez", date(2008, 3, 14), "F", "velocidad", "mariposa", 58, 168),
    ("Carlos Mendoza", date(2007, 7, 2), "M", "medio_fondo", "libre", 72, 181),
    ("Valentina Castro", date(2009, 1, 25), "F", "fondo", "espalda", 55, 165),
    ("Andrés López", date(2008, 11, 8), "M", "velocidad", "pecho", 70, 176),
    ("Mariana Vega", date(2007, 5, 19), "F", "medio_fondo", "mariposa", 60, 170),
    ("Diego Fernández", date(2006, 9, 30), "M", "velocidad", "libre", 75, 184),
    ("Lucía Herrera", date(2009, 6, 11), "F", "aguas_abiertas", "libre", 57, 166),
    ("Gabriel Soto", date(2007, 12, 3), "M", "fondo", "libre", 68, 178),
]

# (índice de atleta, [(prioridad, dist, estilo, actual, meta)], base aeróbica s/100m)
EVENTS = [
    (0, [(1, 100, "mariposa", 67.80, 64.50), (2, 50, "mariposa", 30.10, 29.30)], 78.5),
    (1, [(1, 200, "libre", 128.90, 124.00), (2, 100, "libre", 58.40, 56.80)], 72.0),
    (2, [(1, 400, "espalda", 312.00, 302.00)], 80.2),
    (3, [(1, 100, "pecho", 68.20, 66.00)], 84.0),
    (4, [(1, 200, "mariposa", 138.50, 133.50)], 81.3),
    (5, [(1, 100, "libre", 52.80, 51.40), (2, 50, "libre", 24.40, 23.90)], 69.8),
    (6, [(1, 1500, "libre", 1098.00, 1063.00)], 75.6),
    (7, [(1, 800, "libre", 570.00, 552.00)], 74.1),
]


def plan_start_date(today: date) -> date:
    """Lunes de hace 6 semanas: el plan cursa la semana 7."""
    monday = today - timedelta(days=today.weekday())
    return monday - timedelta(weeks=6)


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        swimmers = []
        for name, birth, gender, specialty, stroke, weight, height in SWIMMERS:
            swimmers.append(await create_swimmer(db, SwimmerCreate(
                name=name, birth_date=birth, gender=gender, specialty=specialty,
                main_stroke=stroke, weight_kg=weight, height_cm=height,
            )))

        start = plan_start_date(date.today())
        plan = await create_plan(db, PlanCreate(
            name="Temporada Nacional 2026", start_date=start, total_weeks=12,
            weeks_per_micro=4, total_km=320, progression_curve="sigmoid",
            main_event="Nacional Juvenil", notes=(
                "Preparación para el Nacional Juvenil. Foco en pruebas principales "
                "de cada atleta y mejora técnica de virajes."
            ),
            competitions=[
                CompetitionInput(name="Copa Invitacional", week_number=5, days=2),
                CompetitionInput(name="Nacional Juvenil", week_number=12, days=3, is_main=True),
            ],
        ))

        for idx, events, aerobic_base in EVENTS:
            await add_athlete(db, plan, AddAthleteRequest(
                swimmer_id=swimmers[idx].id, aerobic_base=aerobic_base,
                aerobic_base_source="t30",
                events=[EventInput(
                    priority=p, distance=d, stroke=s, current_time=c, goal_time=g,
                ) for p, d, s, c, g in events],
            ))

        # Tiempos reales semanas 1-6 con sesgo por atleta (adelantado/atrasado)
        bias = {0: 1.001, 1: 0.998, 2: 1.0, 3: 1.006, 4: 0.997, 5: 0.996, 6: 1.0, 7: 1.002}
        stmt = select(AthleteEvent).join(AthletePlan).where(AthletePlan.plan_id == plan.id)
        all_events = list((await db.execute(stmt)).scalars())
        for event in all_events:
            ap = await db.get(AthletePlan, event.athlete_plan_id)
            swimmer_idx = next(i for i, s in enumerate(swimmers) if s.id == ap.swimmer_id)
            week_rows = list((await db.execute(
                select(WeeklyPlan).where(
                    WeeklyPlan.athlete_event_id == event.id,
                    WeeklyPlan.week_number <= 6,
                ).order_by(WeeklyPlan.week_number)
            )).scalars())
            for w in week_rows:
                if event.priority > 1 and w.week_number % 2 == 0:
                    continue  # pruebas secundarias: registro quincenal
                noise = random.uniform(-0.0015, 0.0015)
                real = w.expected_time * (bias[swimmer_idx] + noise)
                await update_week(db, w.id, WeekUpdateRequest(real_time=round(real, 2)))

        # Tests aeróbicos: T-30 inicial + control reciente para varios atletas
        for idx, _, aerobic_base in EVENTS[:5]:
            base = aerobic_base
            splits_initial = [round(base * random.uniform(0.99, 1.025), 2) for _ in range(30)]
            await create_test(db, AerobicTestCreate(
                swimmer_id=swimmers[idx].id, plan_id=plan.id, test_type="T30",
                test_date=start + timedelta(days=2), splits=splits_initial,
                notes="Test de inicio de macrociclo",
            ))
            improved = base * 0.985
            splits_control = [round(improved * random.uniform(0.99, 1.02), 2) for _ in range(15)]
            await create_test(db, AerobicTestCreate(
                swimmer_id=swimmers[idx].id, plan_id=plan.id, test_type="T15",
                test_date=start + timedelta(weeks=5, days=2), splits=splits_control,
                notes="Control de mitad de ciclo",
            ))

        # Test personalizado 12×400 para la fondista de aguas abiertas
        base400 = 75.6 * 4
        await create_test(db, AerobicTestCreate(
            swimmer_id=swimmers[6].id, plan_id=plan.id, test_type="CUSTOM",
            test_date=start + timedelta(weeks=4, days=3),
            splits=[round(base400 * random.uniform(0.995, 1.015), 1) for _ in range(12)],
            rep_distance=400, notes="12×400 — protocolo del club",
        ))
        # CSS para el velocista
        await create_test(db, AerobicTestCreate(
            swimmer_id=swimmers[5].id, plan_id=plan.id, test_type="CSS",
            test_date=start + timedelta(weeks=3), t400=292.0, t50=27.9,
            notes="CSS 400/50 según Wakayoshi",
        ))

    print("Base de datos sembrada:")
    print(f"  - {len(SWIMMERS)} atletas")
    print(f"  - Macrociclo 'Temporada Nacional 2026' (12 semanas, semana actual: 7)")
    print(f"  - Tiempos reales semanas 1-6 + 12 tests aeróbicos")


if __name__ == "__main__":
    db_file = Path(__file__).parent / "peakstroke.db"
    asyncio.run(seed())
    print(f"  - DB: {db_file}")
