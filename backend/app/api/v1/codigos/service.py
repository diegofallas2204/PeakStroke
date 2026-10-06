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

from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.entidades import Atleta
from app.persistencia.repositorios import (
    RepositorioDeAtletas,
    RepositorioDeCodigos,
    RepositorioDeEquipos,
    RepositorioDeUsuarios,
)

# `normalizar_correo` vive en el repositorio de usuarios, y a propósito: el
# correo invitado se compara contra `users.email`, así que las dos formas de
# normalizarlo tienen que ser LA MISMA. Copiar el `.strip().lower()` habría
# funcionado hasta el día en que una de las dos cambiara.
from app.persistencia.repositorios.codigos import ahora_utc, sigue_vivo
from app.persistencia.repositorios.usuarios import normalizar_correo
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.codigos import LinkCode
from app.persistencia.tablas.equipos import ROLE_ATHLETE, ROLE_COACH, Team, TeamMember
from app.persistencia.tablas.usuarios import User

from .codigos import LINK_CODE_TTL_HOURS, LinkCodeError, generate
from .schemas import InviteRequest


async def issue(
    codigos: RepositorioDeCodigos, swimmer: Swimmer, coach_id: int,
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

    ahora = ahora_utc()
    for previo in await codigos.sin_gastar_de_la_ficha(swimmer.id):
        previo.revoked_at = ahora

    return await codigos.guardar(LinkCode(
        team_id=swimmer.team_id, swimmer_id=swimmer.id, created_by=coach_id,
        code=generate(), expires_at=ahora + timedelta(hours=LINK_CODE_TTL_HOURS),
        invited_email=normalizar_correo(invited_email) if invited_email else None,
    ))


async def check_invitable(
    db: AsyncSession, codigos: RepositorioDeCodigos, email: str, team_id: int,
) -> None:
    """Falla si ese correo no puede aceptar una invitación de este equipo.

    Se pregunta **antes** de crear la ficha, no después: si se comprobara al
    emitir el código, un correo que ya está en otro club dejaría tras de sí una
    ficha huérfana en este cada vez que el entrenador se equivoca de dirección.

    Lo que sí se permite —a propósito— es invitar a un correo sin cuenta: es el
    caso normal, y `invite` la crea.
    """
    user = await RepositorioDeUsuarios(db).por_correo(email)
    if user is None:
        return
    if not user.is_active:
        raise LinkCodeError("Esa cuenta está desactivada")

    ya_ligada = await codigos.ficha_de_la_cuenta(user.id)
    if ya_ligada is not None:
        raise LinkCodeError(
            f"Esa cuenta ya está ligada a la ficha de {ya_ligada.name}",
        )

    membership = await RepositorioDeEquipos(db).pertenencia(
        user.id, incluir_inactivas=True,
    )
    if membership is None:
        return
    if membership.team_id != team_id:
        # Sin decir de qué club: quien pregunta no tiene por qué saberlo.
        raise LinkCodeError("Esa cuenta ya pertenece a otro equipo")
    if membership.role == ROLE_COACH:
        raise LinkCodeError("Esa cuenta es de un entrenador de este equipo")
    if not membership.is_active:
        raise LinkCodeError("El acceso de esa cuenta a este equipo está revocado")


async def invite(
    db: AsyncSession, atletas: RepositorioDeAtletas, codigos: RepositorioDeCodigos,
    data: InviteRequest, team_id: int, coach_id: int,
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
    # La ficha la crea **el repositorio del atleta**, no este módulo: el alta
    # directa del entrenador pasa por el mismo método, y así no hay dos formas
    # de crear una ficha que puedan separarse. Hasta el paso 5 esto importaba
    # `swimmers.service.create_swimmer`, que era lógica cruzada de manual.
    from app.core.security import hash_password

    normalizado = normalizar_correo(data.email)
    # Reinvitar al mismo correo reutiliza la ficha pendiente en vez de dejar dos
    # fichas de la misma persona en la lista de atletas.
    swimmer = await codigos.ficha_pendiente(normalizado, team_id)
    if swimmer is None:
        swimmer = await atletas.guardar(Atleta.nueva(
            data.name, nacimiento=data.birth_date, genero=data.gender,
            especialidad=data.specialty, estilo_principal=data.main_stroke,
            notas=data.notes,
        ))
        assert swimmer is not None   # una ficha nueva siempre es del equipo de quien invita

    usuarios = RepositorioDeUsuarios(db)
    temporal: str | None = None
    if await usuarios.por_correo(normalizado) is None:
        temporal = secrets.token_urlsafe(9)
        await usuarios.crear(
            correo=normalizado, nombre=data.name,
            password_hash=hash_password(temporal),
        )

    code = await issue(codigos, swimmer, coach_id, invited_email=normalizado)
    return swimmer, code, temporal


async def redeem(
    db: AsyncSession, codigos: RepositorioDeCodigos, raw_code: str, user: User,
) -> tuple[Swimmer, Team]:
    """Liga la cuenta de `user` a la ficha del código, y lo mete en el equipo.

    **Un solo mensaje para código inexistente, caducado, gastado y revocado.**
    Distinguirlos permitiría sondear qué códigos existen probando cadenas, y a
    quien teclea bien un código bueno no le aporta nada saber cuál de los cuatro
    era.
    """
    code = await codigos.por_codigo(raw_code)
    if code is None or not sigue_vivo(code):
        raise LinkCodeError("Código inválido o caducado", status=400)

    # Un código dirigido solo lo canjea su destinatario. **Mismo mensaje que el
    # de arriba**, por lo mismo: distinguir "no es tuyo" de "no existe" diría a
    # quien prueba cadenas cuáles son reales, y a quien teclea el suyo bien no le
    # aporta nada. El correo se compara ya normalizado por las dos partes.
    if code.invited_email is not None and \
            code.invited_email != normalizar_correo(user.email):
        raise LinkCodeError("Código inválido o caducado", status=400)

    swimmer = await db.get(Swimmer, code.swimmer_id)
    if swimmer is None or not swimmer.is_active:
        raise LinkCodeError("La ficha de ese código ya no está disponible")
    if swimmer.user_id is not None:
        raise LinkCodeError("Esa ficha ya tiene una cuenta ligada")

    # Una cuenta, una ficha. Sin esto, canjear un segundo código dejaría la
    # primera ficha huérfana y al atleta viendo el histórico de otra persona.
    ya_ligada = await codigos.ficha_de_la_cuenta(user.id)
    if ya_ligada is not None:
        raise LinkCodeError(f"Tu cuenta ya está ligada a la ficha de {ya_ligada.name}")

    membership = await RepositorioDeEquipos(db).pertenencia(
        user.id, incluir_inactivas=True,
    )

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
    code.used_at = ahora_utc()
    code.used_by = user.id
    await db.commit()
    await db.refresh(swimmer)

    team = await db.get(Team, code.team_id)
    return swimmer, team  # type: ignore[return-value]
