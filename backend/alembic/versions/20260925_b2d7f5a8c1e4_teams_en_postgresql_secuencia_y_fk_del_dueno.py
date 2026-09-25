"""teams en PostgreSQL: la secuencia de `id` y la FK «el dueño es miembro»

Dos agujeros de la migración inicial (`40f8ce1d3750`) que solo existían en
PostgreSQL, y los dos por lo mismo: `teams.id` forma parte de la FK compuesta
`fk_teams_owner_is_member`. Se descubrieron el 2026-09-25, la primera vez que
la cadena de migraciones y `seed.py` corrieron enteros contra PostgreSQL (al
probar D0).

1. **`teams.id` no tenía secuencia**: en PostgreSQL no se podía crear ningún
   equipo («null value in column id»). Al ver `id` dentro de una FK, SQLAlchemy
   deja de tratarlo como autoincremental; el modelo lo corrige con
   `autoincrement=True` (ver `persistencia/tablas/equipos.py`), pero la
   migración inicial no lo llevaba. SQLite no lo nota: ahí toda clave primaria
   entera es autoincremental.
2. **`fk_teams_owner_is_member` no existía**: va declarada con `use_alter=True`
   dentro de `op.create_table`. SQLite la escribe dentro del `CREATE TABLE`;
   PostgreSQL la omite para añadirla después con un `ALTER TABLE` que
   `op.create_table` nunca emite. Nada impedía que el dueño de un equipo no
   fuera miembro de él — una invariante de aislamiento de CLAUDE.md.

En SQLite no hace nada: las dos cosas ya están, y SQLite tampoco sabría
añadirlas con un `ALTER`.

Revision ID: b2d7f5a8c1e4
Revises: f4b8e1c2a9d3
Create Date: 2026-09-25 10:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d7f5a8c1e4"
down_revision: str | Sequence[str] | None = "f4b8e1c2a9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _es_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    if _es_sqlite():
        return
    op.execute("CREATE SEQUENCE teams_id_seq OWNED BY teams.id")
    op.execute("ALTER TABLE teams ALTER COLUMN id SET DEFAULT nextval('teams_id_seq')")
    # Si ya hay equipos (creados a mano con su id), la secuencia arranca detrás.
    op.execute("SELECT setval('teams_id_seq', COALESCE(MAX(id), 0) + 1, false) FROM teams")
    op.create_foreign_key(
        "fk_teams_owner_is_member", "teams", "team_members",
        ["id", "owner_id"], ["team_id", "user_id"],
    )


def downgrade() -> None:
    if _es_sqlite():
        return
    op.drop_constraint("fk_teams_owner_is_member", "teams", type_="foreignkey")
    op.execute("ALTER TABLE teams ALTER COLUMN id DROP DEFAULT")
    op.execute("DROP SEQUENCE teams_id_seq")
