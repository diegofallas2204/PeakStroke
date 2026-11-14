"""El test de lactato: una serie con lactato, FC, esfuerzo y brazadas por repetición.

**Tabla aparte de `aerobic_tests`, a propósito** (ver la entidad,
`dominio/entidades/test_de_lactato.py`): su ritmo no es una base aeróbica, y
todo lo que lee `aerobic_tests` —la base por defecto al inscribir, el CSS de la
carga— lo tomaría por una. Aquí no hay `avg_per100`: lo derivado no se guarda,
se calcula al leer (`api/v1/tests/lactato_service`).

Lactato y FC son datos de salud: la segunda frontera (el atleta ve solo lo suyo)
la aplica `repositorios/tests_de_lactato.py`.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.persistencia.tablas import vocabulario as voc


class LactateTest(Base):
    __tablename__ = "lactate_tests"
    __table_args__ = (
        voc.en("mode", voc.MODOS_DE_LACTATO, nombre="ck_lactate_tests_mode"),
        voc.en("target_zone", voc.ZONAS, nombre="ck_lactate_tests_target_zone"),
        voc.en("rest_type", voc.TIPOS_DE_DESCANSO, nombre="ck_lactate_tests_rest_type", nulo=True),
        voc.en("sample_site", voc.SITIOS_DE_MUESTRA, nombre="ck_lactate_tests_sample_site", nulo=True),
        voc.en("hr_method", voc.METODOS_DE_FC, nombre="ck_lactate_tests_hr_method", nulo=True),
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_lactate_tests_swimmer_in_team",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    swimmer_id: Mapped[int] = mapped_column(Integer, index=True)
    test_date: Mapped[date] = mapped_column(Date)
    mode: Mapped[str] = mapped_column(String(12))                  # control | escalonado
    target_zone: Mapped[str] = mapped_column(String(6))            # R1 … V
    rep_distance: Mapped[int] = mapped_column(Integer)
    rest_type: Mapped[str | None] = mapped_column(String(8))       # pausa | salida
    rest_s: Mapped[float | None] = mapped_column(Float)
    proposed_min: Mapped[float | None] = mapped_column(Float)      # tiempo propuesto, s
    proposed_max: Mapped[float | None] = mapped_column(Float)
    # Su mejor marca en la distancia de la repetición: de ahí el «% del mejor».
    reference_time: Mapped[float | None] = mapped_column(Float)
    # Metros del tramo en que se cuentan las brazadas (el 2.º 50 de cada 100 → 50).
    counted_segment_m: Mapped[int | None] = mapped_column(Integer)
    sample_site: Mapped[str | None] = mapped_column(String(8))     # dedo | lobulo
    analyzer: Mapped[str | None] = mapped_column(String(60))
    sample_minute: Mapped[float | None] = mapped_column(Float)     # minuto tras la repetición
    hr_method: Mapped[str | None] = mapped_column(String(12))      # banda | palpacion | optico
    notes: Mapped[str | None] = mapped_column(Text)
    # Se da de baja, no se borra: la medición no se puede rehacer.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    reps: Mapped[list[LactateRep]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="LactateRep.rep_number",
    )


class LactateRep(Base):
    __tablename__ = "lactate_test_reps"
    __table_args__ = (UniqueConstraint("test_id", "rep_number", name="uq_lactate_test_reps_rep"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    test_id: Mapped[int] = mapped_column(
        ForeignKey("lactate_tests.id", ondelete="CASCADE"), index=True,
    )
    rep_number: Mapped[int] = mapped_column(Integer)
    swim_time: Mapped[float] = mapped_column(Float)                # SIEMPRE tiempo nadado
    lactate: Mapped[float | None] = mapped_column(Float)           # mmol/L
    heart_rate: Mapped[int | None] = mapped_column(Integer)        # lat/min
    effort: Mapped[float | None] = mapped_column(Float)            # CR-10
    stroke_counts: Mapped[list[int] | None] = mapped_column(JSON)  # conteos del tramo
    segment_time: Mapped[float | None] = mapped_column(Float)      # tiempo del tramo contado

    test: Mapped[LactateTest] = relationship(back_populates="reps")
