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

import app.dominio.servicios.temporada as temporada
from app.dominio.servicios.envolvente import evento_de_referencia, factibilidad
from app.dominio.servicios.motor import MOTOR
from app.dominio.servicios.tablas import (
    MACRO_15_FASES,
    TABLA_I_MAX,
    TIER_POR_AEROBICO,
    VOLUMEN_MAXIMO_POR_ESTILO,
)
from app.dominio.servicios.zonas import al_reloj
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
    Piscina,
    Prescripcion,
    Prueba,
    Ritmo,
    Tendencia,
    Tiempo,
    TipoDeTest,
    Veredicto,
    Zona,
)
from app.engine.aerobic import analyze_splits
from app.engine.time_utils import to_clock, to_seconds

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
    def test_al_reloj_coincide_con_el_del_motor(self, segundos):
        # `send_off.clock_interval` era la otra mitad de este pin y se borró con
        # su módulo; hoy el motor cuadra al reloj llamando al propio `Tiempo`.
        assert Tiempo(segundos).al_reloj().segundos == pytest.approx(al_reloj(segundos))


class TestPruebaVsLasTablasQueSiguenVivas:
    """Lo que `Prueba` deriva y las tablas del motor indexan tienen que cuadrar.

    **La mayoría de los pines de esta clase se borraron con su copia** en la
    fusión de motores (C4): el perfil por distancia, la corrección de estilo,
    el factor de piscina y los factores de zona ya no tienen una segunda
    implementación en `app/domain/` contra la que contrastar — `Prueba`,
    `Estilo`, `Piscina` y `Zona` **son** la fuente, y `test_dominio_valores.py`
    fija sus reglas. Lo que queda aquí son los pines cuya otra mitad sigue viva
    en `dominio/servicios/tablas.py`.
    """

    def test_el_evento_mas_cercano_coincide_con_el_del_motor(self):
        for distancia in [*DISTANCIAS, 150, 300, 600, 1000, 2000]:
            assert Prueba(distancia).evento_mas_cercano() == evento_de_referencia(distancia)

    def test_las_distancias_de_referencia_son_las_de_la_tabla_de_i_max(self):
        assert set(EVENTOS_DE_REFERENCIA) == set(TABLA_I_MAX["elite"])

    def test_el_tier_coincide_con_la_tabla_de_dominancia_aerobica(self):
        for distancia, datos in TIER_POR_AEROBICO.items():
            assert Prueba(distancia).tier() == datos["tier"]


class TestJuegoDeZonasVsCalcZones:
    """El tipo y el motor construyen el mismo juego de zonas.

    Siguen siendo dos implementaciones: `JuegoDeZonas.de` arma prescripciones y
    `MotorCientifico.zonas` arma el diccionario que consume la interfaz. Las dos
    leen las mismas tablas, pero no comparten el código que las usa.
    """

    @pytest.mark.parametrize("ritmo", RITMOS)
    @pytest.mark.parametrize("piscina", list(Piscina))
    @pytest.mark.parametrize("rep", [50, 100, 200])
    def test_ritmo_salida_y_descanso_coinciden_zona_a_zona(self, ritmo, piscina, rep):
        for prueba in _pruebas_validas():
            viejo = MOTOR.zonas(ritmo, prueba.distancia, prueba.estilo.value, piscina.value, rep)
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
        # `intervalos_de_entrenamiento` redondea el trabajo a 2 decimales antes
        # de cuadrar al reloj; la vía de zonas no. Aquí se comprueba esta, que es
        # la que ve el entrenador en la tabla del equipo.
        prescripcion = Prescripcion.para(Zona.MVO2, Ritmo(62.5), 200)
        trabajo = 62.5 * 2
        assert prescripcion.salida.segundos == pytest.approx(
            al_reloj(trabajo + Zona.MVO2.descanso_para(Tiempo(trabajo)).segundos)
        )


class TestEscalasVsSuFuente:
    """Igual que arriba: los pines contra `app/domain/engine.py` se borraron con
    él. `Nivel`, `Fase` y sus bandas de volumen ya no tienen segunda copia; lo
    que queda es lo que sigue viviendo en `dominio/servicios/tablas.py` y en los
    módulos que la fusión no absorbió.
    """

    def test_el_orden_cronologico_es_el_de_la_estructura_del_macro(self):
        # `MACRO_15_FASES` es la fuente viva del orden, y la usa la curva
        # científica. Si `Fase.secuencia()` se separa de ella, el reparto de
        # fases sobre semanas cambia sin que nadie lo note.
        del_motor = tuple(fase for _, _, fase in MACRO_15_FASES)
        assert tuple(f.value for f in Fase.secuencia()) == del_motor

    def test_los_niveles_son_las_claves_de_las_tablas_cientificas(self):
        assert {n.value for n in Nivel} == set(TABLA_I_MAX)
        for estilo in Estilo:
            assert {n.value for n in Nivel} == set(
                VOLUMEN_MAXIMO_POR_ESTILO[estilo.clave_cientifica]
            )

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
        # La fuente viva se mudó con el paso 4: el veredicto lo emite el motor
        # único (`dominio.servicios.envolvente.factibilidad`) y
        # `engine/feasibility.analyze_feasibility` es ya solo la forma vieja del
        # resultado. El pin sigue el cálculo, que es lo que dice comprobar.
        fuente = inspect.getsource(factibilidad)
        emitidos = set(re.findall(r'estado = "(\w+)"', fuente))
        assert emitidos, "cambió la forma de anotar el veredicto en factibilidad()"
        assert {v.value for v in Veredicto} == emitidos

    def test_la_proyeccion_anual_habla_OTRO_vocabulario_y_este_tipo_no_lo_cubre(self):
        """`Veredicto` es el de la factibilidad, y solo ese. Queda apuntado.

        `temporada.proyectar` emite `ok | optimistic | unrealistic`, que
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

        (De paso: el comentario de `simulator/schemas.py` que documenta esa
        escala dice `below`, un veredicto que el código no emite.)
        """
        anual = set(re.findall(r'veredicto = "(\w+)"', inspect.getsource(temporada)))
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
        from app.api.vocabulario import Gender, Specialty

        assert {g.value for g in Genero} == set(get_args(Gender))
        assert {e.value for e in Especialidad} == set(get_args(Specialty))

    def test_el_estilo_es_el_del_formulario(self):
        from app.api.vocabulario import MainStroke

        assert {e.value for e in Estilo} == set(get_args(MainStroke))

    def test_el_estado_del_macro_es_el_del_endpoint(self):
        from app.api.v1.macrociclos.schemas import PlanUpdate

        assert {e.value for e in EstadoDeMacro} == _literales(
            PlanUpdate.model_fields["status"].annotation
        )

    def test_la_piscina_es_la_del_endpoint(self):
        from app.api.v1.macrociclos.schemas import PlanCreate

        assert {p.value for p in Piscina} == _literales(
            PlanCreate.model_fields["pool"].annotation
        )

    def test_el_tipo_de_test_y_el_modo_de_ingreso_son_los_del_endpoint(self):
        from app.api.v1.tests.schemas import AerobicTestCreate

        def _opciones(campo: str) -> set[str]:
            patron = next(
                m.pattern for m in AerobicTestCreate.model_fields[campo].metadata
                if hasattr(m, "pattern")
            )
            return set(patron.strip("^$()").split("|"))

        assert {t.value for t in TipoDeTest} == _opciones("test_type")
        assert {m.value for m in ModoDeIngreso} == _opciones("input_mode")
