"""El código como se acuña y como se enseña.

De qué símbolos se hace, cuánto dura y cómo se dicta. Lo que decide si **sigue
vivo** —y cómo se compara contra el reloj— está en
`persistencia/repositorios/codigos.py`, junto a la tabla: el corte es entre lo
que se guarda y se compara y lo que se acuña y se enseña. Cuando el §5.13 del
rediseño se construya, las dos mitades se juntan dentro de la entidad.
"""
from __future__ import annotations

import secrets

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


def format_code(code: str) -> str:
    """`ABCD2345` -> `ABCD-2345`. Se lee y se dicta mucho mejor partido."""
    half = len(code) // 2
    return f"{code[:half]}-{code[half:]}"


def generate() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(LINK_CODE_LENGTH))
