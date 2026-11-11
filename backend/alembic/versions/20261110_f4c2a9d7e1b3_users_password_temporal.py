"""users.password_temporal: la contraseña temporal obliga a cambiarse (TODO-27)

Quien da de alta a otro —el entrenador que invita, el operador que restablece—
ve la contraseña que genera el sistema. Hasta ahora valía para siempre. La
columna marca la cuenta cuya contraseña es una de esas; mientras esté puesta, el
API solo la deja cambiarla.

**Subir deja a todas las cuentas sin marca.** No hay forma de saber cuáles de
las que ya existen siguen con su temporal: lo que se guarda es el hash. Las que
se quieran forzar, con `tools/ops.py restablecer-password`.

`ADD COLUMN` a secas, sin modo batch: SQLite lo hace sin copiar la tabla, así
que las vistas `v_admin_*` que nombran `users` no se enteran (lo que obligó a
`legacy_alter_table` en `e3b8f1a6c4d2`). Al bajar, `DROP COLUMN` tampoco copia
(SQLite >= 3.35) y ninguna vista ni índice nombra la columna.

Revision ID: f4c2a9d7e1b3
Revises: e3b8f1a6c4d2
Create Date: 2026-11-10 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4c2a9d7e1b3"
down_revision: str | Sequence[str] | None = "e3b8f1a6c4d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_temporal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "password_temporal")
