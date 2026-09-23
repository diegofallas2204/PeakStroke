"""Catálogo de casos del snapshot del motor — solo datos, sin ejecución.

Vive aparte de `test_motor_snapshot.py` porque son dos cosas distintas: aquí se
decide QUÉ se congela (los ejes del dominio y los valores de entrada), allí CÓMO
se congela y se compara. Al leer un diff del snapshot, este archivo es el que
dice qué significa el caso que falló.

Las entradas son literales CONGELADOS, nunca derivados del motor: si mañana
cambian los factores de zona o el techo I_max, lo que se mueve es la salida
—visible en el diff— y no la entrada, que se movería en silencio.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

# Lunes, para que `monday_of` no desplace la primera semana.
START_DATE = date(2026, 1, 5)

# El tiempo actual determina el nivel (umbral = ritmo de carrera × factor MVO2).
# `test_los_casos_cubren_los_cinco_niveles` comprueba que cada literal sigue
# clasificando en el nivel bajo el que está escrito.
CURRENT_TIME: dict[str, dict[int, float]] = {
    "beginner":     {50: 66.15, 100: 145.55, 200: 316.87, 400: 666.67, 800: 1392.02, 1500: 2678.57},
    "recreational": {50: 52.53, 100: 115.58, 200: 251.63, 400: 529.41, 800: 1105.42, 1500: 2127.10},
    "advanced":     {50: 41.63, 100: 91.61, 200: 199.44, 400: 419.61, 800: 876.15, 1500: 1685.92},
    "competitive":  {50: 31.91, 100: 70.21, 200: 152.84, 400: 321.57, 800: 671.44, 1500: 1292.02},
    "elite":        {50: 24.12, 100: 53.08, 200: 115.56, 400: 243.14, 800: 507.68, 1500: 976.89},
}
LEVELS = tuple(CURRENT_TIME)
DISTANCES = (50, 100, 200, 400, 800, 1500)

# Mejora pedida como fracción del tiempo actual. La "factible" queda por debajo
# del techo I_max del nivel para cualquier distancia y duración de la batería; la
# "agresiva" lo supera en todas, así que dispara la extensión. (Con edad de menor
# o n_mac≠1 el techo se mueve: ahí la etiqueta describe la ENTRADA, no el
# veredicto — que es justo lo que el snapshot congela.)
GOAL_PCT: dict[str, dict[str, float]] = {
    "factible": {"beginner": 0.04, "recreational": 0.03, "advanced": 0.02,
                 "competitive": 0.01, "elite": 0.004},
    "agresiva": {"beginner": 0.15, "recreational": 0.12, "advanced": 0.09,
                 "competitive": 0.06, "elite": 0.03},
    # Meta = tiempo actual: no es un caso raro, es una rama propia de los dos
    # motores (`requested <= 0` en el científico, `improvement = 0` en el
    # adaptador) que produce un macro plano de 15 semanas.
    "sin_mejora": dict.fromkeys(LEVELS, 0.0),
}

WEEKLY_KM: dict[str, float] = {
    "beginner": 15.0, "recreational": 25.0, "advanced": 38.0,
    "competitive": 50.0, "elite": 70.0,
}


@dataclass(frozen=True)
class Case:
    """Un plan: entradas de `generate_plan` en los dos motores."""

    distance: int
    level: str
    stroke: str = "libre"
    pool: str = "50"
    n_mac: int = 1
    age: int | None = None
    goal: str = "factible"
    curve: str = "science"
    total_weeks: int = 15

    @property
    def id(self) -> str:
        edad = f"e{self.age}" if self.age is not None else "adulto"
        return (f"{self.distance}-{self.level}-{self.stroke}-p{self.pool}"
                f"-m{self.n_mac}-{edad}-{self.goal}-{self.curve}-w{self.total_weeks}")

    @property
    def current_time(self) -> float:
        return CURRENT_TIME[self.level][self.distance]

    @property
    def goal_time(self) -> float:
        return round(self.current_time * (1 - GOAL_PCT[self.goal][self.level]), 2)

    @property
    def total_km(self) -> float:
        return round(WEEKLY_KM[self.level] * self.total_weeks, 1)

    def entrada(self) -> dict[str, Any]:
        return {
            "distancia": self.distance, "nivel_esperado": self.level, "estilo": self.stroke,
            "piscina": self.pool, "n_mac": self.n_mac, "edad": self.age,
            "meta": self.goal, "curva": self.curve, "semanas": self.total_weeks,
            "tiempo_actual": self.current_time, "tiempo_meta": self.goal_time,
            "km_totales": self.total_km,
        }


@dataclass(frozen=True)
class RecalcCase:
    """Un plan ya generado + el recálculo que se le aplica desde un tiempo real.

    `anchor_pct` es la mejora REAL acumulada al llegar a `from_week`, como
    fracción del tiempo inicial: positiva = va por delante del plan, negativa =
    el atleta empeoró (que también hay que saber recalcular).
    """

    base: Case
    from_week: int
    anchor_pct: float
    disabled: tuple[int, ...] = ()

    @property
    def id(self) -> str:
        off = "-".join(str(w) for w in self.disabled) if self.disabled else "ninguna"
        return (f"{self.base.id}__desde{self.from_week}"
                f"_ancla{self.anchor_pct * 100:+.1f}_off{off}")

    @property
    def anchor_time(self) -> float:
        return round(self.base.current_time * (1 - self.anchor_pct), 2)

    def entrada(self) -> dict[str, Any]:
        return self.base.entrada() | {
            "desde_semana": self.from_week,
            "tiempo_ancla": self.anchor_time,
            "semanas_deshabilitadas": list(self.disabled),
        }


@dataclass(frozen=True)
class SeasonCase:
    """Una proyección anual: `ScienceEngine.project_season`."""

    distance: int
    level: str
    n_macros: int = 3
    stroke: str = "libre"
    pool: str = "50"
    age: int | None = None
    profile: str | None = None

    @property
    def id(self) -> str:
        edad = f"e{self.age}" if self.age is not None else "adulto"
        perfil = (self.profile or "auto").replace(" ", "_")
        return (f"{self.distance}-{self.level}-{self.stroke}-p{self.pool}"
                f"-{edad}-{perfil}-n{self.n_macros}")

    @property
    def current_time(self) -> float:
        return CURRENT_TIME[self.level][self.distance]

    def entrada(self) -> dict[str, Any]:
        return {
            "distancia": self.distance, "nivel_esperado": self.level, "estilo": self.stroke,
            "piscina": self.pool, "edad": self.age, "perfil": self.profile,
            "n_macros": self.n_macros, "tiempo_actual": self.current_time,
        }


def _plan_cases() -> list[Case]:
    """Batería por bloques: cada bloque añade un eje sobre la rejilla base."""
    cases = [Case(d, lvl) for d in DISTANCES for lvl in LEVELS]        # 30 · rejilla
    cases += [                                                          #  9 · estilos
        Case(50, "advanced", "espalda"), Case(50, "advanced", "pecho"),
        Case(100, "competitive", "mariposa"), Case(100, "competitive", "combinado"),
        Case(100, "competitive", "espalda"),
        Case(200, "recreational", "pecho"), Case(200, "recreational", "combinado"),
        Case(200, "recreational", "mariposa"),
        Case(400, "advanced", "combinado"),
    ]
    cases += [                                                          #  4 · piscina 25
        Case(50, "competitive", pool="25"),
        Case(200, "advanced", "mariposa", pool="25"),
        Case(400, "recreational", "combinado", pool="25"),
        Case(1500, "beginner", pool="25"),
    ]
    cases += [                                                          #  3 · macro 3
        Case(100, "advanced", n_mac=3), Case(800, "competitive", n_mac=3),
        Case(1500, "elite", n_mac=3),
    ]
    cases += [                                                          #  3 · menores
        Case(100, "recreational", age=14), Case(400, "advanced", age=16),
        Case(1500, "beginner", age=14),
    ]
    cases += [                                                          #  5 · extensión
        Case(50, "elite", goal="agresiva"), Case(100, "advanced", goal="agresiva"),
        Case(200, "competitive", goal="agresiva"), Case(400, "beginner", goal="agresiva"),
        Case(800, "recreational", goal="agresiva"),
    ]
    cases += [                                                          #  4 · otras curvas
        Case(100, "advanced", goal="agresiva", curve="exponential"),
        Case(200, "competitive", curve="sigmoid"),
        Case(800, "advanced", goal="agresiva", curve="logarithmic"),
        Case(400, "recreational", goal="agresiva", curve="linear"),
    ]
    cases += [                                                          #  2 · duración
        Case(100, "advanced", total_weeks=10), Case(800, "competitive", total_weeks=20),
    ]
    cases += [Case(200, "advanced", goal="sin_mejora")]                 #  1 · macro plano
    return cases


def _recalc_cases() -> list[RecalcCase]:
    """Recálculos: el segundo camino de escritura del motor de progresión.

    Cubre las tres decisiones que toma `recalculate_remaining` —dónde se ancla,
    si la meta cabe en el tramo que queda, y qué hacer con las semanas muertas—
    sobre planes de distinta distancia, estilo, piscina, edad y curva.
    """
    return [
        # Ancla por delante del plan, meta que sí cabe en el tramo restante.
        RecalcCase(Case(100, "advanced"), from_week=7, anchor_pct=0.01),
        # Misma ancla, meta agresiva: el tramo cierra en SU techo, no en la meta.
        RecalcCase(Case(100, "advanced", goal="agresiva"), from_week=7, anchor_pct=0.01),
        # El atleta empeoró respecto al inicio (ancla más lenta que el actual).
        RecalcCase(Case(100, "advanced"), from_week=7, anchor_pct=-0.01),
        RecalcCase(Case(200, "competitive", "espalda"), from_week=4, anchor_pct=0.005),
        RecalcCase(Case(400, "recreational", "combinado", pool="25"), from_week=5, anchor_pct=0.02),
        # Recalcular el plan ENTERO desde la semana 1 (sin mejora acumulada).
        RecalcCase(Case(800, "beginner"), from_week=1, anchor_pct=0.0),
        # Solo quedan dos semanas: el techo del tramo es diminuto.
        RecalcCase(Case(1500, "elite"), from_week=14, anchor_pct=0.002),
        RecalcCase(Case(50, "advanced", "mariposa"), from_week=6, anchor_pct=0.01),
        # Menor y tercer macro van con meta AGRESIVA a propósito: con meta
        # factible manda la meta y el techo del tramo no ata, así que ni la
        # corrección por edad ni la degradación por macrociclo tocarían un solo
        # número — el caso parecería cubrir el eje sin cubrirlo.
        RecalcCase(Case(100, "recreational", age=14, goal="agresiva"),
                   from_week=6, anchor_pct=0.02),
        RecalcCase(Case(800, "competitive", n_mac=3, goal="agresiva"),
                   from_week=8, anchor_pct=0.01),
        # Curva con pico artificial: el clamp por semana actúa dentro del tramo.
        RecalcCase(Case(100, "advanced", goal="agresiva", curve="exponential"),
                   from_week=5, anchor_pct=0.01),
        # Parón de dos semanas (lesión) y parón largo de cuatro.
        RecalcCase(Case(200, "advanced"), from_week=5, anchor_pct=0.01, disabled=(6, 7)),
        RecalcCase(Case(400, "advanced"), from_week=3, anchor_pct=0.01, disabled=(4, 5, 6, 7)),
        # TODAS las semanas restantes deshabilitadas → el plan se devuelve intacto.
        RecalcCase(Case(100, "advanced", total_weeks=10), from_week=9, anchor_pct=0.01,
                   disabled=(9, 10)),
    ]


def _season_cases() -> list[SeasonCase]:
    """Proyección anual: N macrociclos encadenados con degradación."""
    cases = [SeasonCase(400, lvl) for lvl in LEVELS]                    # 5 · niveles
    cases += [SeasonCase(d, "advanced") for d in (50, 100, 200, 800, 1500)]  # 5 · distancias
    cases += [                                                          # 3 · nº de macros
        SeasonCase(100, "competitive", n_macros=1),
        SeasonCase(100, "competitive", n_macros=2),
        SeasonCase(100, "competitive", n_macros=4),
    ]
    cases += [                                                          # 2 · menores
        SeasonCase(200, "recreational", age=14), SeasonCase(200, "recreational", age=16),
    ]
    # Estilo y piscina no deberían mover la proyección (solo se lee el techo
    # realista del macro); se congela para que se note el día que la muevan.
    cases += [SeasonCase(100, "advanced", stroke="pecho", pool="25")]
    # Perfil forzado por el entrenador contra el que sugiere la distancia.
    cases += [SeasonCase(400, "advanced", profile="fondo")]
    return cases


PLAN_CASES: list[Case] = _plan_cases()
RECALC_CASES: list[RecalcCase] = _recalc_cases()
SEASON_CASES: list[SeasonCase] = _season_cases()

# Todo caso que declara un nivel: se comprueba que el literal sigue clasificando
# ahí (los de recálculo heredan el de su plan base).
LEVEL_CLAIMS: list[tuple[str, int, float, str]] = (
    [(c.id, c.distance, c.current_time, c.level) for c in PLAN_CASES]
    + [(c.id, c.base.distance, c.base.current_time, c.base.level) for c in RECALC_CASES]
    + [(c.id, c.distance, c.current_time, c.level) for c in SEASON_CASES]
)

__all__ = [
    "LEVEL_CLAIMS", "PLAN_CASES", "RECALC_CASES", "SEASON_CASES", "START_DATE",
    "Case", "RecalcCase", "SeasonCase",
]
