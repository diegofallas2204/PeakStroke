"""`Rol`: lo que hoy son `if principal.is_athlete` repartidos por los servicios.

Un rol no tiene estado. Son objetos sin campos, comparables por su clase
(`Entrenador() == Entrenador()`), y su única razón de ser es contestar cinco
preguntas de cinco maneras distintas sin que quien pregunta sepa a quién le está
preguntando.

**El rol no es la cuenta.** Cuelga de la pertenencia al club, que es donde ya
vive en la base de datos (`team_members.role`): un atleta que asciende a
entrenador en su club es un `UPDATE`, y con herencia sobre `Usuario` sería
cambiar de clase una fila que no cambia de clase. Ver `docs/REDISENO.md` §4.1.

**Y ser dueño tampoco es un rol.** `EntrenadorEnJefe` existe aquí arriba porque
el dueño *alcanza* más macrociclos, pero quién es el dueño lo dice
`teams.owner_id` —una columna, única por construcción— y por eso `require_owner`
sigue preguntando por `principal.is_owner` y no por el rol. La jerarquía es del
dominio; el almacenamiento es plano (§4.3).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .vocabulario import Alcance, Recurso, Seccion


class Rol(ABC):
    """Qué alcanza quien hace la petición.

    Las cinco preguntas son las de `docs/REDISENO.md` §4.2. Todas son
    abstractas: un rol nuevo que se olvide de contestar una no se puede
    instanciar, en vez de heredar por defecto el permiso de su padre — que es
    como un rol restringido acaba con más alcance del que se le quiso dar.
    """

    __slots__ = ()

    @abstractmethod
    def puede_ver(self, recurso: Recurso) -> bool:
        """Si este rol puede LEER ese tipo de recurso.

        Responde por el tipo, no por la fila: *qué* filas alcanza lo dicen los
        alcances de abajo, y de imponerlo se encargan `visible_to` y
        `scope_to_own_swimmer`. Un rol jamás dice "sí" a un recurso ajeno.
        """

    @abstractmethod
    def puede_escribir(self, recurso: Recurso) -> bool:
        """Si este rol puede ESCRIBIR ese tipo de recurso."""

    @abstractmethod
    def alcance_de_atletas(self) -> Alcance:
        """Qué fichas de nadador alcanza."""

    @abstractmethod
    def alcance_de_macrociclos(self) -> Alcance:
        """Qué macrociclos alcanza."""

    @abstractmethod
    def secciones_visibles(self) -> frozenset[Seccion]:
        """Qué secciones de la aplicación tiene sentido enseñarle."""

    # ── Derivadas ────────────────────────────────────────────────────────────

    @property
    def alcanza_solo_lo_suyo(self) -> bool:
        """Si este rol solo llega a sus propios datos.

        Es la única pregunta que hace el filtro por nadador, y se deriva del
        alcance en vez de comprobar la clase: preguntar `isinstance(rol,
        AtletaRol)` volvería a atar el filtro a un rol concreto, que es
        exactamente lo que este paso viene a deshacer. Un rol futuro que solo
        se alcance a sí mismo queda filtrado sin tocar el helper.
        """
        return self.alcance_de_atletas() is Alcance.SOLO_YO

    def __eq__(self, otro: object) -> bool:
        return type(self) is type(otro)

    def __hash__(self) -> int:
        return hash(type(self))

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"
