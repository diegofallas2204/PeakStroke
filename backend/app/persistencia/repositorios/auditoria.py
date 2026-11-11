"""La auditoría: anotar eventos, la clave del periodo y la purga de lo caducado.

Sin `Principal`, como `equipos` y `usuarios`: no hay nada que acotar. Nadie lee
la auditoría desde el API de PeakStroke —la lee PSAdmin, y solo por las vistas
`v_admin_*`—, así que este repositorio **solo escribe**, con una excepción:
`fallos_recientes`, que le cuenta al freno de intentos (`core/freno.py`)
los fallos de la última ventana. Devuelve momentos, nunca eventos.

Lo que NO hay aquí, a propósito: ningún método que actualice un evento, ni
uno que borre eventos concretos. La base de datos lo rechazaría de todas
formas (triggers de la migración `e3a9d0c41b7f`); la única escritura que borra
es `purgar_caducados`, y los triggers solo la dejan pasar sobre filas que ya
cumplieron `RETENCION_MESES`.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistencia.tablas.auditoria import (
    FALLO,
    RETENCION_MESES,
    ClaveDeAuditoria,
    EventoDeAuditoria,
)


class RepositorioDeAuditoria:
    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def anotar(self, eventos: list[EventoDeAuditoria]) -> None:
        """Añade los eventos a la sesión. Confirma quien llama."""
        self.db.add_all(eventos)

    async def clave_si_existe(self, periodo: int) -> bytes | None:
        """La clave del periodo **sin crearla**. Si no existe, en ese periodo
        todavía no se guardó ningún evento: no hay huella con la que comparar."""
        fila = await self.db.get(ClaveDeAuditoria, periodo)
        return bytes.fromhex(fila.key_hex) if fila is not None else None

    async def fallos_recientes(
        self, tipo: str, desde: datetime, *,
        huella: str | None = None, correo: str | None = None,
        actor_id: int | None = None, sin_detalle: str | None = None,
        tope: int = 60,
    ) -> list[datetime]:
        """Cuándo falló ese tipo de evento desde `desde`, el más reciente primero.

        Los filtros que se pasen se suman (`huella`, `correo`, `actor_id`);
        `sin_detalle` deja fuera los eventos con ese `detail`. `tope` acota la
        lista: al freno le da igual 60 fallos que 600.
        """
        stmt = (
            select(EventoDeAuditoria.occurred_at)
            .where(
                EventoDeAuditoria.event_type == tipo,
                EventoDeAuditoria.outcome == FALLO,
                EventoDeAuditoria.occurred_at >= desde,
            )
            .order_by(EventoDeAuditoria.occurred_at.desc())
            .limit(tope)
        )
        if huella is not None:
            stmt = stmt.where(EventoDeAuditoria.ip_hash == huella)
        if correo is not None:
            stmt = stmt.where(EventoDeAuditoria.actor_email == correo)
        if actor_id is not None:
            stmt = stmt.where(EventoDeAuditoria.actor_user_id == actor_id)
        if sin_detalle is not None:
            stmt = stmt.where(EventoDeAuditoria.detail != sin_detalle)
        # SQLite devuelve las fechas sin zona; se guardaron en UTC.
        return [
            m if m.tzinfo is not None else m.replace(tzinfo=UTC)
            for m in (await self.db.execute(stmt)).scalars()
        ]

    async def clave_del_periodo(self, periodo: int) -> bytes:
        """La clave HMAC del periodo en curso; la crea si todavía no existe.

        Al crearla **borra las de periodos anteriores**: ese borrado es la
        anonimización. Dos procesos que lleguen a la vez al cambio de periodo
        chocan en la clave primaria; el que pierde lee la del otro, y las dos
        huellas del periodo salen con la misma clave.
        """
        fila = await self.db.get(ClaveDeAuditoria, periodo)
        if fila is None:
            try:
                async with self.db.begin_nested():
                    fila = ClaveDeAuditoria(period=periodo, key_hex=secrets.token_hex(32))
                    self.db.add(fila)
            except IntegrityError:
                fila = await self.db.get(ClaveDeAuditoria, periodo, populate_existing=True)
                assert fila is not None
            await self.retirar_claves_anteriores_a(periodo)
        return bytes.fromhex(fila.key_hex)

    async def retirar_claves_anteriores_a(self, periodo: int) -> None:
        """Borra las claves de periodos pasados: sus huellas ya no se relacionan.

        La llama `clave_del_periodo` al estrenar periodo, y la purga mensual por
        si no hubo ningún evento que lo estrenara: sin tráfico, la clave vieja
        seguiría en la base.
        """
        await self.db.execute(
            delete(ClaveDeAuditoria).where(ClaveDeAuditoria.period < periodo),
        )

    async def purgar_caducados(self) -> int:
        """Borra los eventos de más de `RETENCION_MESES`. Devuelve cuántos.

        El corte lo calcula **el motor**, con la misma expresión que usa su
        trigger: si lo calculara Python, una diferencia de reloj o de formato
        entre los dos haría que el trigger rechazara la purga entera.
        """
        if self.db.bind.dialect.name == "sqlite":
            corte = f"datetime('now', '-{RETENCION_MESES} months')"
        else:
            corte = f"now() - interval '{RETENCION_MESES} months'"
        resultado = await self.db.execute(
            text(f"DELETE FROM auditoria WHERE occurred_at < {corte}"),
        )
        return resultado.rowcount or 0
