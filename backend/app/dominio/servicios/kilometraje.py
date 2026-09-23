"""El reparto de los kilómetros: cuántos cada semana y cómo se dividen por zona.

Dos señales, las dos respaldadas (Bompa & Haff 2009, Issurin 2008):

1. **Envolvente del macro** — rampa de volumen hasta ~70 % del ciclo y descenso
   del 40-60 % hacia la competencia.
2. **Onda del microciclo 3:1** (o 4:1 en micros de cinco) — tres o cuatro
   semanas de carga progresiva y una de descarga para supercompensación.

**El total lo pone el entrenador** (decisión R6): la ciencia da la forma y el
resultado se normaliza para que la suma sea exactamente lo que él planificó. La
banda de `WEEKLY_VOLUME_KM` es un **aviso** que se enseña en la tabla del plan,
nunca un valor por defecto ni un límite — que es justo lo que hacía el motor
científico, prescribiendo 777,7 km donde el entrenador había puesto 450.
"""
from __future__ import annotations

from ..valores import Fase, Nivel, Zona
from .tablas import (
    CAIDA_DEL_TAPER,
    DESCARGA_ULTIMA_SEMANA,
    MEZCLA_DE_ZONAS_POR_DISTANCIA,
    MEZCLA_DE_ZONAS_POR_ESPECIALIDAD,
    ONDA_DEL_MICRO,
    RAMPA_HASTA,
    RAMPA_INICIAL,
)


def _envolvente_del_macro(indice: int, total: int) -> float:
    """Rampa 0.65 → 1.0 hasta el 70 % del ciclo, luego taper hasta 0.40."""
    x = indice / (total - 1) if total > 1 else 0.0
    if x <= RAMPA_HASTA:
        return RAMPA_INICIAL + (1.0 - RAMPA_INICIAL) * (x / RAMPA_HASTA)
    return 1.0 - CAIDA_DEL_TAPER * ((x - RAMPA_HASTA) / (1.0 - RAMPA_HASTA))


def reparto_de_km(semanas: int, km_totales: float, semanas_por_micro: int = 4) -> list[float]:
    """Kilómetros planificados por semana. Suman `km_totales`, no otra cosa."""
    onda = ONDA_DEL_MICRO.get(semanas_por_micro, ONDA_DEL_MICRO[4])
    crudo: list[float] = []
    for i in range(semanas):
        envolvente = _envolvente_del_macro(i, semanas)
        posicion = i % semanas_por_micro
        # La última semana siempre es descarga (taper final), no pico de carga.
        if i == semanas - 1:
            factor = envolvente * DESCARGA_ULTIMA_SEMANA
        else:
            factor = envolvente * onda[min(posicion, len(onda) - 1)]
        crudo.append(factor)
    total_crudo = sum(crudo)
    return [round(f * km_totales / total_crudo, 1) for f in crudo]


def banda_de_aviso(nivel: Nivel, fase: Fase) -> tuple[float, float]:
    """Km semanales {min, max} que la literatura da para ese nivel y esa fase.

    **Aviso, no regla** (R6). Sirve para que la tabla del plan pueda decir
    «esta semana va por debajo de la banda de tu nivel», no para corregir el
    total que puso el entrenador.
    """
    return fase.banda_de_volumen(nivel)


def km_por_zona(
    km_semanales: float,
    distancia: int | None = None,
    especialidad: str | None = None,
) -> dict[str, float]:
    """Kilómetros sugeridos por zona para una semana.

    Manda la distancia de la prueba, que es el driver fisiológico directo: la
    contribución aeróbica pasa del 5 % en un 50 al 95 % en un 1500. La
    especialidad solo entra cuando no hay distancia (el simulador), y las
    distancias intermedias se interpolan entre sus dos vecinas.
    """
    if distancia is not None:
        conocidas = sorted(MEZCLA_DE_ZONAS_POR_DISTANCIA)
        if distancia <= conocidas[0]:
            mezcla = MEZCLA_DE_ZONAS_POR_DISTANCIA[conocidas[0]]
        elif distancia >= conocidas[-1]:
            mezcla = MEZCLA_DE_ZONAS_POR_DISTANCIA[conocidas[-1]]
        elif distancia in MEZCLA_DE_ZONAS_POR_DISTANCIA:
            mezcla = MEZCLA_DE_ZONAS_POR_DISTANCIA[distancia]
        else:
            baja = max(d for d in conocidas if d < distancia)
            alta = min(d for d in conocidas if d > distancia)
            t = (distancia - baja) / (alta - baja)
            m_baja = MEZCLA_DE_ZONAS_POR_DISTANCIA[baja]
            m_alta = MEZCLA_DE_ZONAS_POR_DISTANCIA[alta]
            mezcla = {z.value: m_baja[z.value] + t * (m_alta[z.value] - m_baja[z.value])
                      for z in Zona.ordenadas()}
    else:
        clave = especialidad or "medio_fondo"
        mezcla = MEZCLA_DE_ZONAS_POR_ESPECIALIDAD.get(
            clave, MEZCLA_DE_ZONAS_POR_ESPECIALIDAD["medio_fondo"],
        )
    return {z.value: round(km_semanales * mezcla[z.value], 1) for z in Zona.ordenadas()}
