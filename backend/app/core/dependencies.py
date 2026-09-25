"""Quién hace la petición y en qué equipo.

> Con `PEAKSTROKE_AUTH_ENABLED=false` (por defecto en desarrollo) la app NO pide
> login: toda petición se atribuye al entrenador de desarrollo. `config.py`
> impide que ese modo llegue a producción.

El objeto que viaja por la aplicación es `Principal`, no `User`: el equipo y el
rol no son propiedades de la persona sino de su pertenencia al club, y **todo el
aislamiento de datos se apoya en `principal.team_id`**. Que la dependencia lo
resuelva una sola vez evita que cada endpoint tenga que acordarse de buscarlo.

El resto de la identidad está repartido en tres archivos: qué **es** un
`Principal` (`principal.py`), qué se le **exige** para pasar (`guards.py`) y cómo
se **suplanta** en desarrollo (`dev_identity.py`). Aquí está solo la resolución.
"""
from __future__ import annotations

from dataclasses import replace

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dev_identity import bypass_pedido, dev_user
from app.core.principal import Principal
from app.core.security import TokenError, decode_token
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import User

__all__ = [
    "Principal",
    "bypass_pedido",
    "get_current_principal",
    "get_current_user",
]

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)


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

    **`one_or_none()`, no `.first()`** (R5, aplicada el 2026-09-24). Hoy la
    `UNIQUE` de `team_members.user_id` hace imposible una segunda pertenencia,
    pero el día que se quite —"un cambio de una línea"— `.first()` sin
    `ORDER BY` atendería la petición en un club cualquiera **sin fallar**, y el
    `team_id` es la frontera de todo el aislamiento. Así esa fuga silenciosa se
    convierte en un error inmediato (`MultipleResultsFound`, un 500).
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
    fila = (await db.execute(stmt)).one_or_none()
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


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Quién llama, **sin exigirle pertenencia a ningún equipo**.

    Es deliberadamente más débil que `get_current_principal` y por eso casi
    ningún endpoint debería usarla: sin `Principal` no hay `team_id`, y sin
    `team_id` no hay frontera que aplicar. Existe para el único caso en que
    pedir pertenencia sería absurdo — canjear un código de vinculación, que es
    justo lo que la crea (`api/v1/codigos/router.py`).

    Antes de usarla en un endpoint nuevo, la pregunta es: ¿qué datos de equipo
    toca? Si la respuesta no es "ninguno", la dependencia correcta es la otra.
    """
    if not settings.auth_enabled:
        return await dev_user(db, request)

    try:
        claims = decode_token(_bearer_token(request), "access")
    except TokenError:
        raise _UNAUTHORIZED from None

    user = await db.get(User, claims.user_id)
    # Un token válido de una cuenta ya desactivada no debe seguir abriendo puertas.
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    # Ni uno emitido antes de que el usuario cerrara sesión. La comprobación es
    # gratis: el usuario ya está cargado. Sin ella, `logout` tardaría hasta 15
    # minutos en surtir efecto sobre el access token que el atacante ya tiene.
    if user.token_version != claims.token_version:
        raise _UNAUTHORIZED
    return user


async def get_current_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Principal:
    principal = await _principal_for(db, await get_current_user(request, db))
    # `bypass_pedido` ya exige `dev_identity_enabled`, que a su vez exige el
    # login apagado: con autenticación real la cabecera no la lee nadie.
    if bypass_pedido(request):
        principal = replace(principal, is_developer=True)
    return principal
