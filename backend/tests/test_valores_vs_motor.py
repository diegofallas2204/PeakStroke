"""Los valores nuevos y el código vivo dicen lo mismo — hoy y mientras convivan.

`app/dominio/valores/` es aditivo: nada lo usa todavía, así que durante un tiempo
cada regla existe **dos veces** — en el tipo nuevo y en la función vieja que sigue
sirviendo a producción. Eso es exactamente la situación que produjo P2, y la
única defensa mientras dure es una red que falle en cuanto las dos se separen.

Estos tests son esa red. Cuando el paso correspondiente del rediseño retire la
copia vieja, su test de aquí se borra con ella (y el de `test_dominio_valores.py`
se queda, porque ese fija la regla, no la coincidencia).

No se comparan valores tecleados a mano: se comparan **contra la fuente viva**.
Un número copiado aquí no probaría nada — volvería a divergir a la primera.
"""
from __future__ import annotations

import inspect
import re
from typing import get_args

import pytest

from app.domain.engine import (
    F_FASE,
    I_MAX_TABLE,
    MACRO_15_PHASES,
    PHASE_LABELS,
    PHASE_VOLUME_KEY,
    POOL_FACTOR_25,
    STROKE_TPACE_CORRECTION_S,
    TIER_BY_AEROBIC,
    WEEKLY_VOLUME_KM,
    ZONE_OVER_RACE,
    ScienceEngine,
    classify_level,
    pool_factor,
    profile_for_event,
    zone_factors,
)
from app.dominio.valores import (
    EVENTOS_DE_REFERENCIA,
    Especialidad,
    EstadoDeMacro,
    Estilo,
    Fase,
    Genero,
    JuegoDeZonas,
    ModoDeIngreso,
    Nivel,
    Perfil,
    Piscina,
    Prescripcion,
    Prueba,
    Ritmo,
    Tendencia,
    Tiempo,
    TipoDeTest,
    Veredicto,
    Zona,
    factores_de_zona,
)
from app.engine.aerobic import analyze_splits
from app.engine.envelope import nearest_event
from app.engine.feasibility import analyze_feasibility
from app.engine.send_off import (
    REST_BOUNDS_S,
    REST_RATIO,
    ZONE_ORDER,
    clock_interval,
    rest_for,
)
from app.engine.time_utils import to_clock, to_seconds
from app.engine.zones import ZONE_ORDER as ZONE_ORDER_REEXPORTADO
from app.engine.zones import calc_zones

DISTANCIAS = [25, 50, 100, 200, 300, 400, 800, 1500]
RITMOS = [45.0, 58.24, 62.5, 71.3, 90.0, 133.7]


def _pruebas_validas() -> list[Prueba]:
    return [
        Prueba(distancia, estilo)
        for distancia in DISTANCIAS
        for estilo in Estilo
        if Prueba.es_valida(distancia, estilo)
    ]


class TestTiempoYRitmoVsTimeUtils:
    @pytest.mark.parametrize("texto", ["1:05.32", "65.32", "0:59.99", "25:00.00"])
    def test_desde_texto_coincide_con_to_seconds(self, texto):
        assert Tiempo.desde_texto(texto).segundos == pytest.approx(to_seconds(texto))

    @pytest.mark.parametrize("segundos", [45.1, 65.32, 116.48, 240.0, 1500.5])
    def test_texto_coincide_con_to_clock(self, segundos):
        assert Tiempo(segundos).texto() == to_clock(segundos)

    @pytest.mark.parametrize("segundos", [1.0, 12.4, 88.6, 90.0, 90.01, 247.3])
    def test_al_reloj_coincide_con_clock_interval(self, segundos):
        assert Tiempo(segundos).al_reloj().segundos == pytest.approx(clock_interval(segundos))


