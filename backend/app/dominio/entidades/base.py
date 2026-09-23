"""Lo único que comparten todas las entidades: cómo se comparan.

Un objeto de valor (`valores/`) es igual a otro cuando **valen** lo mismo: dos
`Tiempo(78.0)` son el mismo tiempo. Una entidad no: dos atletas homónimos con la
misma fecha de nacimiento son dos personas distintas, y el mismo atleta con el
nombre corregido sigue siendo él. Lo que decide es la identidad.

De ahí que las entidades se declaren `eq=False`: el `__eq__` que genera
`dataclass` compara campo a campo, que es exactamente la respuesta equivocada.
"""
from __future__ import annotations


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
