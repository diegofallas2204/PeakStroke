"""El código como se acuña y como se enseña.

De qué símbolos se hace y cómo se dicta. Cuánto dura, si **sigue vivo**, quién
puede canjearlo y cómo se gasta o se revoca son de la entidad
(`dominio.entidades.CodigoDeVinculacion`, §5.13, 2026-10-14).
"""
from __future__ import annotations

import secrets

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


def format_code(code: str) -> str:
    """`ABCD2345` -> `ABCD-2345`. Se lee y se dicta mucho mejor partido."""
    half = len(code) // 2
    return f"{code[:half]}-{code[half:]}"


def generate() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(LINK_CODE_LENGTH))