class TestPruebaVsElMotorDeDominio:
    """Lo que `Prueba` deriva y las tablas del motor indexan tienen que cuadrar.

    Los estilos válidos por distancia **ya no se comparan aquí**: `engine/events.py`
    se borró al migrar a `Prueba` y no queda copia contra la que contrastar. Esa
    regla se fija en `test_dominio_valores.py` y en `test_reglas_unicas.py`.
    """

    def test_el_perfil_sugerido_coincide_con_profile_for_event(self):
        for prueba in _pruebas_validas():
            esperado = profile_for_event(prueba.distancia)
            assert prueba.perfil_sugerido().clave_cientifica == esperado

    def test_el_evento_mas_cercano_coincide_con_nearest_event(self):
        for distancia in [*DISTANCIAS, 150, 300, 600, 1000, 2000]:
            assert Prueba(distancia).evento_mas_cercano() == nearest_event(distancia)

    def test_las_distancias_de_referencia_son_las_de_la_tabla_de_i_max(self):
        assert set(EVENTOS_DE_REFERENCIA) == set(I_MAX_TABLE["elite"])

    def test_el_tier_coincide_con_la_tabla_de_dominancia_aerobica(self):
        for distancia, datos in TIER_BY_AEROBIC.items():
            assert Prueba(distancia).tier() == datos["tier"]

    def test_la_correccion_de_estilo_es_la_del_motor(self):
        # En los dos sentidos: que cada estilo esté en la tabla **y** que la
        # tabla no tenga uno que el enum no contemple. Un estilo nuevo en el
        # motor sin miembro aquí sería un `KeyError` el día que se indexe.
        assert {e.clave_cientifica for e in Estilo} == set(STROKE_TPACE_CORRECTION_S)
        for estilo in Estilo:
            assert estilo.correccion_tpace_s == STROKE_TPACE_CORRECTION_S[estilo.clave_cientifica]

    def test_el_factor_de_piscina_es_el_del_motor(self):
        assert {p.clave_cientifica for p in Perfil} == set(POOL_FACTOR_25)
        for perfil in Perfil:
            clave = perfil.clave_cientifica
            assert Piscina.CORTA.factor(perfil) == POOL_FACTOR_25[clave]
            assert Piscina.CORTA.factor(perfil) == pool_factor(clave, "25")
            assert Piscina.LARGA.factor(perfil) == pool_factor(clave, "50")


class TestZonaVsSendOff:
    """La lista suelta y el enum ordenado no pueden separarse sin que esto falle."""

    def test_el_orden_del_enum_es_zone_order(self):
        assert [z.value for z in Zona.ordenadas()] == list(ZONE_ORDER)
        assert [z.value for z in Zona.ordenadas()] == list(ZONE_ORDER_REEXPORTADO)

    def test_no_hay_zonas_de_mas_ni_de_menos(self):
        assert {z.value for z in Zona} == set(REST_RATIO) == set(REST_BOUNDS_S)

    def test_los_ratios_de_descanso_son_los_del_motor(self):
        for zona in Zona:
            assert zona.ratio_descanso == REST_RATIO[zona.value]
            assert zona.limites_descanso_s == REST_BOUNDS_S[zona.value]

    @pytest.mark.parametrize("trabajo", [7.5, 30.0, 67.0, 120.0, 600.0])
    def test_el_descanso_calculado_coincide_con_rest_for(self, trabajo):
        for zona in Zona:
            assert zona.descanso_para(Tiempo(trabajo)).segundos == pytest.approx(
                rest_for(zona.value, trabajo)
            )

    def test_los_factores_de_zona_son_los_del_motor(self):
        for prueba in _pruebas_validas():
            perfil = prueba.perfil_sugerido()
            mios = factores_de_zona(perfil, prueba.distancia)
            del_motor = zone_factors(perfil.clave_cientifica, prueba.distancia)
            assert {z.value: f for z, f in mios.items()} == del_motor

    def test_la_tabla_completa_es_la_misma(self):
        for perfil in Perfil:
            del_motor = ZONE_OVER_RACE[perfil.clave_cientifica]
            for distancia, factores in del_motor.items():
                mios = factores_de_zona(perfil, distancia)
                assert {z.value: f for z, f in mios.items()} == factores


