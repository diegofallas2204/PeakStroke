"""
auth/models.py — Modelo SQLAlchemy del usuario.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("coach", "swimmer", "admin", name="user_role"),
        default="coach",
        nullable=False,
    )
    tier: Mapped[str] = mapped_column(
        Enum("free", "coach", "club", name="subscription_tier"),
        default="free",
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relaciones
    macrocycles: Mapped[list] = relationship(
        "Macrocycle", back_populates="owner", lazy="noload"
    )
