package com.peakstroke.movil.engine

import java.util.Locale

/** Acepta "mm:ss.cc" o segundos sueltos ("65.3"). Lanza si no es válido. */
fun parseTime(s: String): Double {
    val t = s.trim().replace(",", ".")
    if (":" in t) {
        val (m, sec) = t.split(":", limit = 2)
        return m.trim().toInt() * 60 + sec.trim().toDouble()
    }
    return t.toDouble()
}

/** Formatea segundos como "m:ss.cc". */
fun fmt(seconds: Double): String {
    val m = (seconds / 60).toInt()
    val s = seconds % 60
    return String.format(Locale.US, "%d:%05.2f", m, s)
}
