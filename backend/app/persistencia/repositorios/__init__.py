"""Un repositorio por agregado: la única puerta a la base de datos.

Cada repositorio recibe la sesión y el `Principal`, y devuelve **entidades de
dominio** — no filas — allí donde la entidad existe. Eso es lo que quita de en
medio la lógica cruzada: quien pide un macrociclo recibe un `Macrociclo` que ya
sabe en qué semana va, y no necesita importar la función de otro módulo para
averiguarlo.

Se migran de uno en uno.
"""
from __future__ import annotations

from .atletas import RepositorioDeAtletas
from .auditoria import RepositorioDeAuditoria
from .carga import RepositorioDeCarga
from .codigos import RepositorioDeCodigos
from .equipos import RepositorioDeEquipos
from .macrociclos import RepositorioDeMacrociclos
from .resultados import RepositorioDeResultados
from .sesiones import RepositorioDeSesiones
from .tests_aerobicos import RepositorioDeTests
from .usuarios import RepositorioDeUsuarios

__all__ = [
    "RepositorioDeAtletas",
    "RepositorioDeAuditoria",
    "RepositorioDeCarga",
    "RepositorioDeCodigos",
    "RepositorioDeEquipos",
    "RepositorioDeMacrociclos",
    "RepositorioDeResultados",
    "RepositorioDeSesiones",
    "RepositorioDeTests",
    "RepositorioDeUsuarios",
]
