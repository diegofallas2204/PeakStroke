"""Las entidades dan exactamente los mismos números que el código que sustituyen.

Mismo patrón que `test_valores_vs_motor.py`: no se comparan cifras tecleadas a
mano sino **la fuente viva**. Si `analyze_splits` cambia y `TestAerobico` no,
esto se pone rojo — que es el único aviso posible mientras las dos
implementaciones convivan.

Qué convive con qué, y por qué:

* `engine/aerobic.analyze_splits` sigue en pie porque lo usa el endpoint de
  previsualización (`aerobic_tests/router.py`), que analiza sin guardar nada.
  La escritura y la lectura ya pasan por la entidad.
* `core/dates.age_at` y `engine/progression.monday_of` ya **delegan**, así que
  ahí no hay dos implementaciones: lo que se fija es que la delegación no cambió
  la respuesta de sus llamadores.

Los pines se borran con su copia el día que la copia se retire.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.core.dates import age_at
from app.dominio.entidades import Atleta, Macrociclo, TestAerobico, lunes_de
from app.dominio.valores import EstadoDeMacro, ModoDeIngreso, TipoDeTest
from app.engine.aerobic import analyze_splits
from app.engine.progression import monday_of

# (numeros, distancia_rep, salida, modo) — casos que cubren los cuatro caminos:
# con y sin intervalo, en modo `rep` y en modo `clock`, con distancia de
# repetición propia y con intervalos perdidos.
CASOS = [
    ([78.0] * 30, 100, None, "rep"),
    ([78.0, 79.0, 80.0], 100, 90.0, "rep"),
    ([88.0, 92.0, 89.0], 100, 90.0, "rep"),          # el 2.º pierde el intervalo
    ([300.0] * 12, 400, None, "rep"),
    ([62.0], 50, 70.0, "rep"),                        # una sola repetición
    ([75.5, 76.2, 77.9, 78.1, 79.0], 100, 95.0, "rep"),
    ([78.0, 169.0, 260.0], 100, 90.0, "clock"),       # el caso de la nota 19
    ([240.0, 485.0, 733.0], 200, 250.0, "clock"),
    ([80.0 - i * 0.2 for i in range(15)], 100, 95.0, "clock_desde_rep"),
]


def _par(caso) -> tuple[TestAerobico, object]:
    """El mismo test analizado por la entidad y por la función que sustituye."""
    numeros, distancia, salida, modo = caso
    if modo == "clock_desde_rep":
        # Mismo test escrito como llegadas: la conversión tiene que devolver los
        # tiempos de nado originales por los dos caminos.
        numeros = [t + i * salida for i, t in enumerate(numeros)]
        modo = "clock"
    entidad = TestAerobico(
        tipo=TipoDeTest.CUSTOM, fecha=date(2026, 8, 16), numeros=numeros,
        distancia_rep=distancia, salida=salida, modo=ModoDeIngreso.desde_texto(modo),
    )
    motor = analyze_splits(numeros, distancia, send_off=salida, input_mode=modo)
    return entidad, motor


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: f"{len(c[0])}x{c[1]}-{c[3]}")
class TestTestAerobicoVsAnalyzeSplits:
    def test_la_conversion_a_tiempo_nadado_coincide(self, caso):
        entidad, motor = _par(caso)
        nadados = [round(p.tiempo_nadado.segundos, 2) for p in entidad.parciales]
        assert nadados == motor.rep_times

    def test_las_salidas_de_cada_repeticion_coinciden(self, caso):
        entidad, motor = _par(caso)
        inicios = [p.inicio.segundos for p in entidad.parciales if p.inicio is not None]
        assert inicios == motor.departures

    def test_la_base_aerobica_coincide(self, caso):
        entidad, motor = _par(caso)
        assert entidad.base_aerobica().segundos_por_100 == motor.avg_per100

    def test_los_parciales_por_100_coinciden(self, caso):
        entidad, motor = _par(caso)
        assert [r.segundos_por_100 for r in entidad.parciales_por_100()] == motor.per100_splits

    def test_la_consistencia_y_la_tendencia_coinciden(self, caso):
        entidad, motor = _par(caso)
        assert entidad.consistencia() == motor.std_dev
        assert entidad.tendencia().value == motor.trend
        assert entidad.pendiente() == motor.trend_slope

    def test_el_descanso_y_la_densidad_coinciden(self, caso):
        entidad, motor = _par(caso)
        assert [d.segundos for d in entidad.descansos()] == motor.rest_per_rep
        assert entidad.densidad() == motor.density
        assert entidad.ratio_descanso_trabajo() == motor.work_rest_ratio
        assert entidad.intervalos_perdidos() == motor.missed_intervals
        medio = entidad.descanso_medio()
        assert (medio.segundos if medio else None) == motor.avg_rest


class TestEdadVsElEnvoltorio:
    """`core/dates.age_at` delega en `Atleta.edad_en`: misma respuesta."""

    @pytest.mark.parametrize("nacimiento", [
        date(2008, 6, 15), date(2004, 2, 29), date(1999, 12, 31), date(2026, 1, 1), None,
    ])
    @pytest.mark.parametrize("referencia", [
        date(2026, 1, 1), date(2026, 6, 14), date(2026, 6, 15), date(2026, 12, 31),
    ])
    def test_coinciden(self, nacimiento, referencia):
        assert age_at(nacimiento, referencia) == Atleta(nacimiento=nacimiento).edad_en(referencia)


class TestCalendarioVsElMotor:
    """`engine/progression.monday_of` delega en `dominio…macrociclo.lunes_de`."""

    @pytest.mark.parametrize("inicio", [
        date(2026, 1, 5),    # lunes
        date(2026, 1, 7),    # miércoles
        date(2026, 1, 11),   # domingo
        date(2025, 12, 29),  # cruza de año
    ])
    @pytest.mark.parametrize("semana", [1, 2, 12, 18])
    def test_coinciden(self, inicio, semana):
        assert monday_of(inicio, semana) == lunes_de(inicio, semana)

    def test_la_semana_actual_se_apoya_en_el_mismo_lunes(self, ):
        macro = Macrociclo(inicio=date(2026, 1, 7), semanas=12)
        assert macro.lunes_de(1) == monday_of(date(2026, 1, 7), 1)
        assert macro.semana_actual(date(2026, 1, 5)) == 1


class TestEstadoEfectivoVsElEnvoltorio:
    """El envoltorio de `plans/service` desenvuelve el `.value` y nada más."""

    @pytest.mark.parametrize("guardado,hoy,esperado", [
        (EstadoDeMacro.ACTIVO, date(2026, 2, 1), "active"),
        (EstadoDeMacro.ACTIVO, date(2027, 2, 1), "finished"),
        (EstadoDeMacro.SUSPENDIDO, date(2026, 2, 1), "suspended"),
        (EstadoDeMacro.BORRADOR, date(2027, 2, 1), "draft"),
        (EstadoDeMacro.TERMINADO, date(2026, 2, 1), "finished"),
    ])
    def test_el_texto_que_sale_a_la_api_es_el_de_siempre(self, guardado, hoy, esperado):
        macro = Macrociclo(inicio=date(2026, 1, 5), semanas=12, estado=guardado)
        assert macro.estado_efectivo(hoy).value == esperado
