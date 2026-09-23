"""La temporada: N macrociclos encadenados, con re-test entre cada uno (§4.5).

Cada macro parte del techo realista del anterior y su potencial se degrada
(§4.3), así que la suma no es la del primero por tres. Es un **techo** —cada
macro llegando a su máximo—, no la media esperada, y por eso se compara contra
el rango típico de la literatura ajustado por edad.

No sustituye al plan semanal: es la vista con la que el entrenador reparte la
meta de la temporada entre sus macros.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..valores import Perfil
from .envolvente import envolvente_de, evento_de_referencia, nivel_de
from .tablas import MEJORA_ANUAL_ESPERADA, factor_juvenil

# Semanas del macrociclo científico de referencia. La proyección no usa las del
# entrenador a propósito: compara macros teóricos completos, no su calendario.
SEMANAS_DEL_MACRO_TEORICO = 15

# A partir de cuántas veces el techo típico la proyección deja de ser optimista
# para ser poco realista.
FACTOR_OPTIMISTA = 1.8


@dataclass(frozen=True, slots=True)
class MacroProyectado:
    n_mac: int
    tiempo_inicial: float
    tiempo_final: float
    mejora_s: float
    mejora_pct: float


@dataclass(frozen=True, slots=True)
class ProyeccionAnual:
    nivel: str
    n_macros: int
    inicio: float
    fin: float
    mejora_s: float
    mejora_pct: float
    rango_bajo_pct: float
    rango_alto_pct: float
    veredicto: str
    mensaje: str
    macros: list[MacroProyectado]


def proyectar(
    tiempo_actual: float,
    distancia: int,
    n_macros: int = 3,
    edad: int | None = None,
    perfil: str | None = None,
) -> ProyeccionAnual:
    """`n_macros` encadenados desde el tiempo actual."""
    # El perfil por defecto sale del EVENTO de referencia y no de la distancia
    # pedida: coinciden en las seis de tabla y solo divergen en una intermedia
    # (un 150 se indexa al 100, pero su perfil es medio fondo). Se conserva tal
    # cual porque es lo que la proyección lleva calculando desde siempre, y cuál
    # de las dos manda se decide con el defecto 1 de §10.4, que es el mismo
    # tema. El entrenador puede forzarlo.
    elegido = (
        Perfil.desde_texto(perfil) if perfil
        else Perfil.para_distancia(evento_de_referencia(distancia))
    )
    nivel = nivel_de(distancia, tiempo_actual, elegido)

    macros: list[MacroProyectado] = []
    t = tiempo_actual
    for n in range(1, max(1, n_macros) + 1):
        env = envolvente_de(
            distancia, t, SEMANAS_DEL_MACRO_TEORICO, n_mac=n, edad=edad, perfil=elegido,
        )
        fin = env.techo_realista
        macros.append(MacroProyectado(
            n_mac=n, tiempo_inicial=round(t, 2), tiempo_final=round(fin, 2),
            mejora_s=round(t - fin, 2),
            mejora_pct=round((t - fin) / t * 100, 2) if t else 0.0,
        ))
        t = fin

    mejora = tiempo_actual - t
    pct = mejora / tiempo_actual if tiempo_actual else 0.0
    juventud = factor_juvenil(edad)
    bajo_base, alto_base = MEJORA_ANUAL_ESPERADA.get(nivel.value, (0.0, 1.0))
    bajo, alto = bajo_base * juventud, alto_base * juventud

    if pct <= alto:
        veredicto = "ok"
        mensaje = (
            f"Realista — el techo de temporada proyecta {pct*100:.2f}%, "
            f"dentro del rango típico {bajo*100:.1f}–{alto*100:.1f}% para {nivel.value}"
            + (f" (ajustado por edad ×{juventud:g})" if juventud != 1.0 else "") + "."
        )
    elif pct <= alto * FACTOR_OPTIMISTA:
        veredicto = "optimistic"
        mensaje = (
            f"Optimista — el techo de temporada ({pct*100:.2f}%) supera el "
            f"rango típico {bajo*100:.1f}–{alto*100:.1f}% ({nivel.value}). Es el máximo de "
            f"{len(macros)} macros perfectos, no la media esperada."
        )
    else:
        veredicto = "unrealistic"
        mensaje = (
            f"Poco realista — {pct*100:.2f}% excede con mucho el techo "
            f"típico {bajo*100:.1f}–{alto*100:.1f}% ({nivel.value}). Revisa el tiempo "
            f"actual o reparte la meta en más temporadas."
        )

    return ProyeccionAnual(
        nivel=nivel.value, n_macros=len(macros),
        inicio=round(tiempo_actual, 2), fin=round(t, 2),
        mejora_s=round(mejora, 2), mejora_pct=round(pct * 100, 2),
        rango_bajo_pct=round(bajo * 100, 2), rango_alto_pct=round(alto * 100, 2),
        veredicto=veredicto, mensaje=mensaje, macros=macros,
    )
