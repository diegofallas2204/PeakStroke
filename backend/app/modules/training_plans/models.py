"""
training_plans/models.py — Modelos SQLAlchemy para macrociclos, atletas y plan semanal.

Tablas:
  macrocycles           — el plan de temporada del equipo
  macrocycle_phases     — fases configurables (Base/Construcción/Pico/Descenso)
  swimmers              — perfil del atleta (datos deportivos)
  athlete_macrocycles   — liga atleta ↔ macrociclo + base aeróbica
  athlete_events        — hasta 3 pruebas por atleta por macrociclo
  weekly_plans          — plan calculado semana × prueba, con curvas y zonas
  aerobic_tests         — test T-30 o T-15
  aerobic_test_splits   — parciales individuales del test
"""
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# Macrociclo
# ---------------------------------------------------------------------------

class Macrocycle(Base):
    __tablename__ = "macrocycles"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_weeks: Mapped[int] = mapped_column(Integer, nullable=False)
    microcycle_weeks: Mapped[int] = mapped_column(Integer, default=4)
    sessions_per_week: Mapped[int] = mapped_column(Integer, default=5)
    total_km: Mapped[float] = mapped_column(Float, nullable=False)
    progression_curve: Mapped[str] = mapped_column(
        Enum("linear", "exponential", "logarithmic", "sigmoid", name="curve_type"),
        default="sigmoid",
    )
    status: Mapped[str] = mapped_column(
        Enum("draft", "active", "finished", name="macrocycle_status"),
        default="active",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relaciones
    owner: Mapped["User"] = relationship("User", back_populates="macrocycles")  # type: ignore[name-defined]
    phases: Mapped[list["MacrocyclePhase"]] = relationship(
        "MacrocyclePhase", back_populates="macrocycle", cascade="all, delete-orphan"
    )
    athlete_macrocycles: Mapped[list["AthleteMacrocycle"]] = relationship(
        "AthleteMacrocycle", back_populates="macrocycle", cascade="all, delete-orphan"
    )


class MacrocyclePhase(Base):
    __tablename__ = "macrocycle_phases"
    __table_args__ = (UniqueConstraint("macrocycle_id", "week_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    macrocycle_id: Mapped[int] = mapped_column(
        ForeignKey("macrocycles.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    week_start: Mapped[int] = mapped_column(Integer, nullable=False)
    week_end: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    macrocycle: Mapped[Macrocycle] = relationship("Macrocycle", back_populates="phases")


# ---------------------------------------------------------------------------
# Atletas
# ---------------------------------------------------------------------------

class Swimmer(Base):
    __tablename__ = "swimmers"

    id: Mapped[int] = mapped_column(primary_key=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(
        Enum("M", "F", "X", name="gender_type"), nullable=True
    )
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    athlete_macrocycles: Mapped[list["AthleteMacrocycle"]] = relationship(
        "AthleteMacrocycle", back_populates="swimmer", cascade="all, delete-orphan"
    )
    aerobic_tests: Mapped[list["AerobicTest"]] = relationship(
        "AerobicTest", back_populates="swimmer", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Relación atleta ↔ macrociclo
# ---------------------------------------------------------------------------

class AthleteMacrocycle(Base):
    __tablename__ = "athlete_macrocycles"
    __table_args__ = (UniqueConstraint("swimmer_id", "macrocycle_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    swimmer_id: Mapped[int] = mapped_column(
        ForeignKey("swimmers.id", ondelete="CASCADE"), nullable=False
    )
    macrocycle_id: Mapped[int] = mapped_column(
        ForeignKey("macrocycles.id", ondelete="CASCADE"), nullable=False
    )
    aerobic_base: Mapped[float | None] = mapped_column(Float, nullable=True)
    aerobic_base_source: Mapped[str | None] = mapped_column(
        Enum("T30", "T15", "manual", name="aerobic_source"), nullable=True
    )
    aerobic_test_id: Mapped[int | None] = mapped_column(
        ForeignKey("aerobic_tests.id"), nullable=True
    )

    swimmer: Mapped[Swimmer] = relationship("Swimmer", back_populates="athlete_macrocycles")
    macrocycle: Mapped[Macrocycle] = relationship(
        "Macrocycle", back_populates="athlete_macrocycles"
    )
    events: Mapped[list["AthleteEvent"]] = relationship(
        "AthleteEvent", back_populates="athlete_macrocycle", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Pruebas del atleta en el macrociclo (hasta 3)
# ---------------------------------------------------------------------------

class AthleteEvent(Base):
    __tablename__ = "athlete_events"
    __table_args__ = (UniqueConstraint("athlete_macrocycle_id", "priority"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_macrocycle_id: Mapped[int] = mapped_column(
        ForeignKey("athlete_macrocycles.id", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, o 3
    distance: Mapped[int] = mapped_column(Integer, nullable=False)  # metros
    stroke: Mapped[str] = mapped_column(
        Enum("libre", "espalda", "mariposa", "pecho", "combinado", name="stroke_type"),
        nullable=False,
    )
    current_time: Mapped[float] = mapped_column(Float, nullable=False)  # segundos
    goal_time: Mapped[float] = mapped_column(Float, nullable=False)     # segundos
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    athlete_macrocycle: Mapped[AthleteMacrocycle] = relationship(
        "AthleteMacrocycle", back_populates="events"
    )
    weekly_plans: Mapped[list["WeeklyPlan"]] = relationship(
        "WeeklyPlan", back_populates="athlete_event", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Plan semanal
# ---------------------------------------------------------------------------

class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"
    __table_args__ = (UniqueConstraint("athlete_event_id", "week_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    athlete_event_id: Mapped[int] = mapped_column(
        ForeignKey("athlete_events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    week_date: Mapped[date] = mapped_column(Date, nullable=False)  # lunes de esa semana

    # Curva ideal (calculada al crear el macrociclo)
    planned_km: Mapped[float | None] = mapped_column(Float)
    expected_time: Mapped[float | None] = mapped_column(Float)       # segundos
    pace_100m: Mapped[float | None] = mapped_column(Float)

    # Curva recalculada (redistribuye mejora restante sobre semanas activas)
    expected_time_recalc: Mapped[float | None] = mapped_column(Float)
    pace_100m_recalc: Mapped[float | None] = mapped_column(Float)

    # Zonas de entrenamiento (pace_100m por zona)
    zone_r1: Mapped[float | None] = mapped_column(Float)
    zone_r2: Mapped[float | None] = mapped_column(Float)
    zone_mvo2: Mapped[float | None] = mapped_column(Float)
    zone_rl: Mapped[float | None] = mapped_column(Float)
    zone_v: Mapped[float | None] = mapped_column(Float)

    # Registro real (entrada del entrenador semana a semana)
    real_time: Mapped[float | None] = mapped_column(Float)
    real_km: Mapped[float | None] = mapped_column(Float)

    # Control de parón
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    disable_reason: Mapped[str | None] = mapped_column(
        Enum("lesion", "vacaciones", "otro", name="disable_reason_type"), nullable=True
    )

    # Metadatos calculados
    phase_name: Mapped[str | None] = mapped_column(String(100))
    feasibility: Mapped[str | None] = mapped_column(
        Enum("ok", "warning", "aggressive", name="feasibility_type"), nullable=True
    )

    athlete_event: Mapped[AthleteEvent] = relationship(
        "AthleteEvent", back_populates="weekly_plans"
    )


# ---------------------------------------------------------------------------
# Tests aeróbicos (T-30 / T-15)
# ---------------------------------------------------------------------------

class AerobicTest(Base):
    __tablename__ = "aerobic_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    swimmer_id: Mapped[int] = mapped_column(
        ForeignKey("swimmers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    macrocycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("macrocycles.id"), nullable=True
    )
    test_type: Mapped[str] = mapped_column(
        Enum("T30", "T15", name="test_type"), nullable=False
    )
    test_date: Mapped[date] = mapped_column(Date, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_time: Mapped[float | None] = mapped_column(Float)
    std_dev: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    swimmer: Mapped[Swimmer] = relationship("Swimmer", back_populates="aerobic_tests")
    splits: Mapped[list["AerobicTestSplit"]] = relationship(
        "AerobicTestSplit", back_populates="test", cascade="all, delete-orphan"
    )


class AerobicTestSplit(Base):
    __tablename__ = "aerobic_test_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    aerobic_test_id: Mapped[int] = mapped_column(
        ForeignKey("aerobic_tests.id", ondelete="CASCADE"), nullable=False
    )
    rep_number: Mapped[int] = mapped_column(Integer, nullable=False)
    split_time: Mapped[float] = mapped_column(Float, nullable=False)  # segundos

    test: Mapped[AerobicTest] = relationship("AerobicTest", back_populates="splits")
