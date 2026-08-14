"""Sandbox de consola para probar y ajustar el motor de predicción.

Pensado para una sola cosa: dado un tiempo inicial y una meta, ver qué predice
el motor (curva semana a semana + veredicto de factibilidad) y ajustar los
parámetros editando `tuning.json`.

Uso interactivo:
    .venv\\Scripts\\python -m tools.sim_cli
Uso directo (una corrida):
    .venv\\Scripts\\python -m tools.sim_cli --actual 1:05.0 --meta 1:01.0 \\
        --distancia 100 --estilo libre --semanas 16

Flujo de ajuste: corré un escenario -> editá tools/tuning.json en otra ventana
-> presioná 'r' para recargar y recalcular sobre el mismo escenario. Repetí
hasta que las predicciones se sientan bien. El manual PDF explica cada parámetro.
"""
from __future__ import annotations

import argparse
import contextlib
import sys
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

# La consola de Windows usa cp1252 por defecto; forzamos UTF-8 para los símbolos.
with contextlib.suppress(AttributeError, ValueError):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# Permitir `from app...` al correr desde tools/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine.curves import CURVE_LABELS, CURVES
from app.engine.feasibility import analyze_feasibility
from app.engine.progression import generate_plan
from app.engine.time_utils import to_clock, to_seconds
from app.engine.zones import ZONE_LABELS, ZONE_ORDER, zone_factors_for
from tools.tuning_io import TUNING_PATH, apply_tuning, load_tuning

# --- Colores ANSI (degradan a texto plano si la terminal no los soporta) ---
_USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


VERDICT = {
    "ok": ("FACTIBLE", "1;32"),
    "warning": ("EXIGENTE", "1;33"),
    "aggressive": ("AGRESIVO", "1;31"),
}

STROKES = ["libre", "espalda", "mariposa", "pecho", "combinado"]

# Color ANSI por zona (alineado con ZONE_META del frontend).
ZONE_ANSI = {"R1": "32", "R2": "36", "MVO2": "35", "RL": "33", "V": "31"}


@dataclass
class Scenario:
    distance: int = 400
    stroke: str = "libre"
    current: float = to_seconds("4:05.80")
    goal: float = to_seconds("4:03.30")
    weeks: int = 15
    micro: int = 5
    curve: str = "sigmoid"


def render_verdict(s: Scenario) -> None:
    f = analyze_feasibility(s.distance, s.stroke, s.current, s.goal, s.weeks, s.micro)
    label, color = VERDICT.get(f.status, ("—", "0"))
    tier = "Tier 1 (fondo/aeróbico)" if f.tier == 1 else "Tier 2 (velocidad)"
    print(f"\n  VEREDICTO: {_c(label, color)}    [{tier}]")
    print(f"  {f.message}")
    print(
        f"  Mejora total: {_c(f'{f.improvement_total:.2f} s', '1')}"
        f"   |   requerido: {_c(f'{f.improvement_per_micro:.2f} s/micro', '1')}"
        f"   |   techo: {f.window_max:.2f} s/micro"
    )
    if f.window_min is not None:
        print(f"  Ventana realista: {f.window_min:.2f} – {f.window_max:.2f} s/micro")
    if f.recommended_weeks:
        print(
            f"  {_c('Sugerencia:', '1;36')} con este techo necesitarías "
            f"~{f.recommended_weeks} semanas (tenés {s.weeks})."
        )


def build_weeks(s: Scenario) -> list:
    return generate_plan(
        distance=s.distance, current_time=s.current, goal_time=s.goal,
        total_weeks=s.weeks, total_km=40.0, curve=s.curve, start_date=date.today(),
        weeks_per_micro=s.micro,
    )


def render_plan(weeks: list) -> None:
    print(
        f"\n  {'Sem':>3}  {'Fecha':<6}  {'Tiempo':>9}  {'Pace/100':>9}  "
        f"{'Δ prev':>8}  {'Acum':>8}  Fase"
    )
    print("  " + "-" * 62)
    for w in weeks:
        print(
            f"  {w.week_number:>3}  {w.week_date.strftime('%d/%m'):<6}  "
            f"{to_clock(w.expected_time):>9}  {to_clock(w.pace_100m):>9}  "
            f"{w.improvement_vs_prev:>8.2f}  {w.cumulative_improvement:>8.2f}  {w.phase}"
        )


