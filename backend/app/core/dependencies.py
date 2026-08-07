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

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import TokenError, decode_token
from app.modules.auth.models import User
from app.modules.swimmers.models import Swimmer
from app.modules.teams.models import ROLE_ATHLETE, ROLE_COACH, Team, TeamMember

logger = logging.getLogger(__name__)

# Cabecera del conmutador de identidad de desarrollo. Su nombre vive aquí para
# que el endpoint que lista las identidades y los tests no lo escriban a mano.
DEV_USER_HEADER = "X-PeakStroke-Dev-User"

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True, slots=True)
class Principal:
    """La identidad efectiva de una petición: persona + pertenencia + propiedad.

    Dos fronteras cuelgan de aquí, y hasta el 2026-08-06 solo existía la primera:

        Principal { user, membership, is_owner, swimmer_id }
                     │         │          │          │
                     │         └─ team_id ──▶ el CLUB
                     │
                     └─ swimmer_id ──────────▶ el ATLETA

    Sin `swimmer_id`, ningún servicio *podía* filtrar por nadador aunque
    quisiera, y por eso un atleta leía y escribía los datos de sus compañeros.
    """

    user: User
    membership: TeamMember
    is_owner: bool
    # El nadador al que va ligada esta cuenta, si va ligada a alguno. None en un
    # entrenador (normal) y también en un atleta al que nadie le creó la ficha
    # (anomalía de datos, y por eso el filtro de abajo falla cerrado).
    swimmer_id: int | None = None

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
    def is_athlete(self) -> bool:
        return self.membership.role == ROLE_ATHLETE

    @property
    def sees_every_plan(self) -> bool:
        """El dueño llega a todos los macrociclos de su equipo.

        Sin esta excepción, los planes de un entrenador que se va quedarían sin
        nadie capaz de verlos ni reasignarlos.
        """
        return self.is_owner

    def scope_to_own_swimmer(self, stmt, column):
        """Acota una consulta al nadador propio **si quien pregunta es atleta**.

        Un entrenador pasa sin tocar: ver a todo su equipo es su trabajo.

        El caso que importa es el segundo. Un atleta sin nadador ligado no ve
        NADA, no lo ve todo: la consulta se vuelve imposible en vez de quedarse
        sin filtro. Es la diferencia entre que un dato mal ligado no enseñe
        nada y que filtre el club entero, y el modo de fallo hay que elegirlo
        antes de que ocurra, no después.

        `column` es la columna con el `swimmer_id` en el `stmt` que se le pasa,
        porque no todas las tablas lo llaman igual ni lo tienen a la misma
        distancia (`Swimmer.id`, `AerobicTest.swimmer_id`, `AthletePlan.swimmer_id`).
        """
        if not self.is_athlete:
            return stmt
        if self.swimmer_id is None:
            return stmt.where(false())
        return stmt.where(column == self.swimmer_id)

    def owns_swimmer(self, swimmer_id: int) -> bool:
        """Si esta identidad puede actuar sobre ese nadador.

        Para las escrituras cuyo destinatario llega en el CUERPO de la petición
        y no en la URL — crear un test aeróbico a nombre de alguien — donde no
        hay consulta que acotar y hace falta preguntarlo directamente.
        """
        if not self.is_athlete:
            return True
        return self.swimmer_id is not None and self.swimmer_id == swimmer_id


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _UNAUTHORIZED
    return token


async def _principal_for(db: AsyncSession, user: User) -> Principal:
    """Resuelve la pertenencia activa del usuario. Sin ella no puede operar.

    El nadador sale del mismo `select` que la pertenencia, con un `outerjoin`:
    es un dato que se necesita en cada petición y no merece una consulta propia.
    La condición del join lleva `team_id` además de `user_id` porque la clave
    candidata de `team_members` es la pareja, no el usuario suelto.

    A propósito **no** filtra por `Swimmer.is_active`: dar de baja a un nadador
    archiva su ficha deportiva, no revoca el acceso de su cuenta — eso es
    `team_members.is_active`, y ese sí se comprueba tres líneas más arriba.
    Confundirlos dejaría a un atleta dado de baja sin poder ni consultar su
    propio histórico.
    """
    stmt = (
        select(TeamMember, Swimmer.id)
        .outerjoin(
            Swimmer,
            (Swimmer.user_id == TeamMember.user_id)
            & (Swimmer.team_id == TeamMember.team_id),
        )
        .where(TeamMember.user_id == user.id, TeamMember.is_active.is_(True))
    )
    fila = (await db.execute(stmt)).first()
    if fila is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta no pertenece a ningún equipo activo",
        )
    membership, swimmer_id = fila
    owner_stmt = select(Team.id).where(
        Team.id == membership.team_id, Team.owner_id == user.id,
    )
    is_owner = (await db.execute(owner_stmt)).scalar_one_or_none() is not None
    return Principal(
        user=user, membership=membership, is_owner=is_owner, swimmer_id=swimmer_id,
    )


async def _dev_user(db: AsyncSession, request: Request) -> User:
    """La cuenta que se suplanta cuando la autenticación está apagada.

    Por defecto, el entrenador de desarrollo. La cabecera `X-PeakStroke-Dev-User`
    permite cambiarla en caliente para ver la aplicación con los ojos de otro
    rol sin reiniciar el proceso ni tocar `.env`.

    **Solo se lee si `settings.dev_identity_enabled`** (ver allí el porqué de
    sus dos condiciones). Con el login encendido esta función ni siquiera se
    llama, así que la cabecera es papel mojado — y `test_dev_identity.py` lo
    fija con un test, porque romper esa línea abriría suplantación arbitraria
    sin que se note leyendo el diff.

    Un email inexistente o una cuenta inactiva **caen al usuario por defecto**
    con un aviso en el log. Devolver 500 convertiría una errata en la barra de
    desarrollo en una aplicación caída.
    """
    from app.modules.auth import service as auth_service

    if settings.dev_identity_enabled:
        pedido = request.headers.get(DEV_USER_HEADER)
        if pedido:
            user = await auth_service.get_by_email(db, pedido)
            if user is not None and user.is_active:
                return user
            logger.warning(
                "%s: '%s' no existe o está inactivo. Se sigue con %s.",
                DEV_USER_HEADER, pedido, settings.dev_user_email,
            )

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
        return await _principal_for(db, await _dev_user(db, request))

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
