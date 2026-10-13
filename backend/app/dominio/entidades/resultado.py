"""`Resultado`: un tiempo nadado. Paso 6 del rediseño (`docs/REDISENO.md` §5.10).

**Es un hecho sobre una persona, no una propiedad de un plan.** Hasta C6 el
tiempo real vivía en `WeeklyPlan.real_time`, colgando de
`Macrociclo → Inscripcion → PruebaObjetivo → Semana`: borrar la inscripción se
llevaba lo que el atleta había nadado, y borrar un macro sin tests aeróbicos se
llevaba lo de todo el equipo. Colgando del atleta, ninguna de las dos cosas
puede tocarlo.

**La semana no apunta a ningún resultado** (R2 enmendada, §10.2). Los que le
tocan se derivan por `(atleta, prueba, rango de fechas)` y lo que la semana
enseña es su promedio: el entrenador quiere varios tiempos por semana
promediados, y una FK única no admite varios. Uno, varios y ninguno son el mismo
recorrido — filtrar y promediar—, no tres ramas.

**Un tiempo en otra piscina entra convertido** (decidido el 2026-09-22). Se pasa
a la piscina del macrociclo con el mismo factor corta/larga que ya aplican las
zonas (`Piscina.factor`, calibrado con el pool nacional el 2026-06-13) antes de
promediar. Sin convertir, un 200 en corta dentro de un macro de larga saldría
~2 % más rápido que lo que el atleta vale en larga; sin meterlo, el entrenador
vería la semana vacía teniendo un tiempo.

**Solo reancla la curva lo que cae dentro de una semana del plan.** Un resultado
fuera de todas —una competencia suelta, una prueba que no es objetivo de este
macro— es histórico del atleta y no llega nunca a `real_de_la_semana`, así que
no puede tocar la predicción.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Self

from ..valores import Piscina, Prueba, Tiempo
from .base import PorIdentidad

DIAS_DE_UNA_SEMANA = 7


class Contexto(Enum):
    """Dónde se nadó. N2 (§10.3) sigue abierta: qué hace cada uno con el promedio."""

    COMPETENCIA = "competencia"
    CONTROL = "control"
    # Previsto aunque `Serie` haya salido del rediseño (R1): el tiempo de una
    # repetición es un resultado, y cerrar el vocabulario ahora obligaría a una
    # migración el día que se capture.
    SERIE = "serie"

    @classmethod
    def desde_texto(cls, valor: str) -> Self:
        return cls(str(valor).strip().lower())


@dataclass(slots=True, eq=False)
class Resultado(PorIdentidad):
    """Lo que nadó un atleta, en qué prueba, qué día y en qué piscina.

    La piscina es del resultado, no del plan: el número que se guarda es el que
    marcó el reloj, y la conversión a otra piscina se hace al leer
    (`tiempo_en`), nunca al escribir.
    """

    atleta_id: int
    prueba: Prueba
    tiempo: Tiempo
    fecha: date
    piscina: Piscina
    contexto: Contexto = Contexto.CONTROL
    competencia_id: int | None = None
    id: int | None = None

    def tiempo_en(self, piscina: Piscina) -> Tiempo:
        """El tiempo equivalente en `piscina`. En la suya, el mismo número.

        `factor` es el ratio corta/larga sobre el ritmo por perfil de la prueba
        (1.0 en larga); sobre la misma distancia vale igual para el tiempo. Ir de
        una a otra es dividir por el factor de origen y multiplicar por el de
        destino, y en la misma piscina eso es ×1 exacto.
        """
        perfil = self.prueba.perfil_sugerido()
        return Tiempo(self.tiempo.segundos * piscina.factor(perfil) / self.piscina.factor(perfil))

    def cae_en_la_semana(self, *, atleta_id: int, prueba: Prueba, lunes: date) -> bool:
        """Si este resultado es uno de los que esa semana promedia.

        La semana es `[lunes, lunes + 7)`: el lunes de la siguiente ya es suyo.
        La piscina no decide: la de otra entra convertida (`real_de_la_semana`).
        """
        return (
            self.atleta_id == atleta_id
            and self.prueba == prueba
            and lunes <= self.fecha < lunes + timedelta(days=DIAS_DE_UNA_SEMANA)
        )


def de_la_semana(
    resultados: Iterable[Resultado], *, atleta_id: int, prueba: Prueba, lunes: date,
) -> list[Resultado]:
    """Los resultados que le tocan a una semana: 0, 1 o varios, sin distinguir."""
    return [
        r for r in resultados
        if r.cae_en_la_semana(atleta_id=atleta_id, prueba=prueba, lunes=lunes)
    ]


def promedio(resultados: Iterable[Resultado], piscina: Piscina) -> Tiempo | None:
    """El tiempo que representa a un conjunto, en `piscina`; `None` si está vacío.

    El vacío es lo único que no tiene promedio, no una rama del caso de uno: con
    uno solo, el promedio es él.
    """
    tiempos = [r.tiempo_en(piscina).segundos for r in resultados]
    return Tiempo(sum(tiempos) / len(tiempos)) if tiempos else None


def real_de_la_semana(
    resultados: Iterable[Resultado], *,
    atleta_id: int, prueba: Prueba, piscina: Piscina, lunes: date,
) -> Tiempo | None:
    """Lo mismo que `Semana.real()`, para quien tiene el lunes y no la semana.

    `Semana` es entidad desde C9 (2026-10-13) y su `real()` es la cara pública;
    esta función se queda para las vistas, que todavía leen las semanas como
    filas. `piscina` es la del macrociclo: la de la curva contra la que se compara.
    """
    return promedio(de_la_semana(resultados, atleta_id=atleta_id, prueba=prueba, lunes=lunes),
                    piscina)
