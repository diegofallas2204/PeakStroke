"""Tabla del agregado Sesion: lo que el atleta nadó cada día (C7, §5.11).

Mismo patrón que `resultados` y `aerobic_tests`: FK compuesta al nadador contra
`(id, team_id)` —la frontera de equipo la impone el esquema, no una consulta— y
**ninguna** hacia el plan ni hacia la semana. El macrociclo y la semana en que
cae una sesión se derivan por fecha (ver `dominio.entidades.sesion`).

Solo columnas de HECHOS. El ritmo medio y la carga (sTSS) se calculan al leer;
guardarlos crearía dos números que se desincronizan en cuanto se corrige la
distancia o la duración.

**Se borra de verdad**, a diferencia de resultados y tests (decidido al
arrancar C7, 2026-09-23): es un registro que su dueño corrige, de él no cuelga
nada y la carga diaria de C8 se recalcula desde lo que haya.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SwimSession(Base):
    __tablename__ = "sesiones"
    __table_args__ = (
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_sesiones_swimmer_in_team",
        ),
        CheckConstraint("distance_m > 0", name="ck_sesiones_distance_positive"),
        CheckConstraint("duration_s > 0", name="ck_sesiones_duration_positive"),
        CheckConstraint(
            "rpe IS NULL OR (rpe >= 1 AND rpe <= 10)", name="ck_sesiones_rpe_cr10",
        ),
        # Cómo se lee siempre: las de un atleta en un rango de fechas.
        Index("ix_sesiones_swimmer_date", "swimmer_id", "session_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    swimmer_id: Mapped[int] = mapped_column(Integer)
    session_date: Mapped[date] = mapped_column(Date)
    distance_m: Mapped[int] = mapped_column(Integer)
    duration_s: Mapped[int] = mapped_column(Integer)    # total, descansos incluidos
    rpe: Mapped[int | None] = mapped_column(Integer)    # CR-10, 1..10
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
