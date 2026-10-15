"""La cuenta de una persona: identidad, contraseña y sus sesiones (REDISENO §5.1).

**Sin rol ni equipo**, igual que la tabla: describen la relación de la persona
con un club y viven en la `Pertenencia`. Ser entrenador es algo que se es *en*
un club.

Lo que recupera esta clase es el comportamiento de las sesiones, que hasta el
2026-10-14 estaba repartido entre `auth/sessions.py` (`user.refresh_rotation
+= 1` a mano), el repositorio (`token_version += 1`) y el router de la
contraseña, que la cambiaba y revocaba en dos pasos y dos `commit`:

- `revocar_sesiones()` sube la **generación**: todo token emitido antes deja de
  validar en la siguiente petición. Es lo que hace que cerrar sesión cierre algo.
- `rotar_refresh()` sube la **rotación**: el refresh entregado es el único
  válido, y uno gastado que reaparece es una cookie copiada. Son dos contadores
  distintos a propósito —si la rotación subiera la generación, cada refresh
  echaría a las demás pestañas—; el porqué largo está en la tabla.
- `cambiar_password()` cambia el hash **y** revoca: son las dos mitades del
  mismo gesto («creo que me han comprometido la cuenta»), y ahora no se puede
  hacer una sin la otra.

**Recibe el hash, no la contraseña.** El dominio no importa nada fuera de la
biblioteca estándar y Argon2 no lo es: quien hashea es `core/security`, y lo
que la entidad garantiza es qué pasa con las sesiones cuando el hash cambia.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from .base import CamposGobernados, PorIdentidad


@dataclass(slots=True, eq=False)
class Usuario(PorIdentidad, CamposGobernados):
    """Una cuenta. Se compara por `id`: dos cuentas con el mismo nombre son dos.

    Los contadores, el hash y el último acceso solo cambian por sus métodos.
    """

    _GOBERNADOS: ClassVar[frozenset[str]] = frozenset({
        "hash_de_password", "version_de_token", "rotacion_de_refresh", "ultimo_login",
    })

    correo: str
    nombre: str
    hash_de_password: str
    id: int | None = None
    activo: bool = True
    version_de_token: int = 0
    rotacion_de_refresh: int = 0
    creado: datetime | None = None
    ultimo_login: datetime | None = None

    # ── Sesiones ─────────────────────────────────────────────────────────────

    def revocar_sesiones(self) -> None:
        """Invalida de golpe todo token emitido antes: access y refresh."""
        object.__setattr__(self, "version_de_token", self.version_de_token + 1)

    def rotar_refresh(self) -> int:
        """Gasta una rotación y devuelve la nueva: la del único refresh válido."""
        object.__setattr__(self, "rotacion_de_refresh", self.rotacion_de_refresh + 1)
        return self.rotacion_de_refresh

    def cambiar_password(self, nuevo_hash: str) -> None:
        """Cambia el hash y revoca todas las sesiones. Las dos cosas o ninguna."""
        if not nuevo_hash:
            raise ValueError("Una contraseña se guarda por su hash, y no puede ir vacío")
        object.__setattr__(self, "hash_de_password", nuevo_hash)
        self.revocar_sesiones()

    def registrar_login(self, cuando: datetime, *, nuevo_hash: str | None = None) -> None:
        """Sella el acceso y, si el hash era de parámetros viejos, lo renueva.

        Renovar el hash al entrar **no** revoca nada: la contraseña es la misma,
        solo cambia cómo se guarda. Por eso no pasa por `cambiar_password`.
        """
        if nuevo_hash is not None:
            object.__setattr__(self, "hash_de_password", nuevo_hash)
        object.__setattr__(self, "ultimo_login", cuando)

    # ── Consultas ────────────────────────────────────────────────────────────

    def acepta_generacion(self, version: int) -> bool:
        """Si un token de esa generación sigue vivo (no hubo revocación después)."""
        return version == self.version_de_token

    def refresh_gastado(self, rotacion: int) -> bool:
        """Si un refresh con esa rotación ya se usó: reaparecer es robo."""
        return rotacion != self.rotacion_de_refresh

    def __str__(self) -> str:
        return self.correo
