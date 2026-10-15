"""Los tramos de un macrociclo —fases y competencias— y lo que exige su calendario.

Salieron de `macrociclo.py` el 2026-10-14, cuando las reglas de abajo lo
habrían pasado de 300 líneas. `Macrociclo` los reexporta: nadie que los
importara de allí tiene que cambiar.

**Lo que exige el calendario** (TODO-24, 2026-10-14). Hasta entonces nadie lo
validaba —ni el formulario ni el dominio— y lo que se rompía después era
silencioso: el plan generado busca el tramo de cada semana y, si no lo hay,
usa el último. Una semana en un hueco se planificaba como taper.

- Las fases, si las hay, cubren de la semana 1 a la última **sin solaparse ni
  dejar huecos**. Huecos también: por lo de arriba, uno es tan dañino como un
  solape. **El orden no se exige** —el asistente añade fases al final de la
  lista—: se comprueba sobre la lista ordenada y se guarda la que llegó.
- Una competencia cae entre la primera semana y la última.
- El nombre del macrociclo no son solo espacios. Se guarda sin recortar.

**Se aplica al escribir, no al leer**: lo llaman `Macrociclo.nuevo()` y
`renombrar()`, nunca el constructor. El mapeo fila → entidad corre en cada
lectura, y un macrociclo guardado antes de la regla tiene que poder abrirse.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..valores import Fase
from .base import PorIdentidad


@dataclass(slots=True, eq=False)
class FaseDelMacro(PorIdentidad):
    """Un tramo del macrociclo, con el nombre que el entrenador le puso.

    `nombre` es texto libre de la interfaz y `fase` es la clave de dominio: el
    entrenador puede llamarle "Construcción" a lo que el motor conoce como
    `base_especifica` sin que ninguno de los dos pierda su vocabulario.

    Hasta P3 había un tercero, `tipo` (`base|build|peak|taper`), que era lo que la
    base guardaba de verdad mientras `fase` viajaba en `None`. Se fue con la
    migración que convirtió esas filas: hoy la columna guarda la clave de `Fase`.

    `fase` es obligatoria y no admite la extensión: un tramo del plan sin fase
    no le dice nada a la ciencia, y la extensión es lo que viene después del
    macro, no una parte de él.
    """

    fase: Fase
    id: int | None = None
    nombre: str = ""
    semana_inicio: int = 1
    semana_fin: int = 1
    color: str = "#8b5cf6"
    orden: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.fase, Fase):
            raise TypeError("La fase de un tramo del macrociclo es una Fase, no un texto")
        if self.fase.es_extension:
            raise ValueError("La extensión no es una fase del macrociclo")

    def contiene(self, semana: int) -> bool:
        return self.semana_inicio <= semana <= self.semana_fin

    def duracion_en_semanas(self) -> int:
        return max(self.semana_fin - self.semana_inicio + 1, 0)


@dataclass(slots=True, eq=False)
class Competencia(PorIdentidad):
    """Una competencia dentro del macrociclo, anclada a una semana."""

    id: int | None = None
    nombre: str = ""
    semana: int = 1
    dias: int = 1
    es_principal: bool = False


def exigir_nombre(nombre: str) -> str:
    """El nombre tal cual, si tiene algo más que espacios. Si no, `ValueError`."""
    if not nombre or not nombre.strip():
        raise ValueError("El nombre del macrociclo no puede quedar en blanco")
    return nombre


def comprobar_calendario(
    semanas: int, fases: Sequence[FaseDelMacro], competencias: Sequence[Competencia],
) -> None:
    """`ValueError` con la primera razón por la que no caben en `semanas` semanas."""
    for f in fases:
        if f.semana_fin < f.semana_inicio:
            raise ValueError(
                f"La fase «{f.nombre}» acaba antes de empezar "
                f"(semana {f.semana_inicio} a {f.semana_fin})",
            )
        if f.semana_inicio < 1:
            raise ValueError(
                f"Las fases empiezan como pronto en la semana 1: «{f.nombre}» "
                f"empieza en la {f.semana_inicio}",
            )
        if f.semana_fin > semanas:
            raise ValueError(
                f"La fase «{f.nombre}» se sale del macrociclo: acaba en la semana "
                f"{f.semana_fin} y el macro dura {semanas}",
            )
    if fases:
        ordenadas = sorted(fases, key=lambda f: f.semana_inicio)
        if ordenadas[0].semana_inicio != 1:
            raise ValueError(
                f"Las fases tienen que empezar en la semana 1, y la primera "
                f"empieza en la {ordenadas[0].semana_inicio}",
            )
        siguiente = 1
        for f in ordenadas:
            if f.semana_inicio < siguiente:
                raise ValueError(
                    f"La fase «{f.nombre}» se solapa con la anterior en la semana "
                    f"{f.semana_inicio}",
                )
            if f.semana_inicio > siguiente:
                raise ValueError(
                    f"Hay un hueco entre fases: ninguna cubre de la semana {siguiente} "
                    f"a la {f.semana_inicio - 1}",
                )
            siguiente = f.semana_fin + 1
        if siguiente <= semanas:
            raise ValueError(
                f"Las fases acaban en la semana {siguiente - 1} y el macrociclo "
                f"llega hasta la semana {semanas}",
            )
    for c in competencias:
        if not 1 <= c.semana <= semanas:
            raise ValueError(
                f"La competencia «{c.nombre}» cae en la semana {c.semana} y el "
                f"macrociclo va de la 1 a la {semanas}",
            )
