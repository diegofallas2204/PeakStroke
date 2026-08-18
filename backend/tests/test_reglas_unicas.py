"""Regresión: reglas de negocio que existen en UN solo sitio.

La auditoría de 2026-08-13 encontró la misma regla implementada dos veces entre
`app/domain/` y `app/engine/`, con las dos copias ya diciendo cosas distintas.
Estos tests no comprueban el valor de la regla nada más: comprueban que sigue
habiendo una sola copia. Una regla correcta duplicada vuelve a divergir sola.

Divergencia 1 — estilos válidos por distancia. Fuente única:
`app.dominio.valores.Prueba`, que la impone en el constructor. Vivió en
`app.engine.events.allowed_strokes` hasta el 2026-08-16, cuando esos asserts se
**movieron** aquí y el módulo se borró (el frontend conserva su copia en
`lib/constants.ts` para filtrar la interfaz; el backend es quien rechaza).

Divergencia 2 — tope de semanas de extensión. Fuente única:
`app.dominio.servicios.tablas.MAX_SEMANAS_EXTENSION`. Hasta la fusión de motores
(C4) había que comprobar que las **dos** implementaciones capaban en el mismo
número; hoy hay una sola, así que lo que se comprueba es que el número que lee
el entrenador (`factibilidad`) y las filas que ve (`generar_extension`) siguen
cuadrando.
"""
from __future__ import annotations

import importlib.util
import math
from datetime import date

import pytest

import app.dominio.servicios.envolvente as envolvente
from app.dominio.servicios.envolvente import envolvente_de, factibilidad
from app.dominio.servicios.motor import MOTOR
from app.dominio.servicios.tablas import MAX_SEMANAS_EXTENSION
from app.dominio.valores import Estilo, Prueba


class TestEstilosValidosFuenteUnica:
    """El 50 combinado no existe en natación (divergencia 1)."""

    def test_no_hay_50_combinado(self):
        assert Estilo.COMBINADO not in Prueba.estilos_validos(50)
        assert Prueba.es_valida(50, "combinado") is False
        with pytest.raises(ValueError):
            Prueba(50, Estilo.COMBINADO)

    def test_50_tiene_los_cuatro_estilos_reales(self):
        assert sorted(e.value for e in Prueba.estilos_validos(50)) == [
            "espalda", "libre", "mariposa", "pecho",
        ]

    def test_el_motor_no_define_la_regla(self):
        # La copia vivía en `domain/engine.py`, que la fusión borró. Que no
        # reaparezca en el motor nuevo es la misma comprobación, un piso más
        # arriba: la validez de una prueba es de `Prueba` y de nadie más.
        assert not hasattr(envolvente, "allowed_strokes")
        assert not hasattr(envolvente, "estilos_validos")

    def test_el_adaptador_tampoco_la_redefine(self):
        # `app/engine/events.py` se borró al migrar a `Prueba`. Que vuelva a
        # existir es, otra vez, una segunda copia de la misma regla.
        assert importlib.util.find_spec("app.engine.events") is None, (
            "Volvió a aparecer app/engine/events.py: la validez de una prueba "
            "es una invariante de app.dominio.valores.Prueba, no una función."
        )

    # Comportamiento heredado de test_domain_engine.py, ahora sobre la fuente viva.
    def test_800_1500_solo_libre(self):
        assert Prueba.estilos_validos(800) == frozenset({Estilo.LIBRE})
        assert Prueba.estilos_validos(1500) == frozenset({Estilo.LIBRE})

    def test_400_libre_y_combinado(self):
        estilos = Prueba.estilos_validos(400)
        assert Estilo.LIBRE in estilos
        assert Estilo.COMBINADO in estilos
        assert Estilo.MARIPOSA not in estilos

    def test_100_todos_los_estilos(self):
        assert len(Prueba.estilos_validos(100)) == 5


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
        env = envolvente_de(self.DISTANCIA, self.ACTUAL, self.SEMANAS)
        return math.ceil(
            (env.techo_realista - self.META) / env.ritmo_seguro_semanal_s(self.SEMANAS)
        )

    def test_el_escenario_de_referencia_sigue_pasandose_del_tope(self):
        # Si la ciencia se recalibra y esta meta deja de desbordar el tope, los
        # dos tests de abajo dejarían de comprobar nada sin fallar. Este avisa.
        assert self._semanas_extra_honestas() > MAX_SEMANAS_EXTENSION

    def _veredicto(self):
        return factibilidad(self.DISTANCIA, self.ACTUAL, self.META, self.SEMANAS)

    def test_la_factibilidad_capa_en_el_tope(self):
        res = self._veredicto()
        assert res.estado == "aggressive"
        assert res.semanas_extra == MAX_SEMANAS_EXTENSION
        assert res.semanas_recomendadas == self.SEMANAS + MAX_SEMANAS_EXTENSION

    def test_las_semanas_sugeridas_coinciden_con_las_filas_generadas(self):
        """El número que lee el entrenador y las filas que ve tienen que cuadrar.

        Esto es exactamente lo que la divergencia rompía: el simulador sugería
        41 semanas (tope 26) mientras el motor extendía hasta 45 (tope 30). Con
        un solo motor las dos salidas nacen de la misma envolvente, y este test
        fija que sigan naciendo de ahí.
        """
        res = self._veredicto()
        extension = MOTOR.generar_extension(
            distancia=self.DISTANCIA, tiempo_actual=self.ACTUAL,
            techo_realista=res.techo_realista, tiempo_meta=self.META,
            ritmo_seguro=res.ritmo_seguro_semanal_s, n_extra=res.semanas_extra,
            inicio=date(2026, 1, 5), semanas_del_macro=self.SEMANAS,
            km_semanales=20.0,
        )
        assert len(extension) == MAX_SEMANAS_EXTENSION
        assert res.semanas_recomendadas == self.SEMANAS + len(extension)
        assert extension[-1].numero == res.semanas_recomendadas
