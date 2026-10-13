"""C9 punto 3 (REDISENO §5.7): `PruebaObjetivo`.

Lo que un atleta quiere nadar en un macrociclo: una `Prueba`, de dónde parte y a
dónde quiere llegar. Hasta el 2026-10-13 era la fila `AthleteEvent`, armada en
`api/v1/macrociclos/nomina.py` con `AthleteEvent(**event_data.model_dump())`.

Decisiones (opción recomendada, 2026-10-13):
- `factibilidad()` **recibe el techo**, no lo calcula: las entidades no importan
  los servicios, y el techo es del motor (como el CSS de `Sesion.carga`);
- los umbrales del veredicto viven en `Veredicto.del_uso` y el motor los usa:
  la entidad y el motor no pueden dar dos veredictos;
- una prueba nueva se guarda con el estilo **canónico** («crol» entra, «libre»
  sale), como la ficha desde el punto 1. Las filas de antes no se tocan;
- las semanas siguen siendo filas hasta el punto 4, pero ya no las arma el API.

Aquí, el dominio y la traducción; el alta por el API, en
`test_prueba_objetivo_api.py`.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.dominio.entidades import PruebaObjetivo
from app.dominio.servicios.motor import MOTOR
from app.dominio.valores import Estilo, Mejora, Prueba, Tiempo, Veredicto
from app.persistencia.mapeo import prueba_objetivo_desde_fila
from app.persistencia.tablas.planes import AthleteEvent

# ── El dominio ───────────────────────────────────────────────────────────────


def _prueba(actual: float = 130.0, meta: float = 125.0, distancia: int = 200) -> PruebaObjetivo:
    return PruebaObjetivo.nueva(distancia, "libre", actual, meta)


def test_una_prueba_que_no_existe_no_se_puede_tener_de_objetivo():
    with pytest.raises(ValueError, match="No existe la prueba 50 combinado"):
        PruebaObjetivo.nueva(50, "combinado", 30.0, 29.0)


def test_el_alias_del_estilo_entra_y_sale_el_canonico():
    assert PruebaObjetivo.nueva(200, "crol", 130.0, 125.0).prueba == Prueba(200, Estilo.LIBRE)


def test_los_tiempos_son_tiempos_no_numeros_sueltos():
    """Un `float` no dice si es un tiempo o un ritmo (P6): el constructor lo rechaza."""
    with pytest.raises(TypeError):
        PruebaObjetivo(prueba=Prueba(200), actual=130.0, meta=Tiempo(125.0))
    with pytest.raises(TypeError):
        PruebaObjetivo(prueba=Prueba(200), actual=Tiempo(130.0), meta=125.0)
    with pytest.raises(TypeError):
        PruebaObjetivo(prueba="200 libre", actual=Tiempo(130.0), meta=Tiempo(125.0))
    with pytest.raises(ValueError):
        PruebaObjetivo.nueva(200, "libre", 0.0, 125.0)


def test_la_prioridad_empieza_en_uno():
    assert _prueba().prioridad == 1
    with pytest.raises(ValueError, match="prioridad"):
        PruebaObjetivo.nueva(200, "libre", 130.0, 125.0, prioridad=0)
    with pytest.raises(TypeError):
        PruebaObjetivo.nueva(200, "libre", 130.0, 125.0, prioridad=1.5)


def test_la_mejora_pedida_va_de_la_marca_a_la_meta():
    pedida = _prueba(130.0, 125.0).mejora_pedida()
    assert pedida.segundos == 5.0
    assert pedida.base == Tiempo(130.0)
    assert pedida.resultado == Tiempo(125.0)
    assert pedida.porcentaje == pytest.approx(3.846, abs=1e-3)


def test_una_meta_ya_alcanzada_no_pide_nada_y_una_mas_lenta_es_regresion():
    assert _prueba(130.0, 130.0).mejora_pedida().segundos == 0.0
    assert _prueba(130.0, 132.0).mejora_pedida().es_regresion()


def test_dos_pruebas_sin_guardar_no_son_la_misma_aunque_coincidan():
    assert _prueba() != _prueba()
    a, b = _prueba(), _prueba(140.0, 139.0)
    a.id = b.id = 9
    assert a == b


class TestVeredicto:
    def test_los_dos_umbrales_caen_del_lado_permisivo(self):
        assert Veredicto.del_uso(0.85) is Veredicto.OK
        assert Veredicto.del_uso(0.8501) is Veredicto.AVISO
        assert Veredicto.del_uso(1.15) is Veredicto.AVISO
        assert Veredicto.del_uso(1.1501) is Veredicto.AGRESIVO

    def test_no_pedir_nada_es_realista(self):
        assert Veredicto.del_uso(0.0) is Veredicto.OK
        assert Veredicto.del_uso(-0.3) is Veredicto.OK


_CASOS = [
    # distancia, actual, semanas, n_mac, edad, base aeróbica
    (50, 28.5, 12, 1, None, None),
    (100, 62.0, 12, 1, 13, None),
    (200, 130.0, 12, 1, None, 75.0),
    (200, 116.48, 15, 1, None, None),
    (400, 280.0, 15, 2, 16, 72.0),
    (800, 590.0, 18, 1, None, None),
    (1500, 1080.0, 8, 3, None, 68.0),
]
# Cuánto del techo se pide: de una meta más lenta que la marca a tres veces lo
# posible, pasando a los dos lados de cada umbral (0.85 y 1.15).
#
# A los lados y no ENCIMA, a propósito: entidad y motor comparten los umbrales
# pero cada uno calcula el cociente con sus números, y con la meta clavada en
# 0.85 el último bit puede caer distinto (ver `PruebaObjetivo.factibilidad`).
# Este test fija que clasifican igual; no promete el empate en el borde.
_USOS = (-0.2, 0.0, 0.3, 0.84, 0.86, 1.0, 1.14, 1.16, 3.0)


class TestFactibilidad:
    """La entidad clasifica; el techo lo trae quien llama, del motor."""

    @pytest.mark.parametrize("distancia,actual,semanas,n_mac,edad,base", _CASOS)
    def test_da_el_mismo_veredicto_que_el_motor(self, distancia, actual, semanas, n_mac, edad, base):
        envolvente = MOTOR.envolvente(
            distancia, actual, semanas, n_mac=n_mac, edad=edad, base_aerobica=base,
        )
        techo = Mejora(envolvente.mejora_maxima_s, Tiempo(actual))
        vistos = set()
        for uso in _USOS:
            meta = actual - uso * envolvente.mejora_maxima_s
            del_motor = MOTOR.factibilidad(
                distancia, actual, meta, semanas, n_mac=n_mac, edad=edad, base_aerobica=base,
            ).estado
            de_la_entidad = PruebaObjetivo.nueva(distancia, "libre", actual, meta).factibilidad(techo)
            assert de_la_entidad is Veredicto.desde_texto(del_motor), (uso, meta)
            vistos.add(de_la_entidad)
        # Si la rejilla no pisa los tres veredictos, el test compara menos de lo que dice.
        assert vistos == set(Veredicto)

    def test_una_meta_ya_alcanzada_es_realista_sin_mirar_el_techo(self):
        techo = Mejora(0.0, Tiempo(130.0))
        assert _prueba(130.0, 131.0).factibilidad(techo) is Veredicto.OK

    def test_sin_techo_cualquier_mejora_es_agresiva(self):
        assert _prueba(130.0, 129.0).factibilidad(Mejora(0.0, Tiempo(130.0))) is Veredicto.AGRESIVO

    def test_el_techo_tiene_que_ser_el_de_esta_marca(self):
        """Un techo calculado para otro tiempo de partida es el de otro atleta."""
        with pytest.raises(ValueError, match="techo"):
            _prueba(130.0, 125.0).factibilidad(Mejora(4.0, Tiempo(140.0)))
        with pytest.raises(TypeError):
            _prueba(130.0, 125.0).factibilidad(4.0)


def test_el_motor_no_distingue_el_alias_del_estilo_canonico():
    """Lo que hace que guardar «libre» donde llegó «crol» no mueva ningún número."""
    comun = {
        "distancia": 200, "tiempo_actual": 130.0, "tiempo_meta": 125.0, "semanas": 12,
        "km_totales": 300.0, "curva": "science", "inicio": date(2026, 9, 7),
        "base_aerobica": 75.0,
    }
    assert MOTOR.generar_plan(estilo="crol", **comun) == MOTOR.generar_plan(estilo="libre", **comun)
    assert MOTOR.zonas(65.0, 200, "crol") == MOTOR.zonas(65.0, 200, "libre")
    assert MOTOR.zonas(72.0, 200, "braza", "25") == MOTOR.zonas(72.0, 200, "pecho", "25")


# ── La traducción ────────────────────────────────────────────────────────────


def test_la_fila_se_lee_como_entidad_aunque_guarde_un_alias():
    fila = AthleteEvent(
        id=4, athlete_plan_id=9, priority=2, distance=100, stroke="braza",
        current_time=75.5, goal_time=73.0,
    )
    prueba = prueba_objetivo_desde_fila(fila)
    assert (prueba.id, prueba.inscripcion_id, prueba.prioridad) == (4, 9, 2)
    assert prueba.prueba == Prueba(100, Estilo.PECHO)
    assert (prueba.actual, prueba.meta) == (Tiempo(75.5), Tiempo(73.0))
