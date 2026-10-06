"""Entidades: identidad + ciclo de vida. Paso 2 del rediseño (`docs/REDISENO.md` §5).

Se distinguen de `valores/` en que **tienen identidad**: dos `Tiempo(78.0)` son
el mismo tiempo, dos atletas homónimos son dos personas. De ahí que sean mutables
y que se comparen por `id` (ver `base.PorIdentidad`).

No son modelos de SQLAlchemy y no saben que existe una base de datos: la
traducción fila ↔ entidad vive en `app/persistencia/mapeo/`, del lado de fuera.
Lo que estas clases recuperan es el comportamiento que hoy vive en funciones
sueltas que reciben `(db, entidad, …)` — el modelo anémico, P4 de §0:

    plans/service.current_week_of  → Macrociclo.semana_actual()
    plans/service.effective_status → Macrociclo.estado_efectivo()
    core/dates.age_at              → Atleta.edad_en()
    engine/aerobic.analyze_splits  → TestAerobico.base_aerobica() y compañía

Los llamadores no se rompen de golpe: esas funciones se quedan como envoltorio
delegando aquí y se vacían después.
"""
from __future__ import annotations

from .atleta import Atleta, anios_cumplidos
from .base import PorIdentidad
from .inscripcion import Inscripcion, InscripcionImposible
from .macrociclo import Competencia, FaseDelMacro, Macrociclo, lunes_de
from .resultado import (
    DIAS_DE_UNA_SEMANA,
    Contexto,
    Resultado,
    de_la_semana,
    promedio,
    real_de_la_semana,
)
from .sesion import RPE_MAXIMO, RPE_MINIMO, Sesion
from .test_aerobico import PENDIENTE_DE_TENDENCIA, Parcial, TestAerobico

__all__ = [
    "PorIdentidad",
    # atleta
    "Atleta", "anios_cumplidos",
    # inscripción
    "Inscripcion", "InscripcionImposible",
    # macrociclo
    "Macrociclo", "FaseDelMacro", "Competencia", "lunes_de",
    # resultado
    "Resultado", "Contexto", "DIAS_DE_UNA_SEMANA",
    "de_la_semana", "promedio", "real_de_la_semana",
    # sesión
    "Sesion", "RPE_MINIMO", "RPE_MAXIMO",
    # test aeróbico
    "TestAerobico", "Parcial", "PENDIENTE_DE_TENDENCIA",
]
