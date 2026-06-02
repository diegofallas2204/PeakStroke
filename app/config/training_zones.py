"""
training_zones.py — Fuente de verdad única para todos los factores del motor.

Aquí viven:
  - Factores de distancia (cuántos splits de 100m tiene cada prueba)
  - Ratio aeróbico por distancia (% del sistema aeróbico en cada evento)
  - Factores de estilo (eficiencia relativa a crawl)
  - Ventanas de mejora por microciclo para eventos de velocidad (Tier 2)
  - Factores de zonas de entrenamiento
  - Constante empírica de mejora aeróbica por microciclo

Referencia bitácora: Entradas #001 y #002
"""

# ---------------------------------------------------------------------------
# Clasificación de tiers
# ---------------------------------------------------------------------------
# Tier 1 (≥ THRESHOLD): mejora guiada por base aeróbica (regla 1s/micro)
# Tier 2 (<  THRESHOLD): mejora por ventana fraccionada (velocidad/mixto)

TIER_1_THRESHOLD_M: int = 400


# ---------------------------------------------------------------------------
# Factor de distancia
# Para Tier 1: multiplica la mejora de la base aeróbica → mejora en la prueba
# Para ambos tiers: sirve para calcular el parcial por 100m
# ---------------------------------------------------------------------------
# Nota: el 200m usa un factor sub-lineal porque el componente anaeróbico
# (~30–45%) reduce la transferencia de la base aeróbica.

DISTANCE_FACTORS: dict[int, float] = {
    50:   0.15,
    100:  0.45,
    200:  1.80,   # no lineal por mezcla energética
    400:  4.00,   # 4 × 100m splits
    800:  8.00,   # 8 × 100m splits
    1500: 15.00,
}


# ---------------------------------------------------------------------------
# Ratio aeróbico por distancia
# Fracción de la energía que proviene del sistema aeróbico.
# Fuente: fisiología del deporte (valores aproximados para natación).
# ---------------------------------------------------------------------------

AEROBIC_RATIO: dict[int, float] = {
    50:   0.15,
    100:  0.325,
    200:  0.625,
    400:  0.875,
    800:  0.925,
    1500: 0.960,
}


# ---------------------------------------------------------------------------
# Factores de estilo (relativo a crawl = 1.0)
# Reflejan la diferencia de eficiencia mecánica entre estilos.
# Un atleta con la misma base aeróbica nada más lento en mariposa que en crawl.
# Fuente: Entrada #002 bitácora — pendiente validación con entrenadores.
# ---------------------------------------------------------------------------

STROKE_FACTORS: dict[str, float] = {
    "libre":        1.000,
    "crawl":        1.000,  # alias
    "espalda":      0.900,  # rango validado: 0.88–0.92
    "backstroke":   0.900,
    "mariposa":     0.760,  # rango validado: 0.72–0.80
    "butterfly":    0.760,
    "pecho":        0.680,  # rango validado: 0.65–0.72
    "breaststroke": 0.680,
    "combinado":    0.800,  # IM: promedio ponderado de estilos
    "im":           0.800,
}


# ---------------------------------------------------------------------------
# Ventanas de mejora por microciclo — Tier 2 (velocidad)
# Formato: (distancia, estilo) → (mínimo_s, máximo_s)
#
# Si la mejora requerida por micro SUPERA el máximo → objetivo agresivo.
# Si está entre mín y máx → dentro de la ventana realista.
# Fuente: Entrada #002 bitácora.
# ---------------------------------------------------------------------------

SPEED_WINDOWS: dict[tuple[int, str], tuple[float, float]] = {
    # 100m
    (100, "libre"):        (0.40, 0.60),
    (100, "crawl"):        (0.40, 0.60),
    (100, "mariposa"):     (0.30, 0.50),
    (100, "butterfly"):    (0.30, 0.50),
    (100, "espalda"):      (0.35, 0.50),
    (100, "backstroke"):   (0.35, 0.50),
    (100, "pecho"):        (0.25, 0.45),
    (100, "breaststroke"): (0.25, 0.45),
    # 50m
    (50,  "libre"):        (0.10, 0.25),
    (50,  "crawl"):        (0.10, 0.25),
    (50,  "mariposa"):     (0.08, 0.20),
    (50,  "butterfly"):    (0.08, 0.20),
    (50,  "espalda"):      (0.10, 0.22),
    (50,  "backstroke"):   (0.10, 0.22),
    (50,  "pecho"):        (0.08, 0.18),
    (50,  "breaststroke"): (0.08, 0.18),
    # 200m (zona de transición — más aeróbico que 100m pero speed aún domina)
    (200, "libre"):        (0.80, 1.20),
    (200, "crawl"):        (0.80, 1.20),
    (200, "mariposa"):     (0.50, 0.80),
    (200, "butterfly"):    (0.50, 0.80),
    (200, "espalda"):      (0.60, 0.90),
    (200, "backstroke"):   (0.60, 0.90),
    (200, "pecho"):        (0.45, 0.70),
    (200, "breaststroke"): (0.45, 0.70),
}


# ---------------------------------------------------------------------------
# Zonas de entrenamiento
# Factor aplicado al parcial de 100m de la prueba para obtener el ritmo
# de cada zona. Ej: si el parcial de carrera es 65s, R1 = 65 × 1.375 = 89.4s.
#
# IMPORTANTE: Los factores varían ligeramente con la distancia de la prueba.
# Esta tabla usa valores medios. Para mayor precisión, el entrenador puede
# ajustar los factores aquí según su criterio.
# Fuente: Enunciado del proyecto + validación empírica del entrenador.
# ---------------------------------------------------------------------------

ZONE_FACTORS: dict[str, float] = {
    "R1":   1.375,  # Base aeróbica  (rango: 1.35–1.40)
    "R2":   1.275,  # Umbral aeróbico (rango: 1.25–1.30)
    "MVO2": 1.175,  # VO₂ máximo      (rango: 1.15–1.20)
    "RL":   1.125,  # Res. lactato    (rango: 1.10–1.15)
    "V":    1.075,  # Velocidad pura  (rango: 1.05–1.10)
}

ZONE_LABELS: dict[str, str] = {
    "R1":   "Base aeróbica (recuperación activa)",
    "R2":   "Umbral aeróbico",
    "MVO2": "VO₂ máximo / umbral anaeróbico",
    "RL":   "Resistencia de lactato",
    "V":    "Velocidad pura",
}


# ---------------------------------------------------------------------------
# Constante empírica validada
# Regla: 1 segundo de mejora en base aeróbica (R1 × 100m) por microciclo
# produce mejora observable en 400m y 800m.
# Fuente: Entrada #001 bitácora — validada empíricamente por el entrenador.
# ---------------------------------------------------------------------------

AEROBIC_BASE_IMPROVEMENT_PER_MICRO: float = 1.0  # segundos


# ---------------------------------------------------------------------------
# Umbrales de factibilidad
# ---------------------------------------------------------------------------

FEASIBILITY_WARNING_MULTIPLIER: float = 1.5   # hasta 1.5× el techo → warning
# más de 1.5× → agresivo
