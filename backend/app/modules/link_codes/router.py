"""Endpoints del módulo link_codes — sin lógica de negocio.

Los cuatro primeros son del entrenador y viven detrás de `require_coach`. Los
dos últimos son del lado del invitado y usan `get_current_user` en vez de
`get_current_principal`: quien los llama puede no ser todavía de ningún equipo,
y exigírselo dejaría fuera justo al caso que el código existe para resolver.

**Son los únicos dos del API que pueden usar esa dependencia** —junto a
`/auth/me`, que solo dice quién eres—. Cualquier otro endpoint sin `Principal`
es un error: sin él no hay `team_id` y sin `team_id` no hay frontera que aplicar.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import Principal, get_current_user, require_coach
from app.modules.auth.models import User

from . import service
from .models import LinkCode
from .schemas import (
    InviteRequest, InviteResponse, JoinRequestResponse, LinkCodeCreate,
    LinkCodeResponse, RedeemRequest, RedeemResponse,
)

router = APIRouter()


def _to_response(code: LinkCode, swimmer_name: str) -> LinkCodeResponse:
    return LinkCodeResponse(
        id=code.id, swimmer_id=code.swimmer_id, swimmer_name=swimmer_name,
        invited_email=code.invited_email,
        code=service.format_code(code.code), expires_at=code.expires_at,
        created_at=code.created_at,
    )


@router.get("/", response_model=list[LinkCodeResponse])
async def list_codes(
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Los códigos vivos del equipo, para reenviar el que se perdió."""
    codes = await service.active_for_team(db, principal.team_id)
    nombres = await service.swimmer_names(db, principal.team_id)
    return [_to_response(c, nombres.get(c.swimmer_id, "—")) for c in codes]


@router.post("/", response_model=LinkCodeResponse, status_code=201)
async def create_code(
    data: LinkCodeCreate,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    swimmer = await service.swimmer_of_team(db, data.swimmer_id, principal.team_id)
    # 404 y no 403 para una ficha de otro equipo: un 403 confirmaría que existe.
    if swimmer is None:
        raise HTTPException(404, "Atleta no encontrado")
    try:
        code = await service.issue(db, swimmer, principal.id)
    except service.LinkCodeError as e:
        raise HTTPException(e.status, str(e)) from None
    return _to_response(code, swimmer.name)


@router.post("/invite", response_model=InviteResponse, status_code=201)
async def invite(
    data: InviteRequest,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    """Da de alta a un atleta en el equipo por su correo, en un solo gesto.

    Crea la ficha deportiva, la cuenta si esa persona todavía no tenía, y el
    código dirigido a ese correo. **Lo que NO crea es la pertenencia al club**:
    eso lo hace el canje, y por eso hasta entonces el atleta no le aparece a
    nadie como miembro. Ver `service.invite`.

    El equipo sale de la sesión, como siempre; el cuerpo solo trae la persona.

    La comprobación va **antes** de crear la ficha: al revés, invitar a alguien
    que ya está en otro club dejaría una ficha huérfana en este.
    """
    try:
        await service.check_invitable(db, data.email, principal.team_id)
        swimmer, code, temporal = await service.invite(
            db, data, principal.team_id, principal.id,
        )
    except service.LinkCodeError as e:
        raise HTTPException(e.status, str(e)) from None
    return InviteResponse(
        link_code=_to_response(code, swimmer.name),
        account_created=temporal is not None,
        temporary_password=temporal,
    )


@router.delete("/{code_id}", status_code=204)
async def revoke_code(
    code_id: int,
    principal: Principal = Depends(require_coach),
    db: AsyncSession = Depends(get_db),
):
    code = await db.get(LinkCode, code_id)
    if code is None or code.team_id != principal.team_id:
        raise HTTPException(404, "Código no encontrado")
    await service.revoke(db, code)


@router.get("/mine", response_model=list[JoinRequestResponse])
async def my_join_requests(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mis solicitudes de ingreso pendientes. Ver la cabecera del módulo.

    **Sin el código.** Enseñárselo aquí a quien ya está autenticado con ese
    correo dejaría el canje en un botón, y el código existe justo para que haya
    un segundo factor que el entrenador entrega en persona.
    """
    return [
        JoinRequestResponse(
            team_name=nombres.team, swimmer_name=nombres.swimmer,
            invited_by=nombres.coach,
            expires_at=code.expires_at, created_at=code.created_at,
        )
        for code, nombres in await service.describe_pending(db, user)
    ]


@router.post("/redeem", response_model=RedeemResponse)
async def redeem(
    data: RedeemRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Canjea el código y liga la cuenta de quien llama a la ficha.

    `get_current_user` y no `get_current_principal`: ver la cabecera del módulo.
    """
    try:
        swimmer, team = await service.redeem(db, data.code, user)
    except service.LinkCodeError as e:
        raise HTTPException(e.status, str(e)) from None
    return RedeemResponse(
        swimmer_id=swimmer.id, swimmer_name=swimmer.name,
        team_id=team.id, team_name=team.name,
    )
