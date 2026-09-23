"""El administrador de plataforma: **el hueco, y nada más** (R3).

Esta clase existe para que la jerarquía no cierre la puerta —que
`alcance_de_atletas()` pueda devolver `TODOS` sin que eso sea una excepción
cosida a mano— y ahí se acaba. Decisión R3, cerrada el 2026-08-16:

  · **nada la construye.** `core/principal.rol_de` traduce las dos claves que
    hay en `team_members` y levanta `ValueError` con cualquier otra, así que no
    existe fila capaz de producir un administrador. `tests/test_roles.py` lo fija;
  · **ni `es_staff` en `usuarios`, ni campo en `Principal`, ni tabla
    `roles_de_plataforma`.** Un hueco en una jerarquía de clases es gratis y
    reversible; un campo en el objeto del que cuelga el aislamiento, no;
  · y cuando se implemente **no irá en `team_members`**: un administrador cruza
    equipos por definición, y el equipo es la frontera de todo el aislamiento.
    Meterlo ahí obligaría a que cada consulta llevara un "salvo si es admin",
    que es exactamente como se rompen las fronteras. Va como eje ORTOGONAL,
    igual que `is_developer` (`docs/REDISENO.md` §4.4).
"""
from __future__ import annotations

from .rol import Rol
from .vocabulario import Alcance, Recurso, Seccion


class Administrador(Rol):
    """Cruza equipos. Contemplado, no implementado: nada lo instancia."""

    __slots__ = ()

    def puede_ver(self, recurso: Recurso) -> bool:
        return True

    def puede_escribir(self, recurso: Recurso) -> bool:
        return True

    def alcance_de_atletas(self) -> Alcance:
        return Alcance.TODOS

    def alcance_de_macrociclos(self) -> Alcance:
        return Alcance.TODOS

    def secciones_visibles(self) -> frozenset[Seccion]:
        return frozenset(Seccion)
