"""
check_parity.py — Verifica que el motor Kotlin de la app móvil produce los MISMOS
resultados que el motor Python del sandbox (la fuente de verdad).

Corre un set de casos por ambos motores y compara una "huella" canónica (nivel,
factibilidad, semanas, y por semana: km, F, predicho, ritmo /100 y las 5 zonas,
todo a la precisión que muestra la app). Si difieren, imprime el diff y sale != 0.

Uso:   python sandbox/movil/parity/check_parity.py

Requiere Java en el PATH. Si no hay `kotlinc`, lo descarga una vez a
sandbox/movil/parity/.kotlinc/ (cacheado, ~85 MB, gitignored).
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = HERE.parents[1]                       # .../sandbox
ENGINE_DIR = HERE.parents[0] / "app" / "src" / "main" / "java" / "com" / "peakstroke" / "movil" / "engine"
ENGINE_FILES = ["EngineTables.kt", "ScienceEngine.kt", "TimeUtils.kt", "Report.kt"]
KOTLIN_VERSION = "2.0.21"
CACHE = HERE / ".kotlinc"

# ── Casos de prueba (cubren todas las ramas: meta agresiva, alcanzable, lenta;
#    velocidad/medio fondo/fondo; estilos; piscina 25/50) ──────────────────────
CASES = [
    (100, "libre",     "1:05.30", "1:02.00", "velocidad",   "50"),
    (50,  "mariposa",  "28.50",   "27.00",   "velocidad",   "25"),
    (400, "combinado", "5:10.00", "5:00.00", "medio fondo", "50"),
    (1500,"libre",     "18:00.00","17:30.00","fondo",       "50"),
    (200, "espalda",   "2:20.00", "2:25.00", "medio fondo", "25"),
    (800, "libre",     "9:30.00", "9:10.00", "fondo",       "25"),
    (100, "pecho",     "1:20.00", "1:15.00", "velocidad",   "50"),
]
START_DATE = (2026, 1, 5)
ZONES = ["R1", "R2", "MVO2", "RL", "V"]


# ── Lado Python ───────────────────────────────────────────────────────────────
def python_output() -> str:
    sys.path.insert(0, str(SANDBOX))
    from datetime import date
    from engine import ScienceEngine  # type: ignore

    out: list[str] = []
    for i, (d, s, c, g, p, pool) in enumerate(CASES):
        plan = ScienceEngine().generate_plan(
            current_time=_parse(c), goal_time=_parse(g), distance=d,
            stroke=s, pool=pool, profile=p, start_date=date(*START_DATE),
        )
        out.append(f"CASE {i} {d} {s} {c} {g} {p} {pool}")
        out.append(
            f"event={plan.distance} stroke={plan.stroke} profile={plan.profile} "
            f"level={plan.level} feas={plan.feas_status} total={plan.total_weeks} "
            f"macro={plan.macro_weeks} reached={int(plan.goal_reached)} "
            f"realistic={plan.realistic_final:.2f} physio={plan.physio_ceiling:.2f} "
            f"corr={plan.stroke_correction:.2f}"
        )
        for w in plan.weeks:
            z = w.zones.paces
            zs = " ".join(f"{k}={z[k]:.2f}" for k in ZONES)
            out.append(
                f"W{w.week} {w.week_date.strftime('%d/%m')} {w.phase} "
                f"km={w.planned_km:.1f} f={w.f_fase:.2f} pred={w.predicted_time:.2f} "
                f"rp={w.race_pace_100:.2f} {zs}"
            )
    return "\n".join(out)


def _parse(s: str) -> float:
    s = s.strip().replace(",", ".")
    if ":" in s:
        m, sec = s.split(":")
        return int(m) * 60 + float(sec)
    return float(s)


# ── Lado Kotlin ─────────────────────────────────────────────────────────────--
KOTLIN_MAIN = """
package com.peakstroke.movil.engine
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale
private val DF = DateTimeFormatter.ofPattern("dd/MM")
private fun f(p: String, x: Double) = String.format(Locale.US, p, x)
data class PCase(val d:Int,val s:String,val c:String,val g:String,val p:String,val pool:String)
fun main() {
    val cases = listOf(
__CASES__
    )
    val out = StringBuilder()
    for ((i, cs) in cases.withIndex()) {
        val plan = ScienceEngine().generatePlan(
            currentTime = parseTime(cs.c), goalTime = parseTime(cs.g), distance = cs.d,
            stroke = cs.s, pool = cs.pool, profile = cs.p,
            startDate = LocalDate.of(__YEAR__, __MONTH__, __DAY__),
        )
        out.append("CASE $i ${cs.d} ${cs.s} ${cs.c} ${cs.g} ${cs.p} ${cs.pool}\\n")
        out.append("event=${plan.distance} stroke=${plan.stroke} profile=${plan.profile} " +
            "level=${plan.level} feas=${plan.feasStatus} total=${plan.totalWeeks} " +
            "macro=${plan.macroWeeks} reached=${if (plan.goalReached) 1 else 0} " +
            "realistic=${f("%.2f", plan.realisticFinal)} physio=${f("%.2f", plan.physioCeiling)} " +
            "corr=${f("%.2f", plan.strokeCorrection)}\\n")
        for (w in plan.weeks) {
            val z = w.zones.paces
            val zs = listOf("R1","R2","MVO2","RL","V").joinToString(" ") { "$it=${f("%.2f", z.getValue(it))}" }
            out.append("W${w.week} ${w.weekDate.format(DF)} ${w.phase} " +
                "km=${f("%.1f", w.plannedKm)} f=${f("%.2f", w.fFase)} pred=${f("%.2f", w.predictedTime)} " +
                "rp=${f("%.2f", w.racePace100)} $zs\\n")
        }
    }
    print(out.toString().trimEnd('\\n'))
}
"""


def kotlin_output() -> str:
    kotlinc = _ensure_kotlinc()
    build = HERE / ".build"
    if build.exists():
        shutil.rmtree(build)
    build.mkdir()

    # Generar Main.kt con los casos embebidos (misma fuente que Python).
    cases_kt = ",\n".join(
        f'        PCase({d}, "{s}", "{c}", "{g}", "{p}", "{pool}")'
        for (d, s, c, g, p, pool) in CASES
    )
    main_kt = (
        KOTLIN_MAIN.replace("__CASES__", cases_kt)
        .replace("__YEAR__", str(START_DATE[0]))
        .replace("__MONTH__", str(START_DATE[1]))
        .replace("__DAY__", str(START_DATE[2]))
    )
    (build / "Main.kt").write_text(main_kt, encoding="utf-8")

    srcs = [str(ENGINE_DIR / f) for f in ENGINE_FILES] + [str(build / "Main.kt")]
    jar = build / "parity.jar"
    print("Compilando motor Kotlin…")
    _run([kotlinc, *srcs, "-include-runtime", "-d", str(jar)])
    res = _run(["java", "-jar", str(jar)], capture=True)
    return res.stdout.replace("\r\n", "\n").strip()


def _ensure_kotlinc() -> str:
    exe = "kotlinc.bat" if os.name == "nt" else "kotlinc"
    found = shutil.which("kotlinc") or shutil.which(exe)
    if found:
        return found
    cached = CACHE / "kotlinc" / "bin" / exe
    if cached.exists():
        return str(cached)
    url = (f"https://github.com/JetBrains/kotlin/releases/download/"
           f"v{KOTLIN_VERSION}/kotlin-compiler-{KOTLIN_VERSION}.zip")
    print(f"kotlinc no encontrado; descargando una vez a {CACHE} …")
    CACHE.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as r:        # noqa: S310 (release oficial)
        data = r.read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(CACHE)
    if os.name != "nt":
        os.chmod(cached, 0o755)
        os.chmod(CACHE / "kotlinc" / "bin" / "kotlin", 0o755)
    return str(cached)


def _run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 and not capture:
        sys.stderr.write(r.stdout + "\n" + r.stderr + "\n")
        raise SystemExit(f"Comando falló ({r.returncode}): {cmd[0]}")
    return r


# ── Comparación ───────────────────────────────────────────────────────────────
# Tolerancia para valores numéricos: absorbe el ±0.01 de diferencia de redondeo
# de display entre Python (half-even) y Java (half-up). Un bug real del motor
# produce diferencias mucho mayores y sistemáticas, no de medio centésimo.
TOL = 0.02


def _lines_equal(a: str, b: str) -> bool:
    ta, tb = a.split(), b.split()
    if len(ta) != len(tb):
        return False
    for x, y in zip(ta, tb):
        if x == y:
            continue
        if "=" in x and "=" in y:
            kx, vx = x.split("=", 1)
            ky, vy = y.split("=", 1)
            if kx == ky:
                try:
                    if abs(float(vx) - float(vy)) <= TOL:
                        continue
                except ValueError:
                    pass
        return False
    return True


def main() -> int:
    py = python_output().strip()
    kt = kotlin_output().strip()
    pl, kl = py.split("\n"), kt.split("\n")

    diffs = []
    for i in range(max(len(pl), len(kl))):
        a = pl[i] if i < len(pl) else "<falta>"
        b = kl[i] if i < len(kl) else "<falta>"
        if not _lines_equal(a, b):
            diffs.append((a, b))

    if not diffs:
        print(f"PARITY OK — {len(CASES)} casos, motores Python y Kotlin idénticos "
              f"(±{TOL:.2f} de redondeo de display).")
        return 0

    print(f"PARITY FAIL — {len(diffs)} líneas difieren más de {TOL:.2f}:\n")
    for a, b in diffs[:20]:
        print(f"  py : {a}")
        print(f"  kt : {b}")
    if len(diffs) > 20:
        print("  … (más diferencias omitidas)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
