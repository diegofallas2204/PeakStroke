"""Entorno de Alembic para PeakStroke.

Dos ajustes propios sobre la plantilla async:
  · La URL sale de `app.core.config.settings`, no de alembic.ini — así hay una
    sola fuente de verdad y basta cambiar PEAKSTROKE_DATABASE_URL para migrar
    la misma app contra SQLite o PostgreSQL.
  · `render_as_batch=True`: SQLite no sabe hacer ALTER de columnas; sin esto,
    cualquier migración que modifique una columna existente falla en local.
    En PostgreSQL el modo batch es transparente.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Importado por su efecto: puebla Base.metadata con todos los modelos. Lo que no
# esté registrado ahí es invisible para --autogenerate. Misma lista que usa la
# app al arrancar, para que no puedan divergir.
from app.core import model_registry  # noqa: F401
from app.core.config import settings
from app.core.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_IS_SQLITE = settings.database_url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (alembic upgrade head --sql)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_IS_SQLITE,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=_IS_SQLITE,
        # Detecta cambios de tipo y de nullable al autogenerar; sin esto Alembic
        # solo ve tablas y columnas añadidas o borradas.
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
