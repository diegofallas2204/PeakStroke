"""Miembros del equipo — solo entrenadores, y solo del equipo propio.

El alta de aquí es la de los **entrenadores**: son los únicos sin ficha
deportiva, así que su cuenta se crea sola. Un atleta se da de alta por su correo
en un gesto (`POST /link-codes/invite`), que crea ficha, cuenta y código a la vez.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import repo_de_equipos
from app.core.auditoria import TipoDeEvento, auditar
from app.core.database import get_db
from app.core.dependencies import Principal
from app.core.guards import require_coach
from app.dominio.entidades import OperacionDeEquipoImposible
from app.persistencia.repositorios import RepositorioDeEquipos
from app.persistencia.repositorios.usuarios import CredencialesCambiadas
from app.persistencia.tablas.equipos import TeamMember

from . import credenciales, service
from .schemas import MemberCreate, MemberCreated, MemberResponse, PasswordReset, UserUpdate

router = APIRouter()


@router.get("/members", response_model=list[MemberResponse])
async def list_members(
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_members(db, principal.team_id)


@router.post("/members", response_model=MemberCreated, status_code=201)
async def create_member(
    data: MemberCreate,
    principal: Principal = Depends(require_coach),
    equipos: RepositorioDeEquipos = Depends(repo_de_equipos),
    db: AsyncSession = Depends(get_db),
):
    # El email es único en toda la instalación, no por equipo: si no, la misma
    # persona no podría distinguirse al iniciar sesión.
    if await service.get_by_email(db, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese email")
    user, temporary = await service.create_member(db, data, principal.team_id)
    auditar(
        TipoDeEvento.CUENTA_CREADA, principal, objetivo=("user", user.id),
        detalle=f"{user.email} como {data.role}",
    )
    membership = await equipos.pertenencia(user.id)
    return MemberCreated(
        member=await service.get_member(db, user, membership),  # type: ignore[arg-type]
        temporary_password=temporary,
    )


@router.patch("/members/{user_id}", response_model=MemberResponse)
async def update_member(
    user_id: int,
    data: UserUpdate,
    principal: Principal = Depends(require_coach),
    equipos: RepositorioDeEquipos = Depends(repo_de_equipos),
    db: AsyncSession = Depends(get_db),
):
    fila = await service.member_of_team(db, user_id, principal.team_id)
    # 404 y no 403 para una cuenta de otro equipo: un 403 confirmaría que existe.
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    user, membership = fila

    # El dueño del equipo no puede quedarse sin acceso ni dejar de ser entrenador
    # por la puerta de atrás: primero hay que transferir la propiedad. La regla
    # es del club (`Equipo.admite_cambio`).
    team = await equipos.equipo(principal.team_id)
    if team is not None:
        try:
            equipos.como_equipo(team).admite_cambio(
                equipos.como_pertenencia(membership),
                revocar=data.is_active is False, a_atleta=data.role == "athlete",
            )
        except OperacionDeEquipoImposible as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    rol_antes, activa_antes = membership.role, membership.is_active
    await service.update_member(equipos, user, membership, data)
    _auditar_cambios(principal, user.id, user.email, rol_antes, activa_antes, membership)
    return await service.get_member(db, user, membership)


@router.post("/members/{user_id}/reset-password", response_model=PasswordReset)
async def reset_password(
    user_id: int,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """El entrenador le pone una contraseña temporal a un atleta de su club.

    Es el «olvidé mi contraseña» de la app (2026-11-13): hasta entonces solo lo
    hacía el operador del servidor (`ops.py restablecer-password`). Hace lo
    mismo que él —la temporal sale una vez, se cortan todas las sesiones y la
    cuenta queda obligada a cambiarla (TODO-27)—, con dos límites:

    - **solo sobre atletas**: restablecer la de otro entrenador sería quedarse
      con su cuenta, y la de un entrenador sigue siendo del operador;
    - **solo de su club, y con el acceso activo**: otra cuenta es 404.
    """
    fila = await service.member_of_team(db, user_id, principal.team_id)
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    user, membership = fila
    if membership.role != "athlete":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Desde la app solo se restablece la contraseña de un atleta",
        )
    if not membership.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El acceso de esta cuenta está revocado")
    temporal = secrets.token_urlsafe(12)
    try:
        await credenciales.change_password(db, user, temporal, temporal=True)
    except CredencialesCambiadas:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "La contraseña cambió mientras tanto: vuelve a intentarlo",
        ) from None
    auditar(
        TipoDeEvento.PASSWORD_RESTABLECIDA, principal, objetivo=("user", user.id),
        detalle=f"{user.email} · temporal emitida por su entrenador",
    )
    return PasswordReset(temporary_password=temporal)


def _auditar_cambios(
    principal: Principal, user_id: int, email: str,
    rol_antes: str, activa_antes: bool, membership: TeamMember,
) -> None:
    """Un evento por cada cosa que cambió de verdad; renombrar no es seguridad."""
    objetivo = ("user", user_id)
    if membership.role != rol_antes:
        auditar(
            TipoDeEvento.ROL_CAMBIADO, principal, objetivo=objetivo,
            detalle=f"{email}: {rol_antes} → {membership.role}",
        )
    if membership.is_active != activa_antes:
        tipo = TipoDeEvento.MIEMBRO_RESTAURADO if membership.is_active             else TipoDeEvento.MIEMBRO_REVOCADO
        auditar(tipo, principal, objetivo=objetivo, detalle=email)
