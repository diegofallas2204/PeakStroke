"""auditoria: el registro append-only y las vistas de PSAdmin (D0)

Tres cosas:

1. `auditoria` (un evento por fila) y `claves_de_auditoria` (la clave HMAC del
   periodo en curso; ver `app/core/anonimizacion.py`). Sin FKs: el rastro
   sobrevive a lo que describe.
2. **Triggers**: la base rechaza todo `UPDATE` sobre `auditoria` y todo `DELETE`
   de filas con menos de 24 meses (R11, 2026-09-24). Que sea la base y no el
   código es la diferencia entre "append-only" y "append-only mientras nadie se
   equivoque". En PostgreSQL además se rechaza `TRUNCATE`, que no dispara
   triggers de fila.
3. **Las vistas `v_admin_*`**, el ÚNICO contrato de lectura de PSAdmin. Ninguna
   lee tablas deportivas (`plans`, `aerobic_tests`, `resultados`, `sesiones`,
   `carga_diaria`…): `tests/test_auditoria_vistas.py` fija qué tablas lee y qué
   columnas expone cada una.

Revision ID: e3a9d0c41b7f
Revises: d921148a01ad
Create Date: 2026-09-24 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3a9d0c41b7f"
down_revision: str | Sequence[str] | None = "d921148a01ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copiados aquí y no importados de la app: una migración es una foto del
# momento. `TIPOS_DE_ACCESO` en `app/core/auditoria.py` es la otra mitad, y un
# test compara la vista con ese conjunto.
_TIPOS_DE_ACCESO = (
    "sesion.login", "sesion.refresh_reusado", "sesion.logout",
    "cuenta.password_cambiada", "dev.bypass",
)

_SQLITE_TRIGGERS = (
    """
    CREATE TRIGGER tr_auditoria_sin_update BEFORE UPDATE ON auditoria
    BEGIN
        SELECT RAISE(ABORT, 'auditoria es append-only: un evento no se modifica');
    END
    """,
    """
    CREATE TRIGGER tr_auditoria_retencion BEFORE DELETE ON auditoria
    WHEN OLD.occurred_at >= datetime('now', '-24 months')
    BEGIN
        SELECT RAISE(ABORT, 'auditoria: solo se borran eventos de mas de 24 meses');
    END
    """,
)

_PG_TRIGGERS = (
    """
    CREATE FUNCTION auditoria_append_only() RETURNS trigger AS $$
    BEGIN
        IF TG_OP = 'UPDATE' THEN
            RAISE EXCEPTION 'auditoria es append-only: un evento no se modifica';
        ELSIF TG_OP = 'TRUNCATE' THEN
            RAISE EXCEPTION 'auditoria es append-only: no se vacia';
        ELSIF OLD.occurred_at >= now() - interval '24 months' THEN
            RAISE EXCEPTION 'auditoria: solo se borran eventos de mas de 24 meses';
        END IF;
        RETURN OLD;
    END
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE TRIGGER tr_auditoria_append_only BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION auditoria_append_only()
    """,
    """
    CREATE TRIGGER tr_auditoria_sin_truncate BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION auditoria_append_only()
    """,
)

_VISTAS = {
    "v_admin_accesos": f"""
        SELECT id, occurred_at, event_type, outcome, actor_user_id, actor_email,
               team_id, ip_network, ip_hash, user_agent, detail
        FROM auditoria
        WHERE event_type IN ({", ".join(f"'{t}'" for t in _TIPOS_DE_ACCESO)})
    """,
    # Una fila por cuenta. `status` resume los cuatro estados que CLAUDE.md
    # distingue ("revocado ≠ sin equipo"), para que PSAdmin no tenga que
    # reconstruir la regla —y equivocarse— con las columnas sueltas.
    "v_admin_cuentas": """
        SELECT u.id AS user_id, u.email, u.name,
               u.is_active AS account_active, u.created_at, u.last_login_at,
               m.team_id, t.name AS team_name, m.role,
               m.is_active AS membership_active,
               CASE WHEN t.owner_id = u.id THEN 1 ELSE 0 END AS is_owner,
               CASE WHEN EXISTS (SELECT 1 FROM swimmers s WHERE s.user_id = u.id)
                    THEN 1 ELSE 0 END AS has_swimmer_profile,
               CASE WHEN NOT u.is_active THEN 'desactivada'
                    WHEN m.user_id IS NULL THEN 'sin_equipo'
                    WHEN NOT m.is_active THEN 'revocada'
                    ELSE 'activa' END AS status
        FROM users u
        LEFT JOIN team_members m ON m.user_id = u.id
        LEFT JOIN teams t ON t.id = m.team_id
    """,
    # Conteos de PERSONAS, no de trabajo deportivo: ni macrociclos ni tests.
    # Cuántos planes tiene un club ya dice cuánto entrena.
    "v_admin_equipos": """
        SELECT t.id AS team_id, t.name, t.created_at, o.email AS owner_email,
               (SELECT COUNT(*) FROM team_members m
                 WHERE m.team_id = t.id AND m.role = 'coach' AND m.is_active)
                   AS active_coaches,
               (SELECT COUNT(*) FROM team_members m
                 WHERE m.team_id = t.id AND m.role = 'athlete' AND m.is_active)
                   AS active_athletes,
               (SELECT COUNT(*) FROM team_members m
                 WHERE m.team_id = t.id AND NOT m.is_active) AS revoked_members,
               (SELECT COUNT(*) FROM swimmers s
                 WHERE s.team_id = t.id AND s.is_active) AS active_swimmer_profiles,
               (SELECT MAX(a.occurred_at) FROM auditoria a WHERE a.team_id = t.id)
                   AS last_activity_at
        FROM teams t
        LEFT JOIN users o ON o.id = t.owner_id
    """,
}


def upgrade() -> None:
    op.create_table(
        "auditoria",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("outcome", sa.String(length=5), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("target_type", sa.String(length=30), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("ip_network", sa.String(length=50), nullable=True),
        sa.Column("ip_hash", sa.String(length=32), nullable=True),
        sa.Column("user_agent", sa.String(length=60), nullable=True),
        sa.Column("detail", sa.String(length=200), nullable=False),
        sa.CheckConstraint("outcome IN ('ok', 'fallo')", name="ck_auditoria_outcome"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auditoria_occurred_at", "auditoria", ["occurred_at"])
    op.create_index("ix_auditoria_actor", "auditoria", ["actor_user_id", "occurred_at"])
    op.create_index("ix_auditoria_team", "auditoria", ["team_id", "occurred_at"])

    op.create_table(
        "claves_de_auditoria",
        sa.Column("period", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("key_hex", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("period"),
    )

    triggers = _SQLITE_TRIGGERS if op.get_bind().dialect.name == "sqlite" else _PG_TRIGGERS
    for ddl in triggers:
        op.execute(ddl)
    for nombre, cuerpo in _VISTAS.items():
        op.execute(f"CREATE VIEW {nombre} AS {cuerpo}")


def downgrade() -> None:
    for nombre in reversed(list(_VISTAS)):
        op.execute(f"DROP VIEW {nombre}")
    if op.get_bind().dialect.name != "sqlite":
        op.execute("DROP TRIGGER tr_auditoria_sin_truncate ON auditoria")
        op.execute("DROP TRIGGER tr_auditoria_append_only ON auditoria")
        op.execute("DROP FUNCTION auditoria_append_only()")
    # En SQLite los triggers caen con la tabla.
    op.drop_table("claves_de_auditoria")
    op.drop_index("ix_auditoria_team", table_name="auditoria")
    op.drop_index("ix_auditoria_actor", table_name="auditoria")
    op.drop_index("ix_auditoria_occurred_at", table_name="auditoria")
    op.drop_table("auditoria")
