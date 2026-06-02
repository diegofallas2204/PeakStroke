# -*- coding: utf-8 -*-
"""
test_engine.py -- Script de prueba del motor de progresion PeakStroke.

Ejecutar desde la raíz del proyecto:
    python test_engine.py

Muestra cuatro casos de uso que cubren los dos tiers, distintos estilos
y distintas curvas de progresión.
"""

from datetime import date

from app.services.progression_engine import MacrocyclePlan, ProgressionEngine
from app.utils.time_utils import improvement_str, to_seconds, to_time_str


# ── Helpers de impresión ───────────────────────────────────────────────────

SEP  = "-" * 68
SEP2 = "=" * 68

def print_header() -> None:
    print(f"\n{SEP2}")
    print("  PEAKSTROKE -- Motor de Progresion v1.0")
    print(f"{SEP2}")


def print_plan(plan: MacrocyclePlan) -> None:
    fe = plan.feasibility

    tier_label = (
        "Tier 1 — Aeróbico (regla 1s/micro base aeróbica)"
        if fe.tier == 1
        else "Tier 2 — Velocidad/Mixto (ventana fraccionada)"
    )

    print(f"\n{SEP}")
    print(
        f"  {plan.distance}m {plan.stroke.capitalize():<12}  "
        f"{to_time_str(plan.current_time)} → {to_time_str(plan.target_time)}"
    )
    print(
        f"  {plan.num_weeks} semanas · {plan.weeks_per_microcycle} sem/micro · "
        f"{plan.total_km} km · curva {plan.curve}"
    )
    print(f"{SEP}")

    # ── Análisis de factibilidad ──────────────────────────────────────────
    total_imp = plan.feasibility.total_improvement
    print(f"\n  {tier_label}")
    print(f"  Mejora total requerida : {total_imp:.2f} s  "
          f"({total_imp / plan.current_time * 100:.2f}%)")
    print(f"  Mejora por microciclo  : {fe.improvement_per_micro:.3f} s/micro")

    if fe.window_min is not None and fe.window_max is not None:
        print(f"  Ventana realista       : {fe.window_min:.2f}–{fe.window_max:.2f} s/micro")

    status_color = {"ok": "✓", "warning": "⚡", "aggressive": "⚠"}[fe.status]
    print(f"  Estado                 : [{fe.status.upper()}] {status_color} {fe.message}")

    # ── Plan semanal ───────────────────────────────────────────────────────
    # pace_100m es la referencia central: el entrenador escala series de
    # cualquier distancia multiplicando por (metros/100).
    print(f"\n  {'Sem':>3}  {'Fecha':>6}  {'km':>6}  "
          f"{'T.Prueba':>10}  {'Parcial/100m':>13}  {'R1 /100m':>10}  "
          f"{'Semana':>8}  {'Acum.':>7}")
    print(f"  {'':>3}  {'':>6}  {'':>6}  "
          f"{'(total)':>10}  {'(ref.series)':>13}  {'(aerobico)':>10}  "
          f"{'':>8}  {'':>7}")
    print(f"  {'-'*3}  {'-'*6}  {'-'*6}  {'-'*10}  {'-'*13}  {'-'*10}  {'-'*8}  {'-'*7}")

    for w in plan.weekly_plan:
        fecha = w.week_date.strftime("%d/%m")
        imp   = improvement_str(w.improvement_vs_prev)
        acum  = f"{w.cumulative_improvement:+.2f}s"
        print(
            f"  {w.week_number:>3}  {fecha:>6}  {w.planned_km:>6.1f}  "
            f"{to_time_str(w.expected_time):>10}  "
            f"{to_time_str(w.pace_100m):>13}  "
            f"{to_time_str(w.aerobic_target):>10}  "
            f"{imp:>8}  {acum:>7}"
        )

    # ── Zonas de la última semana competitiva (penúltima) ─────────────────
    peak_week = plan.weekly_plan[-2] if len(plan.weekly_plan) >= 2 else plan.weekly_plan[-1]
    print(f"\n  Zonas de entrenamiento — Semana {peak_week.week_number} "
          f"({peak_week.week_date.strftime('%d/%m')}):")
    print(peak_week.zones.pretty())
    print()


