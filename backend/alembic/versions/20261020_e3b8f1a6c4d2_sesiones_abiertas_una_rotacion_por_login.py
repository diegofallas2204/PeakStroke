"""sesiones_abiertas: una rotación del refresh por login, no por cuenta (TODO-30)

`users.refresh_rotation` era una por cuenta: entrar en el móvil gastaba la cookie
del portátil, y su siguiente refresh se cortaba como robo. Ahora cada login abre
una fila de `sesiones_abiertas` con su propia rotación, y el token lleva su id.

**Subir no copia rotaciones.** Los tokens emitidos antes no llevan `sid` y dejan
de valer: todo el que tuviera sesión vuelve a entrar. Hoy nadie la tiene —el
frontend no tiene login—, y una fila inventada para cada cuenta no sería la
sesión de ningún dispositivo. **Bajar** devuelve la columna en 0 y borra la
tabla: los tokens con `sid` no llevan la rotación de la cuenta, así que también
se vuelve a entrar.

**En SQLite, `legacy_alter_table` mientras dura el modo batch**, como en
`c9e1a4d7b2f6`: batch copia `users` a `_alembic_tmp_users` y la renombra, y un
SQLite moderno valida en ese `RENAME` las vistas que la nombran
(`v_admin_cuentas`, `v_admin_accesos`…), que en ese instante no la encuentran.
En PostgreSQL es un `ALTER TABLE ... DROP COLUMN` y no hay copia.

Revision ID: e3b8f1a6c4d2
Revises: d1a7c3e9f5b2
Create Date: 2026-10-20 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3b8f1a6c4d2"
down_revision: str | Sequence[str] | None = "d1a7c3e9f5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _modo_heredado(activo: bool) -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"PRAGMA legacy_alter_table = {'ON' if activo else 'OFF'}")


def upgrade() -> None:
    op.create_table(
        "sesiones_abiertas",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_rotation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"),
                  nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sesiones_abiertas_user_id", "sesiones_abiertas", ["user_id"])
    op.create_index("ix_sesiones_abiertas_expires_at", "sesiones_abiertas", ["expires_at"])

    _modo_heredado(True)
    try:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("refresh_rotation")
    finally:
        _modo_heredado(False)


def downgrade() -> None:
    _modo_heredado(True)
    try:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("refresh_rotation", sa.Integer(), server_default="0", nullable=False),
            )
    finally:
        _modo_heredado(False)
    op.drop_index("ix_sesiones_abiertas_expires_at", table_name="sesiones_abiertas")
    op.drop_index("ix_sesiones_abiertas_user_id", table_name="sesiones_abiertas")
    op.drop_table("sesiones_abiertas")
