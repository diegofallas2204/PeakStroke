"""Las sesiones abiertas: un login por fila, con su rotación del refresh (TODO-30).

Sin `Principal`, por la misma razón que `usuarios`: se consulta **para
construir** la identidad (`get_current_user` pregunta si la sesión del token
sigue viva). Lo que la acota es la cookie firmada, y por eso **toda** consulta
lleva el `user_id` además del `sid`: un token firmado con el `sid` de otra
cuenta no encuentra nada.

Las filas se **borran** (excepción documentada a «nada se borra», decidida el
2026-10-20): cerrar sesión, el reuso, la purga de las caducadas al abrir otra y
subir la generación de la cuenta (`RepositorioDeUsuarios`). El rastro está en la
auditoría; una fila que no fuera una sesión viva solo mentiría.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.entidades import SesionAbierta
from app.persistencia.mapeo.identidad import (
    fila_de_sesion,
    rotacion_condicional,
    sesion_desde_fila,
)
from app.persistencia.tablas.usuarios import OpenSession


class RotacionPerdida(Exception):
    """Otra petición gastó la rotación de esa sesión —o la cerró— entre leerla y
    escribirla (TODO-25). Para `refresh` es el reuso salvo que la sesión ya no
    exista o la generación haya subido; eso lo decide quien la pierde."""

    def __init__(self, sid: str) -> None:
        super().__init__("La rotación de esa sesión ya se gastó")
        self.sid = sid


class RepositorioDeSesionesAbiertas:
    """Ver la cabecera: no lleva `Principal`, y cada consulta lleva la cuenta."""

    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def de(self, sid: str, user_id: int) -> SesionAbierta | None:
        """La sesión de ese `sid` **y esa cuenta**, leída de la base.

        `populate_existing` porque se relee tras perder la rotación: sin él, la
        sesión devolvería la fila que ya tiene en memoria, con la rotación de
        antes. Y es un `select`, no `db.refresh()`: la fila puede haberse borrado
        a la vez (un logout, otro reuso), y entonces es `None` —un 401—, no el
        `InvalidRequestError` de refrescar una fila que no existe (un 500).
        """
        stmt = (
            select(OpenSession)
            .where(OpenSession.id == sid, OpenSession.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        fila = (await self.db.execute(stmt)).scalar_one_or_none()
        return None if fila is None else sesion_desde_fila(fila)

    async def viva(self, sid: str, user_id: int, ahora: datetime) -> bool:
        """Si el access de esa sesión sigue valiendo: existe, es de esa cuenta y
        no caducó. Es una lectura más por cada petición autenticada (por clave
        primaria), y lo que hace que salir de un dispositivo mate su access en
        la siguiente petición y no a los 15 minutos (decidido el 2026-10-20)."""
        stmt = select(OpenSession.id).where(
            OpenSession.id == sid, OpenSession.user_id == user_id,
            OpenSession.expires_at > ahora,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    # ── Escrituras ───────────────────────────────────────────────────────────

    async def abrir(self, sesion: SesionAbierta) -> None:
        """Guarda una sesión recién abierta y confirma.

        De paso **purga las caducadas de todas las cuentas** (decidido el
        2026-10-20): una sola sentencia por el índice de `expires_at`, y así
        quien no vuelve a entrar no deja filas para siempre. Abrir no compite
        con nada —es un `INSERT` con un id aleatorio—, así que el login ya no
        reintenta ni puede dar 503 como en TODO-25.
        """
        if sesion.abierta is None:
            raise ValueError("Una sesión se abre en un instante: falta `abierta`")
        await self.db.execute(delete(OpenSession).where(OpenSession.expires_at <= sesion.abierta))
        self.db.add(fila_de_sesion(sesion))
        await self.db.commit()

    async def rotar(self, sesion: SesionAbierta) -> None:
        """Gasta la rotación con el `UPDATE` condicional y confirma.

        Con 0 filas —otra petición la gastó, o la sesión ya no existe— se
        **confirma** la transacción vacía (no `rollback`: caducaría lo cargado y
        quien siga leería por carga perezosa, un `MissingGreenlet` en async; lo
        vio el revisor de TODO-25) y levanta `RotacionPerdida`. Por eso se exige
        la sesión limpia: lo pendiente se confirmaría aunque la rotación se
        perdiera.
        """
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "Rotar el refresh se guarda con la sesión limpia: confirma antes lo pendiente",
            )
        if (await self.db.execute(rotacion_condicional(sesion))).rowcount != 1:
            await self.db.commit()
            raise RotacionPerdida(sesion.id)
        await self.db.commit()

    async def cerrar(self, sid: str, user_id: int) -> bool:
        """Borra esa sesión y confirma. Devuelve si había algo que cerrar."""
        borradas = (await self.db.execute(
            delete(OpenSession).where(OpenSession.id == sid, OpenSession.user_id == user_id),
        )).rowcount
        await self.db.commit()
        return borradas > 0

    async def cerrar_todas_de(self, user_id: int) -> None:
        """Borra las de esa cuenta **sin confirmar**: lo hace quien sube la
        generación, en su misma transacción (`RepositorioDeUsuarios`)."""
        await self.db.execute(delete(OpenSession).where(OpenSession.user_id == user_id))
