"""Tests del tiempo de salida: el parámetro que faltaba en los tests aeróbicos.

Hasta hoy un test aeróbico solo guardaba la LLEGADA de cada repetición, y el
motor la trataba como si fuera el tiempo nadado. Son la misma cosa únicamente
cuando el nadador sale de cero cada vez; en cuanto hay un intervalo de salida
—que es como se hace un T-30 o un 12×400 de verdad— la llegada que el
entrenador lee en el reloj es acumulada y el tiempo nadado hay que restarlo.

Dos consecuencias, y las dos se prueban aquí:

  1. **La base aeróbica salía mal.** Con llegadas de reloj tomadas por tiempos
     de nado, `avg_per100` crecía repetición a repetición y contaminaba todo lo
     que cuelga de ella (zonas, predicción, factibilidad).
  2. **No había con qué prescribir el entrenamiento.** El ritmo dice a qué nadar;
     la salida dice cada cuánto. Sin la segunda mitad, la tabla de zonas no se
     puede escribir en la pizarra.
"""
from __future__ import annotations

import pytest

from app.dominio.servicios.intervalos import intervalos_de_entrenamiento
from app.dominio.servicios.zonas import al_reloj as clock_interval
from app.dominio.valores import Zona
from app.engine.aerobic import analyze_splits


class TestSalidaEnElAnalisis:
    """`analyze_splits` con intervalo de salida."""

    def test_sin_salida_se_comporta_igual_que_antes(self):
        """La firma nueva no cambia el resultado de los tests ya guardados."""
        a = analyze_splits([78.0] * 30, 100)
        assert a.avg_per100 == pytest.approx(78.0)
        assert a.send_off is None
        assert a.rest_per_rep == []
        assert a.avg_rest is None
        assert a.work_rest_ratio is None

    def test_salida_deriva_el_descanso_de_cada_repeticion(self):
        a = analyze_splits([78.0, 79.0, 80.0], 100, send_off=90.0)
        assert a.rest_per_rep == [12.0, 11.0, 10.0]
        assert a.avg_rest == pytest.approx(11.0)
        # ratio = descanso / trabajo, sobre los promedios
        assert a.work_rest_ratio == pytest.approx(11.0 / 79.0, abs=1e-4)
        # densidad = fracción del ciclo que es nado
        assert a.density == pytest.approx(79.0 / 90.0, abs=1e-4)

    def test_salidas_de_cada_repeticion(self):
        """Salida n = (n-1) × intervalo. Es lo que canta el reloj de pared."""
        a = analyze_splits([78.0, 79.0, 80.0], 100, send_off=90.0)
        assert a.departures == [0.0, 90.0, 180.0]

    def test_no_llegar_a_la_salida_se_marca_pero_no_revienta(self):
        """El atleta que no aguanta el intervalo es un dato, no un error."""
        a = analyze_splits([88.0, 92.0, 89.0], 100, send_off=90.0)
        assert a.missed_intervals == [2]          # 1-indexado, como rep_number
        assert a.rest_per_rep[1] == pytest.approx(-2.0)

    def test_salida_menor_que_cero_es_error(self):
        with pytest.raises(ValueError):
            analyze_splits([78.0], 100, send_off=-5.0)


class TestLlegadasDeReloj:
    """`input_mode="clock"`: lo que el entrenador apunta de verdad."""

    def test_llegadas_acumuladas_se_convierten_a_tiempos_de_nado(self):
        # 3×100 salida 1:30, nadados en 1:18, 1:19, 1:20.
        # El reloj marca 1:18, 2:49 (90+79) y 4:20 (180+80).
        a = analyze_splits(
            [78.0, 169.0, 260.0], 100, send_off=90.0, input_mode="clock",
        )
        assert a.per100_splits == [78.0, 79.0, 80.0]
        assert a.avg_per100 == pytest.approx(79.0)

    def test_es_exactamente_el_bug_que_veniamos_arrastrando(self):
        """Sin convertir, la base aeróbica salía disparatada."""
        llegadas = [78.0, 169.0, 260.0]
        crudo = analyze_splits(llegadas, 100)                      # como antes
        bueno = analyze_splits(llegadas, 100, send_off=90.0, input_mode="clock")
        assert crudo.avg_per100 == pytest.approx(169.0)            # +114%
        assert bueno.avg_per100 == pytest.approx(79.0)

    def test_llegadas_normaliza_por_distancia_de_repeticion(self):
        # 2×400 salida 6:00, nadados en 5:00 y 5:04.
        a = analyze_splits(
            [300.0, 664.0], 400, send_off=360.0, input_mode="clock",
        )
        assert a.per100_splits == [75.0, 76.0]

    def test_modo_reloj_exige_salida(self):
        with pytest.raises(ValueError):
            analyze_splits([78.0, 169.0], 100, input_mode="clock")

    def test_llegar_antes_de_salir_es_imposible(self):
        with pytest.raises(ValueError):
            analyze_splits([78.0, 85.0], 100, send_off=90.0, input_mode="clock")

    def test_modo_desconocido_es_error(self):
        with pytest.raises(ValueError):
            analyze_splits([78.0], 100, input_mode="telepatia")


