"""Tiempos de entrenamiento: del ritmo por zona al intervalo de salida.

Una prescripción de natación tiene **dos** números, no uno:

    10 × 100  a 1:18  salida 1:30
                ^^^^         ^^^^
                ritmo        intervalo de salida

El sistema calculaba el primero desde siempre (`engine/zones.calc_zones`) y no
el segundo, así que la tabla del equipo decía a qué ritmo nadar pero no cada
cuánto salir — que es la mitad que gobierna el sistema energético que se
estimula. Dos series al mismo ritmo con 5 s y con 60 s de descanso no entrenan
lo mismo.

## De dónde sale el descanso

El descanso se expresa como **ratio sobre el trabajo**, no como segundos fijos:
un 100 y un 400 de la misma zona no descansan lo mismo. Los ratios siguen la
progresión fisiológica de la nota 03 del vault (zonas de entrenamiento) y las
prescripciones de Maglischo (*Swimming Fastest*, 2003):

| Zona   | Cualidad                    | Descanso : trabajo | Fuente                        |
|--------|-----------------------------|--------------------|-------------------------------|
| `R1`   | Base aeróbica (Z1-Z2)       | 1 : 0.08           | nado casi continuo, 5-15 s    |
| `R2`   | Umbral aeróbico (Z2-Z3)     | 1 : 0.15           | series de umbral, 10-20 s     |
| `MVO2` | VO2 máximo (Z3-Z4)          | 1 : 0.50           | ~1:1 en repeticiones cortas   |
| `RL`   | Resistencia lactato (Z4)    | 1 : 1.50           | nota 03: glucolítico 1:3-1:4  |
| `V`    | Velocidad pura (Z5)         | 1 : 3.50           | nota 03: descanso completo    |

El principio que ordena la tabla lo dice la propia nota 03: *«en potencia
aláctica, el descanso incompleto convierte el trabajo en entrenamiento
glucolítico»*. Recortar el descanso de una zona rápida no la hace más dura, la
cambia de zona — por eso el descanso crece con la intensidad y nunca al revés.

Los topes en segundos existen porque el ratio solo, en los extremos, produce
disparates: un 25 de velocidad pediría 26 s de descanso (insuficiente para
recuperar la PCr) y un 800 de base aeróbica pediría 50 s (deja de ser continuo).

## Por qué se redondea a 5 segundos

El intervalo se canta sobre el reloj de pared de la piscina, que se lee en
manecillas de 5 s. Un `salida 1:28.6` no existe: el entrenador diría 1:30. Se
redondea **hacia arriba** — hacia abajo recortaría el descanso prescrito, que es
justo lo que la tabla de arriba dice que no se debe hacer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

ZONE_ORDER = ("R1", "R2", "MVO2", "RL", "V")

# Descanso como fracción del tiempo de trabajo. Ver la tabla de la cabecera.
REST_RATIO: dict[str, float] = {
    "R1": 0.08,
    "R2": 0.15,
    "MVO2": 0.50,
    "RL": 1.50,
    "V": 3.50,
}

# Suelo y techo del descanso en segundos, para que el ratio no se desmande en
# repeticiones muy cortas (suelo) ni muy largas (techo).
REST_BOUNDS_S: dict[str, tuple[float, float]] = {
    "R1": (5.0, 20.0),
    "R2": (10.0, 30.0),
    "MVO2": (15.0, 90.0),
    "RL": (30.0, 240.0),
    "V": (60.0, 300.0),
}

# Manecilla del reloj de pared.
CLOCK_STEP_S = 5.0


@dataclass(frozen=True)
class TrainingInterval:
    """Lo que se escribe en la pizarra para una zona y una distancia."""

    zone: str
    pace_100: float          # ritmo objetivo de la zona, s/100m
    work: float              # tiempo de nado de la repetición, s
    rest: float              # descanso real hasta la siguiente salida, s
    interval: float          # salida = trabajo + descanso, cuadrada al reloj
    rest_ratio: float        # descanso / trabajo, ya aplicados los topes
    # Comparación contra la densidad que el atleta demostró en su test, cuando
    # el test la registró. `None` en los tests antiguos, que no la tienen.
    measured_interval: float | None = None
    denser_than_measured: bool | None = None


def clock_interval(seconds: float, step: float = CLOCK_STEP_S) -> float:
    """Redondea hacia arriba al múltiplo de `step` (por defecto, 5 s)."""
    if step <= 0:
        raise ValueError("El paso del reloj debe ser positivo")
    return math.ceil(seconds / step - 1e-9) * step


def rest_for(zone: str, work: float) -> float:
    """Segundos de descanso para esa zona y ese tiempo de trabajo."""
    ratio = REST_RATIO.get(zone)
    if ratio is None:
        raise ValueError(f"Zona desconocida: {zone}")
    low, high = REST_BOUNDS_S[zone]
    return min(max(work * ratio, low), high)


def training_intervals(
    zone_paces: dict[str, float | None],
    rep_distance: int = 100,
    *,
    measured_ratio: float | None = None,
) -> dict[str, TrainingInterval]:
    """Intervalo de salida por zona para repeticiones de `rep_distance` metros.

    `zone_paces` son los ritmos objetivo en s/100m que ya produce
    `engine/zones.calc_zones` (su campo `mid`). Una zona con ritmo `None` no
    aplica a esa prueba y se omite: es lo mismo que hace `calc_zones`.

    `measured_ratio` es el descanso:trabajo que el atleta demostró en su test
    aeróbico. Cuando viene, cada zona añade cuál sería su salida a esa densidad
    y si la prescrita aprieta más que ella. **No altera la prescripción**: la
    densidad de un test de umbral no es la que toca en una serie de velocidad, y
    dejarla mandar convertiría una referencia en una regla.
    """
    if rep_distance <= 0:
        raise ValueError("La distancia de repetición debe ser positiva")

    factor = rep_distance / 100.0
    out: dict[str, TrainingInterval] = {}
    for zone in ZONE_ORDER:
        pace = zone_paces.get(zone)
        if pace is None:
            continue
        work = round(pace * factor, 2)
        rest = rest_for(zone, work)
        interval = clock_interval(work + rest)

        medido = clock_interval(work * (1 + measured_ratio)) \
            if measured_ratio is not None else None

        out[zone] = TrainingInterval(
            zone=zone,
            pace_100=round(pace, 2),
            work=work,
            rest=round(interval - work, 2),
            interval=interval,
            rest_ratio=round(rest / work, 4) if work else 0.0,
            measured_interval=medido,
            denser_than_measured=None if medido is None else interval < medido,
        )
    return out
