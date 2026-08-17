"""Tests directos del motor científico único.

Era `test_domain_engine.py` y preguntaba a `ScienceEngine`, que la fusión de
motores (C4) absorbió. **Los asserts son los mismos**: lo que cambió es a quién
se le hacen y, donde el motor viejo respondía con la forma de su `PlanResult`,
la pregunta se le hace al método que hoy contesta esa misma cosa —el techo a la
envolvente, el veredicto a la factibilidad, las filas al plan—.

Lo único que se cayó son los asserts sobre la **forma** de `PlanResult` (que
`distance` fuera el evento de referencia, que `macro_weeks` contara las semanas
del macro fijo de 15): esa clase no existe y su macro fijo tampoco, porque las
semanas las pone el entrenador (R6).

Cubre: nivel y perfil, margen de confianza, ritmo de sprint, tablas de I_max,
F_FASE, el plan, la degradación por macrociclo (§4.3), la corrección de menores
(§4.4), la curva científica y la proyección anual (§4.5).
"""
from datetime import date

import pytest

from app.dominio.servicios.curvas import Cientifica
from app.dominio.servicios.envolvente import envolvente_de, factibilidad, nivel_de
from app.dominio.servicios.motor import MOTOR
from app.dominio.servicios.tablas import (
    DEGRADACION_ENTRE_MACROS,
    TABLA_I_MAX,
    margen_de_confianza,
)
from app.dominio.valores import Estilo, Fase, Perfil, Zona

INICIO = date(2026, 1, 5)


def _plan(actual, meta, distancia=200, estilo="libre", piscina="50", **kw):
    """Un plan de 15 semanas y 450 km, que es la forma de referencia."""
    return MOTOR.generar_plan(
        distancia, actual, meta, 15, 450.0, "science", INICIO,
        estilo=estilo, piscina=piscina, **kw,
    )


def _techo(actual, distancia=200, semanas=15, **kw):
    return envolvente_de(distancia, actual, semanas, **kw).techo_realista


# ── Funciones puras de apoyo ────────────────────────────────────────────────

class TestNivel:
    @pytest.mark.parametrize(("umbral", "esperado"), [
        (155.0, "beginner"), (130.0, "recreational"), (100.0, "advanced"),
        (80.0, "competitive"), (65.0, "elite"),
    ])
    def test_por_umbral(self, umbral, esperado):
        # El nivel se deriva del ritmo de carrera × factor MVO2; se elige la
        # distancia para que ese producto caiga en el umbral que se quiere probar.
        assert nivel_de(200, umbral * 2 / 1.073).value == esperado

    def test_frontera_competitive(self):
        # 70 s exactos es elite; por encima, competitive.
        assert nivel_de(200, 70.0 * 2 / 1.073).value == "elite"
        assert nivel_de(200, 70.1 * 2 / 1.073).value == "competitive"


class TestPerfilPorDistancia:
    @pytest.mark.parametrize(("distancia", "esperado"), [
        (50, Perfil.VELOCIDAD), (100, Perfil.VELOCIDAD),
        (200, Perfil.MEDIO_FONDO), (400, Perfil.MEDIO_FONDO),
        (800, Perfil.FONDO), (1500, Perfil.FONDO),
    ])
    def test_sugerido(self, distancia, esperado):
        assert Perfil.para_distancia(distancia) is esperado


class TestMargenDeConfianza:
    def test_crece_con_la_distancia_temporal(self):
        assert margen_de_confianza(1) == margen_de_confianza(4) == 2
        assert margen_de_confianza(5) == margen_de_confianza(8) == 4
        assert margen_de_confianza(9) == margen_de_confianza(12) == 6
        assert margen_de_confianza(13) == margen_de_confianza(30) == 8

    def test_el_motor_lo_expone(self):
        assert MOTOR.margen(7) == margen_de_confianza(7)


class TestRitmoDeCarrera:
    def test_sin_correccion_de_100_para_arriba(self):
        assert MOTOR.ritmo_de_carrera_100(120.0, 200) == pytest.approx(60.0)
        assert MOTOR.ritmo_de_carrera_100(900.0, 1500) == pytest.approx(60.0)

    def test_el_sprint_no_se_sostiene_al_doble(self):
        # Un 50 en 30 s no son 60 s de 100: el /100 real es ~10 % más lento.
        assert MOTOR.ritmo_de_carrera_100(30.0, 50) == pytest.approx(66.0)


