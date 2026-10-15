"""Informe de salud: versión, estado de las migraciones y conteos. Solo lee.

**No audita**, a propósito: no cambia nada, y es justo lo que se corre sobre una
base que puede no estar migrada —sin tabla `auditoria`— para saber qué le pasa.
Por la misma razón cada conteo se pide por separado y una tabla que no existe
se enseña como «—» en vez de tumbar el informe.

Los conteos son de **personas y estructura**, no de trabajo deportivo, como las
vistas de PSAdmin: cuántos clubes, cuentas y pertenencias, cuántos eventos de
auditoría y cuándo el último. Ni tiempos ni tests ni planes de nadie.
"""
from __future__ import annotations

import argparse

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

from .comun import Consola, head_de_alembic, version_de_la_base

_CONTEOS = (
    ("clubes", "SELECT count(*) FROM teams"),
    ("cuentas activas", "SELECT count(*) FROM users WHERE is_active"),
    ("cuentas desactivadas", "SELECT count(*) FROM users WHERE NOT is_active"),
    ("pertenencias activas", "SELECT count(*) FROM team_members WHERE is_active"),
    ("pertenencias revocadas", "SELECT count(*) FROM team_members WHERE NOT is_active"),
    ("cuentas sin club", "SELECT count(*) FROM users u WHERE NOT EXISTS "
                         "(SELECT 1 FROM team_members m WHERE m.user_id = u.id)"),
    ("fichas activas", "SELECT count(*) FROM swimmers WHERE is_active"),
    ("eventos de auditoría", "SELECT count(*) FROM auditoria"),
    ("último evento", "SELECT max(occurred_at) FROM auditoria"),
)


async def _valor(db: AsyncSession, sql: str) -> str:
    try:
        valor = (await db.execute(text(sql))).scalar()
    except Exception:
        await db.rollback()
        return "—"
    return "—" if valor is None else str(valor)


async def salud(db: AsyncSession, args: argparse.Namespace, consola: Consola) -> int:
    actual, head = await version_de_la_base(db), head_de_alembic()
    url = make_url(settings.database_url)
    consola.decir(f"PeakStroke {settings.version} · entorno {settings.environment}")
    # Sin contraseña: el informe se pega en un ticket o en un chat.
    consola.decir(f"base: {url.render_as_string(hide_password=True)}")
    estado = "al día" if actual == head else "SIN MIGRAR: `alembic upgrade head`"
    consola.decir(f"migraciones: base {actual or 'ninguna'} · código {head} · {estado}")
    for nombre, sql in _CONTEOS:
        consola.decir(f"  {nombre:<24} {await _valor(db, sql)}")
    return 0 if actual == head else 2
