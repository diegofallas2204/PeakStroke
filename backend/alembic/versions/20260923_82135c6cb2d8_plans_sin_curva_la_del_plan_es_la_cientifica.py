"""plans sin progression_curve: la curva de un plan real es la científica (R7)

`plans.progression_curve` era una casilla del asistente de creación. R7 (§10.1 y
§10.4 de `docs/REDISENO.md`) la saca de la tabla: a mitad de macro las cinco
curvas se separan hasta 1,30 s contra una tolerancia de estado de ±0,4 %, así
que el mismo nado salía «adelantado» o «atrasado» según qué se eligió quince
semanas antes. Desde aquí la curva de un plan es `Macrociclo.curva`, siempre la
científica; elegir curva sigue existiendo en el simulador.

**Qué pasa con un plan que tenía otra curva.** Su `expected_time` (la curva
ideal, que nunca se reescribe) se queda como se generó. Lo que cambia es el
recálculo: el siguiente tiempo real que se apunte reancla la curva restante con
la forma científica. La migración avisa en el log de cuántos planes hay así.

**El downgrade vuelve a poner la columna con `'science'` en todas las filas.** Es
lo único que puede saber: la curva que tenía un plan con otra se pierde al subir.
Mientras nadie haya creado planes con otra curva —el asistente ya no la ofrece—
subir y bajar deja la base igual.

`batch_alter_table` recrea `plans` en SQLite (copia, borra, renombra). Es seguro
porque la conexión de Alembic no enciende `PRAGMA foreign_keys` (ese listener es
del motor de la aplicación, no de este): borrar la tabla vieja no arrastra en
cascada fases, competencias ni inscripciones.

Revision ID: 82135c6cb2d8
Revises: bae825334065
Create Date: 2026-09-23 10:00:00.000000

"""
import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82135c6cb2d8"
down_revision: str | Sequence[str] | None = "bae825334065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    otras = op.get_bind().execute(sa.text(
        "SELECT id, name, progression_curve FROM plans "
        "WHERE progression_curve IS NOT 'science'"
    )).all()
    if otras:
        _log.warning(
            "R7: %d plan(es) tenían otra curva y a partir de ahora recalculan con "
            "la científica: %s", len(otras),
            ", ".join(f"#{i} {n!r} ({c})" for i, n, c in otras),
        )
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.drop_column("progression_curve")


def downgrade() -> None:
    # El `server_default` solo sirve para rellenar las filas que ya existen; la
    # columna original no lo tenía (el defecto era del ORM), así que se quita
    # después para que el esquema quede exactamente como estaba.
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            "progression_curve", sa.String(length=20),
            server_default="science", nullable=False,
        ))
    with op.batch_alter_table("plans", schema=None) as batch_op:
        batch_op.alter_column("progression_curve", server_default=None)
