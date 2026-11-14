"""lactate_tests y lactate_test_reps: el test de lactato (notas 26 y 28 del vault)

Dos tablas nuevas y nada más: no toca `aerobic_tests`, a propósito. El ritmo de
un test de lactato no es una base aeróbica, y todo lo que lee aquella tabla —la
base por defecto al inscribir, el CSS de la carga— lo tomaría por una.

Los CHECK llevan su propia copia de los vocabularios (una migración es una foto
del momento); `tests/test_lactato_api.py` la compara con el dominio.

Revision ID: a7d3e5f1c9b4
Revises: f4c2a9d7e1b3
Create Date: 2026-11-13 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d3e5f1c9b4"
down_revision: str | Sequence[str] | None = "f4c2a9d7e1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (columna, valores, admite NULL)
CHECKS: tuple[tuple[str, tuple[str, ...], bool], ...] = (
    ("mode", ("control", "escalonado"), False),
    ("target_zone", ("R1", "R2", "MVO2", "RL", "V"), False),
    ("rest_type", ("pausa", "salida"), True),
    ("sample_site", ("dedo", "lobulo"), True),
    ("hr_method", ("banda", "palpacion", "optico"), True),
)


def _check(columna: str, valores: tuple[str, ...], nulo: bool) -> sa.CheckConstraint:
    lista = ", ".join(f"'{v}'" for v in valores)
    dentro = f"{columna} IN ({lista})"
    return sa.CheckConstraint(
        f"{columna} IS NULL OR {dentro}" if nulo else dentro,
        name=f"ck_lactate_tests_{columna}",
    )


def upgrade() -> None:
    op.create_table(
        "lactate_tests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("swimmer_id", sa.Integer(), nullable=False),
        sa.Column("test_date", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(length=12), nullable=False),
        sa.Column("target_zone", sa.String(length=6), nullable=False),
        sa.Column("rep_distance", sa.Integer(), nullable=False),
        sa.Column("rest_type", sa.String(length=8), nullable=True),
        sa.Column("rest_s", sa.Float(), nullable=True),
        sa.Column("proposed_min", sa.Float(), nullable=True),
        sa.Column("proposed_max", sa.Float(), nullable=True),
        sa.Column("reference_time", sa.Float(), nullable=True),
        sa.Column("counted_segment_m", sa.Integer(), nullable=True),
        sa.Column("sample_site", sa.String(length=8), nullable=True),
        sa.Column("analyzer", sa.String(length=60), nullable=True),
        sa.Column("sample_minute", sa.Float(), nullable=True),
        sa.Column("hr_method", sa.String(length=12), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_lactate_tests_team_id_teams"),
        sa.ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_lactate_tests_swimmer_in_team",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lactate_tests"),
        *(_check(c, v, n) for c, v, n in CHECKS),
    )
    with op.batch_alter_table("lactate_tests") as batch_op:
        batch_op.create_index("ix_lactate_tests_team_id", ["team_id"])
        batch_op.create_index("ix_lactate_tests_swimmer_id", ["swimmer_id"])
        batch_op.create_index("ix_lactate_tests_is_active", ["is_active"])

    op.create_table(
        "lactate_test_reps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("rep_number", sa.Integer(), nullable=False),
        sa.Column("swim_time", sa.Float(), nullable=False),
        sa.Column("lactate", sa.Float(), nullable=True),
        sa.Column("heart_rate", sa.Integer(), nullable=True),
        sa.Column("effort", sa.Float(), nullable=True),
        sa.Column("stroke_counts", sa.JSON(), nullable=True),
        sa.Column("segment_time", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["test_id"], ["lactate_tests.id"], ondelete="CASCADE",
            name="fk_lactate_test_reps_test_id_lactate_tests",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lactate_test_reps"),
        sa.UniqueConstraint("test_id", "rep_number", name="uq_lactate_test_reps_rep"),
    )
    with op.batch_alter_table("lactate_test_reps") as batch_op:
        batch_op.create_index("ix_lactate_test_reps_test_id", ["test_id"])


def downgrade() -> None:
    op.drop_table("lactate_test_reps")
    op.drop_table("lactate_tests")
