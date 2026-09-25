"""v_admin_actividad: lo que no es acceso, para responder «¿quién revocó a X?» (D0)

`v_admin_accesos` enseña logins, sesiones y el bypass. Todo lo demás que la
auditoría registra —roles, revocaciones, transferencias, códigos, bajas,
borrados— estaba en `auditoria` y en ninguna vista, así que PSAdmin no podía
leerlo: la vista es su único contrato.

Es el complemento exacto de `v_admin_accesos` (un test comprueba que entre las
dos cubren todos los tipos sin solaparse), y **sin IP ni user-agent**: quien
actúa aquí es siempre una cuenta autenticada, y para saber desde dónde entró
está su login en la otra vista. Una columna de red más no responde ninguna
pregunta de actividad y sí es un dato personal más.

`target_type`/`target_id` dicen sobre QUÉ se actuó (`swimmer 12`, `user 7`),
nunca qué contiene: ni nombres ni datos deportivos.

Revision ID: f4b8e1c2a9d3
Revises: e3a9d0c41b7f
Create Date: 2026-09-24 18:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4b8e1c2a9d3"
down_revision: str | Sequence[str] | None = "e3a9d0c41b7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los mismos que filtra `v_admin_accesos` (copia de `e3a9d0c41b7f`: una
# migración no importa la aplicación).
_TIPOS_DE_ACCESO = (
    "sesion.login", "sesion.refresh_reusado", "sesion.logout",
    "cuenta.password_cambiada", "dev.bypass",
)


def upgrade() -> None:
    op.execute(f"""
        CREATE VIEW v_admin_actividad AS
        SELECT id, occurred_at, event_type, outcome, actor_user_id, actor_email,
               team_id, target_type, target_id, detail
        FROM auditoria
        WHERE event_type NOT IN ({", ".join(f"'{t}'" for t in _TIPOS_DE_ACCESO)})
    """)


def downgrade() -> None:
    op.execute("DROP VIEW v_admin_actividad")