def render_zone_matrix(weeks: list) -> None:
    """Matriz semana x zona con el rango de pace objetivo /100m (min–max).

    Reproduce la tabla de zonas que ve cada atleta, pero para todo el macrociclo
    de un vistazo: es la superficie que se afina con `zonas_entrenamiento`.
    """
    print(f"\n  {_c('Zonas de entrenamiento · pace objetivo /100m (min–max)', '1')}")
    header = f"  {'Sem':>3}  {'Fecha':<6}  " + "  ".join(
        _c(f"{z:^13}", ZONE_ANSI[z]) for z in ZONE_ORDER
    )
    print(header)
    print("  " + "-" * 88)
    for w in weeks:
        cells = []
        for z in ZONE_ORDER:
            rng = w.zones.get(z)
            txt = f"{to_clock(rng['min'], 1)}–{to_clock(rng['max'], 1)}" if rng else "—"
            cells.append(f"{txt:^13}")
        print(
            f"  {w.week_number:>3}  {w.week_date.strftime('%d/%m'):<6}  " + "  ".join(cells)
        )
    print(f"  {_c('Tip:', '2')} usá [z] para el detalle min·mid·max y el factor de una semana.")


def render_zone_detail(s: Scenario, weeks: list, week_no: int) -> None:
    """Desglose vertical de una semana: factor aplicado y min·mid·max por zona."""
    wk = next((w for w in weeks if w.week_number == week_no), weeks[-1])
    factors = zone_factors_for(s.distance)
    print(_c(
        f"\n  Zonas · Semana {wk.week_number} ({wk.week_date.strftime('%d/%m')}) · "
        f"esperado {to_clock(wk.expected_time)} · pace/100 {to_clock(wk.pace_100m)}", "1"))
    print(f"    {'':<4} {'Zona':<20} {'Factor':<16} {'min · mid · max'}")
    for z in ZONE_ORDER:
        tag = _c(f"{z:<4}", ZONE_ANSI[z])
        rng = wk.zones.get(z)
        if rng:
            fr = factors.get(z)
            fac = f"x{fr[0]:.3f}–{fr[1]:.3f}" if fr else ""
            times = (f"{to_clock(rng['min'], 1)} · {to_clock(rng['mid'], 1)} · "
                     f"{to_clock(rng['max'], 1)}")
            print(f"    {tag} {ZONE_LABELS[z]:<20} {fac:<16} {times}")
        else:
            print(f"    {tag} {ZONE_LABELS[z]:<20} {_c('no aplica en esta distancia', '2')}")


def show_scenario(s: Scenario) -> None:
    print(_c("\n" + "═" * 66, "2"))
    print(
        f"  {_c('Escenario', '1')}: {s.distance}m {s.stroke}  ·  curva "
        f"{CURVE_LABELS.get(s.curve, s.curve)}  ·  {s.weeks} sem / micro {s.micro}"
    )
    print(
        f"  Tiempo actual: {_c(to_clock(s.current), '1')}"
        f"   →   Meta: {_c(to_clock(s.goal), '1')}"
    )
    render_verdict(s)
    weeks = build_weeks(s)
    render_plan(weeks)
    render_zone_matrix(weeks)
    print(_c("═" * 66, "2"))


# --- Entrada interactiva ---------------------------------------------------

def _ask(prompt: str, default: str) -> str:
    raw = input(f"  {prompt} [{default}]: ").strip()
    return raw or default


def _ask_choice(prompt: str, default: str, options: list[str]) -> str:
    while True:
        val = _ask(f"{prompt} ({'/'.join(options)})", default)
        if val in options:
            return val
        print(f"    opción inválida; elegí entre: {', '.join(options)}")


