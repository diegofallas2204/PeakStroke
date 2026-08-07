"""Endpoints del módulo auth — sin lógica de negocio.

Con `auth_enabled=false` estos endpoints existen y funcionan, pero nadie está
obligado a pasar por ellos: `/me` responde el usuario de desarrollo y el resto
del API sigue accesible. Al encender el interruptor, el frontend ya tiene contra
qué hablar sin tocar el backend.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal, require_coach
from app.core.security import (
    TokenError, create_access_token, create_refresh_token, decode_token,
)
from app.modules.teams import service as teams_service

from . import service
from .models import User
from .schemas import (
    AuthConfig, DevIdentity, LoginRequest, MemberCreate, MemberCreated,
    MemberResponse, PasswordChange, SessionResponse, UserUpdate,
)

router = APIRouter()

_BAD_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Email o contraseña incorrectos",
)


async def _issue_session(db: AsyncSession, response: Response, user: User) -> SessionResponse:
    """Emite el par de tokens: access en el cuerpo, refresh en cookie httpOnly."""
    membership = await teams_service.get_membership(db, user.id)
    if membership is None or not membership.is_active:
        raise _BAD_CREDENTIALS

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=create_refresh_token(user.id),
        httponly=True,                       # invisible para cualquier JS de la página
        secure=settings.refresh_cookie_secure,
        samesite="lax",                      # corta el CSRF de terceros manteniendo la navegación normal
        max_age=settings.refresh_token_days * 24 * 3600,
        path="/api/v1/auth",                 # la cookie solo viaja a los endpoints que la necesitan
    )
    return SessionResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_minutes * 60,
        user=await service.get_member(db, user, membership),
    )


@router.post("/login", response_model=SessionResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user = await service.authenticate(db, data.email, data.password)
    if user is None:
        raise _BAD_CREDENTIALS
    return await _issue_session(db, response, user)


@router.post("/refresh", response_model=SessionResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Renueva el access token y rota el refresh (cada uso emite uno nuevo)."""
    cookie = request.cookies.get(settings.refresh_cookie_name)
    if not cookie:
        raise _BAD_CREDENTIALS
    try:
        user_id = decode_token(cookie, "refresh")
    except TokenError:
        raise _BAD_CREDENTIALS from None

    user = await service.get_user(db, user_id)
    if user is None or not user.is_active:
        raise _BAD_CREDENTIALS
    return await _issue_session(db, response, user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")


@router.get("/config", response_model=AuthConfig)
async def auth_config():
    """Le dice al frontend si hay que pedir login o se está suplantando al
    usuario de desarrollo. En producción siempre responde True."""
    return AuthConfig(auth_enabled=settings.auth_enabled)


@router.get("/dev-identities", response_model=list[DevIdentity])
async def dev_identities(db: AsyncSession = Depends(get_db)):
    """Cuentas que el conmutador de desarrollo puede suplantar.

    **404 con la autenticación encendida**, no 403: con login real esto no es un
    endpoint restringido sino un endpoint que no existe, y un 403 anunciaría que
    hay un modo de suplantación en alguna parte.

    Sin dependencia de sesión a propósito: hace falta ANTES de haber elegido
    identidad, y en el único modo en que responde el API está abierto de todas
    formas.
    """
    if not settings.dev_identity_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
    return await service.dev_identities(db, settings.dev_user_email)


@router.get("/me", response_model=MemberResponse)
async def me(
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_member(db, principal.user, principal.membership)


@router.post("/me/password", status_code=204)
async def change_password(
    data: PasswordChange,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    if not await service.authenticate(db, principal.user.email, data.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    await service.set_password(db, principal.user, data.new_password)


# --- Miembros del equipo — solo entrenadores, y solo del equipo propio ------

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
    db: AsyncSession = Depends(get_db),
):
    # El email es único en toda la instalación, no por equipo: si no, la misma
    # persona no podría distinguirse al iniciar sesión.
    if await service.get_by_email(db, data.email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese email")
    user, temporary = await service.create_member(db, data, principal.team_id)
    membership = await teams_service.get_membership(db, user.id)
    return MemberCreated(
        member=await service.get_member(db, user, membership),  # type: ignore[arg-type]
        temporary_password=temporary,
    )


@router.patch("/members/{user_id}", response_model=MemberResponse)
async def update_member(
    user_id: int,
    data: UserUpdate,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    fila = await service.member_of_team(db, user_id, principal.team_id)
    # 404 y no 403 para una cuenta de otro equipo: un 403 confirmaría que existe.
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    user, membership = fila

    # El dueño del equipo no puede quedarse sin acceso ni dejar de ser entrenador
    # por la puerta de atrás: primero hay que transferir la propiedad.
    team = await teams_service.get_team(db, principal.team_id)
    if team and team.owner_id == user.id and (data.is_active is False or data.role == "athlete"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Ese entrenador es el dueño del equipo. Transfiere la propiedad primero.",
        )

    await service.update_member(db, user, membership, data)
    return await service.get_member(db, user, membership)
