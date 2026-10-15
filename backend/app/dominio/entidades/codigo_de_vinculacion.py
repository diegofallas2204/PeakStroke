"""El código que liga una ficha con una cuenta (REDISENO §5.13).

Ficha y cuenta son la misma persona vista desde dos sitios, y lo único que las
une es que alguien canjee esto. Lo emite el entrenador sobre una ficha suya sin
cuenta; lo canjea la persona. **Caduca a las 72 h, sirve una vez y emitir uno
nuevo revoca el anterior.**

Hasta el 2026-10-14 ese ciclo de vida eran tres columnas que cada sitio
comprobaba a mano (`sigue_vivo` en el repositorio, `revoked_at = ahora` en el
service y en el repositorio, `used_at`/`used_by` en el canje) y la cadena de
`elif` que decide quién puede canjear vivía en `api/v1/codigos/service.redeem`.
Ahora es esta clase: `es_servible()`, `es_para()`, `admite()`, `canjear()` y
`revocar()`.

**`admite()` conserva el orden de siempre** —otro club, entrenador, revocado—
y con él la invariante «revocado ≠ sin club»: una cuenta con la pertenencia
revocada **no** es una cuenta del pool y no entra en ningún club por un código.

R5.3 (§10.2 punto 3) pedía mirar `activa` antes que el club para que un atleta
que deja un club pudiera entrar en otro. **Se llega aquí de verdad**: revocar
una pertenencia no sube `token_version`, así que un access token emitido antes
sigue valiendo hasta que caduca (15 min), y una cuenta de atleta dada de alta
por `POST /auth/members` no tiene ficha que la pare antes. Pero invertir el
orden no basta y rompe dos cosas: trata «revocado» como «sin club», que es lo
que la invariante prohíbe, y `team_members` tiene `UNIQUE(user_id)`, así que
crear la pertenencia del club nuevo sin mover o borrar la vieja daría un
`IntegrityError` (un 500). Queda como decisión, con sus dos lecturas en
TODOS.md (TODO-26).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from .base import CamposGobernados, PorIdentidad
from .equipo import Pertenencia

HORAS_DE_VIDA = 72


class CanjeImposible(ValueError):
    """Quien canjea no puede ligarse por este código. El mensaje es para él."""


def _con_zona(valor: datetime) -> datetime:
    """SQLite devuelve las fechas sin zona aunque la columna la lleve. Lo único
    que se escribe es UTC, así que se asume UTC."""
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=UTC)


@dataclass(slots=True, eq=False)
class CodigoDeVinculacion(PorIdentidad, CamposGobernados):
    """Un código emitido. Se compara por `id`. Gastarlo y revocarlo, solo por
    `canjear` y `revocar`."""

    _GOBERNADOS: ClassVar[frozenset[str]] = frozenset({"usado_en", "usado_por", "revocado_en"})

    equipo_id: int
    ficha_id: int
    emitido_por: int
    codigo: str
    caduca: datetime
    id: int | None = None
    correo_invitado: str | None = None
    usado_en: datetime | None = None
    usado_por: int | None = None
    revocado_en: datetime | None = None
    creado: datetime | None = None

    @classmethod
    def emitir(
        cls, *, equipo_id: int, ficha_id: int, emitido_por: int, codigo: str,
        ahora: datetime, correo_invitado: str | None = None,
    ) -> CodigoDeVinculacion:
        """Un código nuevo, sin guardar, que caduca a las `HORAS_DE_VIDA`.

        El correo llega **ya normalizado**: la regla de normalización es de
        almacenamiento (`repositorios.usuarios.normalizar_correo`) y tiene que
        ser la misma con la que se compara `users.email`.
        """
        return cls(
            equipo_id=equipo_id, ficha_id=ficha_id, emitido_por=emitido_por,
            codigo=codigo, caduca=ahora + timedelta(hours=HORAS_DE_VIDA),
            correo_invitado=correo_invitado,
        )

    # ── Consultas ────────────────────────────────────────────────────────────

    def es_servible(self, ahora: datetime) -> bool:
        """Ni canjeado, ni revocado, ni caducado."""
        return (
            self.usado_en is None and self.revocado_en is None
            and _con_zona(self.caduca) > _con_zona(ahora)
        )

    def es_para(self, correo: str) -> bool:
        """Un código dirigido solo lo canjea su destinatario; uno suelto, quien
        lo tenga. `correo` llega normalizado, como `correo_invitado`."""
        return self.correo_invitado is None or self.correo_invitado == correo

    def admite(self, pertenencia: Pertenencia | None) -> bool:
        """Si la cuenta con esa pertenencia (**revocadas incluidas**) puede
        entrar por este código. Devuelve si hay que **crear** la pertenencia.

        `None` es el pool: la cuenta existe y no es de ningún club, y el código
        es su puerta de entrada. Con pertenencia, en este orden y con estos
        mensajes: de otro club; entrenador; revocada en este club. Ver la
        cabecera para por qué el orden no se invierte (R5.3).
        """
        if pertenencia is None:
            return True
        if pertenencia.equipo_id != self.equipo_id:
            raise CanjeImposible("Tu cuenta ya pertenece a otro equipo")
        if pertenencia.es_entrenador:
            raise CanjeImposible("Una cuenta de entrenador no puede ligarse a una ficha")
        if not pertenencia.activa:
            raise CanjeImposible("Tu acceso a este equipo está revocado")
        return False

    # ── Cambios ──────────────────────────────────────────────────────────────

    def canjear(self, usuario_id: int, ahora: datetime) -> None:
        """Lo gasta a nombre de esa cuenta. Uno que no es servible no se gasta."""
        if not self.es_servible(ahora):
            raise CanjeImposible("Código inválido o caducado")
        object.__setattr__(self, "usado_en", ahora)
        object.__setattr__(self, "usado_por", usuario_id)

    def revocar(self, ahora: datetime) -> bool:
        """Lo anula. Idempotente: revocarlo otra vez no mueve la fecha de la
        primera. Devuelve si cambió algo."""
        if self.revocado_en is not None:
            return False
        object.__setattr__(self, "revocado_en", ahora)
        return True

    def __str__(self) -> str:
        return self.codigo
