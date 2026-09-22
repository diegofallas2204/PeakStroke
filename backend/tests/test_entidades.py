"""Las entidades del paso 2: comportamiento que vuelve a su objeto.

Lo que estos tests fijan no es aritmética —de eso se encarga
`test_entidades_vs_motor.py`, comparando contra la fuente viva— sino las reglas
que ahora son del objeto: la identidad, el estado derivado del calendario y, la
que importa, que un test aeróbico no pueda existir con llegadas de reloj sin
convertir.

Ver `docs/REDISENO.md` §5.
"""
from __future__ import annotations

import ast
import inspect
import sys
from datetime import date
from pathlib import Path

import pytest

from app.dominio.entidades import (
    Atleta,
    Competencia,
    FaseDelMacro,
    Macrociclo,
    TestAerobico,
    anios_cumplidos,
    lunes_de,
)
from app.dominio.valores import (
    Especialidad,
    EstadoDeMacro,
    Estilo,
    Fase,
    ModoDeIngreso,
    Perfil,
    Prueba,
    Tendencia,
    Tiempo,
    TipoDeTest,
)


class TestElDominioNoImportaNada:
    """La regla no negociable de `CLAUDE.md`, comprobada en vez de recordada.

    `app/dominio/` no importa infraestructura: ni SQLAlchemy, ni FastAPI, ni
    Pydantic, ni `app.api`, ni `app.persistencia`, ni `app.core`.
    Se comprueba al revés —**todo import absoluto tiene que ser de la biblioteca
    estándar**— porque una lista de prohibidos solo caza lo que ya se nos ocurrió
    prohibir, y lo que rompe esto es siempre el import que nadie previó.

    Ahora importa más que en el paso 1: `persistencia/mapeo/` está justo al lado
    y traduce en la dirección correcta (fuera → dentro). El día que alguien
    invierta esa flecha para resolver un apuro, el dominio deja de ser portable y
    los repositorios del paso 5 se quedan sin sitio donde vivir.
    """

    def _imports_absolutos(self, archivo: Path) -> list[str]:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        raices: list[str] = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                raices += [alias.name.split(".")[0] for alias in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
                raices.append(nodo.module.split(".")[0])
        return raices

    def test_ningun_archivo_del_dominio_importa_fuera_de_la_biblioteca_estandar(self):
        dominio = Path(__file__).resolve().parent.parent / "app" / "dominio"
        archivos = sorted(dominio.rglob("*.py"))
        assert archivos, "No se encontró app/dominio/: el test estaría pasando en vacío"
        for archivo in archivos:
            for raiz in self._imports_absolutos(archivo):
                assert raiz in sys.stdlib_module_names, (
                    f"{archivo.relative_to(dominio.parent)} importa {raiz!r}. "
                    "app/dominio/ no importa NADA: ni infraestructura, ni app.api, "
                    "ni app.core, ni app.domain. La traducción va en persistencia/mapeo/."
                )


class TestIdentidadDeEntidad:
    """Una entidad es quién es, no cuánto vale."""

    def test_mismo_id_es_la_misma_entidad_aunque_cambien_los_datos(self):
        antes = Atleta(id=7, nombre="Sofía")
        despues = Atleta(id=7, nombre="Sofía Ramírez", peso_kg=61.0)
        assert antes == despues

    def test_distinto_id_son_distintas_aunque_los_datos_coincidan(self):
        assert Atleta(id=1, nombre="Ana") != Atleta(id=2, nombre="Ana")

    def test_dos_atletas_sin_guardar_no_son_el_mismo_aunque_se_llamen_igual(self):
        # Dos hermanos homónimos no son un solo atleta. Hasta que algo les da
        # identidad no hay forma de saber si son la misma persona dos veces.
        uno, otro = Atleta(nombre="Ana"), Atleta(nombre="Ana")
        assert uno != otro
        assert uno == uno

    def test_entidades_de_distinta_clase_nunca_son_iguales(self):
        assert Atleta(id=3) != FaseDelMacro(fase=Fase.TAPER, id=3)

    def test_sirven_de_clave_en_un_conjunto(self):
        assert len({Atleta(id=1), Atleta(id=1), Atleta(id=2)}) == 2


class TestAtleta:
    def test_edad_el_dia_antes_del_cumpleanos_es_la_de_antes(self):
        atleta = Atleta(nacimiento=date(2008, 6, 15))
        assert atleta.edad_en(date(2026, 6, 14)) == 17
        assert atleta.edad_en(date(2026, 6, 15)) == 18

    def test_sin_fecha_de_nacimiento_la_edad_es_desconocida_no_cero(self):
        # Devolver 0 haría pasar por recién nacido a quien tiene el dato vacío.
        assert Atleta(nombre="Ana").edad_en(date(2026, 1, 1)) is None

    def test_la_fecha_de_referencia_importa(self):
        # La edad que ajusta el techo de mejora es la del INICIO del macrociclo:
        # sin eso, un plan se recalcularía distinto el día del cumpleaños.
        atleta = Atleta(nacimiento=date(2010, 12, 31))
        assert atleta.edad_en(date(2026, 1, 5)) == 15
        assert atleta.edad_en(date(2026, 12, 31)) == 16

    def test_la_funcion_suelta_y_el_metodo_son_la_misma_regla(self):
        nacimiento = date(2004, 2, 29)
        assert Atleta(nacimiento=nacimiento).edad_en(date(2026, 3, 1)) == \
            anios_cumplidos(nacimiento, date(2026, 3, 1))

    def test_tiene_cuenta_solo_si_alguien_canjeo_el_codigo(self):
        assert Atleta(nombre="Ana").tiene_cuenta() is False
        assert Atleta(nombre="Ana", usuario_id=4).tiene_cuenta() is True

    def test_el_perfil_lo_manda_la_prueba_no_la_especialidad(self):
        # Un fondista que hoy nada un 100 lo entrena como velocidad.
        fondista = Atleta(especialidad=Especialidad.FONDO)
        assert fondista.perfil_para(Prueba(100, Estilo.LIBRE)) is Perfil.VELOCIDAD

    def test_sin_prueba_delante_responde_la_especialidad(self):
        assert Atleta(especialidad=Especialidad.VELOCIDAD).perfil_para() is Perfil.VELOCIDAD

    def test_aguas_abiertas_entrena_como_fondo(self):
        # No tiene perfil propio en las tablas científicas.
        assert Atleta(especialidad=Especialidad.AGUAS_ABIERTAS).perfil_para() is Perfil.FONDO


class TestMacrociclo:
    def _macro(self, **extra) -> Macrociclo:
        # Lunes 5 de enero de 2026, 12 semanas.
        return Macrociclo(inicio=date(2026, 1, 5), semanas=12, **extra)

    def test_no_se_puede_construir_un_macrociclo_de_cero_semanas(self):
        with pytest.raises(ValueError):
            Macrociclo(inicio=date(2026, 1, 5), semanas=0)

    def test_la_semana_uno_empieza_el_lunes_aunque_el_plan_arranque_el_miercoles(self):
        # Sin normalizar al lunes, dos planes que arrancan en días distintos de
        # la misma semana dejan de ser comparables.
        miercoles = Macrociclo(inicio=date(2026, 1, 7), semanas=12)
        assert miercoles.lunes_de(1) == date(2026, 1, 5)
        assert miercoles.lunes_de(3) == date(2026, 1, 19)
        assert lunes_de(date(2026, 1, 7), 1) == date(2026, 1, 5)

    def test_antes_de_empezar_no_hay_semana_actual(self):
        assert self._macro().semana_actual(date(2025, 12, 30)) is None

    def test_va_contando_las_semanas(self):
        macro = self._macro()
        assert macro.semana_actual(date(2026, 1, 5)) == 1
        assert macro.semana_actual(date(2026, 1, 11)) == 1     # domingo de la 1
        assert macro.semana_actual(date(2026, 1, 12)) == 2

    def test_un_macro_vencido_se_queda_en_su_ultima_semana(self):
        assert self._macro().semana_actual(date(2027, 5, 1)) == 12

    def test_los_estados_manuales_mandan_sobre_la_fecha(self):
        for manual in (EstadoDeMacro.SUSPENDIDO, EstadoDeMacro.BORRADOR, EstadoDeMacro.TERMINADO):
            macro = self._macro(estado=manual)
            assert macro.estado_efectivo(date(2026, 1, 6)) is manual

    def test_un_macro_vigente_cuya_ultima_semana_paso_se_da_por_terminado(self):
        macro = self._macro()
        assert macro.ultimo_dia() == date(2026, 3, 29)
        assert macro.estado_efectivo(date(2026, 3, 29)) is EstadoDeMacro.ACTIVO
        assert macro.estado_efectivo(date(2026, 3, 30)) is EstadoDeMacro.TERMINADO

    def test_esta_vivo_es_la_regla_de_un_atleta_un_macro(self):
        assert self._macro().esta_vivo(date(2026, 2, 1)) is True
        assert self._macro().esta_vivo(date(2027, 2, 1)) is False
        assert self._macro(estado=EstadoDeMacro.BORRADOR).esta_vivo(date(2026, 2, 1)) is False

    def test_la_fase_de_una_semana_es_el_tramo_que_la_cubre(self):
        macro = self._macro(fases=[
            FaseDelMacro(Fase.BASE_GENERAL, nombre="Base", semana_inicio=1, semana_fin=4),
            FaseDelMacro(Fase.UMBRAL_CSS, nombre="Construcción", semana_inicio=5, semana_fin=10),
            FaseDelMacro(Fase.TAPER, nombre="Descenso", semana_inicio=11, semana_fin=12),
        ])
        assert macro.fase_de(1).nombre == "Base"
        assert macro.fase_de(7).nombre == "Construcción"
        # Fuera de rango cae en la última: las semanas de extensión se nadan en
        # régimen de taper, no en un tramo nuevo.
        assert macro.fase_de(15).nombre == "Descenso"

    def test_sin_fases_no_se_inventa_ninguna(self):
        assert self._macro().fase_de(3) is None

    def test_el_tramo_lleva_su_fase_y_el_nombre_es_aparte(self):
        # P3: el entrenador puede llamarle "Construcción" a lo que la ciencia
        # conoce como umbral_css; ninguno de los dos pierde su vocabulario.
        tramo = FaseDelMacro(Fase.UMBRAL_CSS, nombre="Construcción", semana_inicio=5, semana_fin=10)
        assert tramo.fase is Fase.UMBRAL_CSS
        assert tramo.nombre == "Construcción"
        assert tramo.duracion_en_semanas() == 6

    def test_un_tramo_sin_fase_de_dominio_no_se_construye(self):
        with pytest.raises(TypeError):
            FaseDelMacro(nombre="Construcción")          # type: ignore[call-arg]
        with pytest.raises(TypeError):
            FaseDelMacro("umbral_css", nombre="Construcción")   # texto, no Fase

    def test_la_extension_no_es_un_tramo_del_macro(self):
        with pytest.raises(ValueError, match="extensión"):
            FaseDelMacro(Fase.EXTENSION, nombre="Extra")

    def test_la_competencia_principal_es_una_pregunta_del_macro(self):
        macro = self._macro(competencias=[
            Competencia(nombre="Control", semana=6),
            Competencia(nombre="Nacional", semana=12, es_principal=True),
        ])
        assert macro.competencia_principal().nombre == "Nacional"
        assert self._macro().competencia_principal() is None


class TestLaInvarianteDelTestAerobico:
    """El caso de la nota 19 del vault: leer el reloj no puede salir mal."""

    def _t30(self, numeros, **extra) -> TestAerobico:
        return TestAerobico(
            tipo=TipoDeTest.T30, fecha=date(2026, 8, 16), numeros=numeros, **extra,
        )

    def test_las_llegadas_del_reloj_se_convierten_al_construir(self):
        # 3×100 salida 1:30 apuntado como lo marca el reloj de pared.
        test = self._t30([78.0, 169.0, 260.0], salida=Tiempo(90.0), modo=ModoDeIngreso.CLOCK)
        assert [p.tiempo_nadado.segundos for p in test.parciales] == [78.0, 79.0, 80.0]
        assert test.base_aerobica().segundos_por_100 == 79.0

    def test_el_error_de_114_por_ciento_ya_no_se_puede_construir(self):
        # Leído como tiempos de nado, ese mismo test daba 169 s/100m: +114 % de
        # base aeróbica, y con ella zonas, predicción y factibilidad.
        crudo = self._t30([78.0, 169.0, 260.0])
        bueno = self._t30([78.0, 169.0, 260.0], salida=Tiempo(90.0), modo=ModoDeIngreso.CLOCK)
        assert crudo.base_aerobica().segundos_por_100 == 169.0
        assert bueno.base_aerobica().segundos_por_100 == 79.0
        # Y lo que hace imposible equivocarse es que el modo entra por el
        # constructor, no por una llamada que alguien tenga que acordarse de hacer.

    def test_no_hay_puerta_trasera_para_meter_parciales_ya_hechos(self):
        # Si `Parcial` se pudiera pasar construido desde fuera, la conversión
        # volvería a ser opcional y la invariante sería decorativa.
        firma = inspect.signature(TestAerobico.__init__).parameters
        assert "parciales" not in firma, (
            "El constructor de TestAerobico acepta parciales ya hechos: eso "
            "reabre el camino por el que unas llegadas de reloj sin convertir "
            "vuelven a entrar como tiempos nadados."
        )
        assert "numeros" in firma

    def test_las_llegadas_de_reloj_exigen_el_intervalo(self):
        with pytest.raises(ValueError, match="intervalo de salida"):
            self._t30([78.0, 169.0], modo=ModoDeIngreso.CLOCK)

    def test_una_llegada_anterior_a_su_salida_es_un_dato_imposible(self):
        with pytest.raises(ValueError, match="repetición 2"):
            self._t30([78.0, 85.0], salida=Tiempo(90.0), modo=ModoDeIngreso.CLOCK)

    def test_las_salidas_son_fijas_no_encadenadas(self):
        # El reloj no espera a nadie: la repetición n sale en (n-1)*S aunque la
        # anterior se haya pasado del intervalo.
        test = self._t30([88.0, 92.0, 89.0], salida=Tiempo(90.0))
        assert [p.inicio.segundos for p in test.parciales] == [0.0, 90.0, 180.0]
        assert test.parciales[1].descanso_hasta(test.parciales[2]).segundos == pytest.approx(-2.0)
        assert test.intervalos_perdidos() == [2]

    def test_la_llegada_se_deriva_del_inicio_y_lo_nadado(self):
        test = self._t30([78.0, 79.0], salida=Tiempo(90.0))
        assert [p.llegada().segundos for p in test.parciales] == [78.0, 169.0]

    def test_sin_intervalo_no_hay_descanso_ni_densidad_pero_sigue_siendo_un_test(self):
        test = self._t30([78.0, 79.0, 80.0])
        assert test.se_nado_sobre_intervalo() is False
        assert test.densidad() is None
        assert test.descanso_medio() is None
        assert test.descansos() == []
        assert test.parciales[0].llegada() is None
        assert test.base_aerobica().segundos_por_100 == 79.0


class TestAnalisisDelTestAerobico:
    def test_un_t30_son_repeticiones_de_100_por_definicion(self):
        # Aceptar otra distancia produce una base que no compara con ningún otro
        # T-30. La regla vivía suelta en `aerobic_tests/service.py`.
        test = TestAerobico(
            tipo=TipoDeTest.T30, fecha=date(2026, 8, 16),
            numeros=[78.0] * 30, distancia_rep=400,
        )
        assert test.distancia_rep == 100

    def test_un_test_personalizado_respeta_su_distancia(self):
        test = TestAerobico(
            tipo=TipoDeTest.CUSTOM, fecha=date(2026, 8, 16),
            numeros=[300.0] * 12, distancia_rep=400,
        )
        assert test.distancia_rep == 400
        assert test.base_aerobica().segundos_por_100 == 75.0

    def test_los_tests_sin_parciales_no_pasan_por_aqui(self):
        for tipo in (TipoDeTest.CSS, TipoDeTest.DIRECT):
            with pytest.raises(ValueError, match="no se analiza por parciales"):
                TestAerobico(tipo=tipo, fecha=date(2026, 8, 16), numeros=[78.0])

    def test_un_test_sin_parciales_es_un_test_vacio(self):
        with pytest.raises(ValueError, match="al menos un parcial"):
            TestAerobico(tipo=TipoDeTest.T30, fecha=date(2026, 8, 16), numeros=[])

    def test_la_tendencia_sale_de_la_pendiente_no_se_elige(self):
        subiendo = [78.0 + i * 0.3 for i in range(10)]
        assert TestAerobico(
            tipo=TipoDeTest.T30, fecha=date(2026, 8, 16), numeros=subiendo,
        ).tendencia() is Tendencia.EMPEORANDO
        assert TestAerobico(
            tipo=TipoDeTest.T30, fecha=date(2026, 8, 16), numeros=subiendo[::-1],
        ).tendencia() is Tendencia.MEJORANDO
        assert TestAerobico(
            tipo=TipoDeTest.T30, fecha=date(2026, 8, 16), numeros=[78.0] * 10,
        ).tendencia() is Tendencia.ESTABLE

    def test_la_densidad_es_la_fraccion_del_ciclo_que_es_nado(self):
        # Lo que distingue dos series al mismo ritmo que no entrenan lo mismo.
        test = TestAerobico(
            tipo=TipoDeTest.T30, fecha=date(2026, 8, 16),
            numeros=[72.0] * 10, salida=Tiempo(90.0),
        )
        assert test.densidad() == pytest.approx(0.8)
        assert test.descanso_medio().segundos == pytest.approx(18.0)
        assert test.ratio_descanso_trabajo() == pytest.approx(0.25)

    def test_el_intervalo_de_salida_es_siempre_positivo(self):
        with pytest.raises(ValueError):
            TestAerobico(
                tipo=TipoDeTest.T30, fecha=date(2026, 8, 16),
                numeros=[78.0], salida=-5.0,
            )
