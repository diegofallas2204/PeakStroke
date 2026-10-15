"""Los vocabularios cerrados que la base impone con un CHECK (REDISENO §7.2 fila 6).

Salen de los enums del dominio, no de una lista tecleada: la tabla dice lo que
el dominio sabe construir. La migración que creó los CHECK (`c9e1a4d7b2f6`)
lleva su propia copia —una migración es una foto del momento— y
`tests/test_vocabularios.py` compara las tres: el dominio, esto y la migración,
más los `Literal` del API (`app/api/vocabulario.py`), que son los que dan el 422
antes de llegar aquí. Si el API aceptara algo que el CHECK rechaza, saldría un
500 en vez de un 422.
"""
from __future__ import annotations

from sqlalchemy import CheckConstraint

from app.dominio.valores import (
    Especialidad,
    EstadoDeMacro,
    Estilo,
    Genero,
    ModoDeIngreso,
    Piscina,
    TipoDeTest,
)

ESTILOS: tuple[str, ...] = tuple(e.value for e in Estilo)
ESPECIALIDADES: tuple[str, ...] = tuple(e.value for e in Especialidad)
GENEROS: tuple[str, ...] = tuple(g.value for g in Genero)
PISCINAS: tuple[str, ...] = tuple(p.value for p in Piscina)
ESTADOS_DE_MACRO: tuple[str, ...] = tuple(e.value for e in EstadoDeMacro)
TIPOS_DE_TEST: tuple[str, ...] = tuple(t.value for t in TipoDeTest)
MODOS_DE_INGRESO: tuple[str, ...] = tuple(m.value for m in ModoDeIngreso)


def en(columna: str, valores: tuple[str, ...], *, nombre: str, nulo: bool = False) -> CheckConstraint:
    """`CHECK (col IN (...))`, o `col IS NULL OR ...` si la columna admite NULL.

    La misma forma que escribe la migración, para que el metadata y la base digan
    lo mismo.
    """
    lista = ", ".join(f"'{v}'" for v in valores)
    dentro = f"{columna} IN ({lista})"
    return CheckConstraint(f"{columna} IS NULL OR {dentro}" if nulo else dentro, name=nombre)
