"""Tabla `carga_diaria`: la serie de Banister de cada atleta, materializada (C8).

**Es un DERIVADO, no un hecho.** Todo lo que guarda sale de `sesiones` y
`aerobic_tests` con `dominio.servicios.banister`, y nadie la edita. Se guarda por
una razón de escala: las lecturas (tableros, tabla del equipo) son muchas y las
escrituras (una sesión al día por atleta) pocas. Leída, la curva es un rango por
clave primaria; calculada, cada lectura recorrería toda la historia del atleta.

**Por qué no puede quedarse mintiendo** —que es el riesgo de guardar un
derivado—: la escriben **solo** `persistencia/repositorios/carga.recalcular`, y
la llaman, dentro de la MISMA transacción que el cambio, las únicas escrituras
que la alteran (guardar o borrar una sesión; dar de alta o de baja un test).
`tests/test_carga.py` comprueba que la tabla coincide con el cálculo desde cero
tras cualquier secuencia de escrituras.

Una fila por atleta y día, **también los de carga 0**, desde el primer día con
carga hasta el último. Lo que va después (hasta hoy) no se guarda: sin carga,
CTL y ATL solo decaen, y eso se calcula al leer.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, ForeignKeyConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DailyLoad(Base):
    __tablename__ = "carga_diaria"
    __table_args__ = (
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_carga_diaria_swimmer_in_team",
        ),
    )

    # La clave primaria ES el índice de lectura: (atleta, rango de fechas).
    swimmer_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    load_date: Mapped[date] = mapped_column(Date, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    stss: Mapped[float] = mapped_column(Float)
    ctl: Mapped[float] = mapped_column(Float)
    atl: Mapped[float] = mapped_column(Float)
    # TSB no se guarda: es CTL − ATL, y una tercera columna podría discrepar.