# ── Casos de prueba ────────────────────────────────────────────────────────

def main() -> None:
    engine = ProgressionEngine()
    print_header()

    # ── Caso 1: 100m Mariposa — objetivo AGRESIVO (Tier 2) ────────────────
    print("\n  [CASO 1] Sofía R. — 100m Mariposa — Meta ambiciosa")
    plan1 = engine.analyze(
        distance=100, stroke="mariposa",
        current_time=to_seconds("1:07.80"),
        target_time=to_seconds("1:02.00"),
        num_weeks=12, weeks_per_microcycle=4,
        total_km=320, curve="sigmoid",
        start_date=date(2025, 3, 31),
    )
    print_plan(plan1)

    # ── Caso 2: 100m Mariposa — meta REALISTA (Tier 2, OK) ────────────────
    print("  [CASO 2] Sofía R. — 100m Mariposa — Meta conservadora")
    plan2 = engine.analyze(
        distance=100, stroke="mariposa",
        current_time=to_seconds("1:07.80"),
        target_time=to_seconds("1:05.60"),
        num_weeks=12, weeks_per_microcycle=4,
        total_km=320, curve="sigmoid",
        start_date=date(2025, 3, 31),
    )
    print_plan(plan2)

    # ── Caso 3: 400m Crawl — Tier 1, 18 semanas ───────────────────────────
    print("  [CASO 3] Pedro V. — 400m Libre — Tier 1 aeróbico")
    plan3 = engine.analyze(
        distance=400, stroke="libre",
        current_time=to_seconds("4:55.00"),
        target_time=to_seconds("4:42.00"),
        num_weeks=18, weeks_per_microcycle=4,
        total_km=450, curve="sigmoid",
        start_date=date(2025, 3, 31),
    )
    print_plan(plan3)

    # ── Caso 4: 800m Crawl — Tier 1, curva logarítmica ────────────────────
    print("  [CASO 4] María G. — 800m Libre — Curva logarítmica")
    plan4 = engine.analyze(
        distance=800, stroke="libre",
        current_time=to_seconds("10:20.00"),
        target_time=to_seconds("9:48.00"),
        num_weeks=18, weeks_per_microcycle=4,
        total_km=480, curve="logarithmic",
        start_date=date(2025, 3, 31),
    )
    print_plan(plan4)

    # ── Comparación de curvas para el mismo caso ──────────────────────────
    print(f"\n{SEP}")
    print("  COMPARACIÓN DE CURVAS — 100m Mariposa, meta conservadora")
    print(f"  (Mostrando tiempo esperado semanas 1, 4, 7, 10, 12)")
    print(f"{SEP}")

    semanas_clave = [1, 4, 7, 10, 12]
    print(f"  {'Semana':>6}  {'Lineal':>10}  {'Exponencial':>12}  "
          f"{'Logarítmica':>12}  {'Sigmoidal':>10}")
    print(f"  {'-'*6}  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*10}")

    curve_plans: dict[str, MacrocyclePlan] = {}
    for curve in ["linear", "exponential", "logarithmic", "sigmoid"]:
        curve_plans[curve] = engine.analyze(
            distance=100, stroke="mariposa",
            current_time=to_seconds("1:07.80"),
            target_time=to_seconds("1:05.60"),
            num_weeks=12, weeks_per_microcycle=4,
            total_km=320, curve=curve,  # type: ignore
            start_date=date(2025, 3, 31),
        )

    for sem in semanas_clave:
        row = [f"  {sem:>6}"]
        for curve in ["linear", "exponential", "logarithmic", "sigmoid"]:
            w = curve_plans[curve].weekly_plan[sem - 1]
            row.append(f"{to_time_str(w.expected_time):>12}")
        print("".join(row))

    print(f"\n{SEP2}\n")


if __name__ == "__main__":
    main()
