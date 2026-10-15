"""Quitar y devolver acceso: revocar, restaurar, liberar, cortar sesiones y la contraseña.

**Ninguna regla vive aquí.** Lo que se admite lo deciden las entidades
(`Equipo.admite_cambio`, `Equipo.admite_liberar`, `Pertenencia.revocar()`,
`Usuario.revocar_sesiones()`, `Usuario.cambiar_password()`) y lo escriben sus
repositorios. Revocar pasa por el mismo `auth/service.update_member` que el API
—que es donde revocar corta las sesiones—, y la contraseña por el mismo
`auth/credenciales.change_password`. Este módulo busca la cuenta, pregunta,
llama y audita **después** de confirmar.

`--dry-run` hace todas las comprobaciones sobre la entidad (que vive en memoria)
y no llama a ningún `guardar`: enseña lo que haría, sin escribir ni auditar.
"""
from __future__ import annotations

import argparse
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import credenciales
from app.api.v1.auth import service as auth_service
from app.api.v1.auth.schemas import UserUpdate
from app.core.auditoria import TipoDeEvento, auditar
from app.dominio.entidades import OperacionDeEquipoImposible
from app.persistencia.repositorios import RepositorioDeEquipos, RepositorioDeUsuarios
from app.persistencia.tablas.equipos import TeamMember
from app.persistencia.tablas.usuarios import User

from .comun import Consola, OperacionRechazada, actor, confirmar, detalle, ensenar_temporal


async def _cuenta(db: AsyncSession, correo: str) -> User:
    user = await RepositorioDeUsuarios(db).por_correo(correo)
    if user is None:
        raise OperacionRechazada(f"No hay ninguna cuenta con el correo {correo}")
    return user


async def _pertenencia(equipos: RepositorioDeEquipos, user: User) -> TeamMember:
    # Con las revocadas: «revocada» y «sin club» son dos respuestas distintas.
    fila = await equipos.pertenencia(user.id, incluir_inactivas=True)
    if fila is None:
        raise OperacionRechazada(f"{user.email} no pertenece a ningún club (es del pool)")
    return fila


def _auditar(tipo: TipoDeEvento, comando: str, user: User, equipo: int | None, texto: str) -> None:
    auditar(tipo, correo=actor(), equipo=equipo, objetivo=("user", user.id),
            detalle=detalle(comando, texto))


