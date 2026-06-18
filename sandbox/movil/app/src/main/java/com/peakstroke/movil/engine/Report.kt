package com.peakstroke.movil.engine

import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Construye las secciones de texto del reporte, replicando la salida de
 * sandbox/run.py. Las tablas se devuelven en monoespaciado para alinear columnas.
 */
data class Report(
    val diagnosis: String,
    val zonesTable: String,
    val weekTable: String,
    val footer: String,
)

private val DATE_FMT = DateTimeFormatter.ofPattern("dd/MM")

fun buildReport(plan: PlanResult): Report {
    val current = plan.currentTime
    val goal = plan.goalTime
    val tier = TIER_BY_AEROBIC[plan.distance]
    val verdict = when (plan.feasStatus) {
        "ok" -> "✓ OK"
        "warning" -> "⚡ EXIGENTE"
        else -> "⚠ AGRESIVO"
    }
    val deltaGoal = current - goal
    val ceilGain = current - plan.physioCeiling

    // ── Diagnóstico ──────────────────────────────────────────────────────────
    val d = StringBuilder()
    d.appendLine("Prueba:        ${plan.distance}m ${plan.stroke}   (${tier?.desc ?: ""}, tier ${tier?.tier ?: "?"})")
    d.appendLine(String.format(Locale.US,
        "Actual → Meta: %s → %s   (mejora pedida: %.2fs, %.2f%%)",
        fmt(current), fmt(goal), deltaGoal, deltaGoal / current * 100))
    d.appendLine("Perfil:        ${plan.profile.uppercase()}  [${PROFILE_FUENTE[plan.profile]}]")
    d.append("Piscina:       ${plan.pool}m")
    if (plan.strokeCorrection != 0.0) {
        d.append(String.format(Locale.US, "  ·  Estilo ${plan.stroke}: +%.1fs sobre crol", plan.strokeCorrection))
    }
    d.appendLine()
    d.appendLine("Nivel:         ${plan.level.uppercase()}")
    d.appendLine("Factibilidad:  $verdict")
    d.appendLine("  ${plan.feasMessage}")
    d.appendLine("──────────────────────────────────────────")
    when {
        plan.totalWeeks > plan.macroWeeks -> {
            val nExt = plan.totalWeeks - plan.macroWeeks
            d.appendLine("Macro (${plan.macroWeeks} sem): ${fmt(current)} → ${fmt(plan.realisticFinal)}  (techo realista)")
            val tail = if (plan.goalReached) "" else "  ⚠ meta NO alcanzada ni con el máx. de extensión"
            d.appendLine("+ $nExt sem EXTRA (extensión) → meta ${fmt(plan.goalTime)}$tail")
        }
        plan.totalWeeks < ScienceEngine.TOTAL_WEEKS ->
            d.appendLine("Plan ${plan.totalWeeks} sem (meta alcanzable antes de 15): ${fmt(current)} → ${fmt(plan.predictedFinal)}")
        else ->
            d.appendLine("Plan ${plan.totalWeeks} sem: ${fmt(current)} → ${fmt(plan.predictedFinal)}")
    }
    d.append(String.format(Locale.US,
        "Techo físico (I_max, informativo): hasta %s (mejora máx %.2fs vs meta %.2fs)",
        fmt(plan.physioCeiling), ceilGain, deltaGoal))

    // ── Zonas extremas: desde ACTUAL vs desde META ─────────────────────────────
    val z1 = plan.weeks.first().zones
    val z15 = plan.weeks.last().zones
    val zt = StringBuilder()
    zt.appendLine(String.format("  %-5s %14s %14s", "Zona", "desde ACTUAL", "desde META"))
    zt.appendLine("  " + "-".repeat(36))
    for (k in ZONE_KEYS) {
        zt.appendLine(String.format("  %-5s %14s %14s", k, fmt(z1.paces.getValue(k)), fmt(z15.paces.getValue(k))))
    }

    // ── Tabla semana a semana ──────────────────────────────────────────────────
    val wt = StringBuilder()
    val header = String.format("%3s %6s %-14s %5s %4s %11s %7s ", "Sem", "Fecha", "Fase", "Km", "F", "Predicho", "/100") +
        ZONE_KEYS.joinToString(" ") { String.format("%8s", it) }
    wt.appendLine(header)
    wt.appendLine("-".repeat(header.length))

    var prevPhase: String? = null
    var extMarked = false
    for (w in plan.weeks) {
        val z = w.zones
        if (w.isExtension && !extMarked) {
            wt.appendLine("  " + "·".repeat(header.length - 2) + "  ← semanas EXTRA")
            extMarked = true
        }
        val phaseLbl = if (w.phase != prevPhase) PHASE_LABELS.getValue(w.phase) else ""
        prevPhase = w.phase
        val pred = "${fmt(w.predictedTime)}±${w.margin}"
        val zoneCells = ZONE_KEYS.joinToString(" ") { String.format("%8s", fmt(z.paces.getValue(it))) }
        wt.appendLine(String.format(
            Locale.US,
            "%3d %6s %-14s %5.1f %4.2f %11s %7s %s",
            w.week, w.weekDate.format(DATE_FMT), phaseLbl,
            w.plannedKm, w.fFase, pred, fmt(w.racePace100), zoneCells
        ))
    }

    // ── Footer ────────────────────────────────────────────────────────────────
    val macroKm = plan.weeks.filter { !it.isExtension }.sumOf { it.plannedKm }
    val extKm = plan.weeks.filter { it.isExtension }.sumOf { it.plannedKm }
    val f = StringBuilder()
    f.append(String.format(Locale.US, "Volumen del macro (${plan.macroWeeks} sem): %.1f km", macroKm))
    if (extKm > 0) f.append(String.format(Locale.US, "  ·  extensión: %.1f km", extKm))
    f.appendLine()
    f.appendLine("Zonas = ritmo de carrera de la semana × factor(perfil); '/100' = ritmo /100m REALISTA")
    f.append("(en velocidad <100m proyecta a 100m con fatiga, no un simple ×2).")

    return Report(
        diagnosis = d.toString(),
        zonesTable = zt.toString().trimEnd(),
        weekTable = wt.toString().trimEnd(),
        footer = f.toString(),
    )
}
