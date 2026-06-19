"""
sandbox/validate.py — Valida los supuestos del motor contra el pool real.

Con tiempos de competencia (no de entreno) podemos verificar de forma directa:
  1. FACTOR DE PISCINA: ratio real SCM/LCM por prueba vs POOL_FACTOR (0.975).
  2. CSS / UMBRAL: CSS del test 400+50 vs ritmo real de 800 y 1500 (CSS≈1500).
  3. CORRECCIÓN DE ESTILO: dif. real libre↔estilo por 100m vs §7.1.

Todo agrupado por perfil (velocidad / medio fondo / fondo) según la prueba de
mayor FINA del atleta.

    python sandbox/validate.py
"""
from __future__ import annotations

import sys
import statistics as st
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rankings import build_pool, Athlete
from engine import POOL_FACTOR_25, STROKE_TPACE_CORRECTION_S, css_from_test


def fmt(s: float) -> str:
    m = int(s // 60)
    return f"{m}:{s % 60:05.2f}" if m else f"{s:05.2f}"


def profile_of(a: Athlete) -> str:
    """Perfil según la prueba de mayor FINA (o la más larga si no hay FINA)."""
    best_d, best_fina = None, -1
    for (d, _stroke), courses in a.events.items():
        for mk in courses.values():
            f = mk.fina or 0
            if f > best_fina:
                best_fina, best_d = f, d
    if best_d is None:
        return "?"
    if best_d <= 100:
        return "velocidad"
    if best_d <= 400:
        return "medio fondo"
    return "fondo"


def report(title: str, errors: list[float], unit: str = "%") -> None:
    if not errors:
        print(f"  {title:<28} sin datos")
        return
    mean = st.mean(errors)
    mae = st.mean(abs(e) for e in errors)
    sd = st.pstdev(errors)
    print(f"  {title:<28} n={len(errors):>3}  sesgo={mean:+.2f}{unit}  "
          f"|error|={mae:.2f}{unit}  σ={sd:.2f}{unit}")


pool = build_pool()
athletes = list(pool.values())
print(f"\nPool: {len(athletes)} atletas\n")

# ── 1. FACTOR DE PISCINA: SCM/LCM real vs 0.975 ─────────────────────────────
print("=" * 74)
print("1) FACTOR DE PISCINA  (real SCM/LCM vs modelo por especialidad)")
print("   Nota: SCM=enero, LCM=abril → el ratio mezcla viraje + mejora temporal.")
print("=" * 74)
buckets: dict[str, list[float]] = {"velocidad": [], "medio fondo": [], "fondo": []}
all_ratios: list[float] = []
for a in athletes:
    prof = profile_of(a)
    for (d, stroke), courses in a.events.items():
        lcm, scm = courses.get("LCM"), courses.get("SCM")
        if lcm and scm and lcm.seconds > 0:
            ratio = scm.seconds / lcm.seconds
            if 0.90 <= ratio <= 1.05:        # descarta outliers/erratas
                all_ratios.append(ratio)
                if prof in buckets:
                    buckets[prof].append(ratio)
if all_ratios:
    print(f"  GLOBAL   n={len(all_ratios):>3}  ratio medio={st.mean(all_ratios):.4f}  σ={st.pstdev(all_ratios):.4f}")
for prof, rs in buckets.items():
    if rs:
        modelo = POOL_FACTOR_25.get(prof, 0.978)
        print(f"  {prof:<12} n={len(rs):>3}  ratio real={st.mean(rs):.4f}  (modelo {modelo:.4f})")
print()

# ── 2. CSS / UMBRAL: CSS(400+50) vs ritmo real de 800 y 1500 ────────────────
print("=" * 74)
print("2) CSS / UMBRAL  (CSS del test 400+50 LCM vs ritmo real, error %)")
print("   Teoría: CSS ≈ ritmo 1500; 800 algo más rápido que CSS.")
print("=" * 74)
err_1500: list[float] = []
err_800: list[float] = []
examples: list[str] = []
for a in athletes:
    t400 = a.best(400, "libre", "LCM")
    t50 = a.best(50, "libre", "LCM")
    if not (t400 and t50):
        continue
    css = css_from_test(t400.seconds, t50.seconds)   # s/100m
    t1500 = a.best(1500, "libre", "LCM")
    t800 = a.best(800, "libre", "LCM")
    if t1500:
        p1500 = t1500.seconds / 15
        err_1500.append((css - p1500) / p1500 * 100)
        if len(examples) < 8:
            examples.append(
                f"  {a.name:<20} CSS {fmt(css)}  1500-pace {fmt(p1500)}  "
                f"err {(css-p1500)/p1500*100:+.1f}%")
    if t800:
        p800 = t800.seconds / 8
        err_800.append((css - p800) / p800 * 100)
report("CSS vs ritmo 1500", err_1500)
report("CSS vs ritmo 800", err_800)
print("  Ejemplos (CSS vs 1500):")
for e in examples:
    print(e)
print()

# ── 3. CORRECCIÓN DE ESTILO: dif real libre↔estilo /100m vs §7.1 ────────────
print("=" * 74)
print("3) CORRECCIÓN DE ESTILO  (dif. real vs estilo, s/100m vs §7.1)")
print("=" * 74)
stroke_es = {"espalda": "backstroke", "mariposa": "butterfly", "pecho": "breaststroke"}
for stroke_es_name, stroke_key in stroke_es.items():
    diffs: list[float] = []
    for a in athletes:
        for d in (50, 100, 200):
            tf = a.best(d, "libre", "LCM")
            ts = a.best(d, stroke_es_name, "LCM")
            if tf and ts:
                diffs.append((ts.seconds - tf.seconds) / (d / 100))   # s por 100m
    model = STROKE_TPACE_CORRECTION_S[stroke_key]
    if diffs:
        print(f"  {stroke_es_name:<10} n={len(diffs):>3}  real medio={st.mean(diffs):+.1f} s/100m  "
              f"(modelo §7.1 = +{model:.0f})  σ={st.pstdev(diffs):.1f}")
    else:
        print(f"  {stroke_es_name:<10} sin pares libre/estilo")
print()
