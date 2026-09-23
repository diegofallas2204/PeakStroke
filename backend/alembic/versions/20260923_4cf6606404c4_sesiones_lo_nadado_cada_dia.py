"""sesiones: lo que el atleta nadó cada día (C7, §5.11)

Tabla nueva, sin datos que migrar. Cuelga del atleta con la FK compuesta
`(swimmer_id, team_id) → swimmers(id, team_id)`, como `resultados` y
`aerobic_tests`, y no apunta al plan ni a la semana: se encuentran por fecha.

Solo hechos —fecha, metros, duración total y RPE (CR-10)—. El ritmo medio y la
carga se derivan al leer. Es el sustrato del sTSS diario que necesita Banister
(C8).

Revision ID: 4cf6606404c4
Revises: c7a1e0d5b2f4
Create Date: 2026-09-23 19:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4cf6606404c4"
down_revision: str | Sequence[str] | None = "c7a1e0d5b2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sesiones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("swimmer_id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("rpe", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.CheckConstraint("distance_m > 0", name="ck_sesiones_distance_positive"),
        sa.CheckConstraint("duration_s > 0", name="ck_sesiones_duration_positive"),
        sa.CheckConstraint(
            "rpe IS NULL OR (rpe >= 1 AND rpe <= 10)", name="ck_sesiones_rpe_cr10",
        ),
        sa.ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_sesiones_swimmer_in_team",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_sesiones_team"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sesiones_team_id", "sesiones", ["team_id"])
    op.create_index("ix_sesiones_swimmer_date", "sesiones", ["swimmer_id", "session_date"])


def downgrade() -> None:
    op.drop_index("ix_sesiones_swimmer_date", table_name="sesiones")
    op.drop_index("ix_sesiones_team_id", table_name="sesiones")
    op.drop_table("sesiones")
