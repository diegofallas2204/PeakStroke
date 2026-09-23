"""Las constantes científicas que no son de ningún objeto de valor.

Cada una con su § de `SWIMMING_SCIENCE_REFERENCE.md`, que es la fuente de la que
salen todas. **Esta es la única declaración**: `app/domain/engine.py` y
`app/engine/` las importan de aquí mientras dure la fusión (paso 4), y
desaparecen con ellos.

## Qué NO está aquí, y por qué

`docs/REDISENO.md` §6.1 listaba también `ZONE_OVER_RACE`,
`STROKE_TPACE_CORRECTION_S`, `POOL_FACTOR_25`, `F_FASE`, `WEEKLY_VOLUME_KM` y
`RATIO_DESCANSO`. Ese párrafo se escribió antes del paso 1, y hoy esas seis ya
viven **dentro del objeto de valor al que pertenecen**:

    factores de zona        → `valores.zona.factores_de_zona`
    corrección de estilo    → `valores.Estilo.correccion_s`
    factor de piscina       → `valores.Piscina`
    F_FASE y su etiqueta    → `valores.Fase`
    volumen semanal por fase→ `valores.Fase` × `valores.Nivel`
    ratios de descanso      → `valores.Zona.descanso_para`

Copiarlas aquí sería la tercera copia de reglas que el paso 1 acaba de unificar,
y el paso 4 existe justo para retirar copias. Lo que queda en este archivo es lo
que **no** tiene un objeto de valor donde vivir: tablas del macrociclo, del
techo de mejora y del reparto de kilómetros.
"""
from __future__ import annotations

# ── §4.2 · Techo de mejora por MESOCICLO (4-6 sem), proporción decimal ───────
# JERARQUÍA TEMPORAL (nota 17 del vault; confundirla es el error clásico):
#   · I_max          = mejora máx por MESOCICLO.
#   · I_max × (N/5)  = mejora máx por MACROCICLO de N semanas.
#   · TEMPORADA      = 3 macros encadenados con degradación ≈ 1.96× el primero.
# Validado vs literatura: élite ~0.5-1.5%/año (Pyne 2004), joven ~7-14.6%/temporada
# (Morais 2021), progresión por edad×nivel (Ruiz-Navarro 2025).
TABLA_I_MAX: dict[str, dict[int, float]] = {
    "beginner":     {50: 0.035, 100: 0.030, 200: 0.032, 400: 0.035, 800: 0.038, 1500: 0.040},
    "recreational": {50: 0.025, 100: 0.022, 200: 0.024, 400: 0.026, 800: 0.028, 1500: 0.030},
    "advanced":     {50: 0.015, 100: 0.013, 200: 0.015, 400: 0.017, 800: 0.019, 1500: 0.021},
    "competitive":  {50: 0.008, 100: 0.007, 200: 0.008, 400: 0.009, 800: 0.010, 1500: 0.011},
    "elite":        {50: 0.003, 100: 0.0025, 200: 0.003, 400: 0.0035, 800: 0.004, 1500: 0.0045},
}

# §4.3 — decaimiento geométrico del I_max entre macrociclos consecutivos.
# RECALIBRADO 2026-06-22: 0.85 → 0.60. El 0.85 sobreestimaba una temporada de 3
# macros (élite ~3.4%/año vs literatura ~1%). El 0.60 reproduce Morais et al.
# 2021 (7.8 / 3.7 / 3.8% → factor inter-macro ≈ 0.60) y concuerda con Mujika 1995.
# Solo afecta a planes con n_mac ≥ 2. Ver nota 17.
DEGRADACION_ENTRE_MACROS = 0.60

# §4.4 — los menores de 18 tienen más margen de adaptación mientras no han
# alcanzado la maduración biológica. (edad máxima, multiplicador de I_max).
FACTOR_JUVENIL: tuple[tuple[int, float], ...] = ((14, 2.0), (17, 1.5))


def factor_juvenil(edad: int | None) -> float:
    """Multiplicador del techo de mejora por edad (§4.4). 1.0 desde los 18."""
    if edad is None:
        return 1.0
    for hasta, factor in FACTOR_JUVENIL:
        if edad <= hasta:
            return factor
    return 1.0


# §4.5 — mejora ANUAL esperada (temporada de ~3 macros), proporción {min, max}.
# Techo de la literatura para validar la proyección anual (nota 17).
MEJORA_ANUAL_ESPERADA: dict[str, tuple[float, float]] = {
    "beginner":     (0.08, 0.15),
    "recreational": (0.05, 0.10),
    "advanced":     (0.03, 0.06),
    "competitive":  (0.02, 0.035),
    "elite":        (0.005, 0.015),
}

# §7.3 — volumen máximo semanal por estilo y nivel (km). Techo duro: nadar 90 km
# de mariposa no es un plan exigente, es una lesión.
VOLUMEN_MAXIMO_POR_ESTILO: dict[str, dict[str, float]] = {
    "freestyle":         {"beginner": 20, "recreational": 35, "advanced": 55, "competitive": 70, "elite": 90},
    "backstroke":        {"beginner": 18, "recreational": 30, "advanced": 50, "competitive": 65, "elite": 85},
    "butterfly":         {"beginner": 12, "recreational": 20, "advanced": 30, "competitive": 40, "elite": 55},
    "breaststroke":      {"beginner": 15, "recreational": 25, "advanced": 38, "competitive": 50, "elite": 65},
    "individual_medley": {"beginner": 20, "recreational": 30, "advanced": 45, "competitive": 60, "elite": 80},
}

# §13.2 — patrón de carga 3:1 dentro del mesociclo (semana relativa → % carga).
PATRON_DE_CARGA_MESO: dict[int, float] = {1: 0.77, 2: 0.875, 3: 0.975, 0: 0.55}

