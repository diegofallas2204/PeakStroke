"""Tabla del agregado Resultado: los tiempos nadados, colgando del atleta.

Mismo patrón que `aerobic_tests`: FK compuesta al nadador contra
`(id, team_id)` y **ninguna** hacia el plan. Por eso ni sacar a alguien de un
macrociclo ni borrar el macrociclo pueden llevarse lo que nadó.

La competencia **agrupa, no posee** (§7.1): si el macro que la contiene se
borra, el resultado se queda y pierde la etiqueta (`SET NULL`).

`weekly_plans` no tiene FK hacia aquí, y es deliberado (R2 enmendada, §10.2): la
semana deriva sus resultados por atleta, prueba y fechas. `time` es lo que
marcó el reloj en `pool`; la conversión a otra piscina se hace al leer.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.persistencia.tablas import vocabulario as voc

CONTEXTOS: tuple[str, ...] = ("competencia", "control", "serie")
PISCINAS: tuple[str, ...] = ("50", "25")


class Result(Base):
    __tablename__ = "resultados"
    __table_args__ = (
        # Vocabularios cerrados (§7.2 fila 6, migración c9e1a4d7b2f6).
        voc.en("stroke", voc.ESTILOS, nombre="ck_resultados_stroke"),
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_resultados_swimmer_in_team",
        ),
        CheckConstraint(f"context IN {CONTEXTOS!r}", name="ck_resultados_context"),
        CheckConstraint(f"pool IN {PISCINAS!r}", name="ck_resultados_pool"),
        CheckConstraint("time > 0", name="ck_resultados_time_positive"),
        # Cómo se lee siempre: los de un atleta en un rango de fechas.
        Index("ix_resultados_swimmer_date", "swimmer_id", "result_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    swimmer_id: Mapped[int] = mapped_column(Integer)
    distance: Mapped[int] = mapped_column(Integer)
    stroke: Mapped[str] = mapped_column(String(20))
    time: Mapped[float] = mapped_column(Float)             # segundos nadados
    result_date: Mapped[date] = mapped_column(Date)
    pool: Mapped[str] = mapped_column(String(2))           # "50" | "25"
    context: Mapped[str] = mapped_column(
        String(12), default="control", server_default="control",
    )
    competition_id: Mapped[int | None] = mapped_column(
        ForeignKey("competitions.id", ondelete="SET NULL"), index=True,
    )
    # Tampoco se borran: se retiran. Corregir un tiempo mal tecleado es
    # retirarlo y apuntar otro, y el retirado sigue ahí para quien lo busque.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )
