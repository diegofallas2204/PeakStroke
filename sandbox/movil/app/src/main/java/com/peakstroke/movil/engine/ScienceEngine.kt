package com.peakstroke.movil.engine

import java.math.BigDecimal
import java.math.RoundingMode
import java.time.LocalDate
import java.util.Locale
import kotlin.math.abs
import kotlin.math.ceil

/**
 * Motor de progresión — port directo de ScienceEngine en sandbox/engine.py.
 * Zonas ancladas al ritmo de carrera del evento (sem 1 = actual, sem N = meta).
 */

data class WeekZones(
    val css: Double,
    val paces: Map<String, Double>,   // clave de zona → s/100m
)

data class WeekRow(
    val week: Int,
    val weekDate: LocalDate,
    val phase: String,
    val fFase: Double,
    val plannedKm: Double,
    val improvementIndex: Double,
    val predictedTime: Double,
    val margin: Int,
    val cssN: Double,
    val racePace100: Double,
    val zones: WeekZones,
) {
    val isExtension: Boolean get() = phase == "extension"
}

data class PlanResult(
    val distance: Int,
    val stroke: String,
    val profile: String,
    val pool: String,
    val strokeCorrection: Double,
    val currentTime: Double,
    val goalTime: Double,
    val css0: Double,
    val level: String,
    val feasStatus: String,
    val feasMessage: String,
    val predictedFinal: Double,
    val realisticFinal: Double,
    val physioCeiling: Double,
    val totalWeeks: Int,
    val macroWeeks: Int,
    val goalReached: Boolean,
    val weeks: List<WeekRow>,
)

class ScienceEngine {

    companion object {
        const val TOTAL_WEEKS = 15
        const val MAX_EXTENSION_WEEKS = 30
    }

    private fun nearestEvent(distance: Int): Int {
        val known = I_MAX_TABLE.getValue("elite").keys.sorted()
        return known.minByOrNull { abs(it - distance) }!!
    }

    private fun phaseForWeek(week: Int): String {
        for ((ini, fin, phase) in MACRO_15_PHASES) {
            if (week in ini..fin) return phase
        }
        return "umbral_css"
    }

    private fun zonesFromRace(
        racePace: Double, profile: String, distance: Int, strokeKey: String, pool: String
    ): WeekZones {
        val factors = zoneFactors(profile, distance)
        val corr = STROKE_TPACE_CORRECTION_S[strokeKey] ?: 0.0
        val pf = poolFactor(profile, pool)
        return WeekZones(
            css = racePace,
            paces = factors.mapValues { (_, f) -> (racePace * f + corr) * pf },
        )
    }

    private fun weeklyKm(level: String, phase: String, week: Int, strokeKey: String): Double {
        val (vmin, vmax) = WEEKLY_VOLUME_KM.getValue(level).getValue(PHASE_VOLUME_KEY.getValue(phase))
        val mid = (vmin + vmax) / 2.0
        val load = MESO_LOAD_PATTERN.getValue(week % 4)
        val km = mid * load
        val cap = MAX_VOLUME_BY_STROKE.getValue(strokeKey).getValue(level)
        // round(x, 1) de Python usa banker's rounding (HALF_EVEN), no half-up.
        return BigDecimal.valueOf(minOf(km, cap)).setScale(1, RoundingMode.HALF_EVEN).toDouble()
    }

    private fun checkFeasibility(current: Double, goal: Double, event: Int, level: String): Pair<String, String> {
        val pct = (current - goal) / current
        val numMeso = TOTAL_WEEKS / 5.0
        val iMaxTotal = I_MAX_TABLE.getValue(level).getValue(event) * numMeso
        val ratio = if (iMaxTotal != 0.0) pct / iMaxTotal else 999.0
        return when {
            ratio <= 0.85 -> "ok" to String.format(
                Locale.US,
                "Realista — pides %.2f%% y el techo científico para %s/%dm en 15 sem es %.2f%% (uso %.0f%%).",
                pct * 100, level, event, iMaxTotal * 100, ratio * 100
            )
            ratio <= 1.15 -> "warning" to String.format(
                Locale.US,
                "Exigente — pides %.2f%%, cerca del techo %.2f%% (%.0f%% del máximo).",
                pct * 100, iMaxTotal * 100, ratio * 100
            )
            else -> "aggressive" to String.format(
                Locale.US,
                "Agresivo — pides %.2f%%, supera el techo %.2f%% (%.0f%%). Considera más semanas o una meta menos ambiciosa.",
                pct * 100, iMaxTotal * 100, ratio * 100
            )
        }
    }

