"""Carga, guardado y aplicación del tuning del motor de predicción.

El sandbox lee `tuning.json` (junto a este archivo), lo aplica sobre las
constantes del motor en caliente y muestra el efecto. Editar el JSON y recargar
es la forma de ajustar las predicciones a mano sin tocar el código.

Si `tuning.json` no existe, se crea a partir de los valores actuales del motor,
de modo que el archivo siempre arranca idéntico al comportamiento real.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.engine import curves, feasibility, zones

TUNING_PATH = Path(__file__).resolve().parent / "tuning.json"


def _win_key(distance: int, stroke: str) -> str:
    return f"{distance}|{stroke}"


def snapshot_from_engine() -> dict[str, Any]:
    """Construye el tuning por defecto leyendo las constantes vivas del motor."""
    return {
        "curvas": {
            "exponential_k": curves.EXP_K,
            "logarithmic_scale": curves.LOG_SCALE,
            "sigmoid_steepness": curves.SIGMOID_STEEPNESS,
        },
        "tier1_fondo": {
            "base_por_micro": feasibility.TIER1_BASE_PER_MICRO,
            "multiplicador_techo": feasibility.TIER1_CEILING_MULT,
            "factores_distancia": {str(k): v for k, v in feasibility.DISTANCE_FACTORS.items()},
            "ratio_aerobico": {str(k): v for k, v in feasibility.AEROBIC_RATIO.items()},
            "factores_estilo": dict(feasibility.STROKE_FACTORS),
        },
        "tier2_velocidad": {
            "multiplicador_alerta": feasibility.TIER2_WARNING_MULT,
            "ventana_default": list(feasibility._DEFAULT_WINDOW),
            "ventanas": {
                _win_key(d, s): list(v) for (d, s), v in feasibility.SPEED_WINDOWS.items()
            },
        },
        # Factores (min, max) sobre el pace/100m para cada zona, por banda de
        # distancia (clave = distancia máxima de la banda). null = la zona no se
        # prescribe para esa distancia. Esto define los TIEMPOS DE ZONA por semana.
        "zonas_entrenamiento": {
            str(max_dist): {
                z: (list(rng) if rng else None) for z, rng in factors.items()
            }
            for max_dist, factors in zones._ZONE_BANDS
        },
    }


def load_tuning() -> dict[str, Any]:
    """Lee tuning.json; si no existe lo crea desde los valores del motor.

    Auto-completa secciones nuevas que falten en archivos viejos (p. ej.
    `zonas_entrenamiento`) tomándolas de los valores por defecto del motor, para
    que un tuning.json previo siga funcionando sin romperse.
    """
    if not TUNING_PATH.exists():
        data = snapshot_from_engine()
        save_tuning(data)
        return data
    data = json.loads(TUNING_PATH.read_text(encoding="utf-8"))
    defaults = snapshot_from_engine()
    missing = [k for k in defaults if k not in data]
    if missing:
        for k in missing:
            data[k] = defaults[k]
        save_tuning(data)
    return data


def save_tuning(data: dict[str, Any]) -> None:
    TUNING_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def apply_tuning(data: dict[str, Any]) -> None:
    """Vuelca el tuning sobre las constantes del motor (efecto en caliente).

    Sobrescribe los globals de los módulos `curves` y `feasibility`; como las
    funciones leen esos nombres en tiempo de ejecución, el cambio surte efecto
    de inmediato en `generate_plan` y `analyze_feasibility`.
    """
    cur = data["curvas"]
    curves.EXP_K = float(cur["exponential_k"])
    curves.LOG_SCALE = float(cur["logarithmic_scale"])
    curves.SIGMOID_STEEPNESS = float(cur["sigmoid_steepness"])

    t1 = data["tier1_fondo"]
    feasibility.TIER1_BASE_PER_MICRO = float(t1["base_por_micro"])
    feasibility.TIER1_CEILING_MULT = float(t1["multiplicador_techo"])
    feasibility.DISTANCE_FACTORS = {int(k): float(v) for k, v in t1["factores_distancia"].items()}
    feasibility.AEROBIC_RATIO = {int(k): float(v) for k, v in t1["ratio_aerobico"].items()}
    feasibility.STROKE_FACTORS = {k: float(v) for k, v in t1["factores_estilo"].items()}

    t2 = data["tier2_velocidad"]
    feasibility.TIER2_WARNING_MULT = float(t2["multiplicador_alerta"])
    feasibility._DEFAULT_WINDOW = tuple(t2["ventana_default"])  # type: ignore[assignment]
    windows: dict[tuple[int, str], tuple[float, float]] = {}
    for key, val in t2["ventanas"].items():
        dist_s, stroke = key.split("|", 1)
        windows[(int(dist_s), stroke)] = tuple(val)  # type: ignore[assignment]
    feasibility.SPEED_WINDOWS = windows

    bands: list[tuple[int, dict[str, tuple[float, float] | None]]] = []
    for max_dist, factors in sorted(
        data["zonas_entrenamiento"].items(), key=lambda kv: int(kv[0])
    ):
        fmap = {z: (tuple(rng) if rng else None) for z, rng in factors.items()}
        bands.append((int(max_dist), fmap))  # type: ignore[arg-type]
    zones._ZONE_BANDS = bands
