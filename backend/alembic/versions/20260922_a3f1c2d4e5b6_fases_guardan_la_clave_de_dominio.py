"""fases: la base guarda la clave de Fase, no la etiqueta (P3)

Convivían tres vocabularios de fase y la base guardaba los dos que la ciencia no
sabe leer:

  · `plan_phases.type`   → `base|build|peak|taper` (cuatro tramos de interfaz)
  · `weekly_plans.phase` → el NOMBRE del tramo (`"Construcción"`, o lo que el
                           entrenador tecleara)

mientras que `F_FASE` y la banda de volumen se indexan por las cinco claves de
`Fase`. Desde aquí las dos columnas guardan esa clave, y un CHECK impide que
vuelva a entrar otra cosa. El nombre que el entrenador le puso al tramo sigue en
`plan_phases.name`, que es de donde la tabla semanal lo lee ahora.

Cómo se convierten las filas que ya existen:

  · `plan_phases.type`: cada tramo va a la fase con la que más se solapa en la
    forma del macro de 15 semanas (base 0-30 % → base_general, build 30-70 % →
    umbral_css, peak 70-90 % → pre_competitivo, taper → taper). Es el tipo que el
    entrenador eligió, así que manda sobre dónde cayera el tramo. Un tipo que no
    sea ninguno de los cuatro —la API aceptaba cualquier texto— se decide por
    posición: la fase de la ciencia que más semanas comparte con el tramo.
  · `weekly_plans.phase`: la clave del tramo que cubre la semana; si ninguno la
    cubre, la del último (lo mismo que hacía el motor al generarla); y si el plan
    no tiene tramos, la de la ciencia en esa posición del macro.

**El downgrade reconstruye lo de antes**: `weekly_plans.phase` vuelve a ser el
nombre del tramo que cubre la semana, que es exactamente lo que el motor
escribía, y `plan_phases.type` vuelve a los cuatro tramos. Lo único que no se
recupera es la diferencia entre `base_especifica` y `umbral_css`, que el esquema
viejo no sabía guardar (las dos vuelven como `build`).

Las tablas de abajo están copiadas a propósito y no importadas: una migración
es una foto del momento en que se escribió, y si importara `app.dominio` un
cambio futuro del enum reescribiría en silencio lo que esta hizo.

Revision ID: a3f1c2d4e5b6
Revises: 22f704975e94
Create Date: 2026-09-22 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c2d4e5b6"
down_revision: str | Sequence[str] | None = "22f704975e94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# `tablas.MACRO_15_FASES` al 2026-09-22: (semana inicial, semana final, clave).
_MACRO_15: tuple[tuple[int, int, str], ...] = (
    (1, 3, "base_general"),
    (4, 7, "base_especifica"),
    (8, 11, "umbral_css"),
    (12, 13, "pre_competitivo"),
    (14, 15, "taper"),
)
_FASES = tuple(clave for _, _, clave in _MACRO_15)
_CHECK = "{col} IN ('base_general', 'base_especifica', 'umbral_css', 'pre_competitivo', 'taper')"

_DE_TRAMO_A_FASE = {
    "base": "base_general",
    "build": "umbral_css",
    "peak": "pre_competitivo",
    "taper": "taper",
}
_DE_FASE_A_TRAMO = {
    "base_general": "base",
    "base_especifica": "build",
    "umbral_css": "build",
    "pre_competitivo": "peak",
    "taper": "taper",
}


def _fase_por_posicion(inicio: int, fin: int, semanas: int) -> str:
    """La fase de la ciencia que más se solapa con las semanas [inicio, fin]."""
    total = _MACRO_15[-1][1]
    desde, hasta = (inicio - 1) / semanas, fin / semanas

    def solape(tramo: tuple[int, int, str]) -> float:
        ini, fin_, _ = tramo
        return max(0.0, min(hasta, fin_ / total) - max(desde, (ini - 1) / total))

    return max(_MACRO_15, key=solape)[2]


def _tramos_por_plan(conn: sa.Connection) -> dict[int, list[tuple]]:
    filas = conn.execute(sa.text(
        "SELECT plan_id, id, name, type, week_start, week_end FROM plan_phases "
        "ORDER BY plan_id, sort, id"
    )).all()
    por_plan: dict[int, list[tuple]] = {}
    for fila in filas:
        por_plan.setdefault(fila.plan_id, []).append(fila)
    return por_plan


def _tramo_de(semana: int, tramos: list[tuple]) -> tuple | None:
    """El tramo que cubre la semana, o el último (lo que hacía el motor)."""
    if not tramos:
        return None
    return next((t for t in tramos if t.week_start <= semana <= t.week_end), tramos[-1])


def _semanas(conn: sa.Connection) -> list:
    return conn.execute(sa.text(
        "SELECT w.id, w.week_number, a.plan_id, p.total_weeks FROM weekly_plans w "
        "JOIN athlete_events e ON e.id = w.athlete_event_id "
        "JOIN athlete_plans a ON a.id = e.athlete_plan_id "
        "JOIN plans p ON p.id = a.plan_id"
    )).all()


def upgrade() -> None:
    conn = op.get_bind()
    semanas_del_plan = dict(conn.execute(sa.text("SELECT id, total_weeks FROM plans")).all())

    for plan_id, tramos in _tramos_por_plan(conn).items():
        for t in tramos:
            clave = _DE_TRAMO_A_FASE.get(t.type) or (
                t.type if t.type in _FASES
                else _fase_por_posicion(t.week_start, t.week_end, semanas_del_plan[plan_id])
            )
            conn.execute(
                sa.text("UPDATE plan_phases SET type = :clave WHERE id = :id"),
                {"clave": clave, "id": t.id},
            )

    tramos_por_plan = _tramos_por_plan(conn)   # ya con las claves nuevas
    for s in _semanas(conn):
        tramo = _tramo_de(s.week_number, tramos_por_plan.get(s.plan_id, []))
        clave = tramo.type if tramo is not None else _fase_por_posicion(
            s.week_number, s.week_number, max(s.total_weeks, s.week_number),
        )
        conn.execute(
            sa.text("UPDATE weekly_plans SET phase = :clave WHERE id = :id"),
            {"clave": clave, "id": s.id},
        )

    with op.batch_alter_table("plan_phases", schema=None) as batch_op:
        batch_op.alter_column(
            "type", existing_type=sa.String(length=12), type_=sa.String(length=20),
            existing_nullable=False,
        )
        batch_op.create_check_constraint("ck_plan_phases_type", _CHECK.format(col="type"))

    with op.batch_alter_table("weekly_plans", schema=None) as batch_op:
        batch_op.alter_column(
            "phase", existing_type=sa.String(length=60), type_=sa.String(length=20),
            existing_nullable=False,
        )
        batch_op.create_check_constraint("ck_weekly_plans_phase", _CHECK.format(col="phase"))


def downgrade() -> None:
    with op.batch_alter_table("weekly_plans", schema=None) as batch_op:
        batch_op.drop_constraint("ck_weekly_plans_phase", type_="check")
        batch_op.alter_column(
            "phase", existing_type=sa.String(length=20), type_=sa.String(length=60),
            existing_nullable=False,
        )

    with op.batch_alter_table("plan_phases", schema=None) as batch_op:
        batch_op.drop_constraint("ck_plan_phases_type", type_="check")
        batch_op.alter_column(
            "type", existing_type=sa.String(length=20), type_=sa.String(length=12),
            existing_nullable=False,
        )

    conn = op.get_bind()
    # Primero las semanas: su nombre sale del tramo, que todavía no ha cambiado.
    tramos_por_plan = _tramos_por_plan(conn)
    for s in _semanas(conn):
        tramo = _tramo_de(s.week_number, tramos_por_plan.get(s.plan_id, []))
        conn.execute(
            sa.text("UPDATE weekly_plans SET phase = :nombre WHERE id = :id"),
            {"nombre": tramo.name if tramo is not None else "—", "id": s.id},
        )
    for tramos in tramos_por_plan.values():
        for t in tramos:
            conn.execute(
                sa.text("UPDATE plan_phases SET type = :tramo WHERE id = :id"),
                {"tramo": _DE_FASE_A_TRAMO.get(t.type, t.type), "id": t.id},
            )
