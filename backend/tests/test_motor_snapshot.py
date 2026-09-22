"""Snapshot de referencia del motor — red de seguridad para la refactorización.

Los tests del motor comprueban sobre todo INVARIANTES (la curva es monótona, R1
es más lento que V, la meta agresiva cierra en el techo). Eso detecta un motor
roto, pero no detecta un motor que devuelve **otro número plausible**, que es el
modo de fallo de una reestructuración. Este archivo cierra ese hueco: congela la
salida COMPLETA de los cuatro caminos de cálculo sobre una batería de casos
representativos, y falla diciendo qué caso y qué campo cambió.

Un fichero de referencia por camino, porque un diff mezclado no se lee:

  · `MotorCientifico.generar_plan`        → `snapshots/motor_progression.json`
  · `MotorCientifico.recalcular_desde`    → `snapshots/motor_recalculo.json`
  · `MotorCientifico.proyectar_temporada` → `snapshots/motor_temporada.json`

**Los archivos de referencia no se han tocado en la fusión** (C4): los tres
caminos que quedan siguen comparándose contra el JSON que se generó con los
motores viejos, y por eso el `_en_ingles` de abajo traduce las claves del
dataclass nuevo. Un snapshot regenerado no demuestra nada; uno que sobrevive a
la reescritura del motor, sí.

**Se regeneraron una vez, en P3 (2026-09-22), y solo por la fase.** Las fases
por defecto pasaron de los cuatro tramos de interfaz a las cinco de la ciencia,
así que `phase` cambió de texto en todas las semanas y apareció `phase_key` (la
clave que se guarda). Antes de regenerar se comprobó que no se movía **ningún
otro campo** de ningún caso, y el diff de git lo confirma: todas sus líneas son
de `phase`. Los números siguen siendo los que dieron los motores de antes de C4.

El cuarto camino era `ScienceEngine.generate_plan` (`motor_science.json`) y se
retiró **con su algoritmo**: la fusión lo absorbió, así que congelaba una salida
que ya no puede producirse. Lo que de él sobrevive —la forma F_FASE, la
extensión a ritmo seguro y el techo— lo cubren los otros tres caminos,
`test_engine.py` y `test_reglas_unicas.py`.

`ScienceEngine.generate_plan` no recibe `curve` ni `total_weeks` (siempre 15
semanas + curva F_FASE), así que los casos que solo varían en esos dos ejes
producen la misma salida científica; la duplicación se conserva a propósito para
que las dos referencias de plan lleven la misma lista de casos.

El catálogo de casos vive en `tests/motor_casos.py`: qué se congela se decide
allí, cómo se congela y se compara, aquí.

REGENERAR A PROPÓSITO
---------------------
Los ficheros de referencia NO se actualizan solos: un cambio de número es un
fallo hasta que alguien lo declare intencional. Para reescribirlos::

    # PowerShell
    $env:PEAKSTROKE_UPDATE_SNAPSHOTS=1
    .venv\\Scripts\\python -m pytest tests/test_motor_snapshot.py
    Remove-Item Env:\\PEAKSTROKE_UPDATE_SNAPSHOTS

    # bash
    PEAKSTROKE_UPDATE_SNAPSHOTS=1 .venv/Scripts/python -m pytest tests/test_motor_snapshot.py

Después hay que **leer el diff en git**: es la lista exacta de lo que cambió el
comportamiento del motor. Si el diff no se entiende, la refactorización no era
neutra.
"""
from __future__ import annotations

import json
import os
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from motor_casos import (
    LEVEL_CLAIMS,
    PLAN_CASES,
    RECALC_CASES,
    SEASON_CASES,
    START_DATE,
    Case,
    RecalcCase,
    SeasonCase,
)

from app.dominio.servicios.envolvente import nivel_de
from app.dominio.servicios.motor import MOTOR

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"
UPDATE_ENV = "PEAKSTROKE_UPDATE_SNAPSHOTS"
DECIMALS = 6            # redondeo estable al serializar
MAX_DIFF_LINES = 12     # diferencias que se enseñan antes de resumir


# ── Ejecución de cada camino del motor ───────────────────────────────────────

