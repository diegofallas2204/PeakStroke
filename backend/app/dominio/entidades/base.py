"""Lo único que comparten todas las entidades: cómo se comparan.

Un objeto de valor (`valores/`) es igual a otro cuando **valen** lo mismo: dos
`Tiempo(78.0)` son el mismo tiempo. Una entidad no: dos atletas homónimos con la
misma fecha de nacimiento son dos personas distintas, y el mismo atleta con el
nombre corregido sigue siendo él. Lo que decide es la identidad.

De ahí que las entidades se declaren `eq=False`: el `__eq__` que genera
`dataclass` compara campo a campo, que es exactamente la respuesta equivocada.
"""
from __future__ import annotations

from typing import ClassVar


class PorIdentidad:
    """Igualdad y hash por `(clase, id)`. Sin `id`, solo consigo misma.

    Dos entidades recién construidas —todavía sin fila— **no son iguales aunque
    lleven los mismos datos**: hasta que algo les da identidad no hay forma de
    saber si son la misma cosa dos veces o dos cosas parecidas. Suponer que sí
    es como dos hermanos con el mismo nombre acaban siendo un solo atleta.

    El hash de una entidad sin `id` es el de su objeto. Consecuencia: si se mete
    en un `set` y **después** se le asigna `id`, ese `set` queda inconsistente.
    En este paso nadie asigna identidad tras construir (la ponen los mapeos, al
    construir), y cuando aparezca el repositorio del paso 5 será él quien decida
    si hidrata una entidad nueva o rellena una existente.
    """

    __slots__ = ()

    id: int | None

    def __eq__(self, otro: object) -> bool:
        if type(otro) is not type(self):
            return NotImplemented
        if self.id is None or otro.id is None:   # type: ignore[attr-defined]
            return self is otro
        return self.id == otro.id                # type: ignore[attr-defined]

    def __hash__(self) -> int:
        if self.id is None:
            return object.__hash__(self)
        return hash((type(self).__name__, self.id))


class CamposGobernados:
    """Campos que, una vez construida la entidad, **solo cambian por sus métodos**.

    Es el patrón de `Semana.esperado` generalizado (C9, 2026-10-14): el revisor
    del bloque de `Equipo` vio que `club.dueno_id = 5` y `guardar_equipo(club)`
    saltaban las tres comprobaciones de `transferir_propiedad`. Una regla que
    vive en un método no protege nada si el campo se puede asignar al lado.

    La subclase declara `_GOBERNADOS`; sus métodos escriben con
    `object.__setattr__`. El constructor asigna libremente (el campo todavía no
    existe), y el mapeo fila → entidad construye, no asigna.
    """

    __slots__ = ()
    _GOBERNADOS: ClassVar[frozenset[str]] = frozenset()

    def __setattr__(self, nombre: str, valor: object) -> None:
        # `hasattr` es falso mientras el constructor lo asigna por primera vez.
        if nombre in self._GOBERNADOS and hasattr(self, nombre):
            raise AttributeError(
                f"`{nombre}` de {type(self).__name__} solo cambia por sus métodos",
            )
        object.__setattr__(self, nombre, valor)
