"""Modelos de tests aeróbicos (T-30, T-15, personalizado, CSS, directo)."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AerobicTest(Base):
    __tablename__ = "aerobic_tests"
    __table_args__ = (
        # Nadador y macrociclo, del mismo equipo que el test. Con plan_id a NULL
        # (test suelto, sin macrociclo) la segunda constraint no se evalúa.
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_aerobic_tests_swimmer_in_team",
        ),
        ForeignKeyConstraint(
            ["plan_id", "team_id"], ["plans.id", "plans.team_id"],
            name="fk_aerobic_tests_plan_in_team",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    swimmer_id: Mapped[int] = mapped_column(Integer, index=True)
    plan_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # T30 | T15 | CUSTOM | CSS | DIRECT
    test_type: Mapped[str] = mapped_column(String(12))
    test_date: Mapped[date] = mapped_column(Date)
    rep_count: Mapped[int | None] = mapped_column(Integer)
    rep_distance: Mapped[int | None] = mapped_column(Integer)
    # Intervalo de salida del test, en segundos. Sin él solo se sabe a qué ritmo
    # nadó el atleta, no cada cuánto salía — y esa es la mitad que define el
    # estímulo. Nullable porque los tests anteriores al 2026-08-10 no lo tienen.
    send_off: Mapped[float | None] = mapped_column(Float)
    # Cómo hay que leer los números que apuntó el entrenador: `rep` = tiempo
    # nadado, `clock` = llegada acumulada en el reloj de pared. Se guarda porque
    # es el dato que hace reproducible el análisis: con las llegadas y sin el
    # modo, los mismos números significan dos cosas distintas.
    input_mode: Mapped[str] = mapped_column(
        String(8), default="rep", server_default="rep",
    )
    avg_per100: Mapped[float] = mapped_column(Float)            # base aeróbica s/100m
    std_dev: Mapped[float | None] = mapped_column(Float)
    trend: Mapped[str | None] = mapped_column(String(12))       # improving|stable|declining
    css_ms: Mapped[float | None] = mapped_column(Float)         # solo tests CSS
    notes: Mapped[str | None] = mapped_column(Text)
    # Los tests aeróbicos tampoco se borran: se dan de baja, igual que los
    # nadadores. El docstring de `swimmers.set_active` llama al histórico de
    # entrenamiento "el activo más valioso de la aplicación" y nombra estos
    # tests dentro de él; hasta el 2026-08-06 un clic en DELETE lo evaporaba.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    splits: Mapped[list[AerobicSplit]] = relationship(
        back_populates="test", cascade="all, delete-orphan",
        order_by="AerobicSplit.rep_number",
    )


class AerobicSplit(Base):
    __tablename__ = "aerobic_test_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(
        ForeignKey("aerobic_tests.id", ondelete="CASCADE"), index=True,
    )
    rep_number: Mapped[int] = mapped_column(Integer)
    split_time: Mapped[float] = mapped_column(Float)            # tiempo de la repetición
    # Segundo en que ARRANCA la repetición, contado desde el inicio del test.
    # `split_time` siempre fue el tiempo nadado; lo que faltaba era desde cuándo.
    # Con los dos, la llegada es la suma y el descanso hasta la siguiente sale
    # solo — que es lo que el entrenador necesita para prescribir. Nullable: los
    # tests guardados sin intervalo de salida no lo pueden saber a posteriori.
    send_off_time: Mapped[float | None] = mapped_column(Float)

    test: Mapped[AerobicTest] = relationship(back_populates="splits")

    @property
    def arrival_time(self) -> float | None:
        """Lo que marcaba el reloj de pared al tocar la pared."""
        if self.send_off_time is None:
            return None
        return round(self.send_off_time + self.split_time, 2)
