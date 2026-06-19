"""
sandbox/run.py — Calculadora de debug del motor (zonas ancladas al ritmo de carrera).

Macro FIJO de 15 semanas, un atleta. Las zonas se derivan del TIEMPO DEL EVENTO:
sem 1 desde el tiempo actual, sem 15 desde la meta, interpolando con el índice de
mejora (pesos F_FASE). Así el ritmo de entreno de cada semana coincide con el
tiempo de competencia que el atleta puede hacer esa semana.

Entradas: prueba+estilo (estilo limitado por distancia) · actual · meta · perfil
          · piscina.   (Sin test CSS ni 12×400.)

Ciencia en sandbox/engine.py (ZONE_OVER_RACE, STROKE_TPACE_*, I_MAX_TABLE…).
Ejecutar desde la raíz:  python sandbox/run.py
"""
from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import (
    ScienceEngine,
    allowed_strokes,
    profile_for_event,
    zone_factors,
    ZONE_OVER_RACE,
    PROFILE_FUENTE,
    TIER_BY_AEROBIC,
    PHASE_LABELS,
    ZONE_LABELS,
)


def parse_time(s: str) -> float:
    """Acepta 'mm:ss.cc' o segundos sueltos ('65.3')."""
    s = s.strip().replace(",", ".")
    if ":" in s:
        m, sec = s.split(":")
        return int(m) * 60 + float(sec)
    return float(s)


def fmt(seconds: float) -> str:
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:05.2f}"


# ── Entrada ─────────────────────────────────────────────────────────────────

print("=" * 74)
print("  PeakStroke — Calculadora debug (zonas ancladas al ritmo, macro 15 sem)")
print("=" * 74)

distance = int(input("Prueba (m) [50/100/200/400/800/1500]:        ").strip())

strokes = allowed_strokes(distance)
if len(strokes) == 1:
    stroke = strokes[0]
    print(f"Estilo:                                      {stroke} (único para {distance}m)")
else:
    stroke = (input(f"Estilo [{'/'.join(strokes)}]: ").strip().lower() or strokes[0])

current = parse_time(input("Tiempo actual (mm:ss.cc):                    ").strip())
goal    = parse_time(input("Tiempo meta   (mm:ss.cc):                    ").strip())

sug = profile_for_event(distance)
prof_in = input(f"Perfil [velocidad/medio fondo/fondo] (def {sug}): ").strip().lower()
profile = prof_in if prof_in in ZONE_OVER_RACE else sug

pool = (input("Piscina [50/25]:                             ").strip() or "50")

plan = ScienceEngine().generate_plan(
    current_time=current,
    goal_time=goal,
    distance=distance,
    stroke=stroke,
    profile=profile,
    pool=pool,
)

# ── Cabecera / diagnóstico ──────────────────────────────────────────────────

tier = TIER_BY_AEROBIC.get(plan.distance, {})
verdict = {"ok": "✓ OK", "warning": "⚡ EXIGENTE", "aggressive": "⚠ AGRESIVO"}[plan.feas_status]
delta_goal = current - goal
ceil_gain = current - plan.physio_ceiling

print()
print("=" * 74)
print(f"  Prueba:        {plan.distance}m {plan.stroke}   ({tier.get('desc','')}, tier {tier.get('tier','?')})")
print(f"  Actual → Meta: {fmt(current)} → {fmt(goal)}   (mejora pedida: {delta_goal:.2f}s, {delta_goal/current*100:.2f}%)")
print(f"  Perfil:        {plan.profile.upper()}  [{PROFILE_FUENTE[plan.profile]}]")
print(f"  Piscina:       {plan.pool}m"
      + (f"  ·  Estilo {plan.stroke}: +{plan.stroke_correction:.1f}s sobre crol" if plan.stroke_correction else ""))
