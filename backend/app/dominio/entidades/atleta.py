"""El atleta: la ficha deportiva, con su comportamiento dentro.

La edad es el caso de libro de este paso. Nació duplicada —`plans/service.age_at`
y `swimmers/service._age`, la misma aritmética con dos firmas— y el arreglo fue
unificarlas en `core/dates.age_at`: una función suelta que recibe la fecha de
nacimiento de un atleta y no al atleta. Eso resuelve la duplicación pero deja la
regla fuera de su objeto, que es P4: el modelo anémico. Aquí `edad_en()` es del
`Atleta` y `core/dates.age_at` pasa a delegar mientras queden llamadores.

Ficha (`Atleta`) y cuenta (`Usuario`) siguen siendo la misma persona vista desde
dos sitios; lo único que las une es un código de vinculación canjeado, y por eso
`usuario_id` es opcional y `tiene_cuenta()` es una pregunta con sentido.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..valores import Especialidad, Estilo, Genero, Perfil, Prueba
from .base import PorIdentidad


def anios_cumplidos(nacimiento: date | None, referencia: date | None = None) -> int | None:
    """Años cumplidos en `referencia` (hoy si no se indica). La única copia.

    `None` si no hay fecha de nacimiento: la ficha puede no tenerla, y devolver 0
    haría pasar por recién nacido a quien solo tiene el dato sin rellenar.

    Vive como función además de como método porque `core/dates.age_at` la sigue
    necesitando sobre una fecha suelta mientras dure la transición, y una segunda
    copia allí es justo lo que este paso viene a quitar. La cara pública es
    `Atleta.edad_en()`.
    """
    if nacimiento is None:
        return None
    referencia = referencia or date.today()
    anios = referencia.year - nacimiento.year
    if (referencia.month, referencia.day) < (nacimiento.month, nacimiento.day):
        anios -= 1
    return max(anios, 0)


# Aguas abiertas entrena como fondo: no tiene perfil propio en las tablas
# científicas (`ZONE_OVER_RACE` indexa velocidad / medio fondo / fondo).
_PERFIL_DE_ESPECIALIDAD: dict[Especialidad, Perfil] = {
    Especialidad.VELOCIDAD: Perfil.VELOCIDAD,
    Especialidad.MEDIO_FONDO: Perfil.MEDIO_FONDO,
    Especialidad.FONDO: Perfil.FONDO,
    Especialidad.AGUAS_ABIERTAS: Perfil.FONDO,
}


@dataclass(slots=True, eq=False)
class Atleta(PorIdentidad):
    """Una persona del equipo. Identidad + ciclo de vida, no un saco de columnas."""

    id: int | None = None
    equipo_id: int | None = None
    nombre: str = ""
    usuario_id: int | None = None
    nacimiento: date | None = None
    genero: Genero | None = None
    especialidad: Especialidad = Especialidad.MEDIO_FONDO
    estilo_principal: Estilo = Estilo.LIBRE
    peso_kg: float | None = None
    altura_cm: float | None = None
    notas: str | None = None
    activo: bool = True

    def edad_en(self, fecha: date | None = None) -> int | None:
        """Edad en años cumplidos en `fecha` (hoy si no se indica).

        La fecha importa: la edad que ajusta al alza el techo de mejora de los
        menores es la que se tiene **al empezar el macrociclo**, no la de hoy, o
        un plan pasaría a calcularse distinto el día del cumpleaños.
        """
        return anios_cumplidos(self.nacimiento, fecha)

    def tiene_cuenta(self) -> bool:
        """Si alguien canjeó ya el código que une esta ficha con una cuenta."""
        return self.usuario_id is not None

    def perfil_para(self, prueba: Prueba | None = None) -> Perfil:
        """Perfil de entrenamiento con el que indexar las tablas del motor.

        **Manda la distancia de la prueba**, y la especialidad del atleta es el
        respaldo cuando no hay prueba delante. No es una elección de este objeto:
        es la regla que ya aplica el motor —`zone_km_distribution` prioriza la
        distancia «(driver fisiológico directo)» y cae en la especialidad cuando
        no la tiene—, escrita una vez en lugar de repetida en cada llamador.

        Un fondista que hoy nada un 100 entrena ese 100 como velocidad; lo que su
        especialidad dice es a qué se dedica, no a qué ritmo va este juego de
        series.
        """
        if prueba is not None:
            return prueba.perfil_sugerido()
        return _PERFIL_DE_ESPECIALIDAD[self.especialidad]

    def __str__(self) -> str:
        return self.nombre or f"Atleta {self.id}"
