"""Curvas de progresión normalizadas: f(0) = 0, f(1) = 1.

La fracción de mejora acumulada en el punto x (proporción del macrociclo
transcurrida) sigue la fisiología del modelo elegido:
- linear: mejora constante semana a semana.
- exponential: mejoras rápidas al inicio (atletas que retoman forma).
- logarithmic: mejoras decrecientes (atletas cerca de su techo).
- sigmoid: lenta adaptación, aceleración en construcción, meseta en taper.
"""
from __future__ import annotations

import math

CURVES = ["sigmoid", "linear", "exponential", "logarithmic"]

CURVE_LABELS = {
    "sigmoid": "Sigmoidal",
    "linear": "Lineal",
    "exponential": "Exponencial",
    "logarithmic": "Logarítmica",
}

# Parámetros de forma de las curvas (ajustables — ver manual de tuning).
# EXP_K: cuanto más alto, más adelantada la mejora (front-loaded).
# LOG_SCALE: cuanto más alto, más pronunciada la mejora temprana logarítmica.
# SIGMOID_STEEPNESS: cuanto más alto, más plano el inicio/fin y más brusco el centro.
EXP_K = 4.0
LOG_SCALE = 9.0
SIGMOID_STEEPNESS = 10.0


def curve_progress(x: float, curve: str) -> float:
    """Fracción de mejora acumulada [0..1] en el punto x [0..1]."""
    x = max(0.0, min(1.0, x))
    if curve == "linear":
        return x
    if curve == "exponential":
        return (1 - math.exp(-EXP_K * x)) / (1 - math.exp(-EXP_K))
    if curve == "logarithmic":
        return math.log(1 + LOG_SCALE * x) / math.log(1 + LOG_SCALE)
    if curve == "sigmoid":
        def sig(t: float) -> float:
            return 1 / (1 + math.exp(-SIGMOID_STEEPNESS * (t - 0.5)))
        return (sig(x) - sig(0)) / (sig(1) - sig(0))
    return x
