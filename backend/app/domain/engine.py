"""
sandbox/engine.py — Motor científico de predicción para natación.

Toda la lógica sale de la investigación consolidada en
SWIMMING_SCIENCE_REFERENCE.md (la fuente de verdad). No hay parámetros
"quemados" de un atleta concreto: cada número está fundamentado y referenciado
a su sección (§) del documento. Si un atleta no encaja, se recalibra la TEORÍA
(las tablas de aquí), no se mete un caso particular a mano.

──────────────────────────────────────────────────────────────────────────────
MODELO DE ZONAS — ancladas al RITMO DE CARRERA del evento
──────────────────────────────────────────────────────────────────────────────
Las zonas de entrenamiento se calculan como un factor sobre el ritmo de carrera
de la prueba, propio del PERFIL y la distancia:

        zona_pace = ritmo_carrera × factor[perfil][distancia]  (+ estilo, × piscina)

Como se ancla al tiempo del EVENTO (actual→meta), el ritmo de entreno de cada
semana COINCIDE con el tiempo de competencia que el atleta puede hacer esa
semana. No se pide un test aparte (12×400 ni CSS): el actual y la meta mandan.

──────────────────────────────────────────────────────────────────────────────
CADENA DE CÁLCULO  (un atleta, macro fijo de 15 semanas)
──────────────────────────────────────────────────────────────────────────────
  1. Entrada: perfil, prueba+estilo (estilo limitado por distancia), actual, meta.
  2. Progresión ANCLADA A LA META: sem 1 = actual, sem 15 = meta (pesos F_FASE).
        ritmo_carrera_sem = predicho_sem / (distancia/100)
        zonas = ritmo_carrera_sem × factor[perfil][dist] + corr_estilo, × piscina
        → sem 1 zonas desde el ACTUAL, sem 15 zonas desde la META.
  3. nivel = clasificar por UMBRAL (≈CSS, ancla en la zona MVO2)   (§2.4)
     OJO literatura: CSS = umbral (MLSS/umbral de lactato), ~3-10% MÁS LENTO
     que vVO2max. La etiqueta "MVO2" aquí se usa como ancla de umbral (≈CSS),
     NO como velocidad a VO2max literal (esa sería más rápida, cerca de RL).
  4. km    = volumen por fase/nivel + 3:1          (§9.1, §13.2)
  5. factibilidad: mejora pedida vs I_max total (§5.3); techo físico informativo.

NOTAS:
  · Cada PERFIL × distancia tiene sus factores (velocidad/medio fondo/fondo).
  · ESTILO limitado por distancia (800/1500 libre; 400 libre/combinado). Combinado
    = 25% de cada estilo. Corrección de estilo calibrada con el pool.
  · PISCINA de 25m ≈ 2.5% más rápido (§10.1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

# ───────────────────────────────────────────────────────────────────────────
# CONSTANTES CIENTÍFICAS  (fuente: SWIMMING_SCIENCE_REFERENCE.md)
# ───────────────────────────────────────────────────────────────────────────

ZONE_LABELS: dict[str, str] = {
    "R1": "R1", "R2": "R2", "MVO2": "MVO2", "RL": "RL", "V": "V",
}

# ── Estilos válidos por distancia ───────────────────────────────────────────
# 800/1500 solo libre · 400 libre o combinado · 50/100/200 cualquier estilo.
def allowed_strokes(distance: int) -> list[str]:
    if distance in (800, 1500):
        return ["libre"]
    if distance == 400:
        return ["libre", "combinado"]
    return ["libre", "espalda", "mariposa", "pecho", "combinado"]

# ── Corrección de T-pace por estilo (s/100m sobre crol) ─────────────────────
# CALIBRADO con el pool nacional, 2026-06-13. El doc §7.1 tenía espalda/mariposa
# invertidos: data y récords mundiales muestran ESPALDA más lenta que MARIPOSA.
# COMBINADO = 25% de cada estilo (así se nada el IM) → media de los 4.
_STROKE_BASE: dict[str, float] = {
    "freestyle": 0.0,
    "backstroke": 15.0,      # pool +15.5 (doc §7.1 daba +7)
    "butterfly": 10.0,       # pool +10.2 (doc §7.1 daba +13)
    "breaststroke": 23.0,    # pool +22.7 (doc §7.1 +22 ✓)
}
STROKE_TPACE_CORRECTION_S: dict[str, float] = dict(_STROKE_BASE)
STROKE_TPACE_CORRECTION_S["individual_medley"] = sum(_STROKE_BASE.values()) / 4  # 12.0

# ── Zonas como factor sobre el RITMO DE CARRERA del evento ──────────────────
# zona_pace = ritmo_carrera × factor[perfil][distancia]  (+ estilo, × piscina).
# Se ancla al tiempo del EVENTO (actual→meta), así el ritmo de entreno de cada
# semana coincide con el tiempo de competencia de esa semana. NO usa test aparte.
# Los factores varían por distancia porque el ritmo de carrera se acerca a las
# zonas conforme la prueba es más larga (1500 ≈ R1; 50 muy por encima de todo).
#   fondo:        CALIBRADO (reproduce las zonas reales de Emiliano).
#   velocidad/medio fondo: SEED teórico (§16/§18) — pendiente calibrar con datos
#   reales del entrenador, igual que se hizo con fondo.
# Verificado contra el pool nacional (verify_ranges.py, 2026-06-13): el ESCALADO
# entre distancias coincide con los ratios reales de ritmo por especialidad.
ZONE_OVER_RACE: dict[str, dict[int, dict[str, float]]] = {
    "velocidad": {  # nivel SEED; escalado 50→100 VALIDADO con pool (n=127, +0.2%)
        50:  {"R1": 1.562, "R2": 1.417, "MVO2": 1.285, "RL": 1.165, "V": 1.081},
        100: {"R1": 1.419, "R2": 1.288, "MVO2": 1.168, "RL": 1.059, "V": 0.982},
    },
    "medio fondo": {  # CALIBRADO con Emiliano (200 y 400 libre reales: 1:56.48 / 4:05.12)
        200: {"R1": 1.150, "R2": 1.108, "MVO2": 1.073, "RL": 0.987, "V": 0.953},
        400: {"R1": 1.093, "R2": 1.053, "MVO2": 1.020, "RL": 0.938, "V": 0.906},
    },
    "fondo": {  # estructura zonas Emiliano + escalado 800→1500 del pool (real 1.026, n=17)
        800:  {"R1": 1.047, "R2": 1.008, "MVO2": 0.977, "RL": 0.899, "V": 0.868},
        1500: {"R1": 1.020, "R2": 0.982, "MVO2": 0.952, "RL": 0.876, "V": 0.846},
    },
}

PROFILE_FUENTE: dict[str, str] = {
    "velocidad": "nivel seed · escalado validado pool (n=127)",
    "medio fondo": "calibrado Emiliano · escalado validado pool (n=29)",
    "fondo": "estructura Emiliano · escalado pool (n=17) · nivel pend. fondista real",
}

def profile_for_event(distance: int) -> str:
    """Perfil SUGERIDO por distancia (el coach puede sobreescribir).
    velocidad 50-100 · medio fondo 200-400 · fondo 800-1500."""
    if distance <= 100:
        return "velocidad"
    if distance <= 400:
        return "medio fondo"
    return "fondo"

def zone_factors(profile: str, distance: int) -> dict[str, float]:
    """Factores de zona sobre el ritmo de carrera para (perfil, distancia)."""
    table = ZONE_OVER_RACE[profile]
    if distance in table:
        return table[distance]
    nearest = min(table, key=lambda d: abs(d - distance))   # distancia más cercana del perfil
    return table[nearest]

# Corrección por piscina de 25m: el viraje extra cada 25m baja el parcial.
# Factores VALIDADOS con el pool (ratio real SCM/LCM por especialidad, 2026-06-13).
# El pool muestra un RATIO estable (~%) por especialidad, no un tiempo constante.
# Nota: el ratio del pool mezcla viraje + mejora ene→abr, así que el beneficio
# puro de viraje es algo mayor (estos valores son conservadores).
POOL_FACTOR_25: dict[str, float] = {
    "velocidad": 0.982,    # pool: 0.982 (≈ -1.2 s/100m)
    "medio fondo": 0.979,  # pool: 0.979 (≈ -1.4 s/100m) → R1 1:07 → ~1:05.6
    "fondo": 0.968,        # pool: 0.968 (≈ -2.3 s/100m, más virajes relativos)
}

def pool_factor(profile: str, pool: str) -> float:
    """Factor sobre el ritmo si la piscina es de 25m (1.0 si es de 50m)."""
    return POOL_FACTOR_25.get(profile, 0.978) if pool == "25" else 1.0

# ── Ritmo /100m REALISTA para eventos < 100m (corrección de fatiga) ──────────
# Un 50 NO se sostiene al doble de distancia: el /100m real es ~10% más lento
# que el simple ×2 (no se puede nadar 100m al ritmo de un 50). La constante es
# el ratio real 50→100 del pool (n=127, 2026-06-13) — el MISMO escalado que ya
# vive en los factores de velocidad (50 vs 100 difieren por ~1.100 constante).
# Por eso esto SOLO corrige el ritmo /100m mostrado/usado como referencia de
# carrera; las ZONAS no cambian (el factor de 50m ya incorpora este escalado).
SPRINT_TO_100: dict[int, float] = {50: 1.100}

def race_pace_100(predicted: float, distance: int) -> float:
    """Ritmo de carrera /100m REALISTA del evento.

    Para distancias < 100m proyecta a 100m con la fatiga del pool en vez de un
    simple ×2 (que daría un /100 demasiado rápido para velocidad)."""
    naive = predicted / (distance / 100.0)
    return naive * SPRINT_TO_100.get(distance, 1.0)

# §4.2 — mejora máxima del CSS por MESOCICLO (4-6 sem), proporción decimal.
# JERARQUÍA TEMPORAL (clave para no confundir escalas — ver nota 17 del vault):
#   · I_max            = mejora máx por MESOCICLO (4-6 sem).
#   · I_max × (N/5)    = mejora máx por MACROCICLO de N sem (≈3 mesos en 15 sem).
#                        Es la mejora DENTRO de un macro (lo que ve el coach al
#                        comparar el test de inicio con el pico del taper).
#   · TEMPORADA/ANUAL  = 3 macrociclos ENCADENADOS con degradación → suma ≈ 1.96×
#                        el primer macro (con MACROCYCLE_DEGRADATION=0.60).
# Validado vs literatura: élite ~0.5-1.5%/año (Pyne 2004), joven ~7-14.6%/temporada
# (Morais 2021, 3 macros 7.8/3.7/3.8%), progresión por edad×nivel (Ruiz-Navarro 2025).
I_MAX_TABLE: dict[str, dict[int, float]] = {
    "beginner":     {50: 0.035, 100: 0.030, 200: 0.032, 400: 0.035, 800: 0.038, 1500: 0.040},
    "recreational": {50: 0.025, 100: 0.022, 200: 0.024, 400: 0.026, 800: 0.028, 1500: 0.030},
    "advanced":     {50: 0.015, 100: 0.013, 200: 0.015, 400: 0.017, 800: 0.019, 1500: 0.021},
    "competitive":  {50: 0.008, 100: 0.007, 200: 0.008, 400: 0.009, 800: 0.010, 1500: 0.011},
    "elite":        {50: 0.003, 100: 0.0025, 200: 0.003, 400: 0.0035, 800: 0.004, 1500: 0.0045},
}

# §4.3 — decaimiento geométrico del I_max entre macrociclos consecutivos.
# RECALIBRADO 2026-06-22: 0.85 → 0.60. El 0.85 sobreestimaba la acumulación de una
# temporada de 3 macros (élite ~3.4%/año vs literatura ~1%; avanzado ~10% vs 3-6%).
# El valor 0.60 reproduce el único estudio que descompone una temporada en 3 macros
# (Morais et al. 2021, jóvenes 9-14a: 7.8 / 3.7 / 3.8% → factor inter-macro ≈ 0.60)
# y concuerda con Mujika 1995 (tapers 2.9/3.2/1.8% entre temporadas, ~0.62).
# Solo afecta planes con n_mac ≥ 2; los planes de un solo macro no cambian. Ver nota 17.
MACROCYCLE_DEGRADATION = 0.60


def youth_imax_factor(age: int | None) -> float:
    """§4.4 — multiplicador de I_max para atletas menores de 18 años.

    Los jóvenes tienen mayor potencial de adaptación que los adultos mientras no
    han alcanzado la maduración biológica. Edad >= 18 → sin corrección (factor 1.0).
    """
    if age is None or age >= 18:
        return 1.0
    if age <= 14:
        return 2.0
    return 1.5   # 15–17 años


# §4.3 — multiplicador de mejora por fase del macrociclo.
F_FASE: dict[str, float] = {
    "base_general":    0.60,
    "base_especifica": 0.80,
    "umbral_css":      1.00,
    "pre_competitivo": 1.05,
    "taper":           1.15,
    "extension":       1.00,   # semanas extra tras el macro (meta más agresiva que el techo)
}

# §4.5 — mejora ANUAL esperada (temporada de ~3 macros), proporción decimal {min,max}.
# Techo de la literatura para validar la proyección anual (nota 17 del vault):
# Pyne 2004 (élite ~1%), Ruiz-Navarro 2025 (por edad×nivel), Morais 2021 (joven).
ANNUAL_IMPROVEMENT_RANGE: dict[str, tuple[float, float]] = {
    "beginner":     (0.08, 0.15),
    "recreational": (0.05, 0.10),
    "advanced":     (0.03, 0.06),
    "competitive":  (0.02, 0.035),
    "elite":        (0.005, 0.015),
}

# §2.4 — clasificación de nivel por CSS (s/100m), tabla de crol.
def classify_level(css_100m: float) -> str:
    if css_100m > 150:
        return "beginner"
    if css_100m > 120:
        return "recreational"
    if css_100m > 95:
        return "advanced"
    if css_100m > 70:
        return "competitive"
    return "elite"

# §2.2 — CSS desde el test 400m + 50m (helper educativo / verificación).
# VALIDADO con el pool: en fondistas el CSS(400+50) ≈ ritmo de 800 (-0.6%),
# no el de 1500 como dice el doc §2.3 (queda ~3% rápido vs 1500). En medio-
# fondistas sobreestima el umbral de 800/1500 (~6%) porque hacen fade. En
# velocistas NO aplica (no nadan 400). Usar solo en fondo/medio fondo.
def css_from_test(t400_s: float, t50_s: float) -> float:
    """Devuelve el T-pace (s/100m) a partir de los tiempos de 400m y 50m a tope."""
    css_ms = 350.0 / (t400_s - t50_s)
    return 100.0 / css_ms

# §18 — clasificación de tier por dominancia aeróbica (para notas).
TIER_BY_AEROBIC: dict[int, dict] = {
    50:   {"tier": 2, "aerobic": 0.05, "desc": "Sprint — anaeróbico dominante"},
    100:  {"tier": 2, "aerobic": 0.35, "desc": "Sprint-resistencia"},
    200:  {"tier": 2, "aerobic": 0.60, "desc": "Mix — transición"},
    400:  {"tier": 1, "aerobic": 0.87, "desc": "Aeróbico dominante"},
    800:  {"tier": 1, "aerobic": 0.93, "desc": "Aeróbico alto"},
    1500: {"tier": 1, "aerobic": 0.95, "desc": "Aeróbico muy alto"},
}

# §9.1 — volumen semanal (km) por nivel y fase {min,max}.
WEEKLY_VOLUME_KM: dict[str, dict[str, tuple[float, float]]] = {
    "beginner":     {"base_general": (10, 20), "base_especifica": (15, 28), "umbral_css": (15, 25), "taper": (5, 12)},
    "recreational": {"base_general": (18, 32), "base_especifica": (25, 40), "umbral_css": (22, 38), "taper": (8, 18)},
    "advanced":     {"base_general": (25, 45), "base_especifica": (35, 55), "umbral_css": (30, 50), "taper": (12, 25)},
    "competitive":  {"base_general": (35, 55), "base_especifica": (45, 65), "umbral_css": (40, 60), "taper": (15, 30)},
    "elite":        {"base_general": (50, 80), "base_especifica": (60, 90), "umbral_css": (55, 85), "taper": (20, 40)},
}

# §13.2 — patrón de carga 3:1 dentro del mesociclo (semana relativa → % carga).
MESO_LOAD_PATTERN: dict[int, float] = {1: 0.77, 2: 0.875, 3: 0.975, 0: 0.55}

# §20.3 — margen de error de la predicción (s) según banda de semanas.
def confidence_margin(week: int) -> int:
    if week <= 4:
        return 2
    if week <= 8:
        return 4
    if week <= 12:
        return 6
    return 8

# Estructura fija del macrociclo de 15 semanas: (semana_ini, semana_fin, fase).
MACRO_15_PHASES: list[tuple[int, int, str]] = [
    (1, 3, "base_general"),
    (4, 7, "base_especifica"),
    (8, 11, "umbral_css"),
    (12, 13, "pre_competitivo"),
    (14, 15, "taper"),
]


# ── CURVA CIENTÍFICA (fuente única de la forma de progresión) ────────────────
# Distribución de mejora ponderada por F_FASE: cada fase aporta mejora a un ritmo
# proporcional a su F_fase (base general lenta, pico en taper). Es *back-loaded*
# (≈59% en la 2ª mitad, ≈18% en el taper). REEMPLAZA a la sigmoide como curva por
# defecto del sistema. Validada en notas 09/16/17 del vault (Mujika 1995;
# cohorte de periodización; Morais 2021). El simulador conserva sigmoide/exp/log/
# lineal solo para COMPARAR escenarios — la ciencia por defecto es esta.
def _science_curve_segments() -> list[tuple[float, float, float]]:
    """(x_ini, x_fin, peso F_fase) de cada fase como fracción del macro."""
    total_w = MACRO_15_PHASES[-1][1]   # 15 semanas
    return [((ini - 1) / total_w, fin / total_w, F_FASE[phase])
            for ini, fin, phase in MACRO_15_PHASES]

_SCIENCE_SEGMENTS = _science_curve_segments()
_SCIENCE_TOTAL = sum(w * (x1 - x0) for x0, x1, w in _SCIENCE_SEGMENTS)


def science_curve_progress(x: float) -> float:
    """Fracción de mejora acumulada [0..1] en el punto x [0..1] (fracción del
    macro transcurrida) según la curva CIENTÍFICA F_FASE. f(0)=0, f(1)=1.

    Es la integral normalizada de la densidad de mejora (peso F_fase por fase):
    crece lento en base general y acelera hacia el taper (supercompensación)."""
    x = max(0.0, min(1.0, x))
    acc = 0.0
    for x0, x1, w in _SCIENCE_SEGMENTS:
        if x <= x0:
            break
        acc += w * (min(x, x1) - x0)
    return acc / _SCIENCE_TOTAL

# Fase → banda de volumen a usar (pre_competitivo no tiene banda propia).
PHASE_VOLUME_KEY: dict[str, str] = {
    "base_general": "base_general",
    "base_especifica": "base_especifica",
    "umbral_css": "umbral_css",
    "pre_competitivo": "umbral_css",
    "taper": "taper",
    "extension": "umbral_css",   # las semanas extra mantienen volumen de umbral
}

PHASE_LABELS: dict[str, str] = {
    "base_general": "Base general",
    "base_especifica": "Base especif.",
    "umbral_css": "Umbral CSS",
    "pre_competitivo": "Pre-comp.",
    "taper": "Taper",
    "extension": "Extensión",
}

# Normalización de estilo (entrada en español → clave interna).
STROKE_ALIASES: dict[str, str] = {
    "libre": "freestyle", "crol": "freestyle", "freestyle": "freestyle",
    "espalda": "backstroke", "dorso": "backstroke", "backstroke": "backstroke",
    "mariposa": "butterfly", "butterfly": "butterfly",
    "pecho": "breaststroke", "braza": "breaststroke", "breaststroke": "breaststroke",
    "combinado": "individual_medley", "im": "individual_medley",
}

# §7.3 — volumen máximo semanal por estilo y nivel (km).
MAX_VOLUME_BY_STROKE: dict[str, dict[str, float]] = {
    "freestyle":        {"beginner": 20, "recreational": 35, "advanced": 55, "competitive": 70, "elite": 90},
    "backstroke":       {"beginner": 18, "recreational": 30, "advanced": 50, "competitive": 65, "elite": 85},
    "butterfly":        {"beginner": 12, "recreational": 20, "advanced": 30, "competitive": 40, "elite": 55},
    "breaststroke":     {"beginner": 15, "recreational": 25, "advanced": 38, "competitive": 50, "elite": 65},
    "individual_medley":{"beginner": 20, "recreational": 30, "advanced": 45, "competitive": 60, "elite": 80},
}


# ───────────────────────────────────────────────────────────────────────────
# DATACLASSES
# ───────────────────────────────────────────────────────────────────────────

@dataclass
class WeekZones:
    css: float
    paces: dict[str, float]    # clave de zona (ZONE_LABELS) → s/100m


@dataclass
class WeekRow:
    week: int
    week_date: date
    phase: str
    f_fase: float
    planned_km: float
    improvement_index: float   # i_n acumulado
    predicted_time: float      # tiempo de carrera predicho (s)
    margin: int                # ± s de confianza
    css_n: float               # ritmo /100m que ancla las zonas (interno)
    race_pace_100: float       # ritmo /100m REALISTA mostrado (proyecta <100m)
    zones: WeekZones

    @property
    def is_extension(self) -> bool:
        return self.phase == "extension"


@dataclass
class PlanResult:
    distance: int
    stroke: str
    profile: str               # "fondo" | "velocidad" (§18)
    pool: str                  # "50" | "25"
    stroke_correction: float   # s sumados por estilo (§7.1)
    current_time: float
    goal_time: float
    css_0: float               # ritmo de carrera actual /100m → ancla de zonas
    level: str
    feas_status: str
    feas_message: str
    predicted_final: float      # tiempo de la ÚLTIMA semana del plan (meta si se alcanza)
    realistic_final: float      # techo realista al final del macro de 15 sem (§5.3)
    physio_ceiling: float       # mejora máx física (I_max §5.1), informativo
    total_weeks: int            # nº de semanas del plan (puede ser <15 o >15)
    macro_weeks: int            # semanas del macro periodizado (≤15) antes de extensión
    goal_reached: bool          # ¿el plan alcanza la meta?
    weeks: list[WeekRow]


@dataclass
class MacroProjection:
    n_mac: int
    start_time: float          # tiempo al iniciar el macro (s)
    end_time: float            # techo realista al cerrar el macro (s)
    improvement_s: float
    improvement_pct: float


@dataclass
class SeasonProjection:
    """Proyección ANUAL = N macrociclos encadenados (re-test entre cada uno)."""
    level: str
    n_macros: int
    season_start: float
    season_end: float
    season_improvement_s: float
    season_improvement_pct: float     # % de mejora de la temporada completa
    annual_low_pct: float             # techo literatura (mín) para el nivel
    annual_high_pct: float            # techo literatura (máx) para el nivel
    verdict: str                      # "ok" | "optimistic" | "below"
    message: str
    macros: list[MacroProjection]


# ───────────────────────────────────────────────────────────────────────────
# MOTOR
# ───────────────────────────────────────────────────────────────────────────

class ScienceEngine:

    TOTAL_WEEKS = 15
    MAX_EXTENSION_WEEKS = 30   # tope de semanas extra (≈2 macros) para metas muy agresivas

    def _nearest_event(self, distance: int) -> int:
        known = sorted(I_MAX_TABLE["elite"].keys())
        return min(known, key=lambda d: abs(d - distance))

    def _effective_i_max(self, level: str, event: int, n_mac: int, age: int | None) -> float:
        """I_max ajustado por degradación de macrociclo (§4.3) y juventud (§4.4)."""
        base = I_MAX_TABLE[level][event]
        return base * (MACROCYCLE_DEGRADATION ** (n_mac - 1)) * youth_imax_factor(age)

    def _phase_for_week(self, week: int) -> str:
        for ini, fin, phase in MACRO_15_PHASES:
            if ini <= week <= fin:
                return phase
        return "umbral_css"

    def _zones_from_race(
        self, race_pace: float, profile: str, distance: int, stroke_key: str, pool: str
    ) -> WeekZones:
        """Zonas = ritmo_carrera × factor(perfil,dist) + estilo, × piscina (§10.1)."""
        factors = zone_factors(profile, distance)
        corr = STROKE_TPACE_CORRECTION_S.get(stroke_key, 0.0)   # crol → estilo
        pf = pool_factor(profile, pool)                         # 50m=1.0, 25m según pool
        return WeekZones(
            css=race_pace,
            paces={z: (race_pace * f + corr) * pf for z, f in factors.items()},
        )

    def _weekly_km(self, level: str, phase: str, week: int, stroke_key: str) -> float:
        """§9.1 + §13.2 — volumen medio de la fase modulado por el patrón 3:1."""
        vmin, vmax = WEEKLY_VOLUME_KM[level][PHASE_VOLUME_KEY[phase]]
        mid = (vmin + vmax) / 2.0
        load = MESO_LOAD_PATTERN[week % 4]                      # 1,2,3,0 → 0.77..0.55
        km = mid * load
        cap = MAX_VOLUME_BY_STROKE[stroke_key][level]          # §7.3
        return round(min(km, cap), 1)

    def _check_feasibility(
        self, current: float, goal: float, event: int, level: str,
        n_mac: int = 1, age: int | None = None,
    ) -> tuple[str, str]:
        """§5.3 — compara mejora pedida vs mejora máxima científica."""
        pct = (current - goal) / current
        num_meso = self.TOTAL_WEEKS / 5.0
        i_max_total = self._effective_i_max(level, event, n_mac, age) * num_meso
        ratio = pct / i_max_total if i_max_total else 999
        if ratio <= 0.85:
            return "ok", (
                f"Realista — pides {pct*100:.2f}% y el techo científico para "
                f"{level}/{event}m en 15 sem es {i_max_total*100:.2f}% (uso {ratio*100:.0f}%)."
            )
        if ratio <= 1.15:
            return "warning", (
                f"Exigente — pides {pct*100:.2f}%, cerca del techo {i_max_total*100:.2f}% "
                f"({ratio*100:.0f}% del máximo)."
            )
        return "aggressive", (
            f"Agresivo — pides {pct*100:.2f}%, supera el techo {i_max_total*100:.2f}% "
            f"({ratio*100:.0f}%). Considera más semanas o una meta menos ambiciosa."
        )

    def generate_plan(
        self,
        *,
        current_time: float,
        goal_time: float,
        distance: int,
        stroke: str,
        pool: str = "50",
        profile: str | None = None,
        start_date: date | None = None,
        n_mac: int = 1,
        age: int | None = None,
    ) -> PlanResult:
        start_date = start_date or date.today()
        event = self._nearest_event(distance)
        stroke_key = STROKE_ALIASES.get(stroke.lower().strip(), "freestyle")
        profile = profile or profile_for_event(event)
        stroke_corr = STROKE_TPACE_CORRECTION_S.get(stroke_key, 0.0)

        # Ritmo de carrera actual (s/100m) — ancla de las zonas.
        race_pace_0 = current_time / (distance / 100.0)
        # Nivel: ancla en la zona "MVO2", que aquí representa el UMBRAL (≈CSS),
        # no la velocidad a VO2max (literatura: CSS es ~3-10% más lento que vVO2max).
        # Aprox. validada: para Emiliano este ancla cae a ~1% de su CSS real (§2.4).
        threshold = race_pace_0 * zone_factors(profile, distance)["MVO2"]
        level = classify_level(threshold)
        css_0 = race_pace_0
        feas_status, feas_msg = self._check_feasibility(current_time, goal_time, event, level, n_mac, age)

        # ── Progresión al RITMO MÁXIMO REALISTA (techo científico §5.3) ──────
        # safe_total = mejora máx creíble en un macro de 15 sem. La progresión
        # NUNCA va más rápido que eso por semana. El nº de semanas se ajusta a
        # la meta: si cabe antes de la sem 15 → menos semanas; si la meta supera
        # el techo → se añaden semanas EXTRA (extensión) hasta alcanzarla.
        weights = [F_FASE[self._phase_for_week(w)] for w in range(1, self.TOTAL_WEEKS + 1)]
        denom = sum(weights[: self.TOTAL_WEEKS - 1]) or 1.0

        def cum_frac(w: int) -> float:
            """Fracción acumulada del macro al final de la semana w (0 en 1, 1 en 15)."""
            return sum(weights[: w - 1]) / denom

        i_max_total = self._effective_i_max(level, event, n_mac, age) * (self.TOTAL_WEEKS / 5.0)
        safe_total = current_time * i_max_total            # mejora máx realista en 15 sem (s)
        realistic_ceiling = current_time - safe_total      # tiempo realista al cerrar el macro
        requested = current_time - goal_time               # mejora pedida (s)

        def build_week(abs_week: int, phase: str, predicted: float) -> WeekRow:
            race_pace_n = predicted / (distance / 100.0)   # zonas escalan con el ritmo
            return WeekRow(
                week=abs_week,
                week_date=start_date + timedelta(weeks=abs_week - 1),
                phase=phase,
                f_fase=F_FASE[phase],
                planned_km=self._weekly_km(level, phase, abs_week, stroke_key),
                improvement_index=(current_time - predicted) / requested if requested > 0 else 0.0,
                predicted_time=predicted,
                margin=confidence_margin(abs_week),
                css_n=race_pace_n,
                race_pace_100=race_pace_100(predicted, distance),
                zones=self._zones_from_race(race_pace_n, profile, distance, stroke_key, pool),
            )

        rows: list[WeekRow] = []
        goal_reached = True

        if requested <= 0:
            # Meta no más rápida que el actual: macro plano de 15 sem hacia la meta.
            for w in range(1, self.TOTAL_WEEKS + 1):
                predicted = current_time - requested * cum_frac(w)
                rows.append(build_week(w, self._phase_for_week(w), predicted))
            macro_weeks = self.TOTAL_WEEKS

        elif requested <= safe_total:
            # Meta alcanzable dentro del macro → puede cerrarse en MENOS de 15 sem.
            n = self.TOTAL_WEEKS
            for w in range(2, self.TOTAL_WEEKS + 1):
                if safe_total * cum_frac(w) >= requested - 1e-9:
                    n = w
                    break
            frac_n = cum_frac(n) or 1.0
            for w in range(1, n + 1):
                # Reparte la mejora pedida con la forma F_FASE, cerrando en la meta.
                predicted = current_time - requested * (cum_frac(w) / frac_n)
                phase = self._phase_for_week(w)
                if w == n and n < self.TOTAL_WEEKS:
                    phase = "taper"         # garantiza una semana de pico/descarga al cerrar
                rows.append(build_week(w, phase, predicted))
            macro_weeks = n

        else:
            # Meta MÁS agresiva que el techo: el macro cierra en el tiempo realista
            # (sem 15) y se añaden semanas EXTRA al ritmo seguro hasta la meta.
            for w in range(1, self.TOTAL_WEEKS + 1):
                predicted = current_time - safe_total * cum_frac(w)
                rows.append(build_week(w, self._phase_for_week(w), predicted))
            macro_weeks = self.TOTAL_WEEKS

            extra_rate = safe_total / self.TOTAL_WEEKS     # ritmo seguro medio por semana
            remaining = realistic_ceiling - goal_time      # lo que falta tras el macro (s)
            n_ext = math.ceil(remaining / extra_rate) if extra_rate > 0 else 0
            n_ext = min(n_ext, self.MAX_EXTENSION_WEEKS)
            for j in range(1, n_ext + 1):
                abs_week = self.TOTAL_WEEKS + j
                predicted = max(realistic_ceiling - extra_rate * j, goal_time)
                rows.append(build_week(abs_week, "extension", predicted))
            goal_reached = bool(rows) and rows[-1].predicted_time <= goal_time + 1e-6

        # Techo físico informativo, consistente con el techo de factibilidad (§5.3).
        physio_ceiling = realistic_ceiling

        return PlanResult(
            distance=event,
            stroke=stroke_key,
            profile=profile,
            pool=pool,
            stroke_correction=stroke_corr,
            current_time=current_time,
            goal_time=goal_time,
            css_0=css_0,
            level=level,
            feas_status=feas_status,
            feas_message=feas_msg,
            predicted_final=rows[-1].predicted_time,
            realistic_final=realistic_ceiling,
            physio_ceiling=physio_ceiling,
            total_weeks=len(rows),
            macro_weeks=macro_weeks,
            goal_reached=goal_reached,
            weeks=rows,
        )

    def project_season(
        self,
        *,
        current_time: float,
        distance: int,
        stroke: str = "libre",
        pool: str = "50",
        profile: str | None = None,
        age: int | None = None,
        n_macros: int = 3,
    ) -> SeasonProjection:
        """Proyecta una TEMPORADA = `n_macros` macrociclos encadenados (§4.5, nota 17).

        Cada macro parte del techo realista del anterior (modela el re-test entre
        macros) y su potencial se degrada con `MACROCYCLE_DEGRADATION`. Devuelve la
        mejora por macro y la mejora anual total, comparada con el techo de la
        literatura (`ANNUAL_IMPROVEMENT_RANGE`). NO sustituye al plan semanal:
        es la vista anual que el coach usa para repartir la meta entre los 3 macros.
        """
        event = self._nearest_event(distance)
        profile = profile or profile_for_event(event)
        race_pace_0 = current_time / (distance / 100.0)
        level = classify_level(race_pace_0 * zone_factors(profile, distance)["MVO2"])

        macros: list[MacroProjection] = []
        t = current_time
        for n in range(1, max(1, n_macros) + 1):
            # Meta deliberadamente agresiva → cada macro alcanza su techo realista.
            plan = self.generate_plan(
                current_time=t, goal_time=t * 0.80, distance=distance,
                stroke=stroke, pool=pool, profile=profile, n_mac=n, age=age,
            )
            end = plan.realistic_final
            macros.append(MacroProjection(
                n_mac=n, start_time=round(t, 2), end_time=round(end, 2),
                improvement_s=round(t - end, 2),
                improvement_pct=round((t - end) / t * 100, 2) if t else 0.0,
            ))
            t = end

        season_imp = current_time - t
        season_pct = season_imp / current_time if current_time else 0.0
        # La proyección es un TECHO (cada macro llega a su máximo). El rango de la
        # literatura es lo TÍPICO; se ajusta por edad (los menores mejoran más,
        # §4.4) para que la comparación sea justa por edad, no solo por nivel.
        yf = youth_imax_factor(age)
        low_base, high_base = ANNUAL_IMPROVEMENT_RANGE.get(level, (0.0, 1.0))
        low, high = low_base * yf, high_base * yf

        if season_pct <= high:
            verdict = "ok"
            message = (
                f"Realista — el techo de temporada proyecta {season_pct*100:.2f}%, "
                f"dentro del rango típico {low*100:.1f}–{high*100:.1f}% para {level}"
                + (f" (ajustado por edad ×{yf:g})" if yf != 1.0 else "") + "."
            )
        elif season_pct <= high * 1.8:
            verdict = "optimistic"
            message = (
                f"Optimista — el techo de temporada ({season_pct*100:.2f}%) supera el "
                f"rango típico {low*100:.1f}–{high*100:.1f}% ({level}). Es el máximo de "
                f"{len(macros)} macros perfectos, no la media esperada."
            )
        else:
            verdict = "unrealistic"
            message = (
                f"Poco realista — {season_pct*100:.2f}% excede con mucho el techo "
                f"típico {low*100:.1f}–{high*100:.1f}% ({level}). Revisa el tiempo "
                f"actual o reparte la meta en más temporadas."
            )

        return SeasonProjection(
            level=level,
            n_macros=len(macros),
            season_start=round(current_time, 2),
            season_end=round(t, 2),
            season_improvement_s=round(season_imp, 2),
            season_improvement_pct=round(season_pct * 100, 2),
            annual_low_pct=round(low * 100, 2),
            annual_high_pct=round(high * 100, 2),
            verdict=verdict,
            message=message,
            macros=macros,
        )
