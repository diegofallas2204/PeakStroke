"""Crear un club con su dueño, dar de alta una cuenta y transferir la propiedad.

Sustituye a `tools/create_user.py` (retirado en D1, 2026-10-14), que tenía dos
defectos que el propio plan apuntaba: aceptaba `--password` por argumento y no
auditaba. Aquí la contraseña se genera (y se enseña una vez) o se lee por la
entrada estándar con `--password-stdin`.

Las validaciones son las del API, no unas propias: el correo, el nombre y la
contraseña pasan por `UserCreate` y el nombre del club por `TeamUpdate`. Quién
puede ser dueño lo decide `Equipo.transferir_propiedad`, el mismo para el
primer dueño que para una transferencia.
"""
from __future__ import annotations

import argparse
import secrets

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import service as auth_service
from app.api.v1.auth.schemas import UserCreate
from app.api.v1.equipos import service as equipos_service
from app.api.v1.equipos.schemas import TeamUpdate
from app.core.auditoria import TipoDeEvento, auditar
from app.dominio.entidades import OperacionDeEquipoImposible
from app.persistencia.repositorios import RepositorioDeEquipos, RepositorioDeUsuarios
from app.persistencia.tablas.equipos import ROLE_COACH, Team
from app.persistencia.tablas.usuarios import User

from .comun import (
    Consola,
    OperacionRechazada,
    actor,
    confirmar,
    detalle,
    ensenar_temporal,
    leer_password_nueva,
)


def _validar[M: BaseModel](modelo: type[M], **campos: object) -> M:
    try:
        return modelo(**campos)
    except ValidationError as exc:
        errores = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise OperacionRechazada(f"Datos no válidos — {errores}") from None


def _alta(args: argparse.Namespace, consola: Consola, rol: str) -> tuple[UserCreate, bool]:
    """Los datos de la cuenta nueva y si la contraseña es una temporal generada."""
    generada = not args.password_stdin
    password = secrets.token_urlsafe(12) if generada else leer_password_nueva(consola)
    return _validar(UserCreate, email=args.correo, name=args.nombre,
                    password=password, role=rol), generada


async def _que_no_exista(db: AsyncSession, correo: str) -> None:
    if await RepositorioDeUsuarios(db).por_correo(correo) is not None:
        raise OperacionRechazada(f"Ya existe una cuenta con el correo {correo.strip().lower()}")


async def _club(db: AsyncSession, team_id: int | None) -> Team:
    if team_id is not None:
        club = await db.get(Team, team_id)
        if club is None:
            raise OperacionRechazada(f"No hay ningún club con id {team_id}")
        return club
    # Sin indicarlo: si solo hay un club, es evidente cuál (como hacía create_user.py).
    clubes = list((await db.execute(select(Team).order_by(Team.id))).scalars())
    if len(clubes) == 1:
        return clubes[0]
    if not clubes:
        raise OperacionRechazada("No hay ningún club: crea el primero con `crear-equipo`")
    lista = ", ".join(f"#{c.id} {c.name}" for c in clubes)
    raise OperacionRechazada(f"Hay {len(clubes)} clubes; indica cuál con --equipo N ({lista})")


