"""Lo que la identidad decide, y cómo se pinta hacia fuera.

Las consultas de la cuenta están en `persistencia/repositorios/usuarios.py` y
las de la pertenencia en `equipos.py`. Aquí queda lo que **compone**: crear una
cuenta con su pertenencia toca dos agregados, y la ficha de sesión que ve el
usuario junta cuatro tablas.

`normalize_email` ya no vive aquí: es una regla de almacenamiento y se mudó a
`persistencia/repositorios/usuarios.normalizar_correo`, que es de donde la lee
también `link_codes` — antes la importaba de este archivo, y era la última
lógica cruzada entre rebanadas del API.
"""
from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.persistencia.repositorios import RepositorioDeEquipos, RepositorioDeUsuarios
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import User

from .schemas import (
    DevIdentity,
    MemberCreate,
    MemberResponse,
    UserCreate,
    UserUpdate,
)


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    return await RepositorioDeUsuarios(db).por_id(user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await RepositorioDeUsuarios(db).por_correo(email)


async def create_user(db: AsyncSession, data: UserCreate, team_id: int) -> User:
    """Crea la cuenta y su pertenencia al equipo, que es lo que le da el rol.

    Van juntas a propósito: un usuario sin pertenencia no puede hacer nada en la
    aplicación, así que crearlo suelto solo produciría cuentas rotas. Son dos
    agregados, así que la composición vive aquí y no dentro de un repositorio:
    ninguno de los dos manda sobre el otro.
    """
    user = await RepositorioDeUsuarios(db).crear(
        correo=data.email, nombre=data.name,
        password_hash=hash_password(data.password),
    )
    # `flush` ya dio el id; la pertenencia lo necesita para ligarse.
    db.add(TeamMember(team_id=team_id, user_id=user.id, role=data.role))
    await db.commit()
    await db.refresh(user)
    return user


# --- Miembros del equipo (sección Perfil) -----------------------------------

def to_member(
    user: User, membership: TeamMember | None, swimmer: Swimmer | None,
    *, team: Team | None = None,
) -> MemberResponse:
    """La ficha de sesión de una cuenta.

    `membership` puede faltar: es la cuenta que existe en el sistema pero aún no
    está en ningún club — recién registrada, o esperando a que un entrenador la
    invite. Sin pertenencia no hay rol ni equipo, y decirlo con `None` es más
    honesto que inventarse un "athlete" que no significa nada todavía.
    """
    return MemberResponse(
        id=user.id, email=user.email, name=user.name,
        role=membership.role if membership else None,
        # Activo = cuenta activa Y pertenencia activa. Revocar el acceso a un
        # equipo no desactiva la cuenta, pero deja al miembro fuera igualmente.
        # Sin pertenencia manda la cuenta: no hay acceso que revocar.
        is_active=user.is_active and (membership.is_active if membership else True),
        created_at=user.created_at, last_login_at=user.last_login_at,
        team_id=membership.team_id if membership else None,
        team_name=team.name if team else None,
        is_owner=bool(team and team.owner_id == user.id),
        swimmer_id=swimmer.id if swimmer else None,
        swimmer_name=swimmer.name if swimmer else None,
    )


async def _swimmer_by_user(db: AsyncSession, team_id: int) -> dict[int, Swimmer]:
    """user_id → ficha, para las cuentas del equipo que tengan una.

    Lee la tabla directamente y no pasa por `RepositorioDeAtletas`, que exige un
    `Principal`: aquí se está **construyendo** la ficha de sesión, y el
    conmutador de identidades ni siquiera tiene una. Es una lectura hacia abajo,
    no un import cruzado.
    """
    stmt = select(Swimmer).where(Swimmer.user_id.is_not(None), Swimmer.team_id == team_id)
    return {s.user_id: s for s in (await db.execute(stmt)).scalars() if s.user_id}


async def list_members(db: AsyncSession, team_id: int) -> list[MemberResponse]:
    team = await RepositorioDeEquipos(db).equipo(team_id)
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
    dev_user = await RepositorioDeUsuarios(db).por_correo(dev_email)
    if dev_user is None:
        return []
    equipos = RepositorioDeEquipos(db)
    membership = await equipos.pertenencia(dev_user.id)
    if membership is None:
        return []

    team = await equipos.equipo(membership.team_id)
    by_user = await _swimmer_by_user(db, membership.team_id)
    stmt = (
        select(User, TeamMember)
        .join(TeamMember, TeamMember.user_id == User.id)
        # Solo las que se pueden suplantar de verdad: `dev_identity.dev_user`
        # rechaza las cuentas inactivas, así que ofrecerlas sería un botón roto.
        .where(
            TeamMember.team_id == membership.team_id,
            TeamMember.is_active.is_(True),
            User.is_active.is_(True),
        )
        .order_by(TeamMember.role, User.name)
    )
    filas = (await db.execute(stmt)).all()
    identidades = [
        DevIdentity(
            email=u.email, name=u.name, role=m.role,
            is_owner=bool(team and team.owner_id == u.id),
            swimmer_name=s.name if (s := by_user.get(u.id)) else None,
        )
        for u, m in filas
    ]

    # Las cuentas del **pool**: existen y no están en ningún club. Sin ellas en
    # el conmutador, el estado de quien espera invitación —la pantalla que solo
    # tiene perfil y solicitudes— no se puede mirar sin crear datos a mano, que
    # es el motivo por el que ese estado no existía y nadie lo echaba de menos.
    sin_club = (await db.execute(
        select(User)
        .outerjoin(TeamMember, TeamMember.user_id == User.id)
        .where(TeamMember.id.is_(None), User.is_active.is_(True))
        .order_by(User.name)
    )).scalars().all()
    identidades.extend(
        DevIdentity(email=u.email, name=u.name, role=None) for u in sin_club
    )
    return identidades


async def get_member(
    db: AsyncSession, user: User, membership: TeamMember | None,
) -> MemberResponse:
    team = await RepositorioDeEquipos(db).equipo(membership.team_id) if membership else None
    stmt = select(Swimmer).where(Swimmer.user_id == user.id)
    swimmer = (await db.execute(stmt)).scalar_one_or_none()
    return to_member(user, membership, swimmer, team=team)


async def session_for(db: AsyncSession, user: User) -> MemberResponse | None:
    """Quién es quien llama, tenga club o no. **None si se lo revocaron.**

    `/auth/me` pasa por aquí y no por `get_current_principal` a propósito: una
    cuenta sin pertenencia es un estado legítimo del sistema —el atleta que se
    registró y espera invitación— y responderle 403 la dejaría sin poder ni ver
    la pantalla donde canjea el código que la sacaría de ahí.

    Es la única concesión: `/me` no toca ningún dato de equipo. Todo lo demás
    sigue exigiendo `Principal`, porque sin `team_id` no hay frontera que aplicar.

    La consulta trae **también las pertenencias inactivas** para poder separar
    tres estados que se parecen y significan cosas distintas: sin club (entra y
    ve sus solicitudes), en un club (entra normal) y revocado (no entra). Filtrar
    por `is_active` aquí fundiría el tercero con el primero, y quien perdió el
    acceso reaparecería como cuenta del pool.
    """
    membership = await RepositorioDeEquipos(db).pertenencia(
        user.id, incluir_inactivas=True,
    )
    if membership is not None and not membership.is_active:
        return None
    return await get_member(db, user, membership)


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
    equipos: RepositorioDeEquipos, user: User, membership: TeamMember, data: UserUpdate,
) -> None:
    """El nombre vive en la cuenta; el rol y el acceso, en la `Pertenencia`.

    Revocar y restaurar son de la entidad (§5.2, 2026-10-14). **Un `null`
    explícito no cambia nada**: ninguno de los tres puede quedar vacío, y hasta
    el 2026-10-14 `{"name": null}` llegaba a una columna `NOT NULL` y salía como
    un 500. Va en un solo commit: `guardar_pertenencia` confirma también el nombre.

    **Revocar corta las sesiones** de esa cuenta en ese mismo commit (D1,
    decidido el 2026-10-14): antes, el access token emitido antes seguía
    valiendo 15 minutos, y con él `/link-codes/redeem`. Solo si la revocación
    cambió algo: revocar a quien ya lo estaba no vuelve a echarlo de ningún
    sitio. Restaurar no corta nada. Lo usan el API y el CLI (`tools/ops`).
    """
    campos = data.model_dump(exclude_unset=True)
    pertenencia = equipos.como_pertenencia(membership)
    if campos.get("role") is not None:
        pertenencia.cambiar_rol(campos["role"])
    if campos.get("is_active") is True:
        pertenencia.restaurar()
    elif campos.get("is_active") is False and pertenencia.revocar():
        usuarios = RepositorioDeUsuarios(equipos.db)
        usuario = usuarios.entidad(user)
        usuario.revocar_sesiones()
        await usuarios.anotar(usuario)
    if campos.get("name") is not None:
        user.name = campos["name"]
    await equipos.guardar_pertenencia(pertenencia)


async def create_member(
    db: AsyncSession, data: MemberCreate, team_id: int,
) -> tuple[User, str | None]:
    """Crea la cuenta. Devuelve (usuario, contraseña temporal).

    La contraseña temporal solo viene rellena si la generamos aquí: una vez
    guardado el hash no hay forma de recuperarla.

    **No liga ninguna ficha.** Crear el acceso y decir de quién es son dos
    gestos distintos desde el 2026-08-09, y el segundo lo cierra el código de
    vinculación (`api/v1/codigos/`). Ver `MemberCreate`.
    """
    generated = data.password is None
    password = data.password or secrets.token_urlsafe(9)

    user = await create_user(db, UserCreate(
        email=data.email, name=data.name, password=password, role=data.role,
    ), team_id)
    return user, (password if generated else None)
