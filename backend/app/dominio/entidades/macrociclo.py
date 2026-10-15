"""El macrociclo: raíz del agregado de planificación.

Absorbe las funciones sueltas de `plans/service.py` que son puras y no tocan la
base de datos (`current_week_of`, `effective_status`). Eran el ejemplo de P5: el
dashboard importaba `plans.service` para poder preguntar en qué semana va un
plan. Con la semana dentro del objeto, quien tenga el macrociclo ya lo sabe.

**`fase_de()` devuelve la `FaseDelMacro`, no una `Fase`**, porque quien pregunta
casi siempre quiere las dos mitades del desdoble de §5.5: el nombre que el
entrenador le puso al tramo, para enseñarlo, y su `Fase`, para calcular. La
segunda es `fase_de(n).fase` y desde P3 (2026-09-22) siempre está: la base
guarda la clave de la fase, no la etiqueta.

**Se crea y se edita por aquí** (C9, 2026-10-13). Hasta entonces
`api/v1/macrociclos/service.py` armaba la fila con `Plan(**data.model_dump())`
y la editaba con un `setattr` por cada campo del formulario. `nuevo()` lo
construye y los mutadores de abajo son lo único que una ruta puede cambiarle:
las fechas, las semanas, los kilómetros, las fases y las competencias se fijan
al crearlo y no tienen quien los edite.

**Qué rechaza, y cuándo** (TODO-24, 2026-10-14): `nuevo()` exige que las
fases cubran de la semana 1 a la última sin solaparse ni dejar huecos, que las
competencias caigan dentro y que el nombre no sean solo espacios, y
`renombrar()` lo último. **Solo al escribir**: el constructor no lo mira,
porque el mapeo fila → entidad corre en cada lectura y un macrociclo guardado
antes de la regla tiene que poder seguir abriéndose. Las reglas viven en
`calendario_del_macro.py`, con los tramos.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..valores import EstadoDeMacro, Piscina, Ritmo
from .atleta import Atleta
from .base import PorIdentidad
from .calendario_del_macro import (
    Competencia,
    FaseDelMacro,
    comprobar_calendario,
    exigir_nombre,
)
from .inscripcion import Inscripcion, InscripcionImposible

# Estados que el entrenador pone a mano y mandan tal cual sobre la fecha.
_OVERRIDES_MANUALES = (EstadoDeMacro.SUSPENDIDO, EstadoDeMacro.BORRADOR, EstadoDeMacro.TERMINADO)

# La clave de `servicios.curvas.Cientifica`, copiada y no importada porque el
# dominio no importa hacia los lados (ver la cabecera de `entidades/`).
# `tests/test_entidades.py` la compara con la curva viva.
CURVA_DEL_PLAN = "science"


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
class Macrociclo(PorIdentidad):
    """Un plan de temporada: desde cuándo, cuántas semanas y con qué forma."""

    inicio: date
    semanas: int
    id: int | None = None
    equipo_id: int | None = None
    nombre: str = ""
    semanas_por_micro: int = 4
    km_totales: float = 0.0
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

    @classmethod
    def nuevo(
        cls, nombre: str, inicio: date, semanas: int, *, km_totales: float,
        semanas_por_micro: int = 4, piscina: str = "50", n_mac: int = 1,
        prueba_principal: str | None = None, notas: str | None = None,
        fases: Iterable[FaseDelMacro] = (), competencias: Iterable[Competencia] = (),
    ) -> Macrociclo:
        """Un macrociclo sin guardar, desde los valores con que llega (API, seed).

        Nace activo y sin equipo: el equipo y el entrenador a cargo los pone el
        repositorio al guardarlo, de quien lo crea. Nunca de la petición.
        Levanta `ValueError` si no cabe (ver la cabecera).
        """
        # Las competencias, por semana (orden estable): es como las devuelve la
        # base, y la respuesta del alta pinta la colección en el orden en que
        # se armó (TODO-22). Las fases se guardan como llegaron.
        fases, competencias = list(fases), sorted(competencias, key=lambda c: c.semana)
        comprobar_calendario(semanas, fases, competencias)
        return cls(
            inicio=inicio, semanas=semanas, nombre=exigir_nombre(nombre),
            semanas_por_micro=semanas_por_micro, km_totales=km_totales,
            piscina=Piscina.desde_texto(piscina), n_mac=n_mac,
            prueba_principal=prueba_principal, notas=notas,
            fases=fases, competencias=competencias,
        )

    # ── Edición ──────────────────────────────────────────────────────────────
    #
    # Lo único que cambia después de crearlo. Que la meta (`fijar_meta`) sea de
    # dueño es de permisos, no de aquí: lo decide el router (R4).

    def renombrar(self, nombre: str) -> None:
        """Un nombre de solo espacios no vale (TODO-24). El formulario aplica la
        misma regla antes de llegar aquí (`PlanUpdate`): si solo la aplicara la
        entidad, saldría como un 500 y no como un 422."""
        self.nombre = exigir_nombre(nombre)

    def anotar(self, notas: str | None) -> None:
        self.notas = notas

    def fijar_meta(self, prueba_principal: str | None) -> None:
        self.prueba_principal = prueba_principal

    def cambiar_estado(self, estado: EstadoDeMacro) -> None:
        """El estado que pone el entrenador. El que se enseña es `estado_efectivo()`."""
        if not isinstance(estado, EstadoDeMacro):
            raise TypeError("El estado de un macrociclo es un EstadoDeMacro, no un texto")
        self.estado = estado

    def cambiar_piscina(self, piscina: Piscina) -> None:
        if not isinstance(piscina, Piscina):
            raise TypeError("La piscina de un macrociclo es una Piscina, no un texto")
        self.piscina = piscina

    def numerar(self, n_mac: int) -> None:
        """Qué macrociclo de la temporada es (1 = el primero): degrada el techo."""
        if isinstance(n_mac, bool) or not isinstance(n_mac, int):
            raise TypeError(f"El número de macrociclo es un entero: {n_mac!r}")
        if n_mac < 1:
            raise ValueError(f"Los macrociclos de una temporada se cuentan desde 1: {n_mac}")
        self.n_mac = n_mac

    @property
    def curva(self) -> str:
        """La forma de la progresión de un plan real: **siempre la científica** (R7).

        Hasta el 2026-09-23 era una columna que el entrenador elegía al crear el
        plan. No era cosmética: a mitad de macro las cinco curvas se separan hasta
        1,30 s, contra una tolerancia de estado de ±0,4 %, así que el mismo nado
        salía «adelantado» o «atrasado» según una casilla rellenada quince
        semanas antes (§10.4). Elegir curva sigue existiendo, pero en el
        simulador, que compara escenarios y no le da un veredicto a nadie.
        """
        return CURVA_DEL_PLAN

    def inscribir(
        self, atleta: Atleta, base_aerobica: Ritmo | None = None,
        fuente_de_base: str | None = None,
    ) -> Inscripcion:
        """La inscripción de `atleta` en este macrociclo, sin guardar.

        Comprueba lo que el macrociclo puede saber por sí mismo: que la ficha es
        de su club y que sigue activa. Hasta el 2026-10-05 nadie lo miraba al
        inscribir —la lista de asignables escondía las fichas de baja, pero el
        POST las aceptaba—. **«Un atleta, un macrociclo vivo» no es de aquí**:
        pide las inscripciones de todo el equipo y la impone
        `api/v1/macrociclos/inscripcion.py` antes de llamar.
        """
        if atleta.equipo_id != self.equipo_id:
            raise InscripcionImposible("Ese atleta no es de este club")
        if not atleta.activo:
            raise InscripcionImposible(
                f"La ficha de {atleta} está dada de baja: restáurala antes de inscribirla",
            )
        assert atleta.id is not None, "se inscribe una ficha guardada"
        return Inscripcion(
            atleta_id=atleta.id, macrociclo_id=self.id,
            base_aerobica=base_aerobica, fuente_de_base=fuente_de_base,
        )

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
