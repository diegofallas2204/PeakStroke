"""El código como objeto: generarlo, escribirlo, leerlo y saber si sigue vivo.

Nada de aquí decide nada de negocio — eso es `service.py`. Aquí está solo la
mecánica del código: de qué símbolos se hace, cómo se dicta, cuánto dura y cómo
se compara esa duración contra el reloj.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from .models import LinkCode

LINK_CODE_TTL_HOURS = 72
LINK_CODE_LENGTH = 8

# Sin I, L, O, U, 0 ni 1: el código se dicta en voz alta y se teclea a mano, y
# la confusión entre O y 0 cuesta más que los 4 bits que ahorra incluirlas.
# 32 símbolos ** 8 = 1,1e12 combinaciones, con `secrets` detrás.
_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"


class LinkCodeError(Exception):
    """Regla de negocio incumplida. El router la traduce a 400/404/409."""

    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


def normalize_code(raw: str) -> str:
    """Mayúsculas, sin guiones ni espacios. El guion es solo presentación."""
    return "".join(c for c in raw.strip().upper() if c.isalnum())


def format_code(code: str) -> str:
    """`ABCD2345` → `ABCD-2345`. Se lee y se dicta mucho mejor partido."""
    half = len(code) // 2
    return f"{code[:half]}-{code[half:]}"


def generate() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(LINK_CODE_LENGTH))


def now_utc() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    """SQLite devuelve datetimes naive aunque la columna sea timezone=True.

    Compararlos con un `datetime.now(UTC)` revienta con TypeError, y hacerlo en
    el sitio donde se compara —y no aquí— es como se acaba con la mitad de las
    comparaciones sin arreglar. Se asume UTC porque es lo único que se escribe.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def is_live(code: LinkCode, *, now: datetime | None = None) -> bool:
    return (
        code.used_at is None
        and code.revoked_at is None
        and _aware(code.expires_at) > (now or now_utc())
    )
