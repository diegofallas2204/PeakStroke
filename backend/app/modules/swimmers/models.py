"""Modelo de atletas."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Swimmer(Base):
    __tablename__ = "swimmers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(12))
    # velocidad | medio_fondo | fondo | aguas_abiertas
    specialty: Mapped[str] = mapped_column(String(20), default="medio_fondo")
    # libre | espalda | pecho | mariposa | combinado
    main_stroke: Mapped[str] = mapped_column(String(20), default="libre")
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
