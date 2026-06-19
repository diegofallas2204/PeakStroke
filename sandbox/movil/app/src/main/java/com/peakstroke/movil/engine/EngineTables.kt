package com.peakstroke.movil.engine

import kotlin.math.abs

/**
 * Tablas científicas — port directo de sandbox/engine.py (fuente de verdad).
 * Cada número está fundamentado en SWIMMING_SCIENCE_REFERENCE.md. Si un atleta
 * no encaja, se recalibra la TEORÍA (estas tablas), no se mete un caso a mano.
 */

/** Claves de zona, en orden de presentación. */
val ZONE_KEYS = listOf("R1", "R2", "MVO2", "RL", "V")

/** Estilos válidos por distancia (800/1500 solo libre · 400 libre/combinado). */
fun allowedStrokes(distance: Int): List<String> = when (distance) {
    800, 1500 -> listOf("libre")
    400 -> listOf("libre", "combinado")
    else -> listOf("libre", "espalda", "mariposa", "pecho", "combinado")
}

/** Corrección de T-pace por estilo (s/100m sobre crol). Calibrado con pool 2026-06-13. */
private val STROKE_BASE = mapOf(
    "freestyle" to 0.0,
    "backstroke" to 15.0,
    "butterfly" to 10.0,
    "breaststroke" to 23.0,
)
val STROKE_TPACE_CORRECTION_S: Map<String, Double> =
    STROKE_BASE + ("individual_medley" to STROKE_BASE.values.sum() / 4.0)

/** Zonas como factor sobre el ritmo de carrera del evento, por perfil y distancia. */
val ZONE_OVER_RACE: Map<String, Map<Int, Map<String, Double>>> = mapOf(
    "velocidad" to mapOf(
        50 to mapOf("R1" to 1.562, "R2" to 1.417, "MVO2" to 1.285, "RL" to 1.165, "V" to 1.081),
        100 to mapOf("R1" to 1.419, "R2" to 1.288, "MVO2" to 1.168, "RL" to 1.059, "V" to 0.982),
    ),
    "medio fondo" to mapOf(
        200 to mapOf("R1" to 1.150, "R2" to 1.108, "MVO2" to 1.073, "RL" to 0.987, "V" to 0.953),
        400 to mapOf("R1" to 1.093, "R2" to 1.053, "MVO2" to 1.020, "RL" to 0.938, "V" to 0.906),
    ),
    "fondo" to mapOf(
        800 to mapOf("R1" to 1.047, "R2" to 1.008, "MVO2" to 0.977, "RL" to 0.899, "V" to 0.868),
        1500 to mapOf("R1" to 1.020, "R2" to 0.982, "MVO2" to 0.952, "RL" to 0.876, "V" to 0.846),
    ),
)

val PROFILE_FUENTE = mapOf(
    "velocidad" to "nivel seed · escalado validado pool (n=127)",
    "medio fondo" to "calibrado Emiliano · escalado validado pool (n=29)",
    "fondo" to "estructura Emiliano · escalado pool (n=17) · nivel pend. fondista real",
)

/** Perfil sugerido por distancia (velocidad 50-100 · medio fondo 200-400 · fondo 800-1500). */
fun profileForEvent(distance: Int): String = when {
    distance <= 100 -> "velocidad"
    distance <= 400 -> "medio fondo"
    else -> "fondo"
}

fun zoneFactors(profile: String, distance: Int): Map<String, Double> {
    val table = ZONE_OVER_RACE.getValue(profile)
    table[distance]?.let { return it }
    val nearest = table.keys.minByOrNull { abs(it - distance) }!!
    return table.getValue(nearest)
}

/** Corrección por piscina de 25m (1.0 si es de 50m). */
val POOL_FACTOR_25 = mapOf("velocidad" to 0.982, "medio fondo" to 0.979, "fondo" to 0.968)
fun poolFactor(profile: String, pool: String): Double =
    if (pool == "25") POOL_FACTOR_25[profile] ?: 0.978 else 1.0

/** Ritmo /100m realista para eventos < 100m (corrección de fatiga 50→100). */
val SPRINT_TO_100 = mapOf(50 to 1.100)
fun racePace100(predicted: Double, distance: Int): Double {
    val naive = predicted / (distance / 100.0)
    return naive * (SPRINT_TO_100[distance] ?: 1.0)
}

/** §4.2 — mejora máxima del CSS por mesociclo, proporción decimal. */
val I_MAX_TABLE = mapOf(
    "beginner" to mapOf(50 to 0.035, 100 to 0.030, 200 to 0.032, 400 to 0.035, 800 to 0.038, 1500 to 0.040),
    "recreational" to mapOf(50 to 0.025, 100 to 0.022, 200 to 0.024, 400 to 0.026, 800 to 0.028, 1500 to 0.030),
    "advanced" to mapOf(50 to 0.015, 100 to 0.013, 200 to 0.015, 400 to 0.017, 800 to 0.019, 1500 to 0.021),
    "competitive" to mapOf(50 to 0.008, 100 to 0.007, 200 to 0.008, 400 to 0.009, 800 to 0.010, 1500 to 0.011),
    "elite" to mapOf(50 to 0.003, 100 to 0.0025, 200 to 0.003, 400 to 0.0035, 800 to 0.004, 1500 to 0.0045),
)

