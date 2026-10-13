"""Cuánto puede mejorar un atleta, y cuán rápido. El techo de todo lo demás.

Dos objetos y una sola ciencia detrás:

    Envolvente     el techo I_max del macro y el ritmo máximo de una semana
    Factibilidad   ese techo comparado con lo que el entrenador pide

Hasta el paso 4 esto vivía dos veces: `ScienceEngine._check_feasibility` (el
veredicto de la teoría) y `engine/feasibility.analyze_feasibility` (el que veía
el entrenador), con `engine/envelope.py` en medio intentando que coincidieran.
Es la duplicación que hizo divergir el tope de semanas de extensión — 26 aquí,
30 allí, y el simulador sugiriendo 41 semanas mientras el motor extendía a 45.

Los tiempos van en segundos (`float`) y no en `Tiempo`: la fusión tiene la regla
de no mover un solo número, y envolver cada paso intermedio en un objeto que
valida y redondea es exactamente como se mueven. La frontera con `Tiempo` la
pone el paso 5, cuando los repositorios traduzcan.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from ..valores import (
    EVENTOS_DE_REFERENCIA,
    Nivel,
    Perfil,
    Ritmo,
    Veredicto,
    Zona,
    factores_de_zona,
)
from .curvas import Cientifica
from .tablas import (
    DEGRADACION_ENTRE_MACROS,
    MAX_SEMANAS_EXTENSION,
    TABLA_I_MAX,
    factor_juvenil,
)

DISTANCIA_TIER_1 = 400


def evento_de_referencia(distancia: int) -> int:
    """La distancia con entrada propia en las tablas más cercana a esta."""
    return min(EVENTOS_DE_REFERENCIA, key=lambda d: abs(d - distancia))


def umbral_de(
    distancia: int, tiempo_actual: float, perfil: Perfil | None = None,
) -> Ritmo:
    """Ritmo de umbral estimado: el de carrera corregido por el factor MVO2.

    Es una aproximación mientras no haya un test aeróbico: la etiqueta `MVO2`
    se usa aquí como ancla de umbral (≈CSS), no como velocidad a VO2max literal.
    Para Emiliano cae a ~1 % de su CSS real (§2.4).

    **Tiene un borde afilado y por eso es el plan B**: la tabla de niveles está
    calibrada para un test de 400/1500 y aquí se le entrega el ritmo de un 200,
    así que una décima de segundo puede cambiar el nivel —y con él, el volumen
    prescrito— un 45 % (defecto 1 de §10.4). Cuando el atleta tiene test
    aeróbico, manda el test; ver `nivel_de`.
    """
    perfil = perfil or Perfil.para_distancia(distancia)
    ritmo_de_carrera = tiempo_actual / (distancia / 100.0)
    return Ritmo(ritmo_de_carrera * factores_de_zona(perfil, distancia)[Zona.MVO2])


def nivel_de(
    distancia: int,
    tiempo_actual: float,
    perfil: Perfil | None = None,
    base_aerobica: float | None = None,
) -> Nivel:
    """Nivel del atleta para esa prueba y ese tiempo (§2.4).

    **Manda el test aeróbico.** `base_aerobica` es un umbral MEDIDO (s/100 m: lo
    que la inscripción guarda en `aerobic_base`, venga de un T-30, un T-15 o un
    CSS), y la tabla de niveles está calibrada exactamente para eso. Sin test se
    cae al umbral estimado desde el ritmo de carrera, que es una aproximación
    con un borde muy afilado: medido, `2:10.40` en 200 clasifica elite y
    `2:10.50` competitive, y con ello el techo de mejora pasa de 1.17 s a 3.13 s
    — una décima de segundo cambiando el plan un 45 % (defecto 1 de §10.4).

    El test no borra el acantilado, lo esquiva: dos atletas con el mismo test
    salen en el mismo nivel aunque su tiempo de 200 caiga a los dos lados de la
    frontera. Que el nivel dependa del dato para el que la tabla se calibró es
    lo que lo hace estable.

    `perfil` solo se pasa cuando el entrenador lo forzó: cambia qué columna de
    factores se lee y, con ella, el umbral estimado. Con test no interviene.
    """
    if base_aerobica is not None and base_aerobica > 0:
        return Nivel.desde_umbral(Ritmo(base_aerobica))
    return Nivel.desde_umbral(umbral_de(distancia, tiempo_actual, perfil))


def _fraccion_de_la_semana_pico(semanas: int) -> float:
    """Mayor escalón semanal de la curva científica sobre `semanas`.

    La fracción del techo total que la fisiología permite ganar en su semana más
    rápida (el taper). Ninguna curva puede superarla: la científica es la
    trayectoria validada, así que su escalón máximo es el ritmo máximo.
    """
    n = max(semanas, 1)
    cientifica = Cientifica()
    return max(
        cientifica.progreso(k / n) - cientifica.progreso((k - 1) / n)
        for k in range(1, n + 1)
    )


@dataclass(frozen=True, slots=True)
class Envolvente:
    """El techo de mejora de un macro, y el de una sola semana dentro de él."""

    nivel: Nivel
    evento: int
    i_max_total: float        # fracción del tiempo actual que se puede mejorar
    mejora_maxima_s: float    # esa fracción, en segundos
    techo_realista: float     # mejor tiempo creíble al cerrar el macro (s)
    pico_semanal_s: float     # mejora máxima fisiológica de una sola semana (s)

    def ritmo_seguro_semanal_s(self, semanas: int) -> float:
        """Mejora media por semana al ritmo del techo. Es el de la extensión.

        Recibe las semanas en vez de recordarlas: el mismo techo se reparte
        entre las del macro para generar el plan y entre las que quedan para
        recalcularlo, y guardarlas dentro invitaría a usar el reparto que no es.
        """
        return self.mejora_maxima_s / semanas if semanas else 0.0


def envolvente_de(
    distancia: int,
    tiempo_actual: float,
    semanas: int,
    n_mac: int = 1,
    edad: int | None = None,
    perfil: Perfil | None = None,
    base_aerobica: float | None = None,
) -> Envolvente:
    """Techo I_max + ritmo seguro por semana para (prueba, nivel, macro).

    `n_mac` degrada el techo (§4.3: el segundo macro de una temporada rinde
    menos que el primero) y `edad` lo amplía en menores (§4.4).
    `base_aerobica` es el umbral medido del atleta; ver `nivel_de`.
    """
    evento = evento_de_referencia(distancia)
    nivel = nivel_de(distancia, tiempo_actual, perfil, base_aerobica)
    i_max_meso = (
        TABLA_I_MAX[nivel.value][evento]
        * (DEGRADACION_ENTRE_MACROS ** (n_mac - 1))
        * factor_juvenil(edad)
    )
    i_max_total = i_max_meso * (semanas / 5.0)
    mejora_maxima_s = tiempo_actual * i_max_total
    return Envolvente(
        nivel=nivel,
        evento=evento,
        i_max_total=i_max_total,
        mejora_maxima_s=mejora_maxima_s,
        techo_realista=tiempo_actual - mejora_maxima_s,
        pico_semanal_s=mejora_maxima_s * _fraccion_de_la_semana_pico(semanas),
    )


@dataclass(frozen=True, slots=True)
class Factibilidad:
    """El veredicto sobre la meta que puso el entrenador (§5.3)."""

    estado: str                       # ok | warning | aggressive
    mensaje: str
    tier: int
    mejora_total_s: float
    mejora_por_micro_s: float
    techo_por_micro_s: float
    semanas_recomendadas: int | None  # totales (macro + extensión), si es agresiva
    semanas_extra: int | None         # solo las de extensión, ya capadas
    techo_realista: float
    ritmo_seguro_semanal_s: float
    detalle: dict


def factibilidad(
    distancia: int,
    tiempo_actual: float,
    tiempo_meta: float,
    semanas: int,
    semanas_por_micro: int = 4,
    n_mac: int = 1,
    edad: int | None = None,
    base_aerobica: float | None = None,
) -> Factibilidad:
    """Compara la mejora pedida con el techo científico del macro.

    Cuando la meta lo supera, el modelo de EXTENSIÓN dice cuántas semanas extra
    harían falta al ritmo seguro — el mismo número de semanas que el motor
    genera después, porque salen de la misma envolvente y del mismo tope.
    """
    mejora_total = tiempo_actual - tiempo_meta
    micros = max(semanas / semanas_por_micro, 0.001)
    tier = 1 if distancia >= DISTANCIA_TIER_1 else 2

    if mejora_total <= 0:
        return Factibilidad(
            estado=Veredicto.OK.value,
            mensaje="El tiempo meta ya fue alcanzado: el plan será de mantenimiento.",
            tier=tier, mejora_total_s=mejora_total, mejora_por_micro_s=0.0,
            techo_por_micro_s=0.0, semanas_recomendadas=None, semanas_extra=None,
            techo_realista=tiempo_actual, ritmo_seguro_semanal_s=0.0, detalle={},
        )

    env = envolvente_de(
        distancia, tiempo_actual, semanas, n_mac=n_mac, edad=edad,
        base_aerobica=base_aerobica,
    )
    pct = mejora_total / tiempo_actual
    ratio = pct / env.i_max_total if env.i_max_total else 999.0
    ritmo_seguro = env.mejora_maxima_s / semanas if semanas else 0.0

    detalle = {
        "level": env.nivel.value, "event": env.evento,
        "i_max_meso": round(env.i_max_total / (semanas / 5.0), 4),
        "i_max_total_pct": round(env.i_max_total * 100, 2), "ratio": round(ratio, 3),
        "requested_pct": round(pct * 100, 2),
    }
    recomendadas: int | None = None
    extra: int | None = None

    # Los umbrales son de `Veredicto`, no de aquí: `PruebaObjetivo.factibilidad()`
    # clasifica con los mismos. El cociente lo calcula cada uno con sus números
    # (aquí sobre fracciones, allí sobre segundos), así que con la meta clavada
    # en un umbral pueden diferir en el último bit; ver la entidad.
    veredicto = Veredicto.del_uso(ratio)
    if veredicto is Veredicto.OK:
        mensaje = (f"Realista — pides {pct*100:.2f}% y el techo científico para "
                   f"{env.nivel.value}/{env.evento}m en {semanas} sem es "
                   f"{env.i_max_total*100:.2f}% (uso {ratio*100:.0f}%).")
    elif veredicto is Veredicto.AVISO:
        mensaje = (f"Exigente — pides {pct*100:.2f}%, cerca del techo "
                   f"{env.i_max_total*100:.2f}% ({ratio*100:.0f}% del máximo).")
    else:
        falta = env.techo_realista - tiempo_meta      # lo que queda tras el macro
        extra = math.ceil(falta / ritmo_seguro) if ritmo_seguro > 0 else 0
        extra = max(0, min(extra, MAX_SEMANAS_EXTENSION))
        recomendadas = semanas + extra
        tope = (" (tope alcanzado; la meta sigue siendo muy exigente)"
                if extra == MAX_SEMANAS_EXTENSION else "")
        mensaje = (f"Agresivo — pides {pct*100:.2f}%, supera el techo "
                   f"{env.i_max_total*100:.2f}% ({ratio*100:.0f}%). El motor estima "
                   f"~{recomendadas} semanas en total ({extra} extra){tope}.")

    return Factibilidad(
        estado=veredicto.value, mensaje=mensaje, tier=tier,
        mejora_total_s=mejora_total, mejora_por_micro_s=mejora_total / micros,
        techo_por_micro_s=round(env.mejora_maxima_s / micros, 3),
        semanas_recomendadas=recomendadas, semanas_extra=extra,
        techo_realista=round(env.techo_realista, 2),
        ritmo_seguro_semanal_s=round(ritmo_seguro, 4),
        detalle=detalle,
    )