class TestRedondeoAlReloj:
    """Los intervalos se cantan sobre múltiplos de 5 s, no sobre decimales."""

    def test_redondea_hacia_arriba(self):
        assert clock_interval(86.2) == 90.0
        assert clock_interval(90.0) == 90.0
        assert clock_interval(90.1) == 95.0

    def test_paso_configurable(self):
        assert clock_interval(86.2, paso=10) == 90.0
        assert clock_interval(91.0, paso=10) == 100.0

    def test_paso_invalido(self):
        with pytest.raises(ValueError):
            clock_interval(90.0, paso=0)


class TestTiemposDeEntrenamiento:
    """De la base aeróbica a la pizarra: ritmo + salida por zona."""

    ZONAS = {"R1": 82.0, "R2": 75.0, "MVO2": 70.0, "RL": 66.0, "V": 62.0}

    def test_una_entrada_por_zona(self):
        out = intervalos_de_entrenamiento(self.ZONAS, distancia_rep=100)
        assert list(out) == ["R1", "R2", "MVO2", "RL", "V"]

    def test_el_trabajo_escala_con_la_distancia(self):
        out = intervalos_de_entrenamiento(self.ZONAS, distancia_rep=200)
        assert out["R1"].trabajo == pytest.approx(164.0)

    def test_la_salida_siempre_deja_sitio_al_descanso(self):
        for zona, iv in intervalos_de_entrenamiento(self.ZONAS, distancia_rep=100).items():
            assert iv.salida > iv.trabajo, zona
            assert iv.descanso == pytest.approx(iv.salida - iv.trabajo)

    def test_el_descanso_crece_con_la_intensidad(self):
        out = intervalos_de_entrenamiento(self.ZONAS, distancia_rep=100)
        ratios = [out[z].descanso / out[z].trabajo for z in ("R1", "R2", "MVO2", "RL", "V")]
        assert ratios == sorted(ratios), "una zona más dura descansa más, nunca menos"

    def test_valores_concretos_de_la_zona_base(self):
        # R1 a 82 s/100m: descanso 8% = 6.6 s → 88.6 s → 1:30 en el reloj.
        iv = intervalos_de_entrenamiento(self.ZONAS, distancia_rep=100)["R1"]
        assert iv.trabajo == pytest.approx(82.0)
        assert iv.salida == 90.0

    def test_zona_sin_ritmo_se_omite(self):
        out = intervalos_de_entrenamiento({"R1": 82.0, "V": None}, distancia_rep=100)
        assert "V" not in out

    def test_distancia_invalida(self):
        with pytest.raises(ValueError):
            intervalos_de_entrenamiento(self.ZONAS, distancia_rep=0)

    def test_la_tabla_de_ratios_cubre_todas_las_zonas(self):
        assert {z.value for z in Zona.ordenadas()} == {"R1", "R2", "MVO2", "RL", "V"}


class TestDensidadMedida:
    """La salida medida en el test se compara contra la prescrita."""

    def test_la_medida_viaja_hasta_la_prescripcion(self):
        out = intervalos_de_entrenamiento(
            {"R1": 82.0}, distancia_rep=100, ratio_medido=0.30,
        )
        assert out["R1"].salida_medida == 110.0   # 82 × 1.30 = 106.6 → 110
        assert out["R1"].mas_denso_que_lo_medido is True

    def test_sin_medida_no_hay_comparacion(self):
        out = intervalos_de_entrenamiento({"R1": 82.0}, distancia_rep=100)
        assert out["R1"].salida_medida is None
        assert out["R1"].mas_denso_que_lo_medido is None
