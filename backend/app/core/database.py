"""Engine SQLAlchemy async, sesión y Base declarativa."""
from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

IS_SQLITE = settings.database_url.startswith("sqlite")

if IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record) -> None:
        """SQLite ignora las claves foráneas salvo que se pidan, por conexión.

        Sin esto, TODAS las FKs del esquema son decorativas en local: se puede
        borrar un usuario y dejar filas apuntando al vacío sin que nada proteste.
        PostgreSQL sí las aplica — así que el código funcionaría en desarrollo y
        reventaría en producción, que es la peor forma de descubrirlo.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def _revisions(sync_conn: Connection) -> tuple[str | None, str | None]:
    """(revisión aplicada en la DB, última revisión del repo)."""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    current = MigrationContext.configure(sync_conn).get_current_revision()
    head = ScriptDirectory.from_config(Config(str(_ALEMBIC_INI))).get_current_head()
    return current, head


async def init_db() -> None:
    """Verifica que la DB responde y que el esquema está migrado.

    Ya NO crea tablas: desde que existe `alembic/`, el esquema lo define el
    historial de migraciones y nada más. Un `create_all()` al arrancar volvería a
    crear por su cuenta tablas que Alembic cree pendientes, y la siguiente
    migración fallaría con "table already exists".
    """
    async with engine.connect() as conn:
        current, head = await conn.run_sync(_revisions)

    if current == head:
        return
    if current is None:
        logger.warning(
            "La base de datos no tiene esquema (o no está bajo control de Alembic). "
            "Ejecuta:  alembic upgrade head   —o bien:  python seed.py  para datos demo."
        )
    else:
        logger.warning(
            "Esquema desactualizado: la DB está en %s y el repo va por %s. "
            "Ejecuta:  alembic upgrade head",
            current, head,
        )
