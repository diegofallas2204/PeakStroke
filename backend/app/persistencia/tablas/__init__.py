"""Las tablas de SQLAlchemy, del lado de fuera del dominio.

Hasta el paso 5 vivían en `app/modules/<feature>/models.py`, y por eso
`persistencia/mapeo/` tenía que **mirar hacia arriba** para traducir una fila a
una entidad. Con las tablas aquí, la dirección de dependencias del §2 del
rediseño se cumple de hecho y no solo por convención:

    api  →  persistencia  →  dominio          dominio → nada

Se migran por agregado, no de golpe.
"""
from __future__ import annotations

from .atletas import Swimmer
from .codigos import LinkCode
from .equipos import (
    ROLE_ATHLETE,
    ROLE_COACH,
    ROLES,
    CoachAthlete,
    Role,
    Team,
    TeamMember,
)
from .planes import (
    AthleteEvent,
    AthletePlan,
    Competition,
    Plan,
    PlanCoach,
    PlanPhase,
    WeeklyPlan,
)
from .tests_aerobicos import AerobicSplit, AerobicTest
from .usuarios import User

__all__ = [
    "User",
    "LinkCode",
    "AerobicTest", "AerobicSplit",
    "Swimmer",
    "Team", "TeamMember", "CoachAthlete", "Role", "ROLE_COACH", "ROLE_ATHLETE", "ROLES",
    "Plan", "PlanCoach", "PlanPhase", "Competition",
    "AthletePlan", "AthleteEvent", "WeeklyPlan",
]