async def crear_equipo(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    nombre = _validar(TeamUpdate, name=args.nombre_equipo).name
    await _que_no_exista(db, args.correo)
    datos, generada = _alta(args, consola, ROLE_COACH)
    if args.dry_run:
        consola.decir(f"[dry-run] Crear el club «{nombre}» con {datos.email} como dueño.")
        return 0

    equipos = RepositorioDeEquipos(db)
    # El club y la cuenta de su dueño, en UN commit (`create_user` confirma los
    # dos): si la cuenta falla —otra alta con el mismo correo entre medias—, no
    # queda un club vacío.
    club = await equipos.crear(nombre, confirmar=False)
    try:
        user = await auth_service.create_user(db, datos, club.id)
    except IntegrityError:
        await db.rollback()
        raise OperacionRechazada(
            f"Ya existe una cuenta con el correo {datos.email}: no se creó nada",
        ) from None
    # Leídos ya: tras un `rollback` las filas caducan y leerlas sería IO perezosa.
    club_id, user_id, correo = club.id, user.id, user.email

    def _auditar_alta(estado: str) -> None:
        auditar(TipoDeEvento.EQUIPO_CREADO, correo=actor(), equipo=club_id,
                objetivo=("team", club_id), detalle=detalle("crear-equipo", estado))
        auditar(TipoDeEvento.CUENTA_CREADA, correo=actor(), equipo=club_id,
                objetivo=("user", user_id), detalle=detalle("crear-equipo", f"{correo} como coach"))

    # Ponerle dueño es otro commit (la FK del dueño exige que la pertenencia ya
    # exista). Si falla, el club y la cuenta ya están: se auditan como lo que son.
    try:
        equipo = equipos.como_equipo(club)
        equipo.transferir_propiedad(equipos.como_pertenencia(await equipos.pertenencia(user.id)))
        club = await equipos.guardar_equipo(equipo)
    except Exception as exc:
        await db.rollback()
        _auditar_alta(f"SIN DUEÑO: falló al ponerlo ({type(exc).__name__})")
        raise OperacionRechazada(
            f"El club #{club_id} y la cuenta {correo} se crearon, pero no se pudo "
            f"ponerla como dueña ({exc}). Arréglalo con `transferir --equipo {club_id} "
            f"--a {correo}`.",
        ) from exc
    _auditar_alta(f"dueño {correo}")
    consola.decir(f"Club creado: #{club.id} {club.name} · dueño #{user.id} {user.email}")
    if generada:
        ensenar_temporal(consola, datos.password)
    return 0


async def crear_cuenta(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    await _que_no_exista(db, args.correo)
    club = await _club(db, args.equipo)
    datos, generada = _alta(args, consola, args.rol)
    if args.dry_run:
        consola.decir(f"[dry-run] Crear {datos.email} como {datos.role} en «{club.name}».")
        return 0
    user = await auth_service.create_user(db, datos, club.id)
    auditar(TipoDeEvento.CUENTA_CREADA, correo=actor(), equipo=club.id,
            objetivo=("user", user.id),
            detalle=detalle("crear-cuenta", f"{user.email} como {datos.role}"))
    consola.decir(f"Cuenta creada: #{user.id} {user.email} ({datos.role}) en #{club.id} {club.name}")
    if datos.role != ROLE_COACH:
        consola.decir("Sin ficha ligada: un atleta se da de alta mejor por invitación "
                      "(POST /link-codes/invite), que crea ficha, cuenta y código juntos.")
    if generada:
        ensenar_temporal(consola, datos.password)
    return 0


async def transferir(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    equipos = RepositorioDeEquipos(db)
    club = await _club(db, args.equipo)
    nuevo = await RepositorioDeUsuarios(db).por_correo(args.a)
    if nuevo is None:
        raise OperacionRechazada(f"No hay ninguna cuenta con el correo {args.a}")
    if club.owner_id == nuevo.id:
        consola.decir(f"{nuevo.email} ya es el dueño de «{club.name}»: no se cambia nada.")
        return 0
    anterior = await db.get(User, club.owner_id) if club.owner_id is not None else None
    # Comprobar antes de preguntar, sobre la entidad en memoria: no se escribe nada.
    miembro = await equipos.pertenencia(nuevo.id, incluir_inactivas=True)
    try:
        equipos.como_equipo(club).transferir_propiedad(
            equipos.como_pertenencia(miembro) if miembro else None,
        )
    except OperacionDeEquipoImposible as exc:
        raise OperacionRechazada(str(exc)) from exc

    de = anterior.email if anterior else "nadie"
    que = f"Transferir la propiedad de «{club.name}» de {de} a {nuevo.email}."
    if args.dry_run:
        consola.decir(f"[dry-run] {que}")
        return 0
    confirmar(consola, club.name, que)
    club = await equipos_service.transfer_ownership(equipos, club, nuevo.id)
    auditar(TipoDeEvento.PROPIEDAD_TRANSFERIDA, correo=actor(), equipo=club.id,
            objetivo=("user", nuevo.id), detalle=detalle("transferir", f"de {de} a {nuevo.email}"))
    consola.decir(f"«{club.name}» tiene dueño nuevo: {nuevo.email}")
    return 0
