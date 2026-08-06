"""Modelo de atletas."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Swimmer(Base):
    __tablename__ = "swimmers"
    __table_args__ = (
        # Clave candidata para las FKs compuestas de quien referencia a un nadador
        # dentro de un equipo (coach_athletes, athlete_plans, aerobic_tests).
        UniqueConstraint("id", "team_id", name="uq_swimmers_id_team"),
        # Si tiene cuenta, esa cuenta debe ser miembro DEL MISMO equipo. Con
        # user_id a NULL la constraint no se evalúa, que es justo lo que queremos
        # para los nadadores sin acceso.
        ForeignKeyConstraint(
            ["user_id", "team_id"], ["team_members.user_id", "team_members.team_id"],
            name="fk_swimmers_user_in_team",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # El nadador es del EQUIPO, no de un entrenador: que un entrenador se vaya no
    # lo saca del club. Qué entrenadores lo llevan vive en `coach_athletes`.
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    # Cuenta de acceso del nadador, si la tiene. Unique porque la relación es 1:1
    # (ambos motores permiten varios NULL en un índice único).
    user_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(12))
    # velocidad | medio_fondo | fondo | aguas_abiertas
    specialty: Mapped[str] = mapped_column(String(20), default="medio_fondo")
    # libre | espalda | pecho | mariposa | combinado
    main_stroke: Mapped[str] = mapped_column(String(20), default="libre")
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    # Los nadadores no se borran: se dan de baja. Su histórico de entrenamiento
    # es el activo más valioso de la aplicación y no debe evaporarse de un clic.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
