"""El entrenador, y el jefe como una ampliación suya de una sola línea."""
from __future__ import annotations

from .rol import Rol
from .vocabulario import Alcance, Recurso, Seccion

_SECCIONES_DE_ENTRENADOR = frozenset(Seccion)


class Entrenador(Rol):
    """Ve y escribe todo lo de su club, y los macrociclos que lleva.

    El alcance de atletas es `TODOS` —los del equipo— y no `LOS_MIOS` aunque
    `coach_athletes` exista: esa tabla dice quién lleva a quién, pero hoy no
    acota ninguna consulta. Escribir aquí `LOS_MIOS` no cerraría nada (los
    servicios seguirían sin filtrar) y haría creer que sí, que es peor que
    decir la verdad de lo que hay.

    El club aparece como escribible porque un asistente da de alta miembros y
    emite códigos de vinculación, que es `require_coach` en `teams/router.py`.
    Renombrar el club y transferir la propiedad no pasan por aquí: son de dueño,
    y el dueño es una columna (ver la cabecera de `rol.py`).
    """

    __slots__ = ()

    def puede_ver(self, recurso: Recurso) -> bool:
        return True

    def puede_escribir(self, recurso: Recurso) -> bool:
        return True

    def alcance_de_atletas(self) -> Alcance:
        return Alcance.TODOS

    def alcance_de_macrociclos(self) -> Alcance:
        """Solo aquellos en los que figura (`plan_coaches`)."""
        return Alcance.LOS_MIOS

    def secciones_visibles(self) -> frozenset[Seccion]:
        return _SECCIONES_DE_ENTRENADOR


class EntrenadorEnJefe(Entrenador):
    """El dueño del equipo. **Solo amplía el alcance de macrociclos.**

    Y esa ampliación es la regla real: si el jefe no llegara a todos, los
    macrociclos de un entrenador que se va del club no los podría ver ni
    reasignar nadie. No es un rol distinto —hace el mismo trabajo, con las
    mismas escrituras— sino el mismo con más alcance, y por eso hereda en vez de
    duplicar (`docs/REDISENO.md` §4.2 y §4.5).

    Que no sobrescriba nada más es deliberado: cada método que añadiera aquí
    sería una diferencia jefe/asistente que la capa de acceso tendría que
    aprender por separado.
    """

    __slots__ = ()

    def alcance_de_macrociclos(self) -> Alcance:
        return Alcance.TODOS