def new_scenario(prev: Scenario) -> Scenario:
    print(_c("\n  Nuevo escenario (Enter mantiene el valor previo):", "1;36"))
    distance = int(_ask("Distancia (m)", str(prev.distance)))
    stroke = _ask_choice("Estilo", prev.stroke, STROKES)
    current = to_seconds(_ask("Tiempo actual (m:ss.cc)", to_clock(prev.current)))
    goal = to_seconds(_ask("Tiempo meta (m:ss.cc)", to_clock(prev.goal)))
    weeks = int(_ask("Semanas del macrociclo", str(prev.weeks)))
    micro = int(_ask("Semanas por microciclo", str(prev.micro)))
    curve = _ask_choice("Curva", prev.curve, CURVES)
    return Scenario(distance, stroke, current, goal, weeks, micro, curve)


def show_tuning_summary() -> None:
    data = load_tuning()
    cur = data["curvas"]
    t1 = data["tier1_fondo"]
    t2 = data["tier2_velocidad"]
    print(_c(f"\n  Tuning activo  ({TUNING_PATH}):", "1;36"))
    print(f"    Curvas: k_exp={cur['exponential_k']}  "
          f"log={cur['logarithmic_scale']}  sigmoid={cur['sigmoid_steepness']}")
    print(f"    Tier 1: base={t1['base_por_micro']} s/micro  "
          f"techo×{t1['multiplicador_techo']}")
    print(f"    Tier 2: alerta×{t2['multiplicador_alerta']}  "
          f"ventana_default={t2['ventana_default']}")
    bandas = data.get("zonas_entrenamiento", {})
    print(f"    Zonas: {len(bandas)} bandas de distancia "
          f"({', '.join(sorted(bandas, key=int))} m)")
    print("    (editá el archivo y presioná 'r' para recalcular)")


def interactive_loop(scenario: Scenario) -> None:
    apply_tuning(load_tuning())
    show_scenario(scenario)
    menu = _c(
        "\n  [n] nuevo escenario   [r] recargar tuning   [z] zonas de una semana"
        "   [t] ver tuning   [q] salir",
        "2",
    )
    while True:
        print(menu)
        cmd = input("  > ").strip().lower()
        if cmd in ("q", "quit", "salir", ""):
            break
        if cmd == "n":
            scenario = new_scenario(scenario)
            apply_tuning(load_tuning())
            show_scenario(scenario)
        elif cmd == "r":
            apply_tuning(load_tuning())
            print(_c("  ✓ tuning recargado", "1;32"))
            show_scenario(scenario)
        elif cmd == "z":
            week_no = int(_ask("¿Qué semana? (detalle de zonas)", str(scenario.weeks)))
            render_zone_detail(scenario, build_weeks(scenario), week_no)
        elif cmd == "t":
            show_tuning_summary()
        else:
            print("    comando no reconocido")


def parse_args(argv: list[str]) -> argparse.Namespace:
    # default=None: lo que no se pasa se toma del escenario por defecto (Scenario),
    # para que correr sin argumentos use esos valores de forma consistente.
    p = argparse.ArgumentParser(description="Sandbox de predicción PeakStroke")
    p.add_argument("--actual", help="Tiempo actual (m:ss.cc o segundos)")
    p.add_argument("--meta", help="Tiempo meta (m:ss.cc o segundos)")
    p.add_argument("--distancia", type=int, default=None)
    p.add_argument("--estilo", default=None, choices=STROKES)
    p.add_argument("--semanas", type=int, default=None)
    p.add_argument("--micro", type=int, default=None)
    p.add_argument("--curva", default=None, choices=CURVES)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv or sys.argv[1:])
    base = Scenario()
    scenario = replace(
        base,
        distance=args.distancia if args.distancia is not None else base.distance,
        stroke=args.estilo or base.stroke,
        current=to_seconds(args.actual) if args.actual else base.current,
        goal=to_seconds(args.meta) if args.meta else base.goal,
        weeks=args.semanas if args.semanas is not None else base.weeks,
        micro=args.micro if args.micro is not None else base.micro,
        curve=args.curva or base.curve,
    )
    print(_c("\n  PeakStroke · Simulador de predicciones de entrenamiento", "1;36"))
    if args.actual or args.meta:           # corrida única no interactiva
        apply_tuning(load_tuning())
        show_scenario(scenario)
        return
    try:
        interactive_loop(scenario)
    except (EOFError, KeyboardInterrupt):
        print("\n  Hasta luego.")


if __name__ == "__main__":
    main()
