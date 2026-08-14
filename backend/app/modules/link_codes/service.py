"""Lógica de negocio del módulo link_codes.

Dos operaciones y una regla cada una:

    emitir  ──▶  solo el entrenador, solo sobre una ficha SIN cuenta de su equipo
    canjear ──▶  solo el interesado, y solo si el código sigue vivo

El canje es la parte delicada porque toca tres tablas en un orden que no es
negociable: `team_members` primero y `swimmers.user_id` después. La FK compuesta
`(user_id, team_id) → team_members` hace que ligar la ficha antes de existir la
pertenencia falle a nivel de motor.

Aquí están solo las decisiones. La mecánica del código (alfabeto, formato,
caducidad) vive en `codes.py` y las lecturas en `queries.py`.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User

# `normalize_email` es la única función ajena que se importa aquí, y a propósito:
# el correo invitado se compara contra `users.email`, así que las dos formas de
# normalizarlo tienen que ser LA MISMA. Copiar el `.strip().lower()` habría
# funcionado hasta el día en que una de las dos cambie.
from app.modules.auth.service import normalize_email

# Lecturas explícitas de modelos de otros módulos (permitido por las reglas del
# proyecto): el canje escribe la pertenencia y la ficha. No se importa lógica.
from app.modules.swimmers.models import Swimmer
from app.modules.swimmers.schemas import SwimmerCreate
from app.modules.teams.models import ROLE_ATHLETE, ROLE_COACH, Team, TeamMember

from .codes import (
    LINK_CODE_TTL_HOURS,
    LinkCodeError,
    generate,
    is_live,
    normalize_code,
    now_utc,
)
from .models import LinkCode
from .schemas import InviteRequest


async def issue(
    db: AsyncSession, swimmer: Swimmer, coach_id: int,
    *, invited_email: str | None = None,
) -> LinkCode:
    """Emite un código para esa ficha y **revoca el anterior**.

    Que emitir invalide el previo no es un detalle de limpieza: si convivieran
    dos códigos vivos para la misma ficha, el entrenador que reemite porque "el
    otro se perdió" dejaría el perdido funcionando.

    `invited_email` lo convierte en una invitación dirigida: además del código
    hay que ser esa persona. Sin él, el código vale para quien lo tenga — que es
    lo correcto cuando el entrenador lo emite sobre una ficha suelta y se lo
    dicta en el borde de la piscina, sin saber con qué correo se registrará.
    """
    if swimmer.user_id is not None:
        raise LinkCodeError("Esa ficha ya tiene una cuenta ligada")
    if not swimmer.is_active:
        raise LinkCodeError("Esa ficha está dada de baja")

    previos = select(LinkCode).where(
        LinkCode.swimmer_id == swimmer.id,
        LinkCode.used_at.is_(None),
        LinkCode.revoked_at.is_(None),
    )
    ahora = now_utc()
    for previo in (await db.execute(previos)).scalars():
        previo.revoked_at = ahora

    code = LinkCode(
        team_id=swimmer.team_id, swimmer_id=swimmer.id, created_by=coach_id,
        code=generate(), expires_at=ahora + timedelta(hours=LINK_CODE_TTL_HOURS),
        invited_email=normalize_email(invited_email) if invited_email else None,
    )
    db.add(code)
    await db.commit()
    await db.refresh(code)
    return code


async def check_invitable(db: AsyncSession, email: str, team_id: int) -> None:
    """Falla si ese correo no puede aceptar una invitación de este equipo.

    Se pregunta **antes** de crear la ficha, no después: si se comprobara al
    emitir el código, un correo que ya está en otro club dejaría tras de sí una
    ficha huérfana en este cada vez que el entrenador se equivoca de dirección.

    Lo que sí se permite —a propósito— es invitar a un correo sin cuenta: es el
    caso normal, y `invite` la crea.
    """
    user = (await db.execute(
        select(User).where(User.email == normalize_email(email))
    )).scalar_one_or_none()
    if user is None:
        return
    if not user.is_active:
        raise LinkCodeError("Esa cuenta está desactivada")

    ya_ligada = (await db.execute(
        select(Swimmer).where(Swimmer.user_id == user.id)
    )).scalar_one_or_none()
    if ya_ligada is not None:
        raise LinkCodeError(
            f"Esa cuenta ya está ligada a la ficha de {ya_ligada.name}",
        )

    membership = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )).scalar_one_or_none()
    if membership is None:
        return
    if membership.team_id != team_id:
        # Sin decir de qué club: quien pregunta no tiene por qué saberlo.
        raise LinkCodeError("Esa cuenta ya pertenece a otro equipo")
    if membership.role == ROLE_COACH:
        raise LinkCodeError("Esa cuenta es de un entrenador de este equipo")
    if not membership.is_active:
        raise LinkCodeError("El acceso de esa cuenta a este equipo está revocado")


async def _pending_swimmer(
    db: AsyncSession, email: str, team_id: int,
) -> Swimmer | None:
    """La ficha que ya se creó para ese correo en este equipo y sigue pendiente.

    Existe para que reinvitar a la misma persona reemita el código en vez de
    dejar dos fichas suyas en la lista de atletas. Es el caso normal: se manda
    la invitación, se pierde, y el entrenador vuelve a mandarla.
    """
    stmt = (
        select(Swimmer)
        .join(LinkCode, LinkCode.swimmer_id == Swimmer.id)
        .where(
            LinkCode.invited_email == normalize_email(email),
            LinkCode.team_id == team_id,
            LinkCode.used_at.is_(None),
            LinkCode.revoked_at.is_(None),
            Swimmer.user_id.is_(None),
            Swimmer.is_active.is_(True),
        )
        .order_by(LinkCode.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def invite(
    db: AsyncSession, data: InviteRequest, team_id: int, coach_id: int,
) -> tuple[Swimmer, LinkCode, str | None]:
    """Da de alta a esa persona en el equipo: ficha, cuenta y código.

    Devuelve `(ficha, código, contraseña temporal)`. La contraseña solo viene si
    la cuenta se acaba de crear aquí; después ya no se puede volver a leer.

    **La cuenta nueva nace SIN pertenencia a ningún equipo**, a propósito. El
    entrenador puede dar de alta a quien quiera; meterlo en el club es otra cosa
    y la decide la otra parte al canjear el código. Crearla aquí convertiría la
    invitación en un decreto y dejaría el código de adorno — que es exactamente
    lo que hacía el desplegable retirado el 2026-08-09.

    Reinvitar al mismo correo **reutiliza la ficha pendiente** y emite un código
    nuevo (el anterior lo revoca `issue`). Sin eso, cada reenvío dejaba otra
    ficha de la misma persona en la lista de atletas y el código viejo vivo,
    porque `issue` solo revoca los de *esa* ficha.
    """
    # Los dos únicos usos de lógica ajena del módulo, y los dos por la misma
    # razón: crear una cuenta y crear una ficha ya tienen dueño en el proyecto, y
    # reimplementarlos aquí sería tener dos formas de dar de alta a una persona.
    from app.core.security import hash_password
    from app.modules.swimmers.service import create_swimmer

    normalizado = normalize_email(data.email)
    swimmer = await _pending_swimmer(db, normalizado, team_id)
    if swimmer is None:
        swimmer = await create_swimmer(db, SwimmerCreate(
            name=data.name, birth_date=data.birth_date, gender=data.gender,
            specialty=data.specialty, main_stroke=data.main_stroke,
            notes=data.notes,
        ), team_id)

    existente = (await db.execute(
        select(User).where(User.email == normalizado)
    )).scalar_one_or_none()

    temporal: str | None = None
    if existente is None:
        temporal = secrets.token_urlsafe(9)
        db.add(User(
            email=normalizado, name=data.name,
            password_hash=hash_password(temporal),
        ))
        await db.flush()

    code = await issue(db, swimmer, coach_id, invited_email=normalizado)
    return swimmer, code, temporal


async def revoke(db: AsyncSession, code: LinkCode) -> None:
    code.revoked_at = now_utc()
    await db.commit()


async def redeem(db: AsyncSession, raw_code: str, user: User) -> tuple[Swimmer, Team]:
    """Liga la cuenta de `user` a la ficha del código, y lo mete en el equipo.

    **Un solo mensaje para código inexistente, caducado, gastado y revocado.**
    Distinguirlos permitiría sondear qué códigos existen probando cadenas, y a
    quien teclea bien un código bueno no le aporta nada saber cuál de los cuatro
    era.
    """
    stmt = select(LinkCode).where(LinkCode.code == normalize_code(raw_code))
    code = (await db.execute(stmt)).scalar_one_or_none()
    if code is None or not is_live(code):
        raise LinkCodeError("Código inválido o caducado", status=400)

    # Un código dirigido solo lo canjea su destinatario. **Mismo mensaje que el
    # de arriba**, por lo mismo: distinguir "no es tuyo" de "no existe" diría a
    # quien prueba cadenas cuáles son reales, y a quien teclea el suyo bien no le
    # aporta nada. El correo se compara ya normalizado por las dos partes.
    if code.invited_email is not None and \
            code.invited_email != normalize_email(user.email):
        raise LinkCodeError("Código inválido o caducado", status=400)

    swimmer = await db.get(Swimmer, code.swimmer_id)
    if swimmer is None or not swimmer.is_active:
        raise LinkCodeError("La ficha de ese código ya no está disponible")
    if swimmer.user_id is not None:
        raise LinkCodeError("Esa ficha ya tiene una cuenta ligada")

    # Una cuenta, una ficha. Sin esto, canjear un segundo código dejaría la
    # primera ficha huérfana y al atleta viendo el histórico de otra persona.
    ya_ligada = (await db.execute(
        select(Swimmer).where(Swimmer.user_id == user.id)
    )).scalar_one_or_none()
    if ya_ligada is not None:
        raise LinkCodeError(f"Tu cuenta ya está ligada a la ficha de {ya_ligada.name}")

    membership = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == user.id)
    )).scalar_one_or_none()

    if membership is None:
        # El caso que da sentido al pool global: la persona tiene cuenta pero
        # todavía no es de ningún club. El código es su puerta de entrada.
        membership = TeamMember(
            team_id=code.team_id, user_id=user.id, role=ROLE_ATHLETE,
        )
        db.add(membership)
    elif membership.team_id != code.team_id:
        raise LinkCodeError("Tu cuenta ya pertenece a otro equipo")
    elif membership.role == ROLE_COACH:
        raise LinkCodeError("Una cuenta de entrenador no puede ligarse a una ficha")
    elif not membership.is_active:
        raise LinkCodeError("Tu acceso a este equipo está revocado")

    # Orden obligatorio: la FK compuesta de `swimmers` apunta a `team_members`,
    # así que la pertenencia tiene que estar en la sesión antes de ligar la ficha.
    await db.flush()
    swimmer.user_id = user.id
    code.used_at = now_utc()
    code.used_by = user.id
    await db.commit()
    await db.refresh(swimmer)

    team = await db.get(Team, code.team_id)
    return swimmer, team  # type: ignore[return-value]
