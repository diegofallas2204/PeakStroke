"""La prueba objetivo: qué quiere nadar un atleta en un macrociclo, y en cuánto.

§5.7 de `docs/REDISENO.md`, construida en C9 (2026-10-13). Hasta entonces era
solo la fila `AthleteEvent` —`distance` y `stroke` sueltos, dos `float` de
tiempo—, y se armaba en `api/v1/macrociclos/nomina.py` con
`AthleteEvent(**event_data.model_dump())`: lo que la hacía válida era que el
formulario hubiera pasado antes por un validador de Pydantic.

Aquí la prueba es un `Prueba` y las dos marcas son `Tiempo`, así que **una
prueba objetivo inválida no se puede tener en las manos**, venga del API, del
seed o de un test. Es el mismo movimiento que `Prueba` hizo con el 50 combinado.

**`factibilidad()` recibe el techo; no lo calcula** (enmienda a §5.7, que la
firmaba `(nivel, semanas, n_mac, edad)`). Cuánto puede mejorar un atleta en un
macro es la envolvente del motor, y una entidad no importa los servicios: la
flecha va al revés (`servicios/plan.py` importa de aquí). El dato lo trae quien
llama, igual que `Sesion.carga(css)` recibe el CSS. Y el nivel ya no es algo
que se le pase a mano: lo deriva el motor del test aeróbico (defecto 1 de §10.4).

Sus semanas todavía son filas (`Semana`, §5.8, es el punto 4 de C9): esta
entidad lleva solo lo que es de la prueba.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..valores import Mejora, Prueba, Tiempo, Veredicto
from .base import PorIdentidad


@dataclass(slots=True, eq=False)
class PruebaObjetivo(PorIdentidad):
    """Una prueba, la marca de partida y la meta. Cuelga de una inscripción."""

    prueba: Prueba
    actual: Tiempo
    meta: Tiempo
    # Orden entre las pruebas del atleta: la 1 es la principal.
    prioridad: int = 1
    inscripcion_id: int | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.prueba, Prueba):
            raise TypeError("La prueba de un objetivo es una Prueba, no distancia y estilo sueltos")
        if not isinstance(self.actual, Tiempo) or not isinstance(self.meta, Tiempo):
            raise TypeError("La marca actual y la meta son Tiempo, no números sueltos")
        if isinstance(self.prioridad, bool) or not isinstance(self.prioridad, int):
            raise TypeError(f"La prioridad es un entero: {self.prioridad!r}")
        if self.prioridad < 1:
            raise ValueError(f"La prioridad empieza en 1: {self.prioridad}")

    @classmethod
    def nueva(
        cls, distancia: int, estilo: str, actual: float, meta: float, prioridad: int = 1,
    ) -> PruebaObjetivo:
        """Una prueba objetivo sin guardar, desde los números con que llega del API.

        El estilo acepta los alias y sale canónico («crol» entra, «libre» es lo
        que se guarda). Los `ValueError` de `Prueba` y de `Tiempo` suben tal
        cual; son el mensaje del 422 porque `EventInput` la construye dentro de
        su validador (`a_entidad`), antes de que nada más la toque.
        """
        return cls(
            prueba=Prueba(distancia, estilo), actual=Tiempo(actual), meta=Tiempo(meta),
            prioridad=prioridad,
        )

    def mejora_pedida(self) -> Mejora:
        """Lo que hay de la marca actual a la meta, sobre la marca actual.

        Cero si la meta ya está alcanzada y regresión si es más lenta: un plan
        de mantenimiento es legítimo, y el motor lo trata como tal.
        """
        return self.actual - self.meta

    def factibilidad(self, techo: Mejora) -> Veredicto:
        """Si la meta cabe en `techo`: lo más que el motor cree que puede bajar.

        `techo` es la envolvente del macro sobre **esta** marca
        (`MOTOR.envolvente(...).mejora_maxima_s`, como `Mejora` sobre `actual`).
        Un techo sobre otro tiempo de partida es el de otro atleta, y compararlo
        con esta meta daría un veredicto que parece bueno: se rechaza.

        Los umbrales son los del motor (`Veredicto.del_uso`); el cociente, no
        exactamente: aquí es segundos pedidos / segundos de techo y el motor
        divide dos fracciones. Dan lo mismo salvo con la meta clavada en un
        umbral, donde el último bit puede caer a un lado u otro (medido al
        revisar C9: 350 de 48 000 metas sin redondear puestas justo en 0.85;
        0 de 144 000 con metas a la centésima, que es como se apuntan).
        """
        if not isinstance(techo, Mejora):
            raise TypeError("El techo es una Mejora sobre la marca actual, no un número suelto")
        if techo.base != self.actual:
            raise ValueError(
                f"Ese techo se calculó sobre {techo.base}, y esta prueba parte de {self.actual}",
            )
        pedida = self.mejora_pedida()
        if pedida.segundos <= 0:
            return Veredicto.OK          # meta ya alcanzada: plan de mantenimiento
        if techo.segundos <= 0:
            return Veredicto.AGRESIVO    # sin margen, cualquier mejora lo supera
        return Veredicto.del_uso(pedida.segundos / techo.segundos)

    def __str__(self) -> str:
        return f"{self.prueba}: {self.actual} a {self.meta}"