class TestTablaDeIMax:
    def test_estan_los_cinco_niveles(self):
        assert set(TABLA_I_MAX) == {
            "beginner", "recreational", "advanced", "competitive", "elite",
        }

    def test_estan_las_seis_distancias(self):
        for nivel in TABLA_I_MAX.values():
            assert set(nivel) == {50, 100, 200, 400, 800, 1500}

    def test_mas_distancia_mas_margen_dentro_del_nivel(self):
        for nivel in TABLA_I_MAX.values():
            assert nivel[1500] > nivel[800] > nivel[400]

    def test_mas_nivel_menos_margen_en_la_misma_prueba(self):
        for distancia in (50, 100, 200, 400, 800, 1500):
            assert (TABLA_I_MAX["beginner"][distancia]
                    > TABLA_I_MAX["advanced"][distancia]
                    > TABLA_I_MAX["elite"][distancia])

    def test_los_valores_son_proporciones_creibles(self):
        for nivel in TABLA_I_MAX.values():
            for valor in nivel.values():
                assert 0.0 < valor < 0.10


class TestFFase:
    def test_el_taper_es_el_pico(self):
        assert Fase.TAPER.f_fase == max(f.f_fase for f in Fase.secuencia())

    def test_la_base_general_es_la_mas_baja(self):
        assert Fase.BASE_GENERAL.f_fase == min(f.f_fase for f in Fase.secuencia())

    def test_crece_a_lo_largo_del_macro(self):
        pesos = [f.f_fase for f in Fase.secuencia()]
        assert pesos == sorted(pesos)


# ── El plan ─────────────────────────────────────────────────────────────────

class TestElPlan:
    def test_devuelve_una_fila_por_semana(self):
        semanas = _plan(240.0, 236.0)
        assert len(semanas) == 15
        assert [s.numero for s in semanas] == list(range(1, 16))

    def test_las_zonas_respetan_la_jerarquia(self):
        zonas = _plan(240.0, 236.0)[0].zonas
        ritmos = [zonas[z.value]["mid"] for z in Zona.ordenadas()]
        assert ritmos == sorted(ritmos, reverse=True)   # R1 la más lenta, V la más rápida

    def test_el_tiempo_esperado_mejora_semana_a_semana(self):
        tiempos = [s.tiempo_esperado for s in _plan(240.0, 236.0)]
        assert all(b <= a for a, b in zip(tiempos, tiempos[1:], strict=False))

    def test_la_primera_semana_parte_del_actual(self):
        primera = _plan(240.0, 236.0)[0]
        assert primera.tiempo_esperado < 240.0
        assert primera.tiempo_esperado > 239.0   # la primera semana mejora poco

    def test_todas_las_semanas_llevan_kilometros(self):
        assert all(s.km > 0 for s in _plan(240.0, 236.0))

    def test_los_kilometros_suman_los_del_entrenador(self):
        # R6: la ciencia da la forma, el total lo pone el entrenador.
        assert sum(s.km for s in _plan(240.0, 236.0)) == pytest.approx(450.0, abs=0.5)

    def test_la_mariposa_nada_mas_lento_que_el_libre(self):
        libre = _plan(240.0, 236.0, estilo="libre")[0].zonas["R1"]["mid"]
        mariposa = _plan(240.0, 236.0, estilo="mariposa")[0].zonas["R1"]["mid"]
        assert mariposa > libre

    def test_la_piscina_de_25_es_mas_rapida(self):
        larga = _plan(240.0, 236.0, piscina="50")[0].zonas["R1"]["mid"]
        corta = _plan(240.0, 236.0, piscina="25")[0].zonas["R1"]["mid"]
        assert corta < larga

    def test_la_correccion_de_estilo_es_positiva_salvo_en_libre(self):
        for estilo in Estilo:
            if estilo is Estilo.LIBRE:
                assert estilo.correccion_tpace_s == 0.0
            else:
                assert estilo.correccion_tpace_s > 0


class TestElTechoYElVeredicto:
    def test_el_techo_es_mejor_que_el_tiempo_actual(self):
        assert _techo(240.0) < 240.0

    def test_una_meta_pequena_es_realista(self):
        assert factibilidad(200, 240.0, 238.0, 15).estado == "ok"

    def test_una_meta_enorme_es_agresiva(self):
        assert factibilidad(200, 240.0, 180.0, 15).estado == "aggressive"

    def test_la_meta_agresiva_pide_semanas_de_extension(self):
        veredicto = factibilidad(200, 240.0, 180.0, 15)
        assert veredicto.semanas_extra and veredicto.semanas_extra > 0
        extension = MOTOR.generar_extension(
            200, 240.0, veredicto.techo_realista, 180.0,
            veredicto.ritmo_seguro_semanal_s, veredicto.semanas_extra,
            INICIO, 15, 20.0,
        )
        assert extension[0].numero == 16
        assert all(s.fase == Fase.EXTENSION.etiqueta for s in extension)


