"""El plan semana a semana: generarlo, extenderlo y recalcularlo desde un real.

La curva elegida da la FORMA; la ciencia pone los dos límites:

* la mejora dentro del macro no pasa del techo realista — una meta más agresiva
  continúa en la extensión, no en esta curva;
* ninguna semana mejora más rápido que el pico fisiológico, y lo que no cabe se
  **difiere** a las siguientes en vez de perderse.

Así la curva cierra justo donde la tarjeta de factibilidad dice que es realista,
y la diferencia entre curvas es solo de forma.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..entidades import lunes_de
from ..valores import Fase
from .curvas import Curva
from .envolvente import envolvente_de
from .kilometraje import reparto_de_km
from .zonas import zonas_de

# Fases por defecto del macrociclo tal y como las ve el entrenador: cuatro
# tramos con su color. NO son las cinco fases científicas de `Fase` — el reparto
# entre los dos vocabularios sigue sin decidirse (ver `Fase.desde_texto`).
FASES_POR_DEFECTO: list[tuple[str, str, float, str]] = [
    ("Base", "base", 0.30, "#22d3ee"),
    ("Construcción", "build", 0.40, "#8b5cf6"),
    ("Pico", "peak", 0.20, "#fbbf24"),
    ("Descenso", "taper", 0.10, "#34d399"),
]


@dataclass
class SemanaGenerada:
    """Una fila del plan: qué se espera nadar esa semana y a qué ritmos."""

    numero: int
    fecha: date
    tiempo_esperado: float
    ritmo_100: float
    km: float
    fase: str
    mejora_vs_anterior: float
    mejora_acumulada: float
    zonas: dict = field(default_factory=dict)
    deshabilitada: bool = False


def fases_por_defecto(semanas: int) -> list[dict]:
    """Base / Construcción / Pico / Descenso repartidas sobre las semanas."""
    rangos: list[dict] = []
    inicio = 1
    quedan = semanas
    for i, (nombre, tipo, fraccion, color) in enumerate(FASES_POR_DEFECTO):
        if i == len(FASES_POR_DEFECTO) - 1:
            largo = quedan
        else:
            largo = max(1, round(semanas * fraccion))
            largo = min(largo, quedan - (len(FASES_POR_DEFECTO) - 1 - i))
        rangos.append({
            "name": nombre, "type": tipo, "color": color,
            "week_start": inicio, "week_end": inicio + largo - 1, "sort": i,
        })
        inicio += largo
        quedan -= largo
    return rangos


def _fase_de_la_semana(semana: int, fases: list[dict]) -> str:
    for f in fases:
        if f["week_start"] <= semana <= f["week_end"]:
            return f["name"]
    return fases[-1]["name"] if fases else "—"


def acotar_ritmo_semanal(
    esperados: list[float], tiempo_actual: float, pico_semanal_s: float,
) -> list[float]:
    """Ninguna semana mejora más de lo que la fisiología permite.

    Y lo que no cabe **se difiere a las siguientes** en vez de recortarse: es un
    modelo causal —esa ganancia ocurre después, no desaparece—, así que la curva
    cierra en el mismo punto y solo cambia de forma. La científica nunca se
    recorta: su semana más rápida es la que define el tope.
    """
    if pico_semanal_s <= 0:
        return list(esperados)
    pedidos: list[float] = []
    ideal_anterior = tiempo_actual
    for e in esperados:
        pedidos.append(ideal_anterior - e)
        ideal_anterior = e

    salida: list[float] = []
    anterior = tiempo_actual
    diferido = 0.0
    for pedido in pedidos:
        quiere = pedido + diferido
        toma = min(quiere, pico_semanal_s) if quiere > 0 else quiere
        diferido = quiere - toma
        anterior = anterior - toma
        salida.append(anterior)
    return salida


def generar(
    distancia: int,
    tiempo_actual: float,
    tiempo_meta: float,
    semanas: int,
    km_totales: float,
    curva: str,
    inicio: date,
    semanas_por_micro: int = 4,
    fases: list[dict] | None = None,
    estilo: str = "libre",
    piscina: str = "50",
    n_mac: int = 1,
    edad: int | None = None,
) -> list[SemanaGenerada]:
    """El plan completo. Las semanas y los km son los que puso el entrenador."""
    fases = fases or fases_por_defecto(semanas)
    km = reparto_de_km(semanas, km_totales, semanas_por_micro)
    env = envolvente_de(distancia, tiempo_actual, semanas, n_mac=n_mac, edad=edad)

    meta_del_macro = max(tiempo_meta, env.techo_realista)
    mejora = max(tiempo_actual - meta_del_macro, 0.0)
    forma = Curva.desde_clave(curva)
    ideal = [tiempo_actual - mejora * forma.progreso((i + 1) / semanas)
             for i in range(semanas)]
    acotado = acotar_ritmo_semanal(ideal, tiempo_actual, env.pico_semanal_s)

    plan: list[SemanaGenerada] = []
    anterior = tiempo_actual
    for i in range(semanas):
        esperado = acotado[i]
        ritmo = esperado / (distancia / 100)
        plan.append(SemanaGenerada(
            numero=i + 1,
            fecha=lunes_de(inicio, i + 1),
            tiempo_esperado=round(esperado, 2),
            ritmo_100=round(ritmo, 2),
            km=km[i],
            fase=_fase_de_la_semana(i + 1, fases),
            mejora_vs_anterior=round(esperado - anterior, 2),
            mejora_acumulada=round(tiempo_actual - esperado, 2),
            zonas=zonas_de(ritmo, distancia, estilo, piscina),
        ))
        anterior = esperado
    return plan


def extender(
    distancia: int,
    tiempo_actual: float,
    techo_realista: float,
    tiempo_meta: float,
    ritmo_seguro: float,
    n_extra: int,
    inicio: date,
    semanas_del_macro: int,
    km_semanales: float,
    estilo: str = "libre",
    piscina: str = "50",
) -> list[SemanaGenerada]:
    """Las semanas de después, cuando la meta supera el techo del macro.

    Mientras el plan principal comprime la mejora pedida en las semanas que puso
    el entrenador, estas filas enseñan la continuación REALISTA: parten del
    techo y bajan al ritmo seguro hasta tocar la meta.
    """
    semanas: list[SemanaGenerada] = []
    anterior = techo_realista
    for j in range(1, n_extra + 1):
        numero = semanas_del_macro + j
        esperado = max(techo_realista - ritmo_seguro * j, tiempo_meta)
        ritmo = esperado / (distancia / 100)
        semanas.append(SemanaGenerada(
            numero=numero,
            fecha=lunes_de(inicio, numero),
            tiempo_esperado=round(esperado, 2),
            ritmo_100=round(ritmo, 2),
            km=km_semanales,
            fase=Fase.EXTENSION.etiqueta,
            mejora_vs_anterior=round(esperado - anterior, 2),
            mejora_acumulada=round(tiempo_actual - esperado, 2),
            zonas=zonas_de(ritmo, distancia, estilo, piscina),
        ))
        anterior = esperado
    return semanas


def recalcular_desde(
    semanas: list[SemanaGenerada],
    desde_semana: int,
    tiempo_ancla: float,
    tiempo_meta: float,
    curva: str,
    distancia: int,
    deshabilitadas: set[int] | None = None,
    estilo: str = "libre",
    piscina: str = "50",
    n_mac: int = 1,
    edad: int | None = None,
) -> list[SemanaGenerada]:
    """Reancla la curva en un tiempo real y reparte lo que queda.

    Las semanas de parón (lesión, vacaciones) no progresan: mantienen el tiempo
    del ancla previa y su mejora se redistribuye entre las activas que quedan.
    El tramo restante lleva su propia envolvente —calculada sobre esas semanas,
    no sobre el macro entero—, así que una meta que ya no cabe cierra en el
    techo del tramo en vez de forzarse.
    """
    deshabilitadas = deshabilitadas or set()
    restantes = [s for s in semanas if s.numero >= desde_semana]
    activas = [s for s in restantes if s.numero not in deshabilitadas]
    if not activas:
        return semanas

    n_activas = len(activas)
    env = envolvente_de(distancia, tiempo_ancla, n_activas, n_mac=n_mac, edad=edad)
    meta_del_tramo = max(tiempo_meta, env.techo_realista)
    mejora = max(tiempo_ancla - meta_del_tramo, 0.0)
    forma = Curva.desde_clave(curva)
    ideal = [tiempo_ancla - mejora * forma.progreso((k + 1) / n_activas)
             for k in range(n_activas)]
    acotado = acotar_ritmo_semanal(ideal, tiempo_ancla, env.pico_semanal_s)

    anterior = tiempo_ancla
    i = 0
    for semana in restantes:
        if semana.numero in deshabilitadas:
            semana.deshabilitada = True
            semana.tiempo_esperado = round(anterior, 2)
            semana.mejora_vs_anterior = 0.0
        else:
            esperado = acotado[i]
            i += 1
            semana.deshabilitada = False
            semana.mejora_vs_anterior = round(esperado - anterior, 2)
            semana.tiempo_esperado = round(esperado, 2)
            anterior = esperado
        ritmo = semana.tiempo_esperado / (distancia / 100)
        semana.ritmo_100 = round(ritmo, 2)
        semana.zonas = zonas_de(ritmo, distancia, estilo, piscina)
    return semanas
