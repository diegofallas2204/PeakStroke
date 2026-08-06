"""Quién hace la petición, en qué equipo y con qué permisos.

> Con `PEAKSTROKE_AUTH_ENABLED=false` (por defecto en desarrollo) la app NO pide
> login: toda petición se atribuye al entrenador de desarrollo. `config.py`
> impide que ese modo llegue a producción.

El objeto que viaja por la aplicación es `Principal`, no `User`: el equipo y el
rol no son propiedades de la persona sino de su pertenencia al club, y **todo el
aislamiento de datos se apoya en `principal.team_id`**. Que la dependencia lo
resuelva una sola vez evita que cada endpoint tenga que acordarse de buscarlo.
"""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import TokenError, decode_token
from app.modules.auth.models import User
from app.modules.teams.models import ROLE_COACH, Team, TeamMember

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True, slots=True)
class Principal:
    """La identidad efectiva de una petición: persona + pertenencia + propiedad."""

    user: User
    membership: TeamMember
    is_owner: bool

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def team_id(self) -> int:
        return self.membership.team_id

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def is_coach(self) -> bool:
        return self.membership.role == ROLE_COACH

    @property
    def sees_every_plan(self) -> bool:
        """El dueño llega a todos los macrociclos de su equipo.

        Sin esta excepción, los planes de un entrenador que se va quedarían sin
        nadie capaz de verlos ni reasignarlos.
        """
        return self.is_owner


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _UNAUTHORIZED
    return token


async def _principal_for(db: AsyncSession, user: User) -> Principal:
    """Resuelve la pertenencia activa del usuario. Sin ella no puede operar."""
    stmt = select(TeamMember).where(
        TeamMember.user_id == user.id, TeamMember.is_active.is_(True),
    )
    membership = (await db.execute(stmt)).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta no pertenece a ningún equipo activo",
        )
    owner_stmt = select(Team.id).where(
        Team.id == membership.team_id, Team.owner_id == user.id,
    )
    is_owner = (await db.execute(owner_stmt)).scalar_one_or_none() is not None
    return Principal(user=user, membership=membership, is_owner=is_owner)


async def _dev_user(db: AsyncSession) -> User:
    """El entrenador que se suplanta cuando la autenticación está apagada."""
    from app.modules.auth import service as auth_service

    user = await auth_service.get_by_email(db, settings.dev_user_email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"No existe el usuario de desarrollo '{settings.dev_user_email}'. "
                "Créalo con: python seed.py"
            ),
        )
    return user


async def get_current_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if not settings.auth_enabled:
        return await _principal_for(db, await _dev_user(db))

    try:
        user_id = decode_token(_bearer_token(request), "access")
    except TokenError:
        raise _UNAUTHORIZED from None

    user = await db.get(User, user_id)
    # Un token válido de una cuenta ya desactivada no debe seguir abriendo puertas.
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return await _principal_for(db, user)


def require_role(*roles: str) -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Dependencia que exige uno de los roles indicados dentro del equipo."""
    async def checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        # En modo bypass no hay rol real que comprobar: el usuario de desarrollo
        # es siempre el mismo, así que exigir un rol concreto solo estorbaría.
        if not settings.auth_enabled:
            return principal
        if principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu rol no permite esta acción",
            )
        return principal

    return checker


def require_owner() -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Solo el dueño del equipo: transferir la propiedad, borrar el equipo."""
    async def checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not settings.auth_enabled:
            return principal
        if not principal.is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el dueño del equipo puede hacer esto",
            )
        return principal

    return checker


# Atajos para los guards más frecuentes.
require_coach = require_role(ROLE_COACH)
require_team_owner = require_owner()
