"""Regresión: reglas de negocio que existen en UN solo sitio.

La auditoría de 2026-08-13 encontró la misma regla implementada dos veces entre
`app/domain/` y `app/engine/`, con las dos copias ya diciendo cosas distintas.
Estos tests no comprueban el valor de la regla nada más: comprueban que sigue
habiendo una sola copia. Una regla correcta duplicada vuelve a divergir sola.

Divergencia 1 — estilos válidos por distancia. Fuente única:
`app.engine.events.allowed_strokes` (coincide con el frontend `lib/constants.ts`).

Divergencia 2 — tope de semanas de extensión. Fuente única:
`app.domain.MAX_EXTENSION_WEEKS`, que `app.engine.feasibility` importa.
"""
from __future__ import annotations

import ast
import inspect
import math

import app.domain.engine as domain_engine
import app.engine.feasibility as feasibility
from app.domain import MAX_EXTENSION_WEEKS, ScienceEngine
from app.engine.envelope import science_envelope
from app.engine.events import allowed_strokes, is_valid_event


class TestEstilosValidosFuenteUnica:
    """El 50 combinado no existe en natación (divergencia 1)."""

    def test_no_hay_50_combinado(self):
        assert "combinado" not in allowed_strokes(50)
        assert is_valid_event(50, "combinado") is False

    def test_50_tiene_los_cuatro_estilos_reales(self):
        assert sorted(allowed_strokes(50)) == ["espalda", "libre", "mariposa", "pecho"]

    def test_el_dominio_ya_no_define_la_regla(self):
        # La copia de `domain/engine.py` daba el 50 combinado por válido y no
        # estaba exportada: código muerto contradiciendo a la regla viva.
        assert not hasattr(domain_engine, "allowed_strokes"), (
            "Volvió a aparecer allowed_strokes en app/domain/engine.py: "
            "la regla vive en app/engine/events.py y solo ahí."
        )

    # Comportamiento heredado de test_domain_engine.py, ahora sobre la fuente viva.
    def test_800_1500_solo_libre(self):
        assert allowed_strokes(800) == ["libre"]
        assert allowed_strokes(1500) == ["libre"]

    def test_400_libre_y_combinado(self):
        strokes = allowed_strokes(400)
        assert "libre" in strokes
        assert "combinado" in strokes
        assert "mariposa" not in strokes

    def test_100_todos_los_estilos(self):
        assert len(allowed_strokes(100)) == 5


class TestTopeDeExtensionFuenteUnica:
    """El tope de semanas de extensión se declara una vez (divergencia 2).

    Escenario de referencia: 200 libre, 4:00 → 3:00 en 15 semanas. La meta supera
    tanto el techo del macro que la extensión honesta pasa del tope, así que los
    dos motores tienen que capar — y capar en el MISMO número.
    """

    DISTANCIA = 200
    ACTUAL = 240.0
    META = 180.0
    SEMANAS = 15

    def _semanas_extra_honestas(self) -> int:
        """Semanas extra que harían falta de verdad, sin tope."""
        env = science_envelope(self.DISTANCIA, self.ACTUAL, self.SEMANAS)
        safe_rate = env.safe_total_s / self.SEMANAS
        return math.ceil((env.realistic_ceiling - self.META) / safe_rate)

    def test_feasibility_no_redeclara_el_tope(self):
        # Comprobación estructural: comparar valores no basta, porque una copia
        # nueva con el mismo número pasaría y volvería a divergir a la primera
        # que alguien tocara uno de los dos.
        arbol = ast.parse(inspect.getsource(feasibility))
        redeclarado = [
            nodo for nodo in arbol.body
            if isinstance(nodo, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "MAX_EXTENSION_WEEKS"
                    for t in nodo.targets)
        ]
        assert not redeclarado, (
            "app/engine/feasibility.py volvió a declarar MAX_EXTENSION_WEEKS: "
            "tiene que importarlo de app.domain, que es la única fuente."
        )

    def test_los_dos_motores_leen_el_mismo_valor(self):
        assert feasibility.MAX_EXTENSION_WEEKS == MAX_EXTENSION_WEEKS
        assert ScienceEngine.MAX_EXTENSION_WEEKS == MAX_EXTENSION_WEEKS

    def test_el_escenario_de_referencia_sigue_pasandose_del_tope(self):
        # Si la ciencia se recalibra y esta meta deja de desbordar el tope, los
        # dos tests de abajo dejarían de comprobar nada sin fallar. Este avisa.
        assert self._semanas_extra_honestas() > MAX_EXTENSION_WEEKS

    def test_feasibility_capa_en_el_tope(self):
        res = feasibility.analyze_feasibility(
            distance=self.DISTANCIA, stroke="libre", current_time=self.ACTUAL,
            goal_time=self.META, total_weeks=self.SEMANAS,
        )
        assert res.status == "aggressive"
        assert res.extension_weeks == MAX_EXTENSION_WEEKS
        assert res.recommended_weeks == self.SEMANAS + MAX_EXTENSION_WEEKS

    def test_el_dominio_capa_en_el_mismo_tope(self):
        plan = ScienceEngine().generate_plan(
            current_time=self.ACTUAL, goal_time=self.META,
            distance=self.DISTANCIA, stroke="libre", pool="50",
        )
        extras = [w for w in plan.weeks if w.is_extension]
        assert len(extras) == MAX_EXTENSION_WEEKS
        assert plan.total_weeks == ScienceEngine.TOTAL_WEEKS + MAX_EXTENSION_WEEKS

    def test_las_semanas_sugeridas_coinciden_con_el_plan_extendido(self):
        """El número que lee el entrenador y las filas que ve tienen que cuadrar.

        Esto es exactamente lo que la divergencia rompía: el simulador sugería
        41 semanas (tope 26) mientras el motor extendía hasta 45 (tope 30).
        """
        res = feasibility.analyze_feasibility(
            distance=self.DISTANCIA, stroke="libre", current_time=self.ACTUAL,
            goal_time=self.META, total_weeks=self.SEMANAS,
        )
        plan = ScienceEngine().generate_plan(
            current_time=self.ACTUAL, goal_time=self.META,
            distance=self.DISTANCIA, stroke="libre", pool="50",
        )
        assert res.recommended_weeks == plan.total_weeks