async def revocar(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    equipos = RepositorioDeEquipos(db)
    user = await _cuenta(db, args.correo)
    fila = await _pertenencia(equipos, user)
    if not fila.is_active:
        consola.decir(f"{user.email} ya tenía el acceso revocado: no se cambia nada.")
        return 0
    club = await equipos.equipo(fila.team_id)
    try:
        equipos.como_equipo(club).admite_cambio(
            equipos.como_pertenencia(fila), revocar=True, a_atleta=False,
        )
    except OperacionDeEquipoImposible as exc:
        raise OperacionRechazada(str(exc)) from exc

    que = (f"Revocar el acceso de {user.email} ({fila.role}) a «{club.name}» "
           "y cortar todas sus sesiones.")
    if args.dry_run:
        consola.decir(f"[dry-run] {que}")
        return 0
    confirmar(consola, user.email, que)
    await auth_service.update_member(equipos, user, fila, UserUpdate(is_active=False))
    _auditar(TipoDeEvento.MIEMBRO_REVOCADO, "revocar", user, fila.team_id,
             f"{user.email} · sesiones cortadas")
    consola.decir(f"Acceso revocado y sesiones cortadas: {user.email}")
    return 0


async def restaurar(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    equipos = RepositorioDeEquipos(db)
    user = await _cuenta(db, args.correo)
    fila = await _pertenencia(equipos, user)
    if fila.is_active:
        consola.decir(f"{user.email} ya tenía el acceso: no se cambia nada.")
        return 0
    club = await equipos.equipo(fila.team_id)
    que = f"Devolver a {user.email} ({fila.role}) el acceso a «{club.name}»."
    if args.dry_run:
        consola.decir(f"[dry-run] {que}")
        return 0
    await auth_service.update_member(equipos, user, fila, UserUpdate(is_active=True))
    _auditar(TipoDeEvento.MIEMBRO_RESTAURADO, "restaurar", user, fila.team_id, user.email)
    consola.decir(f"Acceso restaurado: {user.email}")
    return 0


async def liberar(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    """TODO-26 (2026-10-14): deja en el pool a un atleta ya revocado."""
    equipos, usuarios = RepositorioDeEquipos(db), RepositorioDeUsuarios(db)
    user = await _cuenta(db, args.correo)
    fila = await _pertenencia(equipos, user)
    club = await equipos.equipo(fila.team_id)
    pertenencia = equipos.como_pertenencia(fila)
    try:
        equipos.como_equipo(club).admite_liberar(pertenencia)
    except OperacionDeEquipoImposible as exc:
        raise OperacionRechazada(str(exc)) from exc
    # Antes de preguntar: un atleta que fue entrenador dejó filas que la FK
    # borraría en cascada (lo encontró el /cso de D1). `liberar` lo vuelve a mirar.
    historia = {k: n for k, n in (await equipos.historia_de_entrenador(pertenencia)).items() if n}
    if historia:
        cuales = ", ".join(f"{n} {k}" for k, n in historia.items())
        raise OperacionRechazada(
            f"{user.email} tiene historia como entrenador en el club ({cuales}): "
            "liberarla la borraría. Déjala revocada.",
        )

    que = (f"Liberar a {user.email} de «{club.name}»: la cuenta queda sin club, su ficha "
           "se queda en el club sin cuenta ligada y se cortan sus sesiones. "
           "La pertenencia se BORRA (no se puede restaurar; habría que volver a invitarla).")
    if args.dry_run:
        consola.decir(f"[dry-run] {que}")
        return 0
    confirmar(consola, user.email, que)
    team_id = fila.team_id
    usuario = usuarios.entidad(user)
    usuario.revocar_sesiones()
    await usuarios.anotar(usuario)
    try:
        ficha = await equipos.liberar(pertenencia)   # confirma las dos cosas juntas
    except OperacionDeEquipoImposible as exc:        # la historia apareció entre medias
        raise OperacionRechazada(str(exc)) from exc
    texto = f"{user.email} · ficha {f'#{ficha} desligada' if ficha else 'ninguna'}"
    _auditar(TipoDeEvento.MIEMBRO_LIBERADO, "liberar", user, team_id, texto)
    consola.decir(f"Liberada: {user.email} ya no pertenece a ningún club.")
    return 0


async def cortar_sesiones(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    usuarios = RepositorioDeUsuarios(db)
    user = await _cuenta(db, args.correo)
    fila = await RepositorioDeEquipos(db).pertenencia(user.id, incluir_inactivas=True)
    que = f"Cortar todas las sesiones abiertas de {user.email} (tendrá que volver a entrar)."
    if args.dry_run:
        consola.decir(f"[dry-run] {que}")
        return 0
    confirmar(consola, user.email, que)
    usuario = usuarios.entidad(user)
    usuario.revocar_sesiones()
    await usuarios.guardar(usuario)
    _auditar(TipoDeEvento.SESIONES_CORTADAS, "cortar-sesiones", user,
             fila.team_id if fila else None, user.email)
    consola.decir(f"Sesiones cortadas: {user.email}")
    return 0


async def restablecer_password(
    db: AsyncSession, args: argparse.Namespace, consola: Consola,
) -> int:
    user = await _cuenta(db, args.correo)
    fila = await RepositorioDeEquipos(db).pertenencia(user.id, incluir_inactivas=True)
    que = (f"Poner a {user.email} una contraseña temporal nueva: la de ahora deja de "
           "valer y se cortan todas sus sesiones.")
    if args.dry_run:
        consola.decir(f"[dry-run] {que}")
        return 0
    confirmar(consola, user.email, que)
    temporal = secrets.token_urlsafe(12)
    await credenciales.change_password(db, user, temporal)   # hash + revocar, un commit
    _auditar(TipoDeEvento.PASSWORD_RESTABLECIDA, "restablecer-password", user,
             fila.team_id if fila else None, f"{user.email} · temporal emitida")
    ensenar_temporal(consola, temporal)
    return 0
