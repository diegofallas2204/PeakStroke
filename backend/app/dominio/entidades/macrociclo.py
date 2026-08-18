"""El macrociclo: raíz del agregado de planificación.

Absorbe las funciones sueltas de `plans/service.py` que son puras y no tocan la
base de datos (`current_week_of`, `effective_status`). Eran el ejemplo de P5: el
dashboard importaba `plans.service` para poder preguntar en qué semana va un
plan. Con la semana dentro del objeto, quien tenga el macrociclo ya lo sabe.

**`fase_de()` devuelve la `FaseDelMacro`, no una `Fase`.** El desdoble de §5.5
es a propósito y aquí solo está la mitad de arriba: la base guarda cuatro tramos
(`base|build|peak|taper`) y `Fase` tiene cinco claves científicas. Ese reparto no
está decidido —la fusión de motores pasó sin cerrarlo— y `escalas.Fase.desde_texto`
se niega expresamente a adivinarlo. Traducirlo aquí sería inventar la sexta
versión de la regla que `Fase` existe para cerrar, así que `FaseDelMacro.fase`
viaja en `None` hasta que el paso 4 diga cómo se reparten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from ..valores import EstadoDeMacro, Fase, Piscina
from .base import PorIdentidad

# Estados que el entrenador pone a mano y mandan tal cual sobre la fecha.
_OVERRIDES_MANUALES = (EstadoDeMacro.SUSPENDIDO, EstadoDeMacro.BORRADOR, EstadoDeMacro.TERMINADO)


def lunes_de(inicio: date, semana: int) -> date:
    """Fecha del lunes de la semana N (1-indexada) desde la fecha de inicio.

    La semana del plan es la semana del calendario: si un macrociclo arranca un
    miércoles, esa semana 1 empezó el lunes anterior. Sin normalizar al lunes,
    dos planes que empiezan en días distintos de la misma semana no son
    comparables entre sí.

    Es función además de método porque `engine/progression.monday_of` la sigue
    necesitando sobre una fecha suelta, dentro de bucles que no tienen un
    `Macrociclo` a mano; ese módulo delega aquí en lugar de conservar su copia.
    """
    base = inicio - timedelta(days=inicio.weekday())
    return base + timedelta(weeks=semana - 1)


@dataclass(slots=True, eq=False)
class FaseDelMacro(PorIdentidad):
    """Un tramo del macrociclo, con el nombre que el entrenador le puso.

    `nombre` es texto libre de la interfaz y `fase` es la clave de dominio: el
    entrenador puede llamarle "Construcción" a lo que el motor conoce como
    `base_especifica` sin que ninguno de los dos pierda su vocabulario.
    """

    id: int | None = None
    nombre: str = ""
    fase: Fase | None = None
    semana_inicio: int = 1
    semana_fin: int = 1
    color: str = "#8b5cf6"
    orden: int = 0

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


@dataclass(slots=True, eq=False)
class Macrociclo(PorIdentidad):
    """Un plan de temporada: desde cuándo, cuántas semanas y con qué forma."""

    inicio: date
    semanas: int
    id: int | None = None
    equipo_id: int | None = None
    nombre: str = ""
    semanas_por_micro: int = 4
    km_totales: float = 0.0
    # La curva sigue siendo la clave de texto (`science`, `sigmoid`…) hasta que el
    # paso 4 la convierta en la `Curva` del patrón Strategy (§6.2).
    curva: str = "science"
    piscina: Piscina = Piscina.LARGA
    n_mac: int = 1
    prueba_principal: str | None = None
    estado: EstadoDeMacro = EstadoDeMacro.ACTIVO
    notas: str | None = None
    fases: list[FaseDelMacro] = field(default_factory=list)
    competencias: list[Competencia] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.semanas < 1:
            raise ValueError(f"Un macrociclo dura al menos una semana: {self.semanas}")

    def duracion_en_semanas(self) -> int:
        return self.semanas

    def lunes_de(self, semana: int) -> date:
        """Fecha del lunes de la semana N de este macrociclo."""
        return lunes_de(self.inicio, semana)

    def ultimo_dia(self) -> date:
        """Domingo de la última semana. Después de esto el macro se acabó."""
        return self.lunes_de(self.semanas) + timedelta(days=6)

    def semana_actual(self, hoy: date | None = None) -> int | None:
        """En qué semana va, 1-indexada. `None` si todavía no ha empezado.

        Nunca pasa de la última: un macrociclo vencido se queda en su semana
        final en vez de seguir contando hacia el infinito.
        """
        hoy = hoy or date.today()
        transcurridas = (hoy - self.lunes_de(1)).days // 7 + 1
        if transcurridas < 1:
            return None
        return min(transcurridas, self.semanas)

    def estado_efectivo(self, hoy: date | None = None) -> EstadoDeMacro:
        """El estado que se le enseña al entrenador.

        Suspendido, borrador y terminado son decisiones suyas y mandan tal cual.
        Lo que se deriva es lo otro: un macro vigente cuya última semana ya pasó
        se da por terminado sin que nadie tenga que acordarse de cerrarlo.
        """
        if self.estado in _OVERRIDES_MANUALES:
            return self.estado
        hoy = hoy or date.today()
        if hoy > self.ultimo_dia():
            return EstadoDeMacro.TERMINADO
        return EstadoDeMacro.ACTIVO

    def esta_vivo(self, hoy: date | None = None) -> bool:
        """Si ocupa el calendario del atleta. La regla «un atleta, un macro vivo»."""
        return self.estado_efectivo(hoy) is EstadoDeMacro.ACTIVO

    def fase_de(self, semana: int) -> FaseDelMacro | None:
        """El tramo que cubre esa semana. `None` si el macro no tiene fases.

        Una semana fuera de rango cae en la última fase, que es el comportamiento
        que ya tiene el plan generado: las semanas de extensión —las que se
        añaden cuando la meta no cabe en el macro— se nadan en régimen de taper,
        no en ninguno nuevo.
        """
        for fase in self.fases:
            if fase.contiene(semana):
                return fase
        return self.fases[-1] if self.fases else None

    def competencia_principal(self) -> Competencia | None:
        return next((c for c in self.competencias if c.es_principal), None)

    def __str__(self) -> str:
        return self.nombre or f"Macrociclo {self.id}"
