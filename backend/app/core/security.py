"""Primitivas de seguridad: hash de contraseñas y firma/verificación de JWT.

Funciones puras — no tocan DB ni conocen los modelos. El módulo `auth` las usa;
`core/dependencies.py` las usa para resolver el usuario de la petición.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import settings

TokenType = Literal["access", "refresh"]

# Argon2id con los parámetros por defecto de argon2-cffi, alineados con la
# recomendación OWASP. El hash lleva embebidos sus propios parámetros, así que
# subirlos en el futuro no invalida los hashes ya guardados.
_hasher = PasswordHasher()


# --- Contraseñas ------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """True si la contraseña coincide. Nunca lanza: un hash corrupto es un fallo."""
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True si el hash se generó con parámetros antiguos (rehashear al entrar)."""
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True


# --- Tokens -----------------------------------------------------------------

class TokenError(Exception):
    """Token ausente, malformado, caducado o del tipo equivocado."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Lo que un token afirma: quién es, de qué generación, y de qué rotación.

    `token_version` lo llevan los dos tipos y sube al revocar (cerrar sesión,
    cambiar la contraseña). `rotation` solo lo lleva el refresh y sube en cada
    uso: es lo que permite detectar que alguien está reusando un token gastado.
    """

    user_id: int
    token_version: int
    rotation: int = 0


def _create_token(
    subject: str, token_type: TokenType, expires: timedelta,
    token_version: int, rotation: int = 0,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,          # id del usuario, siempre string (requisito del RFC)
        "type": token_type,      # impide usar un refresh como access
        "ver": token_version,    # generación de sesiones: subirla revoca lo anterior
        "iat": now,
        "exp": now + expires,
    }
    if token_type == "refresh":
        payload["rot"] = rotation
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: int, token_version: int) -> str:
    return _create_token(
        str(user_id), "access", timedelta(minutes=settings.access_token_minutes), token_version,
    )


def create_refresh_token(user_id: int, token_version: int, rotation: int) -> str:
    return _create_token(
        str(user_id), "refresh", timedelta(days=settings.refresh_token_days),
        token_version, rotation,
    )


def decode_token(token: str, expected_type: TokenType) -> TokenClaims:
    """Devuelve lo que afirma el token, o lanza TokenError.

    Verificar `type` es lo que impide que un refresh (de vida larga) se cuele
    como access en la cabecera Authorization.

    **No comprueba `ver` aquí**: para eso hace falta el usuario, y este módulo no
    toca la base de datos. Quien resuelve al usuario compara — `dependencies.py`
    para el access, `auth/router.py` para el refresh. La firma devuelve el dato
    para que olvidarse de compararlo sea una omisión visible y no un silencio.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"se esperaba un token de tipo '{expected_type}'")
    try:
        return TokenClaims(
            user_id=int(payload["sub"]),
            # Los tokens anteriores a la revocación no llevan `ver`. Se tratan
            # como generación 0, que es la que tienen las cuentas ya existentes.
            token_version=int(payload.get("ver", 0)),
            rotation=int(payload.get("rot", 0)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenError("el token no identifica a ningún usuario") from exc
