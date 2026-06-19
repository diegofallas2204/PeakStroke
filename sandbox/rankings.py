"""
sandbox/rankings.py — Parser de los rankings nacionales (HY-TEK Team Manager).

Lee los .md de E:/PeakStroke/Investigación/Ranking-*.md y construye un POOL de
nadadores: cada atleta (identificado por nombre + equipo) con las pruebas que
nada, su mejor tiempo de la temporada por curso (LCM=piscina 50, SCM=piscina 25),
puntos FINA, edad y torneo.

Pruebas que un atleta NO nada → no aparecen → no son su especialidad.

Uso:
    from rankings import build_pool
    pool = build_pool()              # dict[(name_norm, team)] -> Athlete

    python sandbox/rankings.py       # imprime estadísticas + perfil de un atleta
"""
from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RANKING_DIR = Path("E:/PeakStroke/Investigación")
RANKING_GLOB = "Ranking-*.md"

STROKE_MAP = {
    "Free": "libre", "Back": "espalda", "Breast": "pecho",
    "Fly": "mariposa", "IM": "combinado",
}

# ── Regex de parseo ─────────────────────────────────────────────────────────
# Encabezado de prueba: "...Women...50 Free..." o "...Men...200 IM..."
RE_GENDER = re.compile(r"\b(Women|Men)\b")
RE_EVENT = re.compile(r"\b(\d{2,4})\s*(Free|Back|Breast|Fly|IM)\b")
# Tiempo + curso (L=larga/50, S=corta/25): "27.62 L", "4:05.12 L", "x31.63 S"
RE_TIME = re.compile(r"x?(\d+:\d+\.\d+|\d+\.\d+)\s*([LS])\b")
# Cola del atleta: |F|Nombre|Edad|Equipo|  (P/F/S, nombre, edad, equipo)
RE_ATH = re.compile(
    r"\|\s*([FPS])\s*\|\s*([A-Za-zÀ-ÿ.'\- ]+?)\s*\|\s*(\d{1,2})\s*\|\s*([A-Za-z0-9]+)\s*\|"
)


def to_seconds(t: str) -> float:
    t = t.strip()
    if ":" in t:
        m, s = t.split(":")
        return int(m) * 60 + float(s)
    return float(t)


def fmt(sec: float) -> str:
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:05.2f}" if m else f"{s:05.2f}"


def norm_name(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", n).strip().lower()


@dataclass
class Mark:
    seconds: float
    fina: int | None
    course: str          # "LCM" | "SCM"
    age: int
    meet: str


@dataclass
class Athlete:
    name: str
    team: str
    gender: str
    ages: set[int] = field(default_factory=set)
    # (distance, stroke) -> {"LCM": Mark, "SCM": Mark}
    events: dict[tuple[int, str], dict[str, Mark]] = field(default_factory=dict)

    def best(self, distance: int, stroke: str, course: str | None = None) -> Mark | None:
        ev = self.events.get((distance, stroke))
        if not ev:
            return None
        if course:
            return ev.get(course)
        # mejor entre cursos por FINA si no se especifica
        marks = [m for m in ev.values() if m]
        return min(marks, key=lambda m: m.seconds) if marks else None


def _parse_file(path: Path, pool: dict[tuple[str, str], Athlete]) -> int:
    gender = None
    event: tuple[int, str] | None = None
    n_rows = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue

        ath_m = RE_ATH.search(line)
        time_m = RE_TIME.search(line)

        # ¿Fila de datos? (tiene tiempo + cola de atleta)
        if ath_m and time_m:
            if event is None or gender is None:
                continue
            pfs, name, age_s, team = ath_m.groups()
            seconds, course_l = to_seconds(time_m.group(1)), time_m.group(2)
            course = "LCM" if course_l == "L" else "SCM"
            # FINA: primer entero 3-4 dígitos tras el tiempo
            rest = line[time_m.end():]
            fina_m = re.search(r"(\d{3,4})", rest)
            fina = int(fina_m.group(1)) if fina_m else None
            meet_m = re.search(r"(\d{1,2}/\d{1,2}/\d{4}[^|]*)", line)
            meet = meet_m.group(1).strip() if meet_m else ""
            age = int(age_s)

            key = (norm_name(name), team)
            ath = pool.get(key)
            if not ath:
                ath = Athlete(name=name.strip(), team=team, gender=gender)
                pool[key] = ath
            ath.ages.add(age)
            ev = ath.events.setdefault(event, {})
            prev = ev.get(course)
            if prev is None or seconds < prev.seconds:
                ev[course] = Mark(seconds, fina, course, age, meet)
            n_rows += 1
            continue

        # ¿Encabezado de prueba? (Women/Men + distancia + estilo)
        g = RE_GENDER.search(line)
        e = RE_EVENT.search(line)
        if g:
            gender = "F" if g.group(1) == "Women" else "M"
        if e:
            dist = int(e.group(1))
            stroke = STROKE_MAP[e.group(2)]
            event = (dist, stroke)
    return n_rows


def build_pool() -> dict[tuple[str, str], Athlete]:
    pool: dict[tuple[str, str], Athlete] = {}
    files = sorted(RANKING_DIR.glob(RANKING_GLOB))
    for f in files:
        n = _parse_file(f, pool)
        print(f"  {f.name:<40} {n:>4} marcas", file=sys.stderr)
    return pool


# ── CLI: estadísticas + verificación ────────────────────────────────────────

if __name__ == "__main__":
    print("Parseando rankings...", file=sys.stderr)
    pool = build_pool()

    total_marks = sum(
        len(courses) for a in pool.values() for courses in a.events.values()
    )
    n_m = sum(1 for a in pool.values() if a.gender == "M")
    n_f = sum(1 for a in pool.values() if a.gender == "F")
    print(f"\nAtletas: {len(pool)}  (M={n_m}, F={n_f})")
    print(f"Marcas totales (atleta·prueba·curso): {total_marks}")

    # Distribución de # de pruebas por atleta
    from collections import Counter
    spread = Counter(len(a.events) for a in pool.values())
    print("Pruebas por atleta:", dict(sorted(spread.items())))

    # Verificación: Emiliano Fallas (nuestro atleta de referencia)
    print("\n" + "=" * 60)
    target = None
    for a in pool.values():
        if "emiliano fallas" in norm_name(a.name):
            target = a
            break
    if target:
        print(f"  {target.name}  ({target.team}, {target.gender}, edad {sorted(target.ages)})")
        print(f"  {'Prueba':<16} {'LCM (50m)':>12} {'SCM (25m)':>12} {'FINA':>6}")
        print("  " + "-" * 50)
        order = {"libre": 0, "espalda": 1, "pecho": 2, "mariposa": 3, "combinado": 4}
        for (dist, stroke) in sorted(target.events, key=lambda e: (order[e[1]], e[0])):
            ev = target.events[(dist, stroke)]
            lcm = ev.get("LCM")
            scm = ev.get("SCM")
            best = target.best(dist, stroke)
            print(f"  {dist}m {stroke:<10} "
                  f"{fmt(lcm.seconds) if lcm else '—':>12} "
                  f"{fmt(scm.seconds) if scm else '—':>12} "
                  f"{best.fina if best and best.fina else '—':>6}")
    else:
        print("  Emiliano Fallas no encontrado")
    print("=" * 60)
