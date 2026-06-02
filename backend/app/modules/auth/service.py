"""
auth/service.py — Lógica de negocio de autenticación.
Solo recibe sesión de DB como parámetro; nunca importa desde otros módulos.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.schemas import RegisterRequest


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    existing = await db.scalar(select(User).where(User.email == data.email))
    if existing:
        raise ValueError("Ya existe una cuenta con ese email")

    user = User(
        email=data.email,
        name=data.name,
        hashed_password=hash_password(data.password),
        role="coach",
        tier="coach",  # 30-day trial on Coach tier
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.hashed_password):
        return None
    # Si el trial venció y no hay pago, degradar a free
    if (
        user.tier == "coach"
        and user.trial_ends_at
        and user.trial_ends_at < datetime.now(timezone.utc)
        and not user.stripe_customer_id
    ):
        user.tier = "free"
    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)