# El JSON de referencia se escribió con los nombres del `WeekEntry` viejo. La
# fusión cambió el dataclass, no los números, así que se traduce aquí en vez de
# regenerar el archivo: mantenerlo intacto es lo que hace que el snapshot
# demuestre algo.
_CLAVES_EN_INGLES = {
    "numero": "week_number", "fecha": "week_date", "tiempo_esperado": "expected_time",
    "ritmo_100": "pace_100m", "km": "planned_km",
    # P3: la fase se desdobló en su clave y en el nombre que se enseña; `phase`
    # sigue siendo lo que se enseña y `phase_key` es lo que se guarda.
    "fase": "phase_key", "nombre_fase": "phase",
    "mejora_vs_anterior": "improvement_vs_prev",
    "mejora_acumulada": "cumulative_improvement",
    "zonas": "zones", "deshabilitada": "disabled",
}


def _en_ingles(semana) -> dict[str, Any]:
    return {_CLAVES_EN_INGLES[k]: v for k, v in asdict(semana).items()}


def _plan(case: Case):
    return MOTOR.generar_plan(
        case.distance, case.current_time, case.goal_time, case.total_weeks,
        case.total_km, case.curve, START_DATE, estilo=case.stroke, piscina=case.pool,
        n_mac=case.n_mac, edad=case.age,
    )


def _run_progression(case: Case) -> dict[str, Any]:
    return {"entrada": case.entrada(), "semanas": [_en_ingles(s) for s in _plan(case)]}


def _run_recalculo(case: RecalcCase) -> dict[str, Any]:
    """Plan base + recálculo. `recalculate_remaining` muta la lista y la devuelve.

    Se serializan TODAS las semanas, no solo las recalculadas: las anteriores a
    `from_week` deben quedar intactas, y eso también es comportamiento a congelar.
    """
    base = case.base
    weeks = MOTOR.recalcular_desde(
        _plan(base), desde_semana=case.from_week, tiempo_ancla=case.anchor_time,
        tiempo_meta=base.goal_time, curva=base.curve, distancia=base.distance,
        deshabilitadas=set(case.disabled), estilo=base.stroke, piscina=base.pool,
        n_mac=base.n_mac, edad=base.age,
    )
    return {"entrada": case.entrada(), "semanas": [_en_ingles(s) for s in weeks]}


_CLAVES_DE_TEMPORADA = {
    "nivel": "level", "n_macros": "n_macros", "inicio": "season_start",
    "fin": "season_end", "mejora_s": "season_improvement_s",
    "mejora_pct": "season_improvement_pct", "rango_bajo_pct": "annual_low_pct",
    "rango_alto_pct": "annual_high_pct", "veredicto": "verdict", "mensaje": "message",
    "macros": "macros",
}
_CLAVES_DE_MACRO = {
    "n_mac": "n_mac", "tiempo_inicial": "start_time", "tiempo_final": "end_time",
    "mejora_s": "improvement_s", "mejora_pct": "improvement_pct",
}


def _run_temporada(case: SeasonCase) -> dict[str, Any]:
    proyeccion = MOTOR.proyectar_temporada(
        case.current_time, case.distance, n_macros=case.n_macros,
        edad=case.age, perfil=case.profile,
    )
    crudo = asdict(proyeccion)
    crudo["macros"] = [
        {_CLAVES_DE_MACRO[k]: v for k, v in m.items()} for m in crudo["macros"]
    ]
    return {
        "entrada": case.entrada(),
        "temporada": {_CLAVES_DE_TEMPORADA[k]: v for k, v in crudo.items()},
    }


@dataclass(frozen=True)
class Suite:
    """Un camino del motor: sus casos, cómo se ejecuta y dónde se congela."""

    file: str
    cases: Sequence[Any]
    runner: Callable[[Any], dict[str, Any]]

    @property
    def case_ids(self) -> list[str]:
        return [c.id for c in self.cases]


SUITES: dict[str, Suite] = {
    "progression": Suite("motor_progression.json", PLAN_CASES, _run_progression),
    "recalculo": Suite("motor_recalculo.json", RECALC_CASES, _run_recalculo),
    "temporada": Suite("motor_temporada.json", SEASON_CASES, _run_temporada),
}
CASOS = [(name, cid) for name, s in SUITES.items() for cid in s.case_ids]


# ── Serialización y comparación ──────────────────────────────────────────────

def _normalize(value: Any) -> Any:
    """Estructura serializable con redondeo estable (fechas ISO, floats a 6)."""
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        rounded = round(value, DECIMALS)
        return 0.0 if rounded == 0 else rounded
    return value


