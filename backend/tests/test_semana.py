"""C9 punto 4 (REDISENO §5.8): `Semana`.

La semana del plan de una prueba. Hasta el 2026-10-13 era la fila `WeeklyPlan`,
y el parón, el tiempo real y la curva recalculada se escribían sobre ella desde
`api/v1/macrociclos/semanas.py`.

Decisiones (opción recomendada, 2026-10-13):
- `real()`, `desviacion()` y `zonas()` **reciben su contexto**: la semana no
  guarda sus resultados (R2 enmendada) ni conoce su prueba ni su piscina;
- `esperado` no se puede reasignar: la curva ideal nunca se modifica;
- `parar()` y `reanudar()` son idempotentes y dicen si cambiaron.

Aquí, el dominio y la traducción; lo que se ve por el API, en
`test_semana_api.py`.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.dominio.entidades import Contexto, Resultado, Semana
from app.dominio.servicios.motor import MOTOR
from app.dominio.valores import Fase, Piscina, Prueba, Tiempo, Zona
from app.persistencia.mapeo import semana_desde_fila
from app.persistencia.tablas.planes import WeeklyPlan

LUNES = date(2026, 9, 7)
_200 = Prueba(200, "libre")


def _semana(**cambios) -> Semana:
    base = {
        "numero": 3, "fecha": LUNES, "km_planificados": 28.5,
        "esperado": Tiempo(129.0), "fase": Fase.BASE_ESPECIFICA,
    }
    return Semana(**(base | cambios))


def _resultado(segundos: float, *, dia: int = 0, **cambios) -> Resultado:
    base = {
        "atleta_id": 5, "prueba": _200, "tiempo": Tiempo(segundos),
        "fecha": LUNES + timedelta(days=dia), "piscina": Piscina.LARGA,
        "contexto": Contexto.CONTROL,
    }
    return Resultado(**(base | cambios))


# ── Lo que no se puede construir ni cambiar ──────────────────────────────────


def test_la_curva_ideal_no_se_puede_reasignar():
    semana = _semana()
    with pytest.raises(AttributeError, match="curva ideal"):
        semana.esperado = Tiempo(120.0)
    assert semana.esperado == Tiempo(129.0)


def test_una_semana_se_construye_con_tiempos_y_con_una_fase_del_macro():
    with pytest.raises(TypeError):
        _semana(esperado=129.0)
    with pytest.raises(TypeError):
        _semana(recalculado=128.0)
    with pytest.raises(TypeError):
        _semana(fase="base_especifica")
    with pytest.raises(ValueError, match="extensión"):
        _semana(fase=Fase.EXTENSION)
    with pytest.raises(ValueError):
        _semana(numero=0)
    with pytest.raises(ValueError):
        _semana(km_planificados=-1.0)


def test_dos_semanas_sin_guardar_no_son_la_misma():
    assert _semana() != _semana()
    assert _semana(id=4) == _semana(id=4, numero=9)


# ── Lo que vale hoy ──────────────────────────────────────────────────────────


def test_el_tiempo_vigente_es_el_recalculado_si_lo_hay():
    semana = _semana()
    assert semana.vigente() == Tiempo(129.0)
    semana.reanclar(Tiempo(127.8))
    assert semana.vigente() == Tiempo(127.8)
    assert semana.esperado == Tiempo(129.0)        # reanclar no toca la ideal
    semana.reanclar(None)
    assert semana.vigente() == Tiempo(129.0)
    with pytest.raises(TypeError):
        semana.reanclar(127.8)


def test_el_ritmo_sale_del_tiempo_vigente():
    semana = _semana(recalculado=Tiempo(128.0))
    assert semana.ritmo(200).segundos_por_100 == 64.0


@pytest.mark.parametrize("prueba,piscina", [
    (Prueba(200, "libre"), Piscina.LARGA),
    (Prueba(100, "pecho"), Piscina.CORTA),
    (Prueba(1500, "libre"), Piscina.LARGA),
])
def test_las_zonas_son_las_que_calcula_el_motor(prueba, piscina):
    """El juego de la entidad y el diccionario que sirve el API, mismo ritmo por zona."""
    semana = _semana(esperado=Tiempo(prueba.distancia * 0.66), recalculado=Tiempo(prueba.distancia * 0.65))
    juego = semana.zonas(prueba, piscina)
    del_motor = MOTOR.zonas(
        semana.ritmo(prueba.distancia).segundos_por_100, prueba.distancia,
        prueba.estilo.value, piscina.value,
    )
    for zona in Zona.ordenadas():
        assert round(juego.ritmo_de(zona).segundos_por_100, 2) == del_motor[zona.value]["mid"]
        assert juego[zona].salida.segundos == del_motor[zona.value]["send_off"]
        assert round(juego[zona].descanso.segundos, 2) == del_motor[zona.value]["rest"]


# ── El parón ─────────────────────────────────────────────────────────────────


def test_parar_y_reanudar_dicen_si_cambiaron():
    semana = _semana()
    assert semana.parar("Lesión de hombro") is True
    assert (semana.deshabilitada, semana.razon) == (True, "Lesión de hombro")
    assert semana.parar("Lesión de hombro") is False
    assert semana.parar("Vacaciones") is True          # cambió la razón
    assert semana.reanudar() is True
    assert (semana.deshabilitada, semana.razon) == (False, None)
    assert semana.reanudar() is False


def test_el_paron_no_toca_ningun_tiempo():
    semana = _semana(recalculado=Tiempo(128.0))
    semana.parar()
    assert (semana.esperado, semana.recalculado) == (Tiempo(129.0), Tiempo(128.0))


# ── Lo nadado ────────────────────────────────────────────────────────────────


def test_la_semana_promedia_los_resultados_que_caen_en_sus_siete_dias():
    contexto = {"atleta_id": 5, "prueba": _200, "piscina": Piscina.LARGA}
    semana = _semana()
    nadados = [
        _resultado(128.0), _resultado(130.0, dia=6),
        _resultado(100.0, dia=7),                       # el lunes siguiente ya no es suyo
        _resultado(100.0, dia=-1),                      # ni el domingo anterior
        _resultado(100.0, atleta_id=6),                 # otro atleta
        _resultado(100.0, prueba=Prueba(100, "libre")), # otra prueba
    ]
    assert len(semana.resultados(nadados, atleta_id=5, prueba=_200)) == 2
    assert semana.real(nadados, **contexto) == Tiempo(129.0)
    assert semana.real([], **contexto) is None
    assert semana.real(nadados[2:], **contexto) is None


def test_un_tiempo_de_otra_piscina_entra_convertido():
    en_corta = _resultado(126.0, piscina=Piscina.CORTA)
    real = _semana().real([en_corta], atleta_id=5, prueba=_200, piscina=Piscina.LARGA)
    assert real == en_corta.tiempo_en(Piscina.LARGA)
    assert real.segundos > 126.0                        # en larga se nada más lento


def test_la_desviacion_se_mide_contra_la_curva_ideal():
    semana = _semana(recalculado=Tiempo(127.0))
    rapido, lento = semana.desviacion(Tiempo(128.0)), semana.desviacion(Tiempo(130.5))
    assert rapido.segundos == 1.0 and not rapido.es_regresion()   # 129 − 128, no 127 − 128
    assert lento.segundos == -1.5 and lento.es_regresion()
    assert rapido.base == Tiempo(129.0)
    assert semana.desviacion(None) is None


def test_un_tiempo_real_diminuto_no_tumba_la_desviacion():
    """`129 − 1e-20` es `129` en coma flotante, y una `Mejora` de 129 s sobre 129 s
    no se puede construir. El dato es absurdo pero pasa la validación (`gt=0`), y
    sin esto cada lectura de esa prueba daba 500 hasta borrarlo."""
    desviacion = _semana().desviacion(Tiempo(1e-20))
    assert 128.99 < desviacion.segundos < 129.0
    assert desviacion.resultado.segundos > 0
    assert round(desviacion.porcentaje, 2) == 100.0
    # Y con tiempos de verdad la resta es la de siempre, exacta.
    assert (Tiempo(130.0) - Tiempo(125.0)).segundos == 5.0
    assert (Tiempo(125.0) - Tiempo(130.0)).segundos == -5.0


# ── La traducción ────────────────────────────────────────────────────────────


def test_la_fila_se_lee_como_entidad():
    fila = WeeklyPlan(
        id=40, athlete_event_id=7, week_number=5, week_date=LUNES, planned_km=31.0,
        expected_time=128.4, recalc_time=127.9, phase="umbral_css",
        disabled=True, disable_reason="Competencia",
    )
    semana = semana_desde_fila(fila)
    assert (semana.id, semana.prueba_id, semana.numero, semana.fecha) == (40, 7, 5, LUNES)
    assert (semana.km_planificados, semana.fase) == (31.0, Fase.UMBRAL_CSS)
    assert (semana.esperado, semana.recalculado) == (Tiempo(128.4), Tiempo(127.9))
    assert (semana.deshabilitada, semana.razon) == (True, "Competencia")


def test_una_fila_sin_recalcular_no_inventa_un_tiempo():
    fila = WeeklyPlan(
        id=41, athlete_event_id=7, week_number=6, week_date=LUNES, planned_km=30.0,
        expected_time=128.0, recalc_time=None, phase="taper", disabled=False,
    )
    semana = semana_desde_fila(fila)
    assert semana.recalculado is None and semana.vigente() == Tiempo(128.0)