/** §4.3 — multiplicador de mejora por fase del macrociclo. */
val F_FASE = mapOf(
    "base_general" to 0.60,
    "base_especifica" to 0.80,
    "umbral_css" to 1.00,
    "pre_competitivo" to 1.05,
    "taper" to 1.15,
    "extension" to 1.00,
)

/** §2.4 — clasificación de nivel por CSS (s/100m), tabla de crol. */
fun classifyLevel(css100m: Double): String = when {
    css100m > 150 -> "beginner"
    css100m > 120 -> "recreational"
    css100m > 95 -> "advanced"
    css100m > 70 -> "competitive"
    else -> "elite"
}

/** §18 — clasificación de tier por dominancia aeróbica (para notas). */
data class TierInfo(val tier: Int, val aerobic: Double, val desc: String)
val TIER_BY_AEROBIC = mapOf(
    50 to TierInfo(2, 0.05, "Sprint — anaeróbico dominante"),
    100 to TierInfo(2, 0.35, "Sprint-resistencia"),
    200 to TierInfo(2, 0.60, "Mix — transición"),
    400 to TierInfo(1, 0.87, "Aeróbico dominante"),
    800 to TierInfo(1, 0.93, "Aeróbico alto"),
    1500 to TierInfo(1, 0.95, "Aeróbico muy alto"),
)

/** §9.1 — volumen semanal (km) por nivel y fase {min,max}. */
val WEEKLY_VOLUME_KM = mapOf(
    "beginner" to mapOf("base_general" to (10.0 to 20.0), "base_especifica" to (15.0 to 28.0), "umbral_css" to (15.0 to 25.0), "taper" to (5.0 to 12.0)),
    "recreational" to mapOf("base_general" to (18.0 to 32.0), "base_especifica" to (25.0 to 40.0), "umbral_css" to (22.0 to 38.0), "taper" to (8.0 to 18.0)),
    "advanced" to mapOf("base_general" to (25.0 to 45.0), "base_especifica" to (35.0 to 55.0), "umbral_css" to (30.0 to 50.0), "taper" to (12.0 to 25.0)),
    "competitive" to mapOf("base_general" to (35.0 to 55.0), "base_especifica" to (45.0 to 65.0), "umbral_css" to (40.0 to 60.0), "taper" to (15.0 to 30.0)),
    "elite" to mapOf("base_general" to (50.0 to 80.0), "base_especifica" to (60.0 to 90.0), "umbral_css" to (55.0 to 85.0), "taper" to (20.0 to 40.0)),
)

/** §13.2 — patrón de carga 3:1 dentro del mesociclo (semana relativa → % carga). */
val MESO_LOAD_PATTERN = mapOf(1 to 0.77, 2 to 0.875, 3 to 0.975, 0 to 0.55)

/** §20.3 — margen de error de la predicción (s) según banda de semanas. */
fun confidenceMargin(week: Int): Int = when {
    week <= 4 -> 2
    week <= 8 -> 4
    week <= 12 -> 6
    else -> 8
}

/** Estructura fija del macrociclo de 15 semanas: (semana_ini, semana_fin, fase). */
val MACRO_15_PHASES = listOf(
    Triple(1, 3, "base_general"),
    Triple(4, 7, "base_especifica"),
    Triple(8, 11, "umbral_css"),
    Triple(12, 13, "pre_competitivo"),
    Triple(14, 15, "taper"),
)

/** Fase → banda de volumen a usar. */
val PHASE_VOLUME_KEY = mapOf(
    "base_general" to "base_general",
    "base_especifica" to "base_especifica",
    "umbral_css" to "umbral_css",
    "pre_competitivo" to "umbral_css",
    "taper" to "taper",
    "extension" to "umbral_css",
)

val PHASE_LABELS = mapOf(
    "base_general" to "Base general",
    "base_especifica" to "Base especif.",
    "umbral_css" to "Umbral CSS",
    "pre_competitivo" to "Pre-comp.",
    "taper" to "Taper",
    "extension" to "Extensión",
)

/** Normalización de estilo (entrada en español → clave interna). */
val STROKE_ALIASES = mapOf(
    "libre" to "freestyle", "crol" to "freestyle", "freestyle" to "freestyle",
    "espalda" to "backstroke", "dorso" to "backstroke", "backstroke" to "backstroke",
    "mariposa" to "butterfly", "butterfly" to "butterfly",
    "pecho" to "breaststroke", "braza" to "breaststroke", "breaststroke" to "breaststroke",
    "combinado" to "individual_medley", "im" to "individual_medley",
)

/** §7.3 — volumen máximo semanal por estilo y nivel (km). */
val MAX_VOLUME_BY_STROKE = mapOf(
    "freestyle" to mapOf("beginner" to 20.0, "recreational" to 35.0, "advanced" to 55.0, "competitive" to 70.0, "elite" to 90.0),
    "backstroke" to mapOf("beginner" to 18.0, "recreational" to 30.0, "advanced" to 50.0, "competitive" to 65.0, "elite" to 85.0),
    "butterfly" to mapOf("beginner" to 12.0, "recreational" to 20.0, "advanced" to 30.0, "competitive" to 40.0, "elite" to 55.0),
    "breaststroke" to mapOf("beginner" to 15.0, "recreational" to 25.0, "advanced" to 38.0, "competitive" to 50.0, "elite" to 65.0),
    "individual_medley" to mapOf("beginner" to 20.0, "recreational" to 30.0, "advanced" to 45.0, "competitive" to 60.0, "elite" to 80.0),
)
