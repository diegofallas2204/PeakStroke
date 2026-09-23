"""El atleta: lo suyo, y solo lo suyo."""
from __future__ import annotations

from .rol import Rol
from .vocabulario import Alcance, Recurso, Seccion

# Lo que un atleta escribe sobre sus propios datos. Son dos y son las dos que
# los routers dejan pasar sin `require_coach`: apuntar el tiempo real de su
# semana y registrar sus tests aeróbicos. Todo lo demás —la ficha, el plan, el
# parón de la semana, el club— lo escribe el entrenador.
_ESCRIBE = frozenset({Recurso.SEMANA, Recurso.TEST_AEROBICO})

# La tabla del equipo enseña nombres, ritmos y marcas de todos los compañeros:
# es la sección que el atleta no ve, y `require_coach` la cierra en el backend
# antes de que el menú la esconda.
_NO_VE = frozenset({Recurso.EQUIPO})

_SECCIONES_DE_ATLETA = frozenset({
    Seccion.DASHBOARD,
    Seccion.BASE_AEROBICA,
    Seccion.PLAN_SEMANAL,
})


class AtletaRol(Rol):
    """Ve su ficha, su macrociclo y sus tests; escribe lo que nada.

    Se llama `AtletaRol` y no `Atleta` porque `Atleta` ya existe en
    `dominio.entidades` y es otra cosa: la persona, con su fecha de nacimiento y
    su especialidad. Esto es lo que alcanza dentro de un club — dos objetos
    distintos que se juntan en `Principal`.

    El alcance `SOLO_YO` es lo que activa el filtro por nadador. Y ese filtro
    falla CERRADO: un atleta sin ficha ligada no ve nada, no lo ve todo (ver
    `Principal.scope_to_own_swimmer`).
    """

    __slots__ = ()

    def puede_ver(self, recurso: Recurso) -> bool:
        return recurso not in _NO_VE

    def puede_escribir(self, recurso: Recurso) -> bool:
        return recurso in _ESCRIBE

    def alcance_de_atletas(self) -> Alcance:
        return Alcance.SOLO_YO

    def alcance_de_macrociclos(self) -> Alcance:
        """Aquel en el que está inscrito, y mientras la inscripción siga activa."""
        return Alcance.SOLO_YO

    def secciones_visibles(self) -> frozenset[Seccion]:
        return _SECCIONES_DE_ATLETA
