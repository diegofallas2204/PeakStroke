"""El test de lactato en el dominio: lo que se apunta, lo que se deriva y lo que se avisa.

Los números de referencia salen de la serie real del 22/09/2026 (A01, anonimizada
en `lactato_22_09.py`) y son los que pide el prompt de la sesión (vault): media
4:52.5, CV 0.7 %, deriva de brazada +33.6 %, índice de brazada ≈ 3.98. **Nada de
esto se teclea en la app**: el entrenador apunta tiempo, lactato, FC, esfuerzo y
conteos, y el resto lo calcula el dominio.
"""
from __future__ import annotations

from datetime import date

import pytest
from lactato_22_09 import A01, A06, A08, A16

from app.dominio.entidades import Repeticion, TestDeLactato
from app.dominio.servicios.avisos_de_lactato import avisos
from app.dominio.valores import EstadoDeZona, ModoDeLactato, Tiempo, TipoDeDescanso, Zona


def _test(datos, *, zona: Zona = Zona.R1, tramo_m: int | None = 50, **extra) -> TestDeLactato:
    reps = [
        Repeticion(i + 1, Tiempo(t), lactato=lac, fc=fc, esfuerzo=rpe, brazadas=braz)
        for i, (t, lac, fc, rpe, braz) in enumerate(datos["reps"])
    ]
    return TestDeLactato(
        fecha=date(2026, 9, 22), zona=zona, distancia_rep=400, repeticiones=reps,
        descanso=TipoDeDescanso.PAUSA, descanso_s=30.0,
        propuesto=datos["propuesto"], referencia=datos["referencia"], tramo_m=tramo_m,
        **extra,
    )


class TestLaSerieDeReferencia:
    """A01, 10×400 en R1: la serie limpia."""

    def test_ritmo_medio_y_regularidad(self):
        t = _test(A01)
        assert t.tiempo_medio().segundos == pytest.approx(292.5)
        assert round(t.cv_pct(), 1) == 0.7

    def test_frente_al_propuesto_y_a_su_mejor_marca(self):
        t = _test(A01)
        # Contra el centro del rango propuesto (305 s): 12.5 s más rápido.
        assert t.diferencia_con_propuesto() == pytest.approx(-12.5)
        assert round(t.pct_de_referencia(), 1) == 83.8
        assert round(t.pct_del_propuesto(), 1) == pytest.approx(104.3)

    def test_las_muestras_de_lactato(self):
        t = _test(A01)
        assert t.muestras() == [(2, 3.3), (4, 2.5), (7, 2.9), (8, 3.0), (10, 3.2)]
        assert t.lactato_mediano() == pytest.approx(3.0)

    def test_brazadas_deriva_e_indice(self):
        t = _test(A01)
        primera, ultima = t.repeticiones[0], t.repeticiones[-1]
        assert primera.brazadas_medias() == pytest.approx(30.5)
        assert ultima.brazadas_medias() == pytest.approx(40.75)
        assert round(t.deriva_de_brazada_pct(), 1) == 33.6
        # Una brazada es un brazo; un ciclo son dos.
        assert t.metros_por_brazada(primera) == pytest.approx(50 / 30.5)
        assert t.indice_de_brazada() == pytest.approx(3.98, abs=0.01)

    def test_la_deriva_dentro_de_una_repeticion(self):
        t = _test(A01)
        # La rep. 6 empieza en 32 y acaba en 36 brazadas por 50.
        assert t.repeticiones[5].deriva_interna_pct() == pytest.approx(12.5)

    def test_la_frecuencia_de_ciclo_estimada_y_la_real(self):
        t = _test(A01)
        estimada, es_estimada = t.frecuencia_de_ciclo(t.repeticiones[0])
        # Sin el tiempo del tramo, se reparte el 400 en ocho 50: 36.375 s.
        assert es_estimada is True
        assert estimada == pytest.approx(15.25 / 36.375 * 60)
        con_tramo = Repeticion(1, Tiempo(291.0), brazadas=(31, 31, 30, 30), tiempo_tramo=Tiempo(35.0))
        real, es_estimada = t.frecuencia_de_ciclo(con_tramo)
        assert es_estimada is False
        assert real == pytest.approx(15.25 / 35.0 * 60)

    def test_estado_estable_y_dentro_de_zona(self):
        t = _test(A01)
        assert t.estado_estable() is True
        assert t.subida_en_la_segunda_mitad() == pytest.approx(0.3)
        assert {t.estado_de_zona(lac) for _, lac in t.muestras()} == {EstadoDeZona.DENTRO}

    def test_no_avisa_de_nada(self):
        assert avisos(_test(A01)) == []


