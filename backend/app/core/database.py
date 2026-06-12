"""Engine SQLAlchemy async, sesión y Base declarativa."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Crea las tablas si no existen (local-first; Alembic llegará con el SaaS)."""
    from app.modules.swimmers import models as _swimmers  # noqa: F401
    from app.modules.plans import models as _plans  # noqa: F401
    from app.modules.aerobic_tests import models as _aerobic  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