# ── Degradación por macrociclo (§4.3) ───────────────────────────────────────

class TestDegradacionEntreMacros:
    def test_el_segundo_macro_mejora_menos_que_el_primero(self):
        assert (300.0 - _techo(300.0, 800, n_mac=2)) < (300.0 - _techo(300.0, 800, n_mac=1))

    def test_n_mac_1_es_el_valor_por_defecto(self):
        assert _techo(240.0, 400) == pytest.approx(_techo(240.0, 400, n_mac=1))

    def test_la_razon_entre_macros_es_la_constante(self):
        primero = 300.0 - _techo(300.0, 800, n_mac=1)
        segundo = 300.0 - _techo(300.0, 800, n_mac=2)
        assert segundo / primero == pytest.approx(DEGRADACION_ENTRE_MACROS, abs=0.01)

    def test_el_tercero_es_la_constante_al_cuadrado(self):
        primero = 300.0 - _techo(300.0, 800, n_mac=1)
        tercero = 300.0 - _techo(300.0, 800, n_mac=3)
        assert tercero / primero == pytest.approx(DEGRADACION_ENTRE_MACROS ** 2, abs=0.01)

    def test_la_misma_meta_es_mas_exigente_en_un_macro_posterior(self):
        orden = {"ok": 0, "warning": 1, "aggressive": 2}
        primero = factibilidad(400, 240.0, 234.0, 15, n_mac=1)
        cuarto = factibilidad(400, 240.0, 234.0, 15, n_mac=4)
        assert orden[cuarto.estado] >= orden[primero.estado]


# ── Corrección para menores (§4.4) ──────────────────────────────────────────

class TestCorreccionDeMenores:
    def test_un_menor_llega_mas_lejos_que_un_adulto(self):
        assert _techo(60.0, 100, edad=15) < _techo(60.0, 100, edad=25)

    def test_sin_edad_se_trata_como_adulto(self):
        assert _techo(60.0, 100) == pytest.approx(_techo(60.0, 100, edad=25))

    def test_a_los_18_ya_no_hay_correccion(self):
        assert _techo(60.0, 100, edad=18) == pytest.approx(_techo(60.0, 100, edad=25))

    def test_un_menor_de_14_mejora_al_menos_un_40_por_ciento_mas(self):
        adulto = 300.0 - _techo(300.0, 800, edad=25)
        menor = 300.0 - _techo(300.0, 800, edad=14)
        assert menor >= adulto * 1.4


# ── La curva científica ─────────────────────────────────────────────────────

class TestCurvaCientifica:
    """Back-loaded, con el pico en el taper (nota 09 del vault)."""

    def setup_method(self):
        self.curva = Cientifica()

    def test_extremos(self):
        assert self.curva.progreso(0.0) == pytest.approx(0.0)
        assert self.curva.progreso(1.0) == pytest.approx(1.0)

    def test_no_decrece(self):
        valores = [self.curva.progreso(i / 50) for i in range(51)]
        assert all(b >= a - 1e-9 for a, b in zip(valores, valores[1:], strict=False))

    def test_carga_la_mejora_en_la_segunda_mitad(self):
        assert self.curva.progreso(0.5) < 0.45

    def test_el_taper_aporta_mas_que_la_base_general(self):
        taper = self.curva.progreso(1.0) - self.curva.progreso(13 / 15)
        base = self.curva.progreso(2 / 15) - self.curva.progreso(0.0)
        assert taper > base


# ── Proyección anual (§4.5) ─────────────────────────────────────────────────

class TestProyeccionAnual:
    def test_tres_macros_por_defecto(self):
        proyeccion = MOTOR.proyectar_temporada(300.0, 800)
        assert proyeccion.n_macros == 3
        assert len(proyeccion.macros) == 3

    def test_cada_macro_mejora_menos_que_el_anterior(self):
        mejoras = [m.mejora_s for m in MOTOR.proyectar_temporada(300.0, 800).macros]
        assert mejoras[0] > mejoras[1] > mejoras[2]

    def test_la_temporada_encadena(self):
        proyeccion = MOTOR.proyectar_temporada(300.0, 800)
        assert proyeccion.fin < proyeccion.macros[0].tiempo_final
        assert proyeccion.inicio == pytest.approx(300.0)

    def test_una_temporada_de_elite_no_se_dispara(self):
        proyeccion = MOTOR.proyectar_temporada(15 * 60 + 30, 1500, n_macros=3)
        assert proyeccion.nivel == "elite"
        assert proyeccion.veredicto in ("ok", "optimistic")
        assert proyeccion.rango_alto_pct == pytest.approx(1.5)
