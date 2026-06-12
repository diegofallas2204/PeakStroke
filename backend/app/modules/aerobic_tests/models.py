"""Modelos de tests aeróbicos (T-30, T-15, personalizado, CSS, directo)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AerobicTest(Base):
    __tablename__ = "aerobic_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    swimmer_id: Mapped[int] = mapped_column(ForeignKey("swimmers.id"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plans.id"), index=True)
    # T30 | T15 | CUSTOM | CSS | DIRECT
    test_type: Mapped[str] = mapped_column(String(12))
    test_date: Mapped[date] = mapped_column(Date)
    rep_count: Mapped[int | None] = mapped_column(Integer)
    rep_distance: Mapped[int | None] = mapped_column(Integer)
    avg_per100: Mapped[float] = mapped_column(Float)            # base aeróbica s/100m
    std_dev: Mapped[float | None] = mapped_column(Float)
    trend: Mapped[str | None] = mapped_column(String(12))       # improving|stable|declining
    css_ms: Mapped[float | None] = mapped_column(Float)         # solo tests CSS
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    splits: Mapped[list[AerobicSplit]] = relationship(
        back_populates="test", cascade="all, delete-orphan",
        order_by="AerobicSplit.rep_number",
    )


class AerobicSplit(Base):
    __tablename__ = "aerobic_test_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("aerobic_tests.id"), index=True)
    rep_number: Mapped[int] = mapped_column(Integer)
    split_time: Mapped[float] = mapped_column(Float)            # tiempo de la repetición

    test: Mapped[AerobicTest] = relationship(back_populates="splits")