@cache
def _current(suite: str) -> dict[str, Any]:
    s = SUITES[suite]
    return {case.id: _normalize(s.runner(case)) for case in s.cases}


@cache
def _reference(suite: str) -> dict[str, Any]:
    path = SNAPSHOT_DIR / SUITES[suite].file
    if not path.exists():
        pytest.fail(
            f"Falta la referencia {path}. Genérala a propósito con "
            f"{UPDATE_ENV}=1 (ver el docstring de este archivo)."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    """Aplana a rutas legibles: `semanas[3].zones.R1.mid`."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, sub in value.items():
            out.update(_flatten(sub, f"{prefix}.{key}" if prefix else str(key)))
        return out
    if isinstance(value, list):
        out = {}
        for i, sub in enumerate(value):
            out.update(_flatten(sub, f"{prefix}[{i}]"))
        return out
    return {prefix: value}


def _diff(expected: Any, actual: Any) -> list[str]:
    flat_exp, flat_act = _flatten(expected), _flatten(actual)
    lines: list[str] = []
    for path in sorted(set(flat_exp) | set(flat_act)):
        if path not in flat_act:
            lines.append(f"  {path}: DESAPARECIÓ (referencia: {flat_exp[path]!r})")
        elif path not in flat_exp:
            lines.append(f"  {path}: CAMPO NUEVO (actual: {flat_act[path]!r})")
        elif flat_exp[path] != flat_act[path]:
            lines.append(f"  {path}: referencia {flat_exp[path]!r} · actual {flat_act[path]!r}")
    return lines


@pytest.fixture(scope="session", autouse=True)
def _regenerar_si_se_pide() -> None:
    """Reescribe las referencias solo si se pide explícitamente por entorno."""
    if os.environ.get(UPDATE_ENV, "").strip().lower() not in {"1", "true", "yes", "si", "sí"}:
        return
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for name, suite in SUITES.items():
        payload = json.dumps(_current(name), indent=2, ensure_ascii=False, sort_keys=True)
        (SNAPSHOT_DIR / suite.file).write_text(payload + "\n", encoding="utf-8")
    _reference.cache_clear()


class TestCatalogo:
    def test_los_casos_cubren_los_cinco_niveles(self) -> None:
        """Cada tiempo congelado sigue clasificando en el nivel que dice cubrir."""
        for case_id, distance, current_time, level in LEVEL_CLAIMS:
            assert nivel_de(distance, current_time).value == level, case_id

    @pytest.mark.parametrize("suite", SUITES)
    def test_los_ids_de_caso_son_unicos(self, suite: str) -> None:
        ids = SUITES[suite].case_ids
        assert len(set(ids)) == len(ids)

    @pytest.mark.parametrize("suite", SUITES)
    def test_la_lista_de_casos_no_cambio(self, suite: str) -> None:
        """Añadir o quitar un caso es un cambio deliberado de la red de seguridad."""
        actuales = set(SUITES[suite].case_ids)
        faltan = sorted(set(_reference(suite)) - actuales)
        sobran = sorted(actuales - set(_reference(suite)))
        assert not faltan and not sobran, (
            f"[{suite}] casos en la referencia que ya no existen: {faltan or '—'}; "
            f"casos nuevos sin referencia: {sobran or '—'}. "
            f"Regenera con {UPDATE_ENV}=1 si es intencional."
        )


@pytest.mark.parametrize(("suite", "case_id"), CASOS, ids=[f"{s}·{c}" for s, c in CASOS])
def test_la_salida_del_motor_coincide_con_la_referencia(suite: str, case_id: str) -> None:
    reference = _reference(suite)
    if case_id not in reference:
        pytest.skip(f"caso nuevo sin referencia ({suite}); ver test_la_lista_de_casos_no_cambio")
    diffs = _diff(reference[case_id], _current(suite)[case_id])
    if not diffs:
        return
    shown = diffs[:MAX_DIFF_LINES]
    resto = len(diffs) - len(shown)
    detalle = "\n".join(shown) + (f"\n  … y {resto} diferencias más" if resto else "")
    pytest.fail(
        f"El motor '{suite}' cambió en el caso {case_id} "
        f"({len(diffs)} campos):\n{detalle}\n"
        f"Si el cambio es intencional, regenera la referencia con {UPDATE_ENV}=1.",
        pytrace=False,
    )
