"""Modelos del módulo plans: macrociclo, fases, competencias, atletas y semanas.

Las FKs de composición llevan `ondelete="CASCADE"` para que la base de datos
mantenga la misma regla que el ORM: borrar un macrociclo se lleva sus fases,
competencias e inscripciones. Lo que NO es composición (un nadador, una cuenta)
usa el comportamiento por defecto, que impide borrar mientras algo lo referencie.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        # Clave candidata para las FKs compuestas de todo lo que cuelga del plan.
        UniqueConstraint("id", "team_id", name="uq_plans_id_team"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # El macrociclo vive dentro de un equipo. Qué entrenadores lo llevan está en
    # `plan_coaches`; qué atletas, en `athlete_plans`.
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    start_date: Mapped[date] = mapped_column(Date)
    total_weeks: Mapped[int] = mapped_column(Integer)          # 12..18
    weeks_per_micro: Mapped[int] = mapped_column(Integer, default=4)
    total_km: Mapped[float] = mapped_column(Float)
    progression_curve: Mapped[str] = mapped_column(String(20), default="science")
    pool: Mapped[str] = mapped_column(String(2), default="50")  # "50" larga | "25" corta
    n_mac: Mapped[int] = mapped_column(Integer, default=1)      # número de macrociclo (1=primero)
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
    coaches: Mapped[list[PlanCoach]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class PlanCoach(Base):
    """Entrenadores a cargo del macrociclo.

    Decide quién lo VE y quién lo edita: un entrenador del equipo que no esté
    aquí no accede al plan. La excepción es el dueño del equipo, que llega a
    todos — si no, los macrociclos de un entrenador que se va quedarían sin nadie
    capaz de recuperarlos.
    """
    __tablename__ = "plan_coaches"
    __table_args__ = (
        UniqueConstraint("plan_id", "coach_id", name="uq_plan_coaches_pair"),
        # Plan y entrenador, del mismo equipo. Impuesto por la base de datos.
        ForeignKeyConstraint(
            ["plan_id", "team_id"], ["plans.id", "plans.team_id"],
            name="fk_plan_coaches_plan_in_team", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["coach_id", "team_id"], ["team_members.user_id", "team_members.team_id"],
            name="fk_plan_coaches_coach_in_team", ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    plan_id: Mapped[int] = mapped_column(Integer, index=True)
    coach_id: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan: Mapped[Plan] = relationship(back_populates="coaches")


class PlanPhase(Base):
    __tablename__ = "plan_phases"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True,
    )
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
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True,
    )
    name: Mapped[str] = mapped_column(String(120))
    week_number: Mapped[int] = mapped_column(Integer)
    days: Mapped[int] = mapped_column(Integer, default=1)
    is_main: Mapped[bool] = mapped_column(Boolean, default=False)

    plan: Mapped[Plan] = relationship(back_populates="competitions")


class AthletePlan(Base):
    """Liga un atleta al macrociclo, con su base aeróbica de partida."""
    __tablename__ = "athlete_plans"
    __table_args__ = (
        # Un atleta no puede estar dos veces inscrito en el mismo macrociclo.
        UniqueConstraint("plan_id", "swimmer_id", name="uq_athlete_plans_pair"),
        ForeignKeyConstraint(
            ["plan_id", "team_id"], ["plans.id", "plans.team_id"],
            name="fk_athlete_plans_plan_in_team", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_athlete_plans_swimmer_in_team",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    plan_id: Mapped[int] = mapped_column(Integer, index=True)
    swimmer_id: Mapped[int] = mapped_column(Integer, index=True)
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
    athlete_plan_id: Mapped[int] = mapped_column(
        ForeignKey("athlete_plans.id", ondelete="CASCADE"), index=True,
    )
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
    __table_args__ = (
        UniqueConstraint("athlete_event_id", "week_number", name="uq_weekly_plans_event_week"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_event_id: Mapped[int] = mapped_column(
        ForeignKey("athlete_events.id", ondelete="CASCADE"), index=True,
    )
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