# §18 — dominancia aeróbica por prueba (etiqueta informativa, no entra en cálculo).
TIER_POR_AEROBICO: dict[int, dict] = {
    50:   {"tier": 2, "aerobic": 0.05, "desc": "Sprint — anaeróbico dominante"},
    100:  {"tier": 2, "aerobic": 0.35, "desc": "Sprint-resistencia"},
    200:  {"tier": 2, "aerobic": 0.60, "desc": "Mix — transición"},
    400:  {"tier": 1, "aerobic": 0.87, "desc": "Aeróbico dominante"},
    800:  {"tier": 1, "aerobic": 0.93, "desc": "Aeróbico alto"},
    1500: {"tier": 1, "aerobic": 0.95, "desc": "Aeróbico muy alto"},
}

# Ritmo /100 m REALISTA de las pruebas < 100 m: un 50 no se sostiene al doble de
# distancia. Ratio real 50→100 del pool nacional (n=127, 2026-06-13) — el mismo
# escalado que ya llevan los factores de zona de velocidad, y por eso corrige
# solo el ritmo mostrado, nunca las zonas (estarían corrigiéndolo dos veces).
PROYECCION_SPRINT_A_100: dict[int, float] = {50: 1.100}

# Estructura fija del macrociclo científico de 15 semanas: (ini, fin, fase).
# Es la forma que da la curva científica; el número de semanas real lo pone el
# entrenador, y el motor mapea su plan sobre esta forma.
MACRO_15_FASES: list[tuple[int, int, str]] = [
    (1, 3, "base_general"),
    (4, 7, "base_especifica"),
    (8, 11, "umbral_css"),
    (12, 13, "pre_competitivo"),
    (14, 15, "taper"),
]

# Tope de semanas EXTRA tras el macro cuando la meta supera el techo realista.
# 30 = dos macros de 15 exactos. Evita "semanas necesarias" desorbitadas: el techo
# informa, no fantasea con 80 semanas. Ojo con subirlo: la extensión mejora a
# ritmo seguro PLANO, sin degradación, así que cada semana extra exagera un poco
# más. Tuvo dos valores (30 aquí, 26 en `feasibility`) hasta el 2026-08-13, y el
# simulador sugería 41 semanas mientras el motor extendía hasta 45.
MAX_SEMANAS_EXTENSION = 30

# §20.3 — margen de error de la predicción (s) por banda de semanas.
_MARGENES: tuple[tuple[int, int], ...] = ((4, 2), (8, 4), (12, 6))
MARGEN_MAXIMO_S = 8


def margen_de_confianza(semana: int) -> int:
    """± segundos de confianza de la predicción de esa semana (§20.3)."""
    for hasta, margen in _MARGENES:
        if semana <= hasta:
            return margen
    return MARGEN_MAXIMO_S


# ── Reparto del kilometraje (Bompa & Haff 2009 · Issurin 2008) ───────────────
# Onda intra-microciclo: carga relativa de cada semana dentro del micro.
ONDA_DEL_MICRO: dict[int, list[float]] = {
    4: [0.78, 0.90, 1.00, 0.58],
    5: [0.72, 0.84, 0.94, 1.00, 0.58],
}

# Envolvente del macro: rampa hasta el 70 % del ciclo y descenso al taper.
RAMPA_INICIAL = 0.65
RAMPA_HASTA = 0.70
CAIDA_DEL_TAPER = 0.60
DESCARGA_ULTIMA_SEMANA = 0.55

# Distribución del volumen semanal por zonas, según la distancia de la prueba.
# Driver: la contribución aeróbica cambia con la distancia (Gastin 2001,
# Maglischo 2011) — 50 m 5 % aeróbico, 1500 m 95 %.
MEZCLA_DE_ZONAS_POR_DISTANCIA: dict[int, dict[str, float]] = {
    50:   {"R1": 0.28, "R2": 0.12, "MVO2": 0.18, "RL": 0.25, "V": 0.17},
    100:  {"R1": 0.40, "R2": 0.14, "MVO2": 0.18, "RL": 0.18, "V": 0.10},
    200:  {"R1": 0.53, "R2": 0.16, "MVO2": 0.15, "RL": 0.12, "V": 0.04},
    400:  {"R1": 0.64, "R2": 0.17, "MVO2": 0.11, "RL": 0.06, "V": 0.02},
    800:  {"R1": 0.70, "R2": 0.16, "MVO2": 0.09, "RL": 0.04, "V": 0.01},
    1500: {"R1": 0.74, "R2": 0.15, "MVO2": 0.07, "RL": 0.03, "V": 0.01},
}

# Fallback por especialidad, para cuando no hay distancia (el simulador).
MEZCLA_DE_ZONAS_POR_ESPECIALIDAD: dict[str, dict[str, float]] = {
    "velocidad":      {"R1": 0.35, "R2": 0.13, "MVO2": 0.18, "RL": 0.22, "V": 0.12},
    "medio_fondo":    {"R1": 0.53, "R2": 0.16, "MVO2": 0.15, "RL": 0.12, "V": 0.04},
    "fondo":          {"R1": 0.68, "R2": 0.16, "MVO2": 0.10, "RL": 0.05, "V": 0.01},
    "aguas_abiertas": {"R1": 0.74, "R2": 0.15, "MVO2": 0.07, "RL": 0.03, "V": 0.01},
}

# ── Veredicto de factibilidad (§5.3) ────────────────────────────────────────
# Cociente entre la mejora pedida y el techo científico del macro.
RATIO_REALISTA = 0.85
RATIO_EXIGENTE = 1.15

# Tolerancia para clasificar el tiempo real contra el esperado (±0.4 %).
TOLERANCIA_DE_ESTADO = 0.004
