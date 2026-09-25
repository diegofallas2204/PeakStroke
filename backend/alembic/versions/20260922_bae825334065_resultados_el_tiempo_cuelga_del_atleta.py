"""resultados: el tiempo nadado cuelga del atleta, no del plan (C6, R2)

Hasta aquí el tiempo real vivía en `weekly_plans.real_time`, colgando de
`plans → athlete_plans → athlete_events → weekly_plans`. Borrar la inscripción
se lo llevaba (por eso `remove_athlete` tuvo que volverse baja lógica) y borrar
un macro sin tests aeróbicos se llevaba los de todo el equipo.

Esta migración crea `resultados` y copia en ella cada `real_time` no nulo, con
un `INSERT ... SELECT`:

  · atleta y equipo  ← `athlete_plans` (también las inscripciones dadas de baja:
                       lo que nadó alguien a quien sacaron sigue siendo suyo)
  · prueba           ← `athlete_events.distance` + `stroke`, tal cual
  · fecha            ← `weekly_plans.week_date` (el lunes de la semana)
  · piscina          ← `plans.pool`
  · contexto         ← 'control' (§7.4)

**No hay `UPDATE` de vuelta** (R2 enmendada, §10.2): la semana no guarda
referencia al resultado, lo deriva por atleta, prueba y fechas.

**`real_time` NO se borra.** Convive una versión como sombra —la aplicación la
sigue escribiendo al apuntar un tiempo, ya no la lee— y es lo que hace reversible
esta migración: el downgrade solo tiene que tirar la tabla nueva.

Dos comprobaciones que abortan en vez de dejar datos a medias:

  · upgrade: las filas copiadas tienen que ser exactamente los `real_time` no
    nulos. Si no cuadran, tira la tabla y falla. Lo de tirarla no sobra: Alembic
    corre el DDL de SQLite sin transacción, así que sin eso la tabla se quedaría
    a medias y el siguiente intento reventaría con "table already exists".
  · downgrade: si hay más resultados vivos que `real_time` no nulos, hay tiempos
    que la columna vieja no sabe guardar (varios en una semana, o uno fuera de
    toda semana) y tirar la tabla los perdería. Falla antes de tirarla. Los
    resultados RETIRADOS (`is_active = 0`, correcciones) sí se pierden al bajar:
    el esquema viejo no tenía dónde ponerlos.

Revision ID: bae825334065
Revises: a3f1c2d4e5b6
Create Date: 2026-09-22 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bae825334065"
down_revision: str | Sequence[str] | None = "a3f1c2d4e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REAL_TIMES = "SELECT count(*) FROM weekly_plans WHERE real_time IS NOT NULL"


def upgrade() -> None:
    op.create_table(
        "resultados",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("swimmer_id", sa.Integer(), nullable=False),
        sa.Column("distance", sa.Integer(), nullable=False),
        sa.Column("stroke", sa.String(length=20), nullable=False),
        sa.Column("time", sa.Float(), nullable=False),
        sa.Column("result_date", sa.Date(), nullable=False),
        sa.Column("pool", sa.String(length=2), nullable=False),
        sa.Column("context", sa.String(length=12), server_default="control", nullable=False),
        sa.Column("competition_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.CheckConstraint(
            "context IN ('competencia', 'control', 'serie')", name="ck_resultados_context",
        ),
        sa.CheckConstraint("pool IN ('50', '25')", name="ck_resultados_pool"),
        sa.CheckConstraint("time > 0", name="ck_resultados_time_positive"),
        sa.ForeignKeyConstraint(
            ["competition_id"], ["competitions.id"],
            name="fk_resultados_competition", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_resultados_swimmer_in_team",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_resultados_team"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resultados_team_id", "resultados", ["team_id"])
    op.create_index("ix_resultados_competition_id", "resultados", ["competition_id"])
    op.create_index("ix_resultados_is_active", "resultados", ["is_active"])
    op.create_index("ix_resultados_swimmer_date", "resultados", ["swimmer_id", "result_date"])

    conn = op.get_bind()
    esperadas = conn.execute(sa.text(_REAL_TIMES)).scalar_one()
    conn.execute(sa.text("""
        INSERT INTO resultados
            (team_id, swimmer_id, distance, stroke, time, result_date, pool,
             context, competition_id, is_active)
        SELECT ap.team_id, ap.swimmer_id, e.distance, e.stroke, w.real_time,
               w.week_date, p.pool, 'control', NULL, TRUE
        FROM weekly_plans w
        JOIN athlete_events e ON e.id = w.athlete_event_id
        JOIN athlete_plans ap ON ap.id = e.athlete_plan_id
        JOIN plans p ON p.id = ap.plan_id
        WHERE w.real_time IS NOT NULL
        ORDER BY w.id
    """))
    copiadas = conn.execute(sa.text("SELECT count(*) FROM resultados")).scalar_one()
    if copiadas != esperadas:
        _tirar_tabla()
        raise RuntimeError(
            f"C6: se esperaban {esperadas} resultados (real_time no nulos) y se "
            f"copiaron {copiadas}. Hay semanas con tiempo cuya cadena hasta el plan "
            "está rota; no se sigue."
        )


def downgrade() -> None:
    conn = op.get_bind()
    vivos = conn.execute(
        sa.text("SELECT count(*) FROM resultados WHERE is_active"),
    ).scalar_one()
    en_columna = conn.execute(sa.text(_REAL_TIMES)).scalar_one()
    if vivos > en_columna:
        raise RuntimeError(
            f"C6: hay {vivos} resultados vivos y solo {en_columna} real_time. "
            "Los que sobran no caben en weekly_plans.real_time y tirar la tabla "
            "los perdería; no se baja."
        )
    _tirar_tabla()


def _tirar_tabla() -> None:
    op.drop_index("ix_resultados_swimmer_date", table_name="resultados")
    op.drop_index("ix_resultados_is_active", table_name="resultados")
    op.drop_index("ix_resultados_competition_id", table_name="resultados")
    op.drop_index("ix_resultados_team_id", table_name="resultados")
    op.drop_table("resultados")
