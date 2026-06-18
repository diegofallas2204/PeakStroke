
package com.peakstroke.movil.engine
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale
private val DF = DateTimeFormatter.ofPattern("dd/MM")
private fun f(p: String, x: Double) = String.format(Locale.US, p, x)
data class PCase(val d:Int,val s:String,val c:String,val g:String,val p:String,val pool:String)
fun main() {
    val cases = listOf(
        PCase(100, "libre", "1:05.30", "1:02.00", "velocidad", "50"),
        PCase(50, "mariposa", "28.50", "27.00", "velocidad", "25"),
        PCase(400, "combinado", "5:10.00", "5:00.00", "medio fondo", "50"),
        PCase(1500, "libre", "18:00.00", "17:30.00", "fondo", "50"),
        PCase(200, "espalda", "2:20.00", "2:25.00", "medio fondo", "25"),
        PCase(800, "libre", "9:30.00", "9:10.00", "fondo", "25"),
        PCase(100, "pecho", "1:20.00", "1:15.00", "velocidad", "50")
    )
    val out = StringBuilder()
    for ((i, cs) in cases.withIndex()) {
        val plan = ScienceEngine().generatePlan(
            currentTime = parseTime(cs.c), goalTime = parseTime(cs.g), distance = cs.d,
            stroke = cs.s, pool = cs.pool, profile = cs.p,
            startDate = LocalDate.of(2026, 1, 5),
        )
        out.append("CASE $i ${cs.d} ${cs.s} ${cs.c} ${cs.g} ${cs.p} ${cs.pool}\n")
        out.append("event=${plan.distance} stroke=${plan.stroke} profile=${plan.profile} " +
            "level=${plan.level} feas=${plan.feasStatus} total=${plan.totalWeeks} " +
            "macro=${plan.macroWeeks} reached=${if (plan.goalReached) 1 else 0} " +
            "realistic=${f("%.2f", plan.realisticFinal)} physio=${f("%.2f", plan.physioCeiling)} " +
            "corr=${f("%.2f", plan.strokeCorrection)}\n")
        for (w in plan.weeks) {
            val z = w.zones.paces
            val zs = listOf("R1","R2","MVO2","RL","V").joinToString(" ") { "$it=${f("%.2f", z.getValue(it))}" }
            out.append("W${w.week} ${w.weekDate.format(DF)} ${w.phase} " +
                "km=${f("%.1f", w.plannedKm)} f=${f("%.2f", w.fFase)} pred=${f("%.2f", w.predictedTime)} " +
                "rp=${f("%.2f", w.racePace100)} $zs\n")
        }
    }
    print(out.toString().trimEnd('\n'))
}
