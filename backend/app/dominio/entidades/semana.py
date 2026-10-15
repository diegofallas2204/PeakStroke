"""La semana del plan de una prueba: qué se espera nadar y qué se ha movido.

§5.8 de `docs/REDISENO.md`, construida en C9 (2026-10-13). Hasta entonces era
solo la fila `WeeklyPlan`, y sus tres escrituras —el parón, el tiempo real y la
curva recalculada— eran asignaciones sobre esa fila hechas desde
`api/v1/macrociclos/semanas.py`.

Tres cosas que este tipo sostiene y la fila no:

**La curva ideal no se modifica nunca.** `esperado` se fija al construir y la
entidad rechaza cualquier asignación posterior. Lo que cambia cuando el atleta
nada algo o el entrenador pone un parón es `recalculado`, que es otra cosa: sin
esa separación no habría contra qué medir el progreso. Era una regla del
CLAUDE.md que cada escritura tenía que acordarse de respetar.

**No guarda ningún tiempo real.** Lo nadado vive en `Resultado`, colgando del
atleta (R2 enmendada, §10.2). La semana lo deriva: de los resultados que se le
pasan toma los que caen en sus siete días y enseña el promedio.

**Sus derivados reciben su contexto** (enmienda a §5.8, que los firmaba sin
argumentos). Una semana no conoce a su atleta, su prueba ni la piscina de su
macrociclo —cuelga de una `PruebaObjetivo`, que cuelga de una `Inscripcion`—,
así que `real()` y `zonas()` los piden. Es la misma decisión que
`PruebaObjetivo.factibilidad(techo)`.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from ..valores import Fase, JuegoDeZonas, Mejora, Piscina, Prueba, Ritmo, Tiempo
from .base import PorIdentidad
from .resultado import Resultado, de_la_semana, promedio


@dataclass(slots=True, eq=False)
class Semana(PorIdentidad):
    """Una semana de una prueba objetivo: la prevista, y lo que la ha movido."""

    numero: int
    fecha: date                        # el lunes: la semana es [fecha, fecha + 7)
    km_planificados: float
    esperado: Tiempo                   # curva ideal original — NUNCA se modifica
    fase: Fase                         # clave de dominio, no la etiqueta del tramo
    recalculado: Tiempo | None = None  # curva reanclada tras un tiempo real o un parón
    deshabilitada: bool = False        # parón: lesión, vacaciones, competencia
    razon: str | None = None
    prueba_id: int | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.numero, bool) or not isinstance(self.numero, int):
            raise TypeError(f"El número de semana es un entero: {self.numero!r}")
        if self.numero < 1:
            raise ValueError(f"Las semanas se cuentan desde 1: {self.numero}")
        if not isinstance(self.esperado, Tiempo):
            raise TypeError("El tiempo esperado de una semana es un Tiempo")
        if self.recalculado is not None and not isinstance(self.recalculado, Tiempo):
            raise TypeError("El tiempo recalculado de una semana es un Tiempo, o no hay")
        if not isinstance(self.fase, Fase):
            raise TypeError("La fase de una semana es una Fase, no un texto")
        if self.fase.es_extension:
            raise ValueError("La extensión no es una semana del macrociclo")
        if self.km_planificados < 0:
            raise ValueError(f"Los kilómetros de una semana no son negativos: {self.km_planificados}")

    def __setattr__(self, nombre: str, valor: object) -> None:
        # `hasattr` es falso mientras el constructor lo asigna por primera vez.
        if nombre == "esperado" and hasattr(self, "esperado"):
            raise AttributeError(
                "La curva ideal no se modifica: lo que cambia es `recalculado` (reanclar)",
            )
        object.__setattr__(self, nombre, valor)

    # ── Lo que vale hoy ──────────────────────────────────────────────────────

    def vigente(self) -> Tiempo:
        """El tiempo con el que se entrena esta semana: el recalculado si lo hay."""
        return self.recalculado if self.recalculado is not None else self.esperado

    def ritmo(self, distancia: int) -> Ritmo:
        """Ritmo de carrera /100 m del tiempo vigente. De aquí salen las zonas."""
        return self.vigente().a_ritmo(distancia)

    def zonas(self, prueba: Prueba, piscina: Piscina) -> JuegoDeZonas:
        """Las cinco prescripciones de la semana. **Derivado, no se guarda.**"""
        return JuegoDeZonas.de(self.ritmo(prueba.distancia), prueba, piscina)

    # ── Lo que la mueve ──────────────────────────────────────────────────────
    #
    # `parar` y `reanudar` son idempotentes y devuelven si cambiaron, como el
    # resto de las entidades. Ninguna toca `esperado`.

    def parar(self, razon: str | None = None) -> bool:
        """Parón del entrenador: esta semana no progresa. `True` si cambió algo."""
        cambia = not self.deshabilitada or self.razon != razon
        self.deshabilitada, self.razon = True, razon
        return cambia

    def reanudar(self) -> bool:
        """Quita el parón, y con él su razón. `True` si estaba parada."""
        cambia = self.deshabilitada or self.razon is not None
        self.deshabilitada, self.razon = False, None
        return cambia

    def reanclar(self, tiempo: Tiempo | None) -> None:
        """Fija el tiempo recalculado. `None` devuelve la semana a la curva ideal."""
        if tiempo is not None and not isinstance(tiempo, Tiempo):
            raise TypeError("Una semana se reancla a un Tiempo, o a nada")
        self.recalculado = tiempo

    # ── Lo nadado, que no es suyo ────────────────────────────────────────────

    def resultados(
        self, de_el_atleta: Iterable[Resultado], *, atleta_id: int, prueba: Prueba,
    ) -> list[Resultado]:
        """De esos resultados, los que caen en esta semana: 0, 1 o varios."""
        return de_la_semana(de_el_atleta, atleta_id=atleta_id, prueba=prueba, lunes=self.fecha)

    def real(
        self, de_el_atleta: Iterable[Resultado], *,
        atleta_id: int, prueba: Prueba, piscina: Piscina,
    ) -> Tiempo | None:
        """El tiempo real de la semana: el promedio de sus resultados, o `None`.

        `piscina` es la del macrociclo: un tiempo nadado en otra entra convertido
        a esta. **Solo esto reancla la curva**: un resultado que no cae en
        ninguna semana no llega aquí y no puede tocar la predicción.
        """
        return promedio(self.resultados(de_el_atleta, atleta_id=atleta_id, prueba=prueba), piscina)

    def desviacion(self, real: Tiempo | None) -> Mejora | None:
        """Lo nadado contra la curva **ideal**: positiva si fue más rápido.

        Contra `esperado` y no contra `vigente()`: el recalculado ya está
        anclado a lo que se nadó, así que compararse con él no diría nada.
        """
        return self.esperado - real if real is not None else None

    def __str__(self) -> str:
        return f"S{self.numero} ({self.fecha:%d/%m}): {self.vigente()}"