print(f"  Nivel:         {plan.level.upper()}")
print(f"  Factibilidad:  {verdict}")
print(f"    {plan.feas_message}")
print("-" * 74)
if plan.total_weeks > plan.macro_weeks:
    # Meta agresiva: el macro cierra en el tiempo realista; el resto son semanas extra.
    n_ext = plan.total_weeks - plan.macro_weeks
    print(f"  Macro ({plan.macro_weeks} sem): {fmt(current)} → {fmt(plan.realistic_final)}  (techo realista)")
    tail = "" if plan.goal_reached else "  ⚠ meta NO alcanzada ni con el máx. de extensión"
    print(f"  + {n_ext} sem EXTRA (extensión) → meta {fmt(plan.goal_time)}{tail}")
elif plan.total_weeks < ScienceEngine.TOTAL_WEEKS:
    # Meta alcanzable antes de las 15 semanas: se recortó el macro.
    print(f"  Plan {plan.total_weeks} sem (meta alcanzable antes de 15): "
          f"{fmt(current)} → {fmt(plan.predicted_final)}")
else:
    print(f"  Plan {plan.total_weeks} sem: {fmt(current)} → {fmt(plan.predicted_final)}")
print(f"  Techo físico (I_max, informativo): hasta {fmt(plan.physio_ceiling)} "
      f"(mejora máx {ceil_gain:.2f}s vs meta {delta_goal:.2f}s)")
print("=" * 74)
print()

# ── Zonas extremas: del tiempo ACTUAL vs del tiempo META ────────────────────

zone_keys = list(ZONE_LABELS.keys())
z1 = plan.weeks[0].zones      # derivadas del tiempo actual
z15 = plan.weeks[-1].zones    # derivadas del tiempo meta
corr = plan.stroke_correction
print(f"Zonas de entrenamiento — perfil {plan.profile.upper()}, piscina {plan.pool}m"
      + (f", estilo +{corr:.1f}s" if corr else "") + ":")
print(f"  {'Zona':<5} {'desde ACTUAL':>14} {'desde META':>14}")
print("  " + "-" * 36)
for k in zone_keys:
    print(f"  {ZONE_LABELS[k]:<5} {fmt(z1.paces[k]):>14} {fmt(z15.paces[k]):>14}")
print()

# ── Tabla semana a semana ───────────────────────────────────────────────────

header = (
    f"{'Sem':>3} {'Fecha':>6} {'Fase':<14} {'Km':>5} {'F':>4} "
    f"{'Predicho':>11} {'/100':>7} " + " ".join(f"{ZONE_LABELS[k]:>8}" for k in zone_keys)
)
print(header)
print("-" * len(header))

prev_phase = None
ext_marked = False
for w in plan.weeks:
    z = w.zones
    if w.is_extension and not ext_marked:
        print("  " + "·" * (len(header) - 2) + "  ← semanas EXTRA (meta supera el techo del macro)")
        ext_marked = True
    phase_lbl = PHASE_LABELS[w.phase] if w.phase != prev_phase else ""
    prev_phase = w.phase
    pred = f"{fmt(w.predicted_time)}±{w.margin}"
    zone_cells = " ".join(f"{fmt(z.paces[k]):>8}" for k in zone_keys)
    print(
        f"{w.week:>3} {w.week_date.strftime('%d/%m'):>6} {phase_lbl:<14} "
        f"{w.planned_km:>5.1f} {w.f_fase:>4.2f} "
        f"{pred:>11} {fmt(w.race_pace_100):>7} {zone_cells}"
    )

print()
macro_km = sum(w.planned_km for w in plan.weeks if not w.is_extension)
ext_km = sum(w.planned_km for w in plan.weeks if w.is_extension)
print(f"Volumen del macro ({plan.macro_weeks} sem): {macro_km:.1f} km"
      + (f"  ·  extensión: {ext_km:.1f} km" if ext_km else ""))
print("Zonas = ritmo de carrera de la semana × factor(perfil); '/100' = ritmo /100m REALISTA")
print("(en velocidad <100m proyecta a 100m con fatiga, no un simple ×2).")
print("Macro hasta el techo realista · semanas EXTRA (si las hay) cierran la meta agresiva.")
print()