class TestLaZona:
    def test_los_rangos_decididos(self):
        assert Zona.R1.rango_de_lactato == (2.0, 3.5)
        assert Zona.R2.rango_de_lactato == (4.0, 6.0)
        assert Zona.MVO2.rango_de_lactato == (6.0, 8.0)
        assert Zona.RL.rango_de_lactato == (8.0, None)
        # V es aláctica: se prescribe por distancia y descanso.
        assert Zona.V.rango_de_lactato is None

    def test_el_hueco_entre_r1_y_r2_no_es_de_ninguna(self):
        r1 = _test(A01, zona=Zona.R1)
        r2 = _test(A01, zona=Zona.R2)
        assert r1.estado_de_zona(3.7) is EstadoDeZona.ENCIMA
        assert r2.estado_de_zona(3.7) is EstadoDeZona.DEBAJO

    def test_en_v_no_hay_veredicto(self):
        assert _test(A01, zona=Zona.V).estado_de_zona(3.0) is None

    def test_r2_es_el_umbral_anaerobico(self):
        assert Zona.R2.etiqueta == "Umbral anaeróbico"


class TestLosAvisos:
    """Avisan, no bloquean: el test se guarda igual."""

    def test_muestra_contaminada_y_repeticion_lenta(self):
        encontrados = {(a.repeticion, a.campo) for a in avisos(_test(A06))}
        assert encontrados == {(2, "lactato"), (6, "tiempo")}
        assert round(_test(A06).cv_pct(), 1) == 3.9

    def test_lactato_por_debajo_del_reposo(self):
        assert {(a.repeticion, a.campo) for a in avisos(_test(A08))} == {(8, "lactato")}

    def test_fc_que_cae_mientras_sube_el_esfuerzo_y_salto_de_lactato(self):
        encontrados = {(a.repeticion, a.campo) for a in avisos(_test(A16))}
        assert {r for r, c in encontrados if c == "fc"} == {3, 4, 5, 6, 7, 8}
        assert {r for r, c in encontrados if c == "lactato"} == {5, 6}
        assert {c for _, c in encontrados} == {"fc", "lactato"}

    def test_cada_aviso_dice_que_pasa(self):
        for aviso in avisos(_test(A16)):
            assert aviso.mensaje and aviso.mensaje[0].isupper()


class TestLoQueNoSeAdmite:
    def test_sin_repeticiones(self):
        with pytest.raises(ValueError):
            TestDeLactato(fecha=date(2026, 9, 22), zona=Zona.R1, distancia_rep=400, repeticiones=[])

    @pytest.mark.parametrize("campo, valor", [
        ("lactato", -1.0), ("lactato", 40.0), ("fc", 20), ("fc", 260),
        ("esfuerzo", -0.5), ("esfuerzo", 10.5),
    ])
    def test_valores_fuera_de_lo_fisiologico(self, campo, valor):
        with pytest.raises(ValueError):
            Repeticion(1, Tiempo(300.0), **{campo: valor})

    def test_brazadas_imposibles(self):
        with pytest.raises(ValueError):
            Repeticion(1, Tiempo(300.0), brazadas=(30, 0))

    def test_brazadas_sin_saber_que_tramo_se_conto(self):
        with pytest.raises(ValueError, match="tramo"):
            _test(A01, tramo_m=None)

    def test_repeticiones_que_no_van_seguidas(self):
        with pytest.raises(ValueError):
            TestDeLactato(
                fecha=date(2026, 9, 22), zona=Zona.R1, distancia_rep=400,
                repeticiones=[Repeticion(1, Tiempo(300.0)), Repeticion(3, Tiempo(300.0))],
            )

    def test_un_propuesto_al_reves(self):
        with pytest.raises(ValueError):
            TestDeLactato(
                fecha=date(2026, 9, 22), zona=Zona.R1, distancia_rep=400,
                repeticiones=[Repeticion(1, Tiempo(300.0))], propuesto=(306.0, 304.0),
            )


class TestSinDatosOpcionales:
    def test_sin_referencia_ni_propuesto_ni_lactato(self):
        t = TestDeLactato(
            fecha=date(2026, 9, 22), zona=Zona.R1, distancia_rep=400,
            repeticiones=[Repeticion(1, Tiempo(300.0)), Repeticion(2, Tiempo(302.0))],
        )
        assert t.pct_de_referencia() is None
        assert t.pct_del_propuesto() is None
        assert t.diferencia_con_propuesto() is None
        assert t.lactato_mediano() is None
        assert t.estado_estable() is None
        assert t.indice_de_brazada() is None
        assert t.deriva_de_brazada_pct() is None
        assert avisos(t) == []

    def test_el_escalonado_no_tiene_estado_estable(self):
        # El modelo ya admite el escalonado; el veredicto de estado estable es
        # propio de una serie a ritmo constante.
        t = _test(A01, modo=ModoDeLactato.ESCALONADO)
        assert t.estado_estable() is None
