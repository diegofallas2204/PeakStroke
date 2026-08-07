"""Lógica de negocio del módulo auth."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, needs_rehash, verify_password
# Lecturas explícitas de modelos de otros módulos (permitido por las reglas del
# proyecto): la sección Perfil necesita el rol —que vive en la pertenencia— y a
# qué nadador va ligada cada cuenta. No se importa lógica ajena.
from app.modules.swimmers.models import Swimmer
from app.modules.teams.models import Team, TeamMember

from .models import User
from .schemas import (
    DevIdentity, MemberCreate, MemberResponse, UserCreate, UserUpdate,
)


def normalize_email(email: str) -> str:
    """Los emails se guardan y se buscan siempre en minúsculas y sin espacios."""
    return email.strip().lower()


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == normalize_email(email))
    return (await db.execute(stmt)).scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate, team_id: int) -> User:
    """Crea la cuenta y su pertenencia al equipo, que es lo que le da el rol.

    Van juntas a propósito: un usuario sin pertenencia no puede hacer nada en la
    aplicación, así que crearlo suelto solo produciría cuentas rotas.
    """
    user = User(
        email=normalize_email(data.email),
        name=data.name,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    await db.flush()          # necesitamos el id antes de ligar la pertenencia
    db.add(TeamMember(team_id=team_id, user_id=user.id, role=data.role))
    await db.commit()
    await db.refresh(user)
    return user


async def revoke_sessions(db: AsyncSession, user: User) -> None:
    """Invalida todos los tokens ya emitidos para esa cuenta.

    Sube la generación de sesiones. Cualquier access o refresh que lleve la
    anterior deja de validar en la siguiente petición — no en 15 minutos ni en
    30 días, en la siguiente.

    Es lo que convierte `logout` en algo más que borrar una cookie del
    navegador. Un refresh token capturado sobrevivía a "cerrar sesión" y servía
    para emitir access tokens nuevos durante un mes.
    """
    user.token_version += 1
    await db.commit()


async def set_password(db: AsyncSession, user: User, new_password: str) -> User:
    user.password_hash = hash_password(new_password)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    """Devuelve el usuario si las credenciales son válidas, None si no.

    Un único None para "no existe", "contraseña incorrecta" y "cuenta
    desactivada": distinguirlos en la respuesta permitiría enumerar qué emails
    están registrados.
    """
    user = await get_by_email(db, email)
    if user is None:
        # Hash de descarte para que la respuesta tarde lo mismo exista o no el
        # usuario. Sin esto, el tiempo de respuesta delata qué emails son reales.
        hash_password(password)
        return None
    if not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    return user


# --- Miembros del equipo (sección Perfil) -----------------------------------

def to_member(
    user: User, membership: TeamMember, swimmer: Swimmer | None,
    *, team: Team | None = None,
) -> MemberResponse:
    return MemberResponse(
        id=user.id, email=user.email, name=user.name,
        role=membership.role,
        # Activo = cuenta activa Y pertenencia activa. Revocar el acceso a un
        # equipo no desactiva la cuenta, pero deja al miembro fuera igualmente.
        is_active=user.is_active and membership.is_active,
        created_at=user.created_at, last_login_at=user.last_login_at,
        team_id=membership.team_id,
        team_name=team.name if team else None,
        is_owner=bool(team and team.owner_id == user.id),
        swimmer_id=swimmer.id if swimmer else None,
        swimmer_name=swimmer.name if swimmer else None,
    )


async def _swimmer_by_user(db: AsyncSession, team_id: int) -> dict[int, Swimmer]:
    stmt = select(Swimmer).where(Swimmer.user_id.is_not(None), Swimmer.team_id == team_id)
    return {s.user_id: s for s in (await db.execute(stmt)).scalars() if s.user_id}


async def list_members(db: AsyncSession, team_id: int) -> list[MemberResponse]:
    team = await db.get(Team, team_id)
    by_user = await _swimmer_by_user(db, team_id)
    stmt = (
        select(User, TeamMember)
        .join(TeamMember, TeamMember.user_id == User.id)
        .where(TeamMember.team_id == team_id)
        .order_by(User.name)
    )
    filas = (await db.execute(stmt)).all()
    return [to_member(u, m, by_user.get(u.id), team=team) for u, m in filas]


async def dev_identities(db: AsyncSession, dev_email: str) -> list[DevIdentity]:
    """Cuentas activas del equipo del usuario de desarrollo, para el conmutador.

    Existe para que el frontend no lleve emails a fuego: la lista sale de la DB
    que se esté usando, así que un `seed.py` distinto o una cuenta añadida a mano
    aparecen solas.

    Si el usuario de desarrollo no existe todavía (base recién creada, sin
    sembrar) devuelve lista vacía en vez de reventar: el conmutador se dibuja
    vacío y la aplicación sigue funcionando.
    """
    dev_user = await get_by_email(db, dev_email)
    if dev_user is None:
        return []
    membership = (await db.execute(
        select(TeamMember).where(
            TeamMember.user_id == dev_user.id, TeamMember.is_active.is_(True),
        )
    )).scalar_one_or_none()
    if membership is None:
        return []

    team = await db.get(Team, membership.team_id)
    by_user = await _swimmer_by_user(db, membership.team_id)
    stmt = (
        select(User, TeamMember)
        .join(TeamMember, TeamMember.user_id == User.id)
        # Solo las que se pueden suplantar de verdad: `_dev_user` rechaza las
        # cuentas inactivas, así que ofrecerlas sería ofrecer un botón roto.
        .where(
            TeamMember.team_id == membership.team_id,
            TeamMember.is_active.is_(True),
            User.is_active.is_(True),
        )
        .order_by(TeamMember.role, User.name)
    )
    filas = (await db.execute(stmt)).all()
    return [
        DevIdentity(
            email=u.email, name=u.name, role=m.role,
            is_owner=bool(team and team.owner_id == u.id),
            swimmer_name=s.name if (s := by_user.get(u.id)) else None,
        )
        for u, m in filas
    ]


async def get_member(db: AsyncSession, user: User, membership: TeamMember) -> MemberResponse:
    team = await db.get(Team, membership.team_id)
    stmt = select(Swimmer).where(Swimmer.user_id == user.id)
    swimmer = (await db.execute(stmt)).scalar_one_or_none()
    return to_member(user, membership, swimmer, team=team)


async def member_of_team(
    db: AsyncSession, user_id: int, team_id: int,
) -> tuple[User, TeamMember] | None:
    """Usuario + pertenencia, solo si es de ESE equipo. None si no lo es."""
    stmt = (
        select(User, TeamMember)
        .join(TeamMember, TeamMember.user_id == User.id)
        .where(User.id == user_id, TeamMember.team_id == team_id)
    )
    return (await db.execute(stmt)).first()


async def update_member(
    db: AsyncSession, user: User, membership: TeamMember, data: UserUpdate,
) -> None:
    """El nombre vive en la cuenta; el rol y el acceso, en la pertenencia."""
    campos = data.model_dump(exclude_unset=True)
    if "name" in campos:
        user.name = campos["name"]
    if "role" in campos:
        membership.role = campos["role"]
    if "is_active" in campos:
        membership.is_active = campos["is_active"]
    await db.commit()


async def create_member(
    db: AsyncSession, data: MemberCreate, team_id: int,
) -> tuple[User, str | None]:
    """Crea la cuenta y la liga a un nadador. Devuelve (usuario, contraseña temporal).

    La contraseña temporal solo viene rellena si la generamos aquí: una vez
    guardado el hash no hay forma de recuperarla.
    """
    generated = data.password is None
    password = data.password or secrets.token_urlsafe(9)

    user = await create_user(db, UserCreate(
        email=data.email, name=data.name, password=password, role=data.role,
    ), team_id)

    if data.swimmer_id is not None:
        swimmer = await db.get(Swimmer, data.swimmer_id)
        # La FK compuesta ya impide ligar un nadador de otro equipo; comprobarlo
        # aquí convierte un error de integridad en un "no encontrado" limpio.
        if swimmer is not None and swimmer.team_id == team_id:
            swimmer.user_id = user.id
            await db.commit()
    return user, (password if generated else None)