    fun generatePlan(
        currentTime: Double,
        goalTime: Double,
        distance: Int,
        stroke: String,
        pool: String = "50",
        profile: String? = null,
        startDate: LocalDate = LocalDate.now(),
    ): PlanResult {
        val event = nearestEvent(distance)
        val strokeKey = STROKE_ALIASES[stroke.lowercase().trim()] ?: "freestyle"
        val prof = profile ?: profileForEvent(event)
        val strokeCorr = STROKE_TPACE_CORRECTION_S[strokeKey] ?: 0.0

        val racePace0 = currentTime / (distance / 100.0)
        val threshold = racePace0 * zoneFactors(prof, distance).getValue("MVO2")
        val level = classifyLevel(threshold)
        val css0 = racePace0
        val (feasStatus, feasMsg) = checkFeasibility(currentTime, goalTime, event, level)

        val weights = (1..TOTAL_WEEKS).map { F_FASE.getValue(phaseForWeek(it)) }
        val denom = weights.take(TOTAL_WEEKS - 1).sum().let { if (it == 0.0) 1.0 else it }

        fun cumFrac(w: Int): Double = weights.take(w - 1).sum() / denom

        val iMaxTotal = I_MAX_TABLE.getValue(level).getValue(event) * (TOTAL_WEEKS / 5.0)
        val safeTotal = currentTime * iMaxTotal
        val realisticCeiling = currentTime - safeTotal
        val requested = currentTime - goalTime

        fun buildWeek(absWeek: Int, phase: String, predicted: Double): WeekRow {
            val racePaceN = predicted / (distance / 100.0)
            return WeekRow(
                week = absWeek,
                weekDate = startDate.plusWeeks((absWeek - 1).toLong()),
                phase = phase,
                fFase = F_FASE.getValue(phase),
                plannedKm = weeklyKm(level, phase, absWeek, strokeKey),
                improvementIndex = if (requested > 0) (currentTime - predicted) / requested else 0.0,
                predictedTime = predicted,
                margin = confidenceMargin(absWeek),
                cssN = racePaceN,
                racePace100 = racePace100(predicted, distance),
                zones = zonesFromRace(racePaceN, prof, distance, strokeKey, pool),
            )
        }

        val rows = mutableListOf<WeekRow>()
        var goalReached = true
        val macroWeeks: Int

        if (requested <= 0) {
            for (w in 1..TOTAL_WEEKS) {
                val predicted = currentTime - requested * cumFrac(w)
                rows.add(buildWeek(w, phaseForWeek(w), predicted))
            }
            macroWeeks = TOTAL_WEEKS
        } else if (requested <= safeTotal) {
            var n = TOTAL_WEEKS
            for (w in 2..TOTAL_WEEKS) {
                if (safeTotal * cumFrac(w) >= requested - 1e-9) {
                    n = w
                    break
                }
            }
            val fracN = cumFrac(n).let { if (it == 0.0) 1.0 else it }
            for (w in 1..n) {
                val predicted = currentTime - requested * (cumFrac(w) / fracN)
                var phase = phaseForWeek(w)
                if (w == n && n < TOTAL_WEEKS) phase = "taper"
                rows.add(buildWeek(w, phase, predicted))
            }
            macroWeeks = n
        } else {
            for (w in 1..TOTAL_WEEKS) {
                val predicted = currentTime - safeTotal * cumFrac(w)
                rows.add(buildWeek(w, phaseForWeek(w), predicted))
            }
            macroWeeks = TOTAL_WEEKS

            val extraRate = safeTotal / TOTAL_WEEKS
            val remaining = realisticCeiling - goalTime
            var nExt = if (extraRate > 0) ceil(remaining / extraRate).toInt() else 0
            nExt = minOf(nExt, MAX_EXTENSION_WEEKS)
            for (j in 1..nExt) {
                val absWeek = TOTAL_WEEKS + j
                val predicted = maxOf(realisticCeiling - extraRate * j, goalTime)
                rows.add(buildWeek(absWeek, "extension", predicted))
            }
            goalReached = rows.isNotEmpty() && rows.last().predictedTime <= goalTime + 1e-6
        }

        return PlanResult(
            distance = event,
            stroke = strokeKey,
            profile = prof,
            pool = pool,
            strokeCorrection = strokeCorr,
            currentTime = currentTime,
            goalTime = goalTime,
            css0 = css0,
            level = level,
            feasStatus = feasStatus,
            feasMessage = feasMsg,
            predictedFinal = rows.last().predictedTime,
            realisticFinal = realisticCeiling,
            physioCeiling = realisticCeiling,
            totalWeeks = rows.size,
            macroWeeks = macroWeeks,
            goalReached = goalReached,
            weeks = rows,
        )
    }
}