class TestJuegoDeZonasVsCalcZones:
    """El adaptador que hoy alimenta la tabla del equipo y el nuevo tipo cuadran."""

    @pytest.mark.parametrize("ritmo", RITMOS)
    @pytest.mark.parametrize("piscina", list(Piscina))
    @pytest.mark.parametrize("rep", [50, 100, 200])
    def test_ritmo_salida_y_descanso_coinciden_zona_a_zona(self, ritmo, piscina, rep):
        for prueba in _pruebas_validas():
            viejo = calc_zones(ritmo, prueba.distancia, prueba.estilo.value, piscina.value, rep)
            nuevo = JuegoDeZonas.de(
                Ritmo(ritmo), prueba, piscina, distancia_rep=rep,
            )
            for zona in Zona.ordenadas():
                esperado = viejo[zona.value]
                prescripcion = nuevo[zona]
                assert round(prescripcion.ritmo.segundos_por_100, 2) == esperado["mid"]
                assert prescripcion.salida.segundos == pytest.approx(esperado["send_off"])
                assert round(prescripcion.descanso.segundos, 2) == pytest.approx(esperado["rest"])

    def test_la_prescripcion_suelta_tambien_coincide(self):
        # `send_off.training_intervals` redondea el trabajo a 2 decimales antes de
        # cuadrar al reloj; `calc_zones` no. Aquí se comprueba la vía de zonas,
        # que es la que ve el entrenador en la tabla del equipo.
        prescripcion = Prescripcion.para(Zona.MVO2, Ritmo(62.5), 200)
        trabajo = 62.5 * 2
        assert prescripcion.salida.segundos == pytest.approx(
            clock_interval(trabajo + rest_for("MVO2", trabajo))
        )


class TestEscalasVsSuFuente:
    @pytest.mark.parametrize("umbral", [200.0, 150.1, 150.0, 120.1, 120.0, 95.1, 95.0, 70.1, 70.0])
    def test_el_nivel_coincide_con_classify_level(self, umbral):
        assert Nivel.desde_umbral(Ritmo(umbral)).value == classify_level(umbral)

    def test_las_fases_son_las_cinco_claves_cientificas_mas_la_extension(self):
        assert {f.value for f in Fase} == set(F_FASE)

    def test_cada_fase_lleva_su_f_fase(self):
        for fase in Fase:
            assert fase.f_fase == F_FASE[fase.value]

    def test_el_orden_cronologico_es_el_de_la_estructura_del_macro(self):
        # `MACRO_15_PHASES` es la fuente viva del orden. Si `Fase.secuencia()` se
        # separa de ella, el reparto de fases sobre semanas cambia sin que nadie
        # lo note — exactamente lo que pasa con dos listas de zonas.
        del_motor = tuple(fase for _, _, fase in MACRO_15_PHASES)
        assert tuple(f.value for f in Fase.secuencia()) == del_motor

    def test_la_banda_de_volumen_es_la_del_motor(self):
        for fase in Fase:
            assert fase.clave_de_volumen == PHASE_VOLUME_KEY[fase.value]
            for nivel in Nivel:
                esperada = WEEKLY_VOLUME_KM[nivel.value][PHASE_VOLUME_KEY[fase.value]]
                assert fase.banda_de_volumen(nivel) == esperada

    def test_las_etiquetas_de_fase_son_las_del_motor(self):
        for fase in Fase:
            assert fase.etiqueta == PHASE_LABELS[fase.value]

    def test_los_niveles_son_las_claves_de_las_tablas_cientificas(self):
        assert {n.value for n in Nivel} == set(WEEKLY_VOLUME_KM)

    def test_la_tendencia_es_la_que_anota_el_analisis_aerobico(self):
        # Las tres que puede escribir `analyze_splits`, ni una más.
        fuente = inspect.getsource(analyze_splits)
        anotadas = set(re.findall(r'trend = "(\w+)"', fuente))
        assert anotadas, (
            "No se encontró ninguna asignación `trend = \"...\"` en analyze_splits: "
            "cambió de forma y este pin dejó de leer lo que dice comprobar."
        )
        assert {t.value for t in Tendencia} == anotadas

    def test_el_veredicto_es_el_de_la_factibilidad(self):
        fuente = inspect.getsource(analyze_feasibility)
        emitidos = set(re.findall(r'status = "(\w+)"', fuente))
        assert emitidos, "cambió la forma de anotar el veredicto en analyze_feasibility"
        assert {v.value for v in Veredicto} == emitidos

    def test_la_proyeccion_anual_habla_OTRO_vocabulario_y_este_tipo_no_lo_cubre(self):
        """`Veredicto` es el de la factibilidad, y solo ese. Queda apuntado.

        `ScienceEngine.project_season` emite `ok | optimistic | unrealistic`, que
        es una escala distinta: no dice si la meta es alcanzable sino si la
        temporada proyectada es realista. El §3.4 del rediseño solo nombra la
        primera, así que meter los dos vocabularios en un enum sería inventar
        modelo — pero que falte **sin que nada avise** es cómo empezó P2.

        Y lo peor no es que sean dos: es que **se solapan a medias**. Los dos
        emiten `ok`, así que `Veredicto.desde_texto` traga el veredicto anual
        cuando dice `ok` y revienta cuando dice `optimistic`. Un tipo que acepta
        la mitad de lo que le llega es más difícil de detectar que uno que
        rechaza todo, y es exactamente la trampa que dejaría creer que este enum
        ya cubre las dos escalas.

        Este test es el aviso: si alguien decide unificarlas o crear la segunda,
        falla y hay que actualizar el modelo a la vez que el código.

        (De paso: los dos comentarios que documentan esa escala —`engine.py:437` y
        `simulator/schemas.py:102`— dicen `below`, un veredicto que el código no
        emite.)
        """
        anual = set(re.findall(r'verdict = "(\w+)"', inspect.getsource(ScienceEngine)))
        de_factibilidad = {v.value for v in Veredicto}
        assert anual == {"ok", "optimistic", "unrealistic"}, (
            f"cambiaron los veredictos de la proyección anual: {anual}"
        )
        assert anual - de_factibilidad == {"optimistic", "unrealistic"}, (
            "Cambió la relación entre las dos escalas de veredicto. Decide en el "
            "modelo (§3.4) si son una o dos antes de tocar el enum."
        )
        assert anual & de_factibilidad == {"ok"}, "el solape a medias dejó de serlo"


