"""Los dos tipos de acceso del CLI de operaciones entran en v_admin_accesos (D1)

D1 añade cuatro tipos de evento. Dos son **de acceso**, y decidirlo así (2026-10-14)
es lo que obliga a esta migración:

  · `sesion.cortadas`              un operador corta todas las sesiones de una cuenta
  · `cuenta.password_restablecida` un operador le pone una contraseña temporal

Son de la misma familia que `sesion.logout` y `cuenta.password_cambiada`: quien
mire en PSAdmin «¿por qué esta persona perdió la sesión?» los busca en la misma
vista. Los otros dos —`miembro.liberado` y `equipo.creado`— son actividad, y
`v_admin_actividad` ya los recoge sin cambios por ser «todo lo que no es acceso».

Las dos vistas de eventos filtran por la misma lista (una con `IN`, la otra con
`NOT IN`), así que se recrean **las dos**: cambiar solo una haría que esos dos
tipos salieran en ambas. `test_auditoria_vistas.py` compara la lista con
`TIPOS_DE_ACCESO` y comprueba que se reparten sin solaparse. Las columnas no
cambian. La lista va copiada, no importada: una migración no importa la
aplicación (si mañana el enum cambia, esta migración tiene que seguir
describiendo lo que hizo hoy).

Revision ID: d1a7c3e9f5b2
Revises: c9e1a4d7b2f6
Create Date: 2026-10-14 20:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1a7c3e9f5b2"
down_revision: str | Sequence[str] | None = "c9e1a4d7b2f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ANTES = (
    "sesion.login", "sesion.refresh_reusado", "sesion.logout",
    "cuenta.password_cambiada", "dev.bypass",
)
_AHORA = (*_ANTES, "sesion.cortadas", "cuenta.password_restablecida")


def _lista(tipos: tuple[str, ...]) -> str:
    return ", ".join(f"'{t}'" for t in tipos)


def _crear(tipos: tuple[str, ...]) -> None:
    op.execute(f"""
        CREATE VIEW v_admin_accesos AS
        SELECT id, occurred_at, event_type, outcome, actor_user_id, actor_email,
               team_id, ip_network, ip_hash, user_agent, detail
        FROM auditoria
        WHERE event_type IN ({_lista(tipos)})
    """)
    op.execute(f"""
        CREATE VIEW v_admin_actividad AS
        SELECT id, occurred_at, event_type, outcome, actor_user_id, actor_email,
               team_id, target_type, target_id, detail
        FROM auditoria
        WHERE event_type NOT IN ({_lista(tipos)})
    """)


def _borrar() -> None:
    op.execute("DROP VIEW v_admin_actividad")
    op.execute("DROP VIEW v_admin_accesos")


def upgrade() -> None:
    _borrar()
    _crear(_AHORA)


def downgrade() -> None:
    _borrar()
    _crear(_ANTES)
