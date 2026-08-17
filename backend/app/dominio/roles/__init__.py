"""Roles: el polimorfismo que sustituye a los `if` de permisos. Paso 3 (§4).

    Rol (abstracto)
      ├── Administrador       plataforma; cruza equipos   (R3: solo el hueco)
      ├── EntrenadorEnJefe    = dueño; ve TODOS los macrociclos del club
      │     └── hereda de Entrenador y solo amplía el alcance
      ├── Entrenador          ve los macrociclos en los que está
      └── AtletaRol           ve lo suyo y solo lo suyo

Igual que `valores/` y `entidades/`, no importa nada: son objetos sin estado que
contestan preguntas, y no saben que existe una petición HTTP ni una fila de
`team_members`. Quién los construye a partir de una pertenencia es
`core/principal.rol_de`, del lado de fuera.

**Tres cosas que este paquete NO hace, y cada una tiene su motivo:**

* no dice quién es el dueño — eso es `teams.owner_id`, una columna, y por eso
  `require_owner` sigue preguntando por `principal.is_owner` (§4.3);
* no conoce el modo desarrollador — `is_developer` es un eje ORTOGONAL al rol, no
  un rol más, y no existe forma de persistirlo. Un `RolDesarrollador` aquí sería
  justo esa forma;
* no impone nada por sí solo. Un rol contesta; quien acota las consultas son
  `plans/access.visible_to` y `Principal.scope_to_own_swimmer`.
"""
from __future__ import annotations

from .administrador import Administrador
from .atleta import AtletaRol
from .entrenador import Entrenador, EntrenadorEnJefe
from .rol import Rol
from .vocabulario import Alcance, Recurso, Seccion

__all__ = [
    "Rol",
    "Administrador",
    "Entrenador",
    "EntrenadorEnJefe",
    "AtletaRol",
    "Alcance",
    "Recurso",
    "Seccion",
]