def _literales(anotacion: object) -> set[str]:
    """Los `str` de un `Literal[...]`, incluso envuelto en `| None`."""
    valores: set[str] = set()
    for arg in get_args(anotacion):
        if isinstance(arg, str):
            valores.add(arg)
        else:
            valores |= _literales(arg)
    return valores


class TestEscalasVsLosSchemas:
    """Los `Literal` de Pydantic son hoy la única barrera; el enum tiene que caber."""

    def test_el_genero_y_la_especialidad_son_los_del_formulario(self):
        from app.modules.swimmers.schemas import Gender, Specialty

        assert {g.value for g in Genero} == set(get_args(Gender))
        assert {e.value for e in Especialidad} == set(get_args(Specialty))

    def test_el_estilo_es_el_del_formulario(self):
        from app.modules.swimmers.schemas import MainStroke

        assert {e.value for e in Estilo} == set(get_args(MainStroke))

    def test_el_estado_del_macro_es_el_del_endpoint(self):
        from app.modules.plans.schemas import PlanUpdate

        assert {e.value for e in EstadoDeMacro} == _literales(
            PlanUpdate.model_fields["status"].annotation
        )

    def test_la_piscina_es_la_del_endpoint(self):
        from app.modules.plans.schemas import PlanCreate

        assert {p.value for p in Piscina} == _literales(
            PlanCreate.model_fields["pool"].annotation
        )

    def test_el_tipo_de_test_y_el_modo_de_ingreso_son_los_del_endpoint(self):
        from app.modules.aerobic_tests.schemas import AerobicTestCreate

        def _opciones(campo: str) -> set[str]:
            patron = next(
                m.pattern for m in AerobicTestCreate.model_fields[campo].metadata
                if hasattr(m, "pattern")
            )
            return set(patron.strip("^$()").split("|"))

        assert {t.value for t in TipoDeTest} == _opciones("test_type")
        assert {m.value for m in ModoDeIngreso} == _opciones("input_mode")
