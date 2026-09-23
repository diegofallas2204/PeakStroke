"""Invariantes de `app/dominio/valores/` — un test por regla que el tipo impone.

Estos tests no comprueban cálculos: comprueban que ciertos errores **no se pueden
escribir**. El que más importa es `test_no_existe_el_50_combinado`: la divergencia
que abrió P2 fue posible porque la validez de una prueba era una función suelta
que alguien pudo copiar mal. Mientras este test pase, la copia no cabe.

La correspondencia con el código vivo (que las tablas de aquí no se separen de
las de `app/domain` y `app/engine`) se comprueba en `test_valores_vs_motor.py`.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Mapping

import pytest

from app.dominio.valores import (
    Duracion,
    Especialidad,
    EstadoDeMacro,
    Estilo,
    Fase,
    Genero,
    JuegoDeZonas,
    Mejora,
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
)

TODAS_LAS_ESCALAS = [
    Nivel, Perfil, Fase, Especialidad, Genero, TipoDeTest,
    ModoDeIngreso, Tendencia, EstadoDeMacro, Veredicto,
]


# ───────────────────────────────────────────────────────────────────────────
# Tiempo y Ritmo son tipos DISTINTOS
# ───────────────────────────────────────────────────────────────────────────

class TestTiempoYRitmoNoSeMezclan:
    """El error de mezclar segundos absolutos con segundos/100 m deja de compilar.

    Hoy son ocho columnas `float` y nada impide restarlas entre sí (P6).
    """

    def test_no_se_resta_un_ritmo_de_un_tiempo(self):
        with pytest.raises(TypeError):
            Tiempo(116.48) - Ritmo(58.24)

    def test_no_se_resta_un_tiempo_de_un_ritmo(self):
        with pytest.raises(TypeError):
            Ritmo(58.24) - Tiempo(116.48)

    def test_no_se_suman(self):
        with pytest.raises(TypeError):
            Tiempo(116.48) + Ritmo(58.24)

    def test_no_se_comparan(self):
        with pytest.raises(TypeError):
            _ = Tiempo(58.24) < Ritmo(58.24)

    def test_no_son_iguales_aunque_lleven_el_mismo_numero(self):
        assert Tiempo(58.24) != Ritmo(58.24)

    def test_convertir_exige_decir_la_distancia(self):
        # Es justo el dato que falta cuando alguien los mezcla.
        assert Ritmo.desde(Tiempo(116.48), 200) == Ritmo(58.24)
        assert Ritmo(58.24).a_tiempo(200) == Tiempo(116.48)

    def test_un_ritmo_no_se_deriva_de_un_numero_suelto(self):
        # TypeError, no ValueError: pasar un float donde va un Tiempo es un bug
        # de programación. Pydantic convierte los ValueError en 422, así que un
        # bug se le reportaría al entrenador como error de su formulario.
        with pytest.raises(TypeError):
            Ritmo.desde(116.48, 200)


class TestTiempo:
    def test_desde_texto_en_los_tres_formatos(self):
        assert Tiempo.desde_texto("1:05.32").segundos == pytest.approx(65.32)
        assert Tiempo.desde_texto("65.32").segundos == pytest.approx(65.32)
        assert Tiempo.desde_texto("1:00:00").segundos == pytest.approx(3600.0)

    def test_texto_es_la_vuelta_de_desde_texto(self):
        assert Tiempo.desde_texto("1:05.32").texto() == "1:05.32"
        assert Tiempo(45.1).texto() == "45.10"

    @pytest.mark.parametrize("valor", [0, -1.0, float("nan"), float("inf")])
    def test_un_tiempo_no_puede_ser_cero_negativo_ni_infinito(self, valor):
        with pytest.raises(ValueError):
            Tiempo(valor)

    def test_se_ordenan(self):
        assert Tiempo(110.0) < Tiempo(116.48)
        assert max(Tiempo(110.0), Tiempo(116.48)) == Tiempo(116.48)

    def test_la_resta_devuelve_una_mejora_positiva_al_bajar_el_tiempo(self):
        mejora = Tiempo(120.0) - Tiempo(117.0)
        assert isinstance(mejora, Mejora)
        assert mejora.segundos == pytest.approx(3.0)
        assert mejora.base == Tiempo(120.0)
        assert mejora.base_segundos == pytest.approx(120.0)

    def test_al_reloj_redondea_hacia_arriba(self):
        # Hacia abajo recortaría el descanso, que es como una zona se vuelve otra.
        assert Tiempo(88.6).al_reloj().segundos == pytest.approx(90.0)
        assert Tiempo(90.0).al_reloj().segundos == pytest.approx(90.0)
        assert Tiempo(90.01).al_reloj().segundos == pytest.approx(95.0)

    def test_al_reloj_exige_un_paso_positivo(self):
        with pytest.raises(ValueError):
            Tiempo(90.0).al_reloj(0)


class TestMejora:
    """Lleva las dos formas en que hoy se expresa lo mismo: segundos y fracción."""

    def test_da_los_segundos_y_el_porcentaje_sin_recalcular(self):
        mejora = Tiempo(200.0) - Tiempo(190.0)
        assert mejora.segundos == pytest.approx(10.0)
        assert mejora.fraccion == pytest.approx(0.05)
        assert mejora.porcentaje == pytest.approx(5.0)

    def test_de_fraccion_es_el_lenguaje_del_motor_cientifico(self):
        mejora = Mejora.de_fraccion(Tiempo(200.0), 0.05)
        assert mejora.segundos == pytest.approx(10.0)
        assert mejora.resultado == Tiempo(190.0)

    def test_una_regresion_es_una_mejora_negativa_y_lo_dice(self):
        mejora = Tiempo(190.0) - Tiempo(200.0)
        assert mejora.es_regresion()
        assert mejora.porcentaje == pytest.approx(-5.263, abs=1e-3)

    def test_no_se_puede_mejorar_mas_que_el_tiempo_entero(self):
        # El resultado sería cero o negativo: no es un tiempo.
        with pytest.raises(ValueError):
            Mejora(200.0, Tiempo(200.0))

    def test_mejorar_un_RITMO_da_un_ritmo_y_no_un_tiempo(self):
        """P6 reentraba por aquí: con `base` en float, esto daba `Tiempo 1:18.00`.

        Una mejora de 2 s/100 m sobre 80 s/100 m es un ritmo de 78 s/100 m, no un
        tiempo absoluto de un minuto dieciocho. Una base que no sabe de qué
        unidad era solo puede adivinar, y adivinaba mal.
        """
        de_ritmo = Ritmo(80.0) - Ritmo(78.0)
        assert isinstance(de_ritmo.resultado, Ritmo)
        assert de_ritmo.resultado == Ritmo(78.0)

        de_tiempo = Tiempo(200.0) - Tiempo(190.0)
        assert isinstance(de_tiempo.resultado, Tiempo)
        assert de_tiempo.resultado == Tiempo(190.0)

    def test_la_base_tiene_que_traer_su_unidad(self):
        with pytest.raises(TypeError):
            Mejora(3.0, 120.0)

    def test_entre_dos_tiempos_es_lo_mismo_que_restarlos(self):
        assert Mejora.entre(Tiempo(120.0), Tiempo(117.0)) == Tiempo(120.0) - Tiempo(117.0)


class TestDuracionEsLoQuePuedeValerCeroOMenos:
    """El tipo que faltaba, y el hueco que dejaba.

    `Tiempo` hacía de nado y de instante a la vez, y solo el nado es siempre
    positivo. Estos tests son los casos que **no se podían escribir** antes.
    """

    def test_la_salida_de_la_primera_repeticion_es_cero(self):
        # `[0.0, 90.0, 180.0]` — está en test_aerobic_salida_api.py. Con `Tiempo`
        # el primer parcial de cualquier serie era inconstruible.
        salidas = [Duracion(i * 90.0) for i in range(3)]
        assert [d.segundos for d in salidas] == [0.0, 90.0, 180.0]
        with pytest.raises(ValueError):
            Tiempo(0.0)

    def test_el_descanso_perdido_es_negativo_y_eso_es_un_hecho(self):
        # Llegar después de tu salida no es un error de dato: es `missed_intervals`.
        salida, llegada = Duracion(90.0), Duracion(93.5)
        perdido = salida - llegada
        assert perdido.es_negativa()
        assert perdido.texto() == "-3.50"

    def test_la_conversion_reloj_a_nadado_ya_se_puede_escribir(self):
        """La invariante que más protege la base aeróbica, ahora expresable.

        Llegadas acumuladas del reloj → tiempos nadados. Antes reventaba en el
        primer parcial, porque restarle su salida (0) levantaba ValueError.
        """
        llegadas = [Duracion(78.0), Duracion(169.0), Duracion(260.0)]
        salidas = [Duracion(i * 90.0) for i in range(3)]
        nadados = [(ll - s).a_tiempo() for ll, s in zip(llegadas, salidas, strict=True)]
        assert [round(t.segundos, 2) for t in nadados] == [78.0, 79.0, 80.0]

    def test_restar_dos_instantes_da_un_hueco_no_una_mejora(self):
        # `Tiempo(90) - Tiempo(30)` sigue siendo la lectura de rendimiento
        # (+60 s, 66.67 %), que para dos llegadas de reloj no significa nada.
        # `diferencia()` es la aritmética de reloj.
        assert Tiempo(90.0).diferencia(Tiempo(30.0)) == Duracion(60.0)
        assert Tiempo(30.0).diferencia(Tiempo(90.0)) == Duracion(-60.0)
        assert isinstance(Tiempo(90.0) - Tiempo(30.0), Mejora)

    def test_desplazar_un_tiempo_por_una_duracion_sigue_siendo_un_tiempo(self):
        assert Tiempo(90.0) + Duracion(5.0) == Tiempo(95.0)
        assert Tiempo(90.0) + Duracion(-5.0) == Tiempo(85.0)

    def test_no_se_mezcla_con_ritmo_ni_se_convierte_sola(self):
        with pytest.raises(TypeError):
            Duracion(10.0) + Ritmo(58.24)
        with pytest.raises(TypeError):
            Tiempo(90.0) + Tiempo(5.0)
        # Pasar a Tiempo es explícito, y falla si no es positiva.
        assert Duracion(90.0).a_tiempo() == Tiempo(90.0)
        with pytest.raises(ValueError):
            Duracion(-1.0).a_tiempo()

    def test_admite_cero_y_negativos_pero_no_infinitos(self):
        assert Duracion(0.0).segundos == 0.0
        assert (-Duracion(5.0)).segundos == -5.0
        assert abs(Duracion(-5.0)) == Duracion(5.0)
        with pytest.raises(ValueError):
            Duracion(float("nan"))


# ───────────────────────────────────────────────────────────────────────────
# Prueba: la validez es del constructor
# ───────────────────────────────────────────────────────────────────────────

class TestPruebaRechazaLoImposible:
    def test_no_existe_el_50_combinado(self):
        """EL test. Esta prueba no existe en natación y ya se coló una vez.

        La copia mala vivía en `domain/engine.py` y la buena en `engine/events.py`
        (auditoría 2026-08-13). Con la regla dentro del constructor no hay dos
        copias que puedan separarse: el objeto inválido no llega a existir.
        """
        with pytest.raises(ValueError, match="50 combinado"):
            Prueba(50, Estilo.COMBINADO)
        with pytest.raises(ValueError):
            Prueba(50, "combinado")
        with pytest.raises(ValueError):
            Prueba(50, "im")
        assert Prueba.es_valida(50, Estilo.COMBINADO) is False

    def test_el_50_tiene_los_otros_cuatro_estilos(self):
        for estilo in (Estilo.LIBRE, Estilo.ESPALDA, Estilo.PECHO, Estilo.MARIPOSA):
            assert Prueba(50, estilo).estilo is estilo

    def test_de_600_para_arriba_solo_libre(self):
        assert Prueba(800, Estilo.LIBRE).distancia == 800
        for distancia in (800, 1500):
            for estilo in (Estilo.COMBINADO, Estilo.MARIPOSA, Estilo.ESPALDA, Estilo.PECHO):
                with pytest.raises(ValueError):
                    Prueba(distancia, estilo)

    def test_el_400_es_libre_o_combinado_pero_no_mariposa(self):
        assert Prueba(400, Estilo.COMBINADO).estilo is Estilo.COMBINADO
        with pytest.raises(ValueError):
            Prueba(400, Estilo.MARIPOSA)

    def test_de_100_a_299_se_nadan_los_cinco(self):
        assert Prueba.estilos_validos(100) == frozenset(Estilo)
        assert Prueba(200, Estilo.COMBINADO).estilo is Estilo.COMBINADO

    @pytest.mark.parametrize("distancia", [0, -100])
    def test_la_distancia_tiene_que_ser_positiva(self, distancia):
        # Valor malo del tipo correcto: lo puede escribir una persona -> 422.
        with pytest.raises(ValueError):
            Prueba(distancia, Estilo.LIBRE)

    @pytest.mark.parametrize("distancia", [1.5, True, "200"])
    def test_una_distancia_que_no_es_entera_es_un_bug_no_un_422(self, distancia):
        # Pydantic ya garantiza `int` en los tres endpoints, así que llegar aquí
        # con otra cosa es un fallo del programa: tiene que romper con un 500 que
        # se vea en el log, no salir como error del formulario del entrenador.
        with pytest.raises(TypeError):
            Prueba(distancia, Estilo.LIBRE)

    def test_un_estilo_desconocido_no_pasa(self):
        with pytest.raises(ValueError):
            Prueba(100, "mariposilla")


class TestPruebaSabeDeSi:
    def test_perfil_sugerido_por_distancia(self):
        assert Prueba(50).perfil_sugerido() is Perfil.VELOCIDAD
        assert Prueba(100).perfil_sugerido() is Perfil.VELOCIDAD
        assert Prueba(200).perfil_sugerido() is Perfil.MEDIO_FONDO
        assert Prueba(400).perfil_sugerido() is Perfil.MEDIO_FONDO
        assert Prueba(800).perfil_sugerido() is Perfil.FONDO

    def test_el_tier_corta_en_400(self):
        assert Prueba(200).tier() == 2
        assert Prueba(400).tier() == 1
        assert Prueba(400).es_aerobica()
        assert not Prueba(200).es_aerobica()

    def test_evento_mas_cercano_para_indexar_las_tablas(self):
        assert Prueba(200).evento_mas_cercano() == 200
        assert Prueba(1000).evento_mas_cercano() == 800
        # Empate (300 dista 100 de 200 y de 400): gana el corto, que es lo que
        # hace `envelope.nearest_event` y lo que deja el techo del lado seguro.
        assert Prueba(300, Estilo.COMBINADO).evento_mas_cercano() == 200

    def test_acepta_el_estilo_como_texto_porque_asi_llega_de_fuera(self):
        assert Prueba(200, "crol") == Prueba(200, Estilo.LIBRE)
        assert Prueba(200, "freestyle") == Prueba(200, Estilo.LIBRE)

    def test_dos_pruebas_iguales_son_la_misma(self):
        assert Prueba(200, Estilo.LIBRE) == Prueba(200, "libre")
        assert len({Prueba(200), Prueba(200, "crol")}) == 1


class TestEstiloYPiscina:
    @pytest.mark.parametrize(
        ("alias", "esperado"),
        [
            ("libre", Estilo.LIBRE), ("crol", Estilo.LIBRE), ("freestyle", Estilo.LIBRE),
            ("espalda", Estilo.ESPALDA), ("dorso", Estilo.ESPALDA),
            ("backstroke", Estilo.ESPALDA),
            ("pecho", Estilo.PECHO), ("braza", Estilo.PECHO),
            ("breaststroke", Estilo.PECHO),
            ("mariposa", Estilo.MARIPOSA), ("butterfly", Estilo.MARIPOSA),
            ("combinado", Estilo.COMBINADO), ("im", Estilo.COMBINADO),
            ("individual_medley", Estilo.COMBINADO),
            (" IM ", Estilo.COMBINADO), ("Mariposa", Estilo.MARIPOSA),
        ],
    )
    def test_los_alias_de_los_dos_idiomas_entran_por_la_misma_puerta(self, alias, esperado):
        # Antes eran dos diccionarios: `events._STROKE_ALIASES` normalizaba a
        # español y `domain.STROKE_ALIASES` a inglés. Ahora entra texto y sale
        # `Estilo`, que lleva las dos grafías como propiedades suyas.
        assert Estilo.desde_texto(alias) is esperado

    def test_el_estilo_lleva_su_clave_cientifica(self):
        assert Estilo.COMBINADO.clave_cientifica == "individual_medley"
        assert Estilo.LIBRE.clave_cientifica == "freestyle"

    def test_el_combinado_corrige_como_la_media_de_los_cuatro(self):
        cuatro = [e for e in Estilo if e is not Estilo.COMBINADO]
        media = sum(e.correccion_tpace_s for e in cuatro) / 4
        assert Estilo.COMBINADO.correccion_tpace_s == pytest.approx(media)

    def test_la_piscina_de_50_no_corrige_nada(self):
        for perfil in Perfil:
            assert Piscina.LARGA.factor(perfil) == 1.0

    def test_la_de_25_es_mas_rapida_en_todos_los_perfiles(self):
        for perfil in Perfil:
            assert Piscina.CORTA.factor(perfil) < 1.0


# ───────────────────────────────────────────────────────────────────────────
# Zona: el orden es el tipo
# ───────────────────────────────────────────────────────────────────────────

class TestZonaEsUnEnumOrdenado:
    """La jerarquía deja de ser una lista suelta que se pueda separar de otra."""

    def test_ordena_por_intensidad(self):
        assert Zona.R1 < Zona.R2 < Zona.MVO2 < Zona.RL < Zona.V
        assert Zona.V > Zona.R1
        assert Zona.R1 <= Zona.R1

    def test_ordenar_una_lista_desordenada_devuelve_la_jerarquia(self):
        revueltas = [Zona.V, Zona.R1, Zona.RL, Zona.MVO2, Zona.R2]
        assert tuple(sorted(revueltas)) == Zona.ordenadas()

    def test_no_se_compara_con_lo_que_no_es_una_zona(self):
        with pytest.raises(TypeError):
            _ = Zona.R1 < "R2"

    def test_el_descanso_crece_con_la_intensidad_y_nunca_al_reves(self):
        # Recortar el descanso de una zona rápida no la hace más dura: la cambia
        # de zona. Por eso esta monotonía es una invariante, no una casualidad.
        ratios = [z.ratio_descanso for z in Zona.ordenadas()]
        assert ratios == sorted(ratios)
        assert all(a < b for a, b in zip(ratios, ratios[1:], strict=False))

    def test_los_topes_evitan_los_disparates_de_los_extremos(self):
        # Un 25 de velocidad pediría 26 s por ratio: se sube al suelo de la zona.
        corto = Zona.V.descanso_para(Tiempo(7.5))
        assert corto.segundos == Zona.V.limites_descanso_s[0]
        # Un 800 de base aeróbica pediría 50 s: se baja al techo.
        largo = Zona.R1.descanso_para(Tiempo(600.0))
        assert largo.segundos == Zona.R1.limites_descanso_s[1]

    def test_el_descanso_se_pide_sobre_un_tiempo(self):
        with pytest.raises(TypeError):
            Zona.R1.descanso_para(70.0)


class TestPrescripcion:
    def test_la_salida_es_el_trabajo_mas_el_descanso_o_no_se_construye(self):
        buena = Prescripcion.para(Zona.R1, Ritmo(67.0))
        assert buena.salida.segundos == pytest.approx(
            buena.trabajo.segundos + buena.descanso.segundos
        )
        with pytest.raises(ValueError, match="no es el trabajo más el descanso"):
            Prescripcion(
                zona=Zona.R1, ritmo=Ritmo(67.0), salida=Tiempo(70.0),
                descanso=Duracion(10.0), distancia_rep=100,
            )

    def test_el_descanso_de_una_prescripcion_es_una_duracion(self):
        # Un descanso es un hueco, no un nado: el prescrito sale positivo, pero
        # el real de un parcial puede ser negativo y los dos tienen que compararse.
        buena = Prescripcion.para(Zona.R1, Ritmo(67.0))
        assert isinstance(buena.descanso, Duracion)
        with pytest.raises(TypeError):
            Prescripcion(
                zona=buena.zona, ritmo=buena.ritmo, salida=buena.salida,
                descanso=Tiempo(buena.descanso.segundos), distancia_rep=100,
            )

    def test_la_salida_se_canta_en_manecillas_de_cinco_segundos(self):
        for zona in Zona.ordenadas():
            salida = Prescripcion.para(zona, Ritmo(67.0)).salida.segundos
            assert salida % 5 == pytest.approx(0.0)

    def test_cuadrar_al_reloj_nunca_recorta_el_descanso_prescrito(self):
        for zona in Zona.ordenadas():
            for rep in (50, 100, 200, 400):
                p = Prescripcion.para(zona, Ritmo(67.0), rep)
                assert p.descanso.segundos >= zona.descanso_para(p.trabajo).segundos

    def test_el_texto_es_lo_que_se_escribe_en_la_pizarra(self):
        p = Prescripcion.para(Zona.R2, Ritmo(78.0), 100)
        assert p.texto(10) == "10 × 100 a 1:18 salida 1:30"

    def test_cuantas_veces_se_repite_no_es_parte_de_la_prescripcion(self):
        """La misma zona al mismo ritmo son 10×400 en R1 y 8×25 en V.

        Por eso las repeticiones son un argumento de `texto()` y no un campo: el
        número pertenece a la serie que se manda nadar, y tenerlo también aquí
        serían otra vez dos mitades de lo mismo pudiendo separarse.
        """
        assert not hasattr(Prescripcion.para(Zona.R1, Ritmo(67.0)), "repeticiones")
        with pytest.raises(ValueError):
            Prescripcion.para(Zona.R1, Ritmo(67.0)).texto(0)

    def test_una_serie_sin_repeticiones_tambien_se_lee(self):
        assert Prescripcion.para(Zona.R2, Ritmo(78.0)).texto() == "100 a 1:18 salida 1:30"

    @pytest.mark.parametrize("rep", [0, -100])
    def test_la_distancia_de_repeticion_es_positiva(self, rep):
        # Por esta vía el error sale de `Ritmo.a_tiempo`, que corre antes: las
        # guardas de `__post_init__` no llegan a ejecutarse. Se comprueban abajo
        # construyendo la prescripción directamente — si no, borrarlas dejaría
        # este test en verde.
        with pytest.raises(ValueError, match="distancia tiene que ser positiva"):
            Prescripcion.para(Zona.R1, Ritmo(67.0), rep)

    @pytest.mark.parametrize(
        ("rep", "error", "texto"),
        [
            (0, ValueError, "repetición tiene que ser positiva"),
            (-100, ValueError, "repetición tiene que ser positiva"),
            (100.0, TypeError, "metros enteros"),
            (True, TypeError, "metros enteros"),
        ],
    )
    def test_las_guardas_del_constructor_se_ejecutan_de_verdad(self, rep, error, texto):
        buena = Prescripcion.para(Zona.R1, Ritmo(67.0))
        with pytest.raises(error, match=texto):
            Prescripcion(
                zona=buena.zona, ritmo=buena.ritmo, salida=buena.salida,
                descanso=buena.descanso, distancia_rep=rep,
            )


class TestJuegoDeZonas:
    RITMO = Ritmo(58.24)
    PRUEBA = Prueba(200, Estilo.LIBRE)

    def test_lleva_las_cinco_zonas_en_orden(self):
        juego = JuegoDeZonas.de(self.RITMO, self.PRUEBA)
        assert [p.zona for p in juego.prescripciones] == list(Zona.ordenadas())
        assert len(juego) == 5

    def test_un_juego_incompleto_no_se_construye(self):
        completo = JuegoDeZonas.de(self.RITMO, self.PRUEBA)
        with pytest.raises(ValueError):
            JuegoDeZonas(self.PRUEBA, Piscina.LARGA, completo.prescripciones[:4])

    def test_se_indexa_por_zona(self):
        juego = JuegoDeZonas.de(self.RITMO, self.PRUEBA)
        assert juego[Zona.R1].zona is Zona.R1
        assert juego.ritmo_de(Zona.V) == juego[Zona.V].ritmo

    def test_es_un_mapping_de_verdad(self):
        """El §3.3 lo especifica como `Mapping[Zona, Prescripcion]`, no parecido.

        Sin heredar de `Mapping`, cada consumidor que quiera serializar las cinco
        zonas vuelve a iterar la lista de zonas **por fuera** del juego — que es
        la lista suelta que `Zona` existe para eliminar.
        """
        juego = JuegoDeZonas.de(self.RITMO, self.PRUEBA)
        assert isinstance(juego, Mapping)
        assert list(juego.keys()) == list(Zona.ordenadas())
        assert len(dict(juego)) == 5
        assert juego.get(Zona.V) is juego[Zona.V]
        assert juego.get("R1") is None          # una clave que no es Zona no está
        assert Zona.R1 in juego and "R1" not in juego

    def test_la_zona_mas_intensa_es_la_mas_rapida(self):
        juego = JuegoDeZonas.de(self.RITMO, self.PRUEBA)
        ritmos = [juego[z].ritmo for z in Zona.ordenadas()]
        assert all(a > b for a, b in zip(ritmos, ritmos[1:], strict=False))

    def test_la_piscina_de_25_da_ritmos_mas_rapidos(self):
        larga = JuegoDeZonas.de(self.RITMO, self.PRUEBA, Piscina.LARGA)
        corta = JuegoDeZonas.de(self.RITMO, self.PRUEBA, Piscina.CORTA)
        assert all(corta[z].ritmo < larga[z].ritmo for z in Zona.ordenadas())

    def test_el_estilo_lento_pide_ritmos_mas_lentos(self):
        libre = JuegoDeZonas.de(self.RITMO, Prueba(200, Estilo.LIBRE))
        pecho = JuegoDeZonas.de(self.RITMO, Prueba(200, Estilo.PECHO))
        assert all(pecho[z].ritmo > libre[z].ritmo for z in Zona.ordenadas())

    def test_se_ancla_a_un_ritmo_no_a_un_numero(self):
        with pytest.raises(TypeError):
            JuegoDeZonas.de(58.24, self.PRUEBA)


# ───────────────────────────────────────────────────────────────────────────
# Escalas
# ───────────────────────────────────────────────────────────────────────────

class TestNivelSiempreDerivado:
    """`Nivel` no se escribe a mano: sale de un umbral."""

    @pytest.mark.parametrize(
        ("umbral", "esperado"),
        [
            (200.0, Nivel.PRINCIPIANTE),
            (150.1, Nivel.PRINCIPIANTE),
            (150.0, Nivel.RECREATIVO),     # frontera: el umbral exacto ya no es principiante
            (120.1, Nivel.RECREATIVO),
            (120.0, Nivel.AVANZADO),
            (95.1, Nivel.AVANZADO),
            (95.0, Nivel.COMPETITIVO),
            (70.1, Nivel.COMPETITIVO),
            (70.0, Nivel.ELITE),
            (55.0, Nivel.ELITE),
        ],
    )
    def test_cada_tramo_y_su_frontera(self, umbral, esperado):
        assert Nivel.desde_umbral(Ritmo(umbral)) is esperado

    def test_no_se_deriva_de_un_float_suelto(self):
        # Un float podría ser un tiempo absoluto, y el nivel saldría disparatado.
        with pytest.raises(TypeError):
            Nivel.desde_umbral(95.0)
        with pytest.raises(TypeError):
            Nivel.desde_umbral(Tiempo(95.0))


class TestFaseEsElUnicoVocabulario:
    def test_lleva_su_f_fase_dentro(self):
        assert Fase.BASE_GENERAL.f_fase == 0.60
        assert Fase.TAPER.f_fase == 1.15
        assert Fase.TAPER.f_fase > Fase.BASE_GENERAL.f_fase

    def test_lleva_su_banda_de_volumen_dentro(self):
        assert Fase.BASE_GENERAL.banda_de_volumen(Nivel.ELITE) == (50, 80)
        minimo, maximo = Fase.TAPER.banda_de_volumen(Nivel.PRINCIPIANTE)
        assert minimo < maximo

    def test_el_taper_descarga_respecto_a_la_base(self):
        for nivel in Nivel:
            assert Fase.TAPER.banda_de_volumen(nivel)[1] < Fase.BASE_GENERAL.banda_de_volumen(nivel)[1]

    def test_las_fases_sin_banda_propia_usan_la_de_umbral(self):
        for fase in (Fase.PRE_COMPETITIVO, Fase.EXTENSION):
            assert fase.banda_de_volumen(Nivel.AVANZADO) == Fase.UMBRAL_CSS.banda_de_volumen(
                Nivel.AVANZADO
            )

    def test_lleva_su_orden_cronologico_dentro(self):
        """Por lo mismo que `Zona.ordenadas()`: si no está en el tipo, aparece
        una `FASE_ORDER` suelta al lado el día que alguien reparta fases sobre
        semanas. La extensión no es una fase del macro y va detrás de todas."""
        assert Fase.secuencia() == (
            Fase.BASE_GENERAL, Fase.BASE_ESPECIFICA, Fase.UMBRAL_CSS,
            Fase.PRE_COMPETITIVO, Fase.TAPER,
        )
        assert Fase.EXTENSION not in Fase.secuencia()
        ordenes = [f.orden for f in Fase.secuencia()]
        assert ordenes == sorted(ordenes) == [0, 1, 2, 3, 4]
        assert Fase.EXTENSION.orden == len(Fase.secuencia())

    def test_el_orden_no_es_el_reparto_que_C4_tiene_que_decidir(self):
        # Exponer el orden de las cinco no adelanta nada sobre cómo se reparten
        # los cuatro tramos de la interfaz sobre ellas: eso sigue rechazándose.
        with pytest.raises(ValueError):
            Fase.desde_texto("build")

    def test_la_banda_se_pide_con_un_nivel(self):
        with pytest.raises(TypeError):
            Fase.TAPER.banda_de_volumen("elite")

    @pytest.mark.parametrize("ajeno", ["Construcción", "build", "peak", "Descenso", "Base"])
    def test_no_traduce_los_otros_dos_vocabularios(self, ajeno):
        """Cuatro tramos contra cinco fases, y el reparto SIGUE sin decidirse.

        Adivinarlo aquí sería inventar la sexta versión de la regla que este tipo
        existe para cerrar.
        """
        with pytest.raises(ValueError):
            Fase.desde_texto(ajeno)


class TestEscalasRestantes:
    def test_el_perfil_lleva_las_dos_grafias(self):
        assert Perfil.MEDIO_FONDO.value == "medio_fondo"
        assert Perfil.MEDIO_FONDO.clave_cientifica == "medio fondo"

    def test_un_t30_son_repeticiones_de_100_por_definicion(self):
        assert TipoDeTest.T30.distancia_rep_fija == 100
        assert TipoDeTest.T15.distancia_rep_fija == 100
        assert TipoDeTest.CUSTOM.distancia_rep_fija is None
        assert TipoDeTest.CSS.tiene_parciales is False

    def test_el_modo_de_ingreso_dice_si_los_numeros_vienen_acumulados(self):
        assert ModoDeIngreso.CLOCK.es_acumulado
        assert not ModoDeIngreso.REP.es_acumulado

    @pytest.mark.parametrize("escala", TODAS_LAS_ESCALAS)
    def test_desde_texto_es_la_vuelta_del_valor(self, escala):
        for miembro in escala:
            assert escala.desde_texto(miembro.value) is miembro
            assert escala.desde_texto(miembro.value.upper()) is miembro

    @pytest.mark.parametrize("escala", TODAS_LAS_ESCALAS)
    def test_un_valor_desconocido_no_pasa(self, escala):
        with pytest.raises(ValueError):
            escala.desde_texto("lo-que-sea")


# ───────────────────────────────────────────────────────────────────────────
# Inmutabilidad
# ───────────────────────────────────────────────────────────────────────────

class TestSonInmutables:
    OBJETOS = [
        Tiempo(116.48),
        Ritmo(58.24),
        Mejora(3.0, Tiempo(120.0)),
        Duracion(-12.5),
        Prueba(200, Estilo.LIBRE),
        Prescripcion.para(Zona.R1, Ritmo(67.0)),
    ]

    @pytest.mark.parametrize("objeto", OBJETOS)
    def test_no_se_les_puede_asignar(self, objeto):
        campo = dataclasses.fields(objeto)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(objeto, campo, 1)

    @pytest.mark.parametrize("objeto", OBJETOS)
    def test_no_admiten_atributos_nuevos(self, objeto):
        # `slots=True`: sin `__dict__` no hay estado que colar por la puerta de
        # atrás. El tipo de la excepción depende de CPython (un nombre fuera de
        # `__slots__` no llega al `FrozenInstanceError`); lo que se fija es que
        # no se pueda.
        assert not hasattr(objeto, "__dict__")
        assert type(objeto).__slots__
        with pytest.raises((AttributeError, TypeError)):
            objeto.inventado = 1

    def test_sirven_de_clave_en_un_diccionario(self):
        cache = {Prueba(200, Estilo.LIBRE): "200 libre"}
        assert cache[Prueba(200, "crol")] == "200 libre"
