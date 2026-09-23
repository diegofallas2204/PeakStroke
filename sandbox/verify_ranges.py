"""
sandbox/verify_ranges.py — Verifica el escalado entre distancias del motor
contra el pool, por especialidad (velocidad / medio fondo / fondo).

IDENTIDAD CLAVE: como las zonas (R1..V) son fijas para el atleta, el factor
sobre el ritmo de carrera cumple  zona = ritmo(d) × factor(d)  →
    ritmo(d1) / ritmo(d2) = factor(d2) / factor(d1)
Es decir, los factores ZONE_OVER_RACE implican un ratio de ritmos entre
distancias. El pool da el ratio REAL → comparamos.

    python sandbox/verify_ranges.py
"""
from __future__ import annotations

import sys
import statistics as st
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rankings import build_pool, Athlete
from engine import ZONE_OVER_RACE


def fmt(s: float) -> str:
    m = int(s // 60)
    return f"{m}:{s % 60:05.2f}" if m else f"{s:05.2f}"


# Especialidad por prueba de mayor FINA
def specialty(a: Athlete) -> str | None:
    best_d, best_f = None, -1
    for (d, _s), courses in a.events.items():
        for mk in courses.values():
            if (mk.fina or 0) > best_f:
                best_f, best_d = mk.fina or 0, d
    if best_d is None:
        return None
    if best_d <= 100:
        return "velocidad"
    if best_d <= 400:
        return "medio fondo"
    return "fondo"


SPEC_DISTANCES = {
    "velocidad":   [50, 100, 200],
    "medio fondo": [100, 200, 400],
    "fondo":       [400, 800, 1500],
}

pool = build_pool()
athletes = list(pool.values())

print("\nRitmo de carrera /100m por distancia (mediana del pool, libre LCM)")
print("y RATIO entre distancias consecutivas: REAL (pool) vs MOTOR (factores).\n")

for spec, dists in SPEC_DISTANCES.items():
    group = [a for a in athletes if specialty(a) == spec]
    print("=" * 70)
    print(f"{spec.upper()}   (n={len(group)} atletas con esa especialidad)")
    print("=" * 70)

    # mediana de ritmo/100 por distancia
    paces: dict[int, list[float]] = {d: [] for d in dists}
    for a in group:
        for d in dists:
            mk = a.best(d, "libre", "LCM")
            if mk:
                paces[d].append(mk.seconds / (d / 100))
    med = {d: (st.median(v) if v else None) for d, v in paces.items()}
    line = "  ritmo med:  " + "   ".join(
        f"{d}m {fmt(med[d])}" if med[d] else f"{d}m —" for d in dists
    )
    print(line)

    # ratios consecutivos: real (pareado por atleta) vs motor
    factors = ZONE_OVER_RACE.get(spec, {})
    for d1, d2 in zip(dists, dists[1:]):
        pair = []
        for a in group:
            m1, m2 = a.best(d1, "libre", "LCM"), a.best(d2, "libre", "LCM")
            if m1 and m2:
                pair.append((m2.seconds / (d2 / 100)) / (m1.seconds / (d1 / 100)))
        real = st.median(pair) if pair else None
        # motor: ritmo(d2)/ritmo(d1) = factor(d1)/factor(d2)  (usa R1; igual para toda zona)
        motor = (factors[d1]["R1"] / factors[d2]["R1"]) if (d1 in factors and d2 in factors) else None
        rr = f"{real:.3f}" if real else "—"
        mm = f"{motor:.3f}" if motor else "— (sin factor)"
        diff = f"{(real-motor)/motor*100:+.1f}%" if (real and motor) else ""
        npair = f"n={len(pair)}"
        print(f"  {d1}->{d2}m  ritmo×: REAL {rr}  MOTOR {mm}  {diff}  ({npair})")
    print()
