"""El test de lactato según la plantilla del entrenador (Tabla Medición)

Lo que la plantilla tiene y la v1 no: en la cabecera, la técnica (estilo), la
piscina y la intensidad propuesta («Intens. Pro», % de su mejor marca); por
repetición, la serie y los parciales; y el bloque de recuperación (minuto, FC y
lactato después de la serie), que va en su propia tabla.

Todo admite NULL: la hoja real deja columnas enteras sin llenar. `lactate_tests`
se recrea en modo batch (SQLite no añade un CHECK con `ADD COLUMN`); ninguna
vista la nombra. No se toca `a7d3e5f1c9b4`, que ya está aplicada.

Revision ID: b8e4f2a6d1c3
Revises: a7d3e5f1c9b4
Create Date: 2026-11-16 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8e4f2a6d1c3"
down_revision: str | Sequence[str] | None = "a7d3e5f1c9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTILOS = ("libre", "espalda", "pecho", "mariposa", "combinado")


def upgrade() -> None:
    with op.batch_alter_table("lactate_tests") as batch_op:
        batch_op.add_column(sa.Column("stroke", sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column("pool_length", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("proposed_intensity_min", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("proposed_intensity_max", sa.Float(), nullable=True))
        lista = ", ".join(f"'{e}'" for e in ESTILOS)
        batch_op.create_check_constraint(
            "ck_lactate_tests_stroke", f"stroke IS NULL OR stroke IN ({lista})",
        )
        batch_op.create_check_constraint(
            "ck_lactate_tests_pool_length", "pool_length IS NULL OR pool_length IN (25, 50)",
        )

    with op.batch_alter_table("lactate_test_reps") as batch_op:
        batch_op.add_column(sa.Column("series", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("splits", sa.JSON(), nullable=True))

    op.create_table(
        "lactate_recovery",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Float(), nullable=False),
        sa.Column("heart_rate", sa.Integer(), nullable=True),
        sa.Column("lactate", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["test_id"], ["lactate_tests.id"], ondelete="CASCADE",
            name="fk_lactate_recovery_test_id_lactate_tests",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lactate_recovery"),
        sa.UniqueConstraint("test_id", "minute", name="uq_lactate_recovery_minute"),
    )
    with op.batch_alter_table("lactate_recovery") as batch_op:
        batch_op.create_index("ix_lactate_recovery_test_id", ["test_id"])


def downgrade() -> None:
    op.drop_table("lactate_recovery")
    with op.batch_alter_table("lactate_test_reps") as batch_op:
        batch_op.drop_column("splits")
        batch_op.drop_column("series")
    with op.batch_alter_table("lactate_tests") as batch_op:
        batch_op.drop_constraint("ck_lactate_tests_pool_length", type_="check")
        batch_op.drop_constraint("ck_lactate_tests_stroke", type_="check")
        batch_op.drop_column("proposed_intensity_max")
        batch_op.drop_column("proposed_intensity_min")
        batch_op.drop_column("pool_length")
        batch_op.drop_column("stroke")
