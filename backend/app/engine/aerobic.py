"""Análisis de tests aeróbicos: T-30, T-15, tests personalizados N×D y CSS.

Todos los resultados se normalizan a un parcial por 100m (la unidad central
del sistema), que define la base aeróbica del atleta.

**El intervalo de salida.** Un test aeróbico de verdad se nada sobre un
intervalo: el entrenador canta "salida 1:30" y lee en el reloj la LLEGADA de
cada repetición. Hasta el 2026-08-10 este módulo solo aceptaba tiempos de nado,
así que un entrenador que apuntara lo que el reloj marcaba —lo normal— producía
una base aeróbica acumulada y sin sentido, y con ella zonas, predicción y
factibilidad. `input_mode="clock"` convierte esas llegadas restándoles la salida
que les corresponde; `send_off` es lo que hace posible la resta.

De la salida sale además el descanso real de cada repetición, y de ahí la
densidad del test: el dato que faltaba para prescribir los tiempos de
entrenamiento (ver `dominio/servicios/intervalos.py`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Pendiente (s/100m por repetición) a partir de la cual el test se considera
# en mejora o en caída en lugar de estable.
_TREND_SLOPE = 0.05

# Cómo hay que leer los números que llega el entrenador.
INPUT_REP = "rep"        # tiempo nadado en cada repetición
INPUT_CLOCK = "clock"    # llegada acumulada en el reloj de pared
INPUT_MODES = (INPUT_REP, INPUT_CLOCK)


@dataclass
class AerobicAnalysis:
    per100_splits: list[float]     # cada repetición normalizada a s/100m
    avg_per100: float              # base aeróbica (s/100m)
    std_dev: float                 # consistencia del test
    trend: str                     # improving | stable | declining
    trend_slope: float             # s/100m por repetición (negativo = mejora)
    # Tiempos de nado reales de cada repetición, ya despejados de la llegada.
    # Coinciden con lo que entró en modo `rep`; en modo `clock` no.
    rep_times: list[float] = field(default_factory=list)
    # --- Todo lo de abajo requiere intervalo de salida; sin él va vacío ---
    send_off: float | None = None
    departures: list[float] = field(default_factory=list)   # salida de cada rep
    rest_per_rep: list[float] = field(default_factory=list)
    avg_rest: float | None = None
    work_rest_ratio: float | None = None    # descanso medio / trabajo medio
    density: float | None = None            # fracción del ciclo que es nado
    missed_intervals: list[int] = field(default_factory=list)  # rep_number 1..N


def _rep_times_from(
    splits: list[float], send_off: float | None, input_mode: str,
) -> tuple[list[float], list[float]]:
    """Devuelve (tiempos de nado, salidas). La salida n es (n-1) × intervalo.

    El reloj no espera a nadie: las salidas son fijas aunque una repetición se
    pase de intervalo. Modelarlas como "sale cuando llega el anterior" sería
    inventarse un test distinto del que se nadó.
    """
    if input_mode not in INPUT_MODES:
        raise ValueError(f"Modo de ingreso desconocido: {input_mode}")
    if send_off is not None and send_off <= 0:
        raise ValueError("El intervalo de salida debe ser positivo")

    if send_off is None:
        if input_mode == INPUT_CLOCK:
            raise ValueError(
                "Las llegadas de reloj necesitan el intervalo de salida "
                "para despejar el tiempo nadado",
            )
        return list(splits), []

    departures = [i * send_off for i in range(len(splits))]
    if input_mode == INPUT_REP:
        return list(splits), departures

    rep_times = [round(t - d, 3) for t, d in zip(splits, departures, strict=True)]
    for i, t in enumerate(rep_times):
        if t <= 0:
            raise ValueError(
                f"La llegada de la repetición {i + 1} es anterior a su salida: "
                "revisa el intervalo o el modo de ingreso",
            )
    return rep_times, departures


def analyze_splits(
    splits: list[float],
    rep_distance: int = 100,
    send_off: float | None = None,
    input_mode: str = INPUT_REP,
) -> AerobicAnalysis:
    """Analiza los parciales de un test aeróbico.

    `splits` son los tiempos de cada repetición en segundos —o las llegadas
    acumuladas del reloj, si `input_mode="clock"`—; `rep_distance` permite tests
    personalizados (ej. 12×400: cada split se divide entre 4 para obtener el
    parcial por 100m, como hacen los entrenadores a mano).

    `send_off` es el intervalo de salida en segundos. Es opcional porque los
    tests guardados antes de que existiera no lo tienen, y un test sin él sigue
    siendo un test válido: solo pierde el descanso y la densidad.
    """
    if not splits:
        raise ValueError("Se requiere al menos un parcial")
    if rep_distance <= 0:
        raise ValueError("La distancia de repetición debe ser positiva")

    rep_times, departures = _rep_times_from(splits, send_off, input_mode)

    factor = rep_distance / 100.0
    per100 = [round(s / factor, 2) for s in rep_times]
    n = len(per100)
    avg = sum(per100) / n
    variance = sum((t - avg) ** 2 for t in per100) / n
    std = variance ** 0.5

    slope = _linear_slope(per100)
    if slope <= -_TREND_SLOPE:
        trend = "improving"
    elif slope >= _TREND_SLOPE:
        trend = "declining"
    else:
        trend = "stable"

    analysis = AerobicAnalysis(
        per100_splits=per100,
        avg_per100=round(avg, 2),
        std_dev=round(std, 3),
        trend=trend,
        trend_slope=round(slope, 4),
        rep_times=[round(t, 2) for t in rep_times],
    )
    if send_off is None:
        return analysis

    rest = [round(send_off - t, 2) for t in rep_times]
    avg_work = sum(rep_times) / n
    analysis.send_off = send_off
    analysis.departures = departures
    analysis.rest_per_rep = rest
    analysis.avg_rest = round(sum(rest) / n, 2)
    analysis.work_rest_ratio = round(analysis.avg_rest / avg_work, 4) if avg_work else None
    analysis.density = round(avg_work / send_off, 4)
    analysis.missed_intervals = [i + 1 for i, r in enumerate(rest) if r < 0]
    return analysis


def _linear_slope(values: list[float]) -> float:
    """Pendiente de regresión lineal simple sobre el índice de repetición."""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den else 0.0


@dataclass
class CssResult:
    css_ms: float        # velocidad crítica de nado en m/s
    t_pace_100: float    # pace por 100m equivalente (segundos)


def css_from_400_50(t400: float, t50: float) -> CssResult:
    """Critical Swim Speed según Wakayoshi et al. (1992): 350/(T400-T50)."""
    if t400 <= t50:
        raise ValueError("El tiempo de 400m debe ser mayor al de 50m")
    css = 350.0 / (t400 - t50)
    return CssResult(css_ms=round(css, 3), t_pace_100=round(100.0 / css, 2))
