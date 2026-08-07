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
from dataclasses import dataclass, replace
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

# Cabeceras del conmutador de desarrollo. Sus nombres viven aquí para que el
# endpoint que las anuncia, el CORS y los tests no los escriban a mano.
#
# Son dos ejes distintos y esa separación es el punto:
#
#   X-PeakStroke-Dev-User    ──▶  QUIÉN eres.  La interfaz que ves es la de ese
#                                 rol, fielmente: un atleta recibe 403 donde un
#                                 atleta recibe 403. Sin eso no se puede revisar
#                                 la UI de atleta, porque todo respondería 200.
#
#   X-PeakStroke-Dev-Bypass  ──▶  Si además puedes SALTARTE los guards de rol.
#                                 Levanta lo que puedes hacer, no lo que ves: el
#                                 filtro por nadador sigue puesto, así que sigues
#                                 mirando la aplicación con los ojos de esa
#                                 persona mientras te desatascas.
#
# Juntarlas en una sola sería perder justo lo que hace útil al conmutador.
DEV_USER_HEADER = "X-PeakStroke-Dev-User"
DEV_BYPASS_HEADER = "X-PeakStroke-Dev-Bypass"

# Solo ASCII: una cabecera HTTP no puede llevar tildes, así que "sí" nunca
# llegaría hasta aquí aunque lo aceptáramos.
_VERDADERO = {"1", "true", "yes", "on", "si"}

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
    # Modo desarrollador: los guards de rol dejan pasar. Es un tercer eje,
    # ortogonal al rol, y **nunca sale de la base de datos**: ni de una columna,
    # ni de un campo del usuario, ni del cuerpo de la petición. Solo de una
    # cabecera, y solo cuando `settings.dev_identity_enabled`. Que no exista
    # ninguna forma de persistirlo es lo que garantiza que no pueda llegar a
    # producción por un dato mal puesto.
    is_developer: bool = False

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

    Un email inexistente o una cuenta inactiva (`users.is_active`) **caen al
    usuario por defecto** con un aviso en el log. Devolver 500 convertiría una
    errata en la barra de desarrollo en una aplicación caída.

    Ojo con el caso que **no** cubre ese fallback: la pertenencia revocada
    (`team_members.is_active`) se comprueba después, en `_principal_for`, así
    que suplantar a alguien con el acceso al equipo revocado da 403 y no cae al
    usuario por defecto. Es correcto —esa cuenta no puede operar— pero el
    conmutador del frontend debería no ofrecerla, y por eso
    `service.dev_identities` filtra las dos banderas.
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


def bypass_pedido(request: Request) -> bool:
    """Si esta petición pide modo desarrollador, y si tiene derecho a pedirlo.

    Misma puerta que la cabecera de identidad, a propósito: son la misma
    facilidad de desarrollo y deben apagarse juntas. Con el login encendido —o
    en producción— la cabecera es texto que nadie lee.
    """
    if not settings.dev_identity_enabled:
        return False
    return (request.headers.get(DEV_BYPASS_HEADER) or "").strip().lower() in _VERDADERO


async def get_current_principal(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Principal:
    if not settings.auth_enabled:
        principal = await _principal_for(db, await _dev_user(db, request))
        if bypass_pedido(request):
            principal = replace(principal, is_developer=True)
        return principal

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
    return await _principal_for(db, user)


def require_role(*roles: str) -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Dependencia que exige uno de los roles indicados dentro del equipo.

    **Comprueba el rol siempre, también con el login apagado.** Hasta el
    2026-08-06 había aquí un atajo que devolvía el principal sin mirar nada si
    `auth_enabled=false`, justificado en que "el usuario de desarrollo es
    siempre el mismo, así que exigir un rol concreto solo estorbaría".

    Esa premisa murió el mismo día en que se añadió `X-PeakStroke-Dev-User`. Con
    el conmutador de identidad hay un rol real —el de la cuenta suplantada— y el
    atajo pasó a ser un agujero: un atleta llamaba
    `PATCH /auth/members/{su_id} {"role":"coach"}`, se ascendía, y con eso
    desactivaba TODO el filtro por nadador, que solo actúa sobre atletas.

    403 y no 404 a propósito: aquí el recurso no es ajeno, es el rol el que no
    alcanza. Decirlo claro no filtra nada que quien pregunta no sepa ya.

    La única excepción es el modo desarrollador (`X-PeakStroke-Dev-Bypass`), que
    no puede existir con el login encendido. Ver `bypass_pedido`.
    """
    async def checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in roles:
            exigir_o_bypass(principal, f"rol {'/'.join(roles)}")
        return principal

    return checker


def require_owner() -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Solo el dueño del equipo: renombrarlo, transferir la propiedad.

    Mismo motivo que `require_role` para comprobar siempre: con el conmutador de
    identidad, un entrenador asistente puede suplantarse y la diferencia entre
    dueño y asistente es justo lo que la Fase 4 del plan quiere poder ver.
    """
    async def checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.is_owner:
            exigir_o_bypass(principal, "dueño del equipo")
        return principal

    return checker


def exigir_o_bypass(principal: Principal, exigido: str) -> None:
    """Lanza 403, salvo que quien pregunta esté en modo desarrollador.

    El aviso en el log no es decorativo: el modo desarrollador existe para
    desatascarse mientras se depura, y una traza que diga qué guard se saltó y
    con qué identidad es la diferencia entre *usarlo* y *olvidar que está
    puesto*. Si aparece en un log que no sea tu portátil, algo va muy mal —
    `dev_identity_enabled` tendría que haberlo hecho imposible.
    """
    if principal.is_developer:
        logger.warning(
            "MODO DESARROLLADOR: %s (%s) se salta el guard de %s",
            principal.user.email, principal.role, exigido,
        )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Tu rol no permite esta acción (se requiere: {exigido})",
    )


# Atajos para los guards más frecuentes.
require_coach = require_role(ROLE_COACH)
require_team_owner = require_owner()
