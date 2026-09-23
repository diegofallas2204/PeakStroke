"""carga_diaria: la serie de Banister de cada atleta, materializada (C8, §5.12)

Un DERIVADO de `sesiones` y `aerobic_tests`: sTSS del día, CTL y ATL (el TSB es
su resta y no se guarda). Clave primaria `(swimmer_id, load_date)`, que es
también el índice por el que se lee.

**La migración no la rellena.** Calcularla es ciencia de `app.dominio`, y una
migración no importa la aplicación (es una foto del momento, ver
`a3f1c2d4e5b6`). Si al subir ya hay sesiones, avisa, y
`python tools/recalcular_carga.py` la reconstruye entera; a partir de ahí la
mantienen al día las escrituras de sesiones y tests.

Revision ID: d921148a01ad
Revises: 4cf6606404c4
Create Date: 2026-09-23 21:00:00.000000

"""
import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d921148a01ad"
down_revision: str | Sequence[str] | None = "4cf6606404c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    op.create_table(
        "carga_diaria",
        sa.Column("swimmer_id", sa.Integer(), nullable=False),
        sa.Column("load_date", sa.Date(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("stss", sa.Float(), nullable=False),
        sa.Column("ctl", sa.Float(), nullable=False),
        sa.Column("atl", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_carga_diaria_swimmer_in_team",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_carga_diaria_team"),
        sa.PrimaryKeyConstraint("swimmer_id", "load_date"),
    )
    op.create_index("ix_carga_diaria_team_id", "carga_diaria", ["team_id"])

    sesiones = op.get_bind().execute(sa.text("SELECT count(*) FROM sesiones")).scalar_one()
    if sesiones:
        _log.warning(
            "C8: hay %d sesiones y carga_diaria está vacía. "
            "Reconstrúyela con `python tools/recalcular_carga.py`.", sesiones,
        )


def downgrade() -> None:
    op.drop_index("ix_carga_diaria_team_id", table_name="carga_diaria")
    op.drop_table("carga_diaria")
