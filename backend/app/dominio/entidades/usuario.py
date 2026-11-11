"""La cuenta de una persona: identidad, contraseña y sus sesiones (REDISENO §5.1).

**Sin rol ni equipo**, igual que la tabla: describen la relación de la persona
con un club y viven en la `Pertenencia`. Ser entrenador es algo que se es *en*
un club.

Lo que recupera esta clase es el comportamiento de las sesiones, que hasta el
2026-10-14 estaba repartido entre `auth/sessions.py` (`user.refresh_rotation
+= 1` a mano), el repositorio (`token_version += 1`) y el router de la
contraseña, que la cambiaba y revocaba en dos pasos y dos `commit`:

- `revocar_sesiones()` sube la **generación**: todo token emitido antes deja de
  validar en la siguiente petición. Es lo que hace que «salir de todas», cambiar
  la contraseña o revocar cierren algo; salir de **un** dispositivo es cerrar su
  `SesionAbierta`.
- `abrir_sesion()` abre una `SesionAbierta`: un login en un dispositivo, con
  **su** rotación del refresh (TODO-30). Hasta el 2026-10-20 la rotación vivía
  aquí, una por cuenta, y entrar en el móvil gastaba la cookie del portátil.
  Generación y rotación siguen siendo dos cosas distintas a propósito: si
  rotar subiera la generación, cada refresh echaría a los demás dispositivos.
- `cambiar_password()` cambia el hash **y** revoca: son las dos mitades del
  mismo gesto («creo que me han comprometido la cuenta»), y ahora no se puede
  hacer una sin la otra.

**Recibe el hash, no la contraseña.** El dominio no importa nada fuera de la
biblioteca estándar y Argon2 no lo es: quien hashea es `core/security`, y lo
que la entidad garantiza es qué pasa con las sesiones cuando el hash cambia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar

from .base import CamposGobernados, PorIdentidad
from .sesion_abierta import SesionAbierta


@dataclass(slots=True, eq=False)
class Usuario(PorIdentidad, CamposGobernados):
    """Una cuenta. Se compara por `id`: dos cuentas con el mismo nombre son dos.

    Los contadores, el hash y el último acceso solo cambian por sus métodos.
    """

    _GOBERNADOS: ClassVar[frozenset[str]] = frozenset({
        "hash_de_password", "version_de_token", "ultimo_login", "hash_leido",
        "version_leida", "password_temporal",
    })

    correo: str
    nombre: str
    hash_de_password: str
    id: int | None = None
    activo: bool = True
    version_de_token: int = 0
    creado: datetime | None = None
    ultimo_login: datetime | None = None
    # La contraseña actual la generó el sistema y la conoce quien dio el alta o
    # la restableció (TODO-27). Mientras siga puesta, la cuenta solo puede
    # cambiarla. Solo se mueve con `cambiar_password`.
    password_temporal: bool = False
    # El hash con el que se construyó: el que verificó el login. Escribir el
    # acceso es «si la contraseña sigue siendo esa» (revisor de TODO-30): un
    # cambio de contraseña a la vez no puede dejar entrar a quien usó la vieja.
    hash_leido: str = field(init=False, repr=False)
    # La generación con la que se construyó: lo que la entidad sube se escribe
    # como «+ n» en SQL (vuelta 3 del revisor de TODO-30), y `n` se cuenta desde
    # aquí, **no** desde la fila, que la sesión guarda con referencia débil y
    # puede releerse ya con la subida de otro (la trampa de TODO-25).
    version_leida: int = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hash_leido", self.hash_de_password)
        object.__setattr__(self, "version_leida", self.version_de_token)

    def subidas_de_generacion(self) -> int:
        """Cuántas veces se revocó desde que se construyó."""
        return self.version_de_token - self.version_leida

    # ── Sesiones ─────────────────────────────────────────────────────────────

    def revocar_sesiones(self) -> None:
        """Invalida de golpe todo token emitido antes: access y refresh."""
        object.__setattr__(self, "version_de_token", self.version_de_token + 1)

    def abrir_sesion(self, ahora: datetime, vigencia: timedelta) -> SesionAbierta:
        """Un login nuevo: una sesión de este dispositivo, en rotación 0."""
        if self.id is None:
            raise ValueError("Solo una cuenta ya guardada abre sesiones")
        return SesionAbierta.abrir(self.id, ahora, vigencia)

    def cambiar_password(self, nuevo_hash: str, *, temporal: bool = False) -> None:
        """Cambia el hash y revoca todas las sesiones. Las dos cosas o ninguna.

        `temporal` dice quién la eligió: `False` (por defecto) es la propia
        persona, y la cuenta queda libre; `True` es una que generó el sistema
        para que otro la entregue, y obliga a cambiarla al entrar."""
        if not nuevo_hash:
            raise ValueError("Una contraseña se guarda por su hash, y no puede ir vacío")
        object.__setattr__(self, "hash_de_password", nuevo_hash)
        object.__setattr__(self, "password_temporal", temporal)
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

    def __str__(self) -> str:
        return self.correo
