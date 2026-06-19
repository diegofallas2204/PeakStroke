"""Modelos del módulo plans: macrociclo, fases, competencias, atletas y semanas."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    total_weeks: Mapped[int] = mapped_column(Integer)          # 12..18
    weeks_per_micro: Mapped[int] = mapped_column(Integer, default=4)
    total_km: Mapped[float] = mapped_column(Float)
    progression_curve: Mapped[str] = mapped_column(String(20), default="sigmoid")
    pool: Mapped[str] = mapped_column(String(2), default="50")  # "50" larga | "25" corta
    main_event: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="active")  # active|draft|finished|suspended
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    phases: Mapped[list[PlanPhase]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="PlanPhase.sort"
    )
    competitions: Mapped[list[Competition]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="Competition.week_number"
    )
    athlete_plans: Mapped[list[AthletePlan]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class PlanPhase(Base):
    __tablename__ = "plan_phases"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    type: Mapped[str] = mapped_column(String(12), default="base")  # base|build|peak|taper
    week_start: Mapped[int] = mapped_column(Integer)
    week_end: Mapped[int] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(12), default="#8b5cf6")
    sort: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[Plan] = relationship(back_populates="phases")


class Competition(Base):
    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    week_number: Mapped[int] = mapped_column(Integer)
    days: Mapped[int] = mapped_column(Integer, default=1)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)

    plan: Mapped[Plan] = relationship(back_populates="competitions")


class AthletePlan(Base):
    """Liga un atleta al macrociclo, con su base aeróbica de partida."""
    __tablename__ = "athlete_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"), index=True)
    swimmer_id: Mapped[int] = mapped_column(ForeignKey("swimmers.id"), index=True)
    aerobic_base: Mapped[float | None] = mapped_column(Float)   # s/100m
    aerobic_base_source: Mapped[str | None] = mapped_column(String(12))  # t30|t15|css|manual

    plan: Mapped[Plan] = relationship(back_populates="athlete_plans")
    events: Mapped[list[AthleteEvent]] = relationship(
        back_populates="athlete_plan", cascade="all, delete-orphan",
        order_by="AthleteEvent.priority",
    )


class AthleteEvent(Base):
    """Prueba objetivo de un atleta dentro del plan (hasta 3 recomendadas)."""
    __tablename__ = "athlete_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_plan_id: Mapped[int] = mapped_column(ForeignKey("athlete_plans.id"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    distance: Mapped[int] = mapped_column(Integer)
    stroke: Mapped[str] = mapped_column(String(20))
    current_time: Mapped[float] = mapped_column(Float)   # segundos
    goal_time: Mapped[float] = mapped_column(Float)      # segundos

    athlete_plan: Mapped[AthletePlan] = relationship(back_populates="events")
    weeks: Mapped[list[WeeklyPlan]] = relationship(
        back_populates="event", cascade="all, delete-orphan",
        order_by="WeeklyPlan.week_number",
    )


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_event_id: Mapped[int] = mapped_column(ForeignKey("athlete_events.id"), index=True)
    week_number: Mapped[int] = mapped_column(Integer)
    week_date: Mapped[date] = mapped_column(Date)
    planned_km: Mapped[float] = mapped_column(Float)
    expected_time: Mapped[float] = mapped_column(Float)      # curva ideal original
    recalc_time: Mapped[float | None] = mapped_column(Float)  # curva recalculada
    real_time: Mapped[float | None] = mapped_column(Float)
    phase: Mapped[str] = mapped_column(String(60), default="")
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    disable_reason: Mapped[str | None] = mapped_column(String(200))

    event: Mapped[AthleteEvent] = relationship(back_populates="weeks")
