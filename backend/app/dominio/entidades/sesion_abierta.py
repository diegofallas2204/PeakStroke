"""Una sesión abierta: un login en un dispositivo, con su propia rotación (TODO-30).

Hasta el 2026-10-20 la rotación del refresh era **una por cuenta**
(`users.refresh_rotation`, en `Usuario`): entrar en el móvil gastaba la cookie
del portátil, y su siguiente refresh se cortaba como robo — las dos fuera y un
`REFRESH_REUSADO` falso, cada vez que alguien usaba dos dispositivos. Ahora cada
login abre una de estas, y el token lleva su `id` (`sid`).

    login ──▶ abierta (rotación 0) ──refresh──▶ rotación n+1 ──refresh──▶ …
                 │                          │
                 │   refresh de rotación vieja, o dos a la vez: reuso
                 │   logout de este dispositivo, o la purga al caducar
                 ▼                          ▼
              cerrada (la fila se borra: el rastro vive en la auditoría)

Cortar **todas** las de una cuenta no es de aquí: lo hace la generación de
`Usuario` (`revocar_sesiones`), y el repositorio borra sus filas.

**El id es aleatorio, no un entero.** SQLite sin `AUTOINCREMENT` reutiliza el
último rowid borrado: un refresh de una sesión cerrada habría revivido en la
siguiente que se abriera. `secrets` es de la biblioteca estándar.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from .base import CamposGobernados, PorIdentidad


def _con_zona(valor: datetime) -> datetime:
    """SQLite devuelve las fechas sin zona; se guardan siempre en UTC."""
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=UTC)


@dataclass(slots=True, eq=False)
class SesionAbierta(PorIdentidad, CamposGobernados):
    """Se compara por `id`. La rotación y la caducidad solo cambian al rotar."""

    _GOBERNADOS: ClassVar[frozenset[str]] = frozenset({"rotacion", "caduca", "rotacion_leida"})

    id: str
    usuario_id: int
    caduca: datetime
    rotacion: int = 0
    abierta: datetime | None = None
    # Con la que se construyó: gastar la rotación es «pasar de esta a la
    # siguiente», y eso es lo que el repositorio le pide a la base (TODO-25).
    rotacion_leida: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rotacion_leida", self.rotacion)

    @classmethod
    def abrir(cls, usuario_id: int, ahora: datetime, vigencia: timedelta) -> SesionAbierta:
        return cls(
            id=secrets.token_urlsafe(24), usuario_id=usuario_id,
            caduca=ahora + vigencia, abierta=ahora,
        )

    def rotar(self, ahora: datetime, vigencia: timedelta) -> int:
        """Gasta una rotación y desliza la caducidad: la del refresh nuevo."""
        object.__setattr__(self, "rotacion", self.rotacion + 1)
        object.__setattr__(self, "caduca", ahora + vigencia)
        return self.rotacion

    def refresh_gastado(self, rotacion: int) -> bool:
        """Si un refresh con esa rotación ya se usó: reaparecer es una copia."""
        return rotacion != self.rotacion

    def caducada(self, ahora: datetime) -> bool:
        return _con_zona(ahora) >= _con_zona(self.caduca)

    def roto(self) -> bool:
        """Si desde que se construyó se gastó alguna rotación."""
        return self.rotacion != self.rotacion_leida
