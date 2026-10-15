"""CHECK en los vocabularios cerrados que quedaban sin él (REDISENO §7.2 fila 6)

Hasta aquí solo `team_members.role`, las fases (`plan_phases.type`,
`weekly_plans.phase`) y `resultados` tenían CHECK; el resto aceptaba cualquier
texto y lo único que lo frenaba era el `Literal` o el `pattern` del schema. Un
valor que entrara por otra puerta (el seed, una herramienta, SQL a mano) se
descubría al leerlo: el mapeo a entidad es estricto y revienta.

Lo que se añade, columna a columna:

  · `swimmers.gender`         F | M, o NULL
  · `swimmers.specialty`      velocidad | medio_fondo | fondo | aguas_abiertas
  · `swimmers.main_stroke`    libre | espalda | pecho | mariposa | combinado
  · `plans.pool`              50 | 25
  · `plans.status`            active | draft | finished | suspended
  · `athlete_events.stroke`   los cinco estilos
  · `resultados.stroke`       los cinco estilos
  · `aerobic_tests.test_type` T30 | T15 | CUSTOM | CSS | DIRECT
  · `aerobic_tests.input_mode` rep | clock

**Zona, nivel y perfil no tienen columna**: son derivados que se calculan al
leer (C7: «la sesión guarda hechos, no derivados»), así que no hay nada que
restringir. `athlete_plans.aerobic_base_source` y `aerobic_tests.trend` se
quedan sin CHECK a propósito: el primero lo acepta el API como texto libre (un
CHECK lo convertiría en un 500) y el segundo lo escribe el motor.

**Los estilos se convierten antes a su clave.** Hasta C9 punto 3 (2026-10-13)
el alta guardaba el estilo como llegaba, así que una base real puede tener
«crol», «braza» o «Freestyle» en `swimmers.main_stroke`, `athlete_events.stroke`
o `resultados.stroke`. Se leían bien (`Estilo.desde_texto` conoce los alias),
pero un CHECK no los admite: la migración los reescribe a su clave —como hizo
`a3f1c2d4e5b6` con las fases— con la tabla de alias de ese día, copiada abajo.
El downgrade no los devuelve: la clave también era válida antes.

**Antes de crear el CHECK se comprueba que ninguna fila lo incumple**, con un
mensaje que dice cuál. Un `ALTER` que falla a medias en PostgreSQL deja la
transacción abortada sin decir qué fila era; en SQLite, el modo batch copiaría
la tabla y fallaría al insertar. Se comprobó la base de desarrollo en solo
lectura el 2026-10-14: ninguna fila fuera de vocabulario.

**En SQLite, `legacy_alter_table` mientras dura el modo batch.** Batch copia la
tabla a `_alembic_tmp_<tabla>` y la renombra; un SQLite moderno valida en ese
`RENAME` las vistas que la nombran, y `v_admin_cuentas` y `v_admin_equipos` leen
`swimmers`, que en ese instante no existe. Con el modo heredado el `RENAME` no
toca las vistas, que vuelven a encontrar `swimmers` en cuanto existe. En
PostgreSQL el CHECK es un `ALTER TABLE ... ADD CONSTRAINT` y no hay copia.

Los vocabularios están **copiados** y no importados, como en `a3f1c2d4e5b6`: una
migración es una foto del momento en que se escribió. `tests/test_vocabularios.py`
los compara con los enums del dominio y con los `Literal` del API.

Revision ID: c9e1a4d7b2f6
Revises: b2d7f5a8c1e4
Create Date: 2026-10-14 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e1a4d7b2f6"
down_revision: str | Sequence[str] | None = "b2d7f5a8c1e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ESTILOS = ("libre", "espalda", "pecho", "mariposa", "combinado")

# `valores.prueba._ALIAS_DE_ESTILO` al 2026-10-14 (la clave se busca en minúsculas
# y sin espacios alrededor, como `Estilo.desde_texto`).
ALIAS_DE_ESTILO = {
    "libre": "libre", "crol": "libre", "freestyle": "libre",
    "espalda": "espalda", "dorso": "espalda", "backstroke": "espalda",
    "pecho": "pecho", "braza": "pecho", "breaststroke": "pecho",
    "mariposa": "mariposa", "butterfly": "mariposa",
    "combinado": "combinado", "im": "combinado", "individual_medley": "combinado",
}
COLUMNAS_DE_ESTILO = (("swimmers", "main_stroke"), ("athlete_events", "stroke"), ("resultados", "stroke"))

# (tabla, nombre del CHECK, columna, valores, admite NULL)
CHECKS: tuple[tuple[str, str, str, tuple[str, ...], bool], ...] = (
    ("swimmers", "ck_swimmers_gender", "gender", ("F", "M"), True),
    ("swimmers", "ck_swimmers_specialty", "specialty",
     ("velocidad", "medio_fondo", "fondo", "aguas_abiertas"), False),
    ("swimmers", "ck_swimmers_main_stroke", "main_stroke", ESTILOS, False),
    ("plans", "ck_plans_pool", "pool", ("50", "25"), False),
    ("plans", "ck_plans_status", "status", ("active", "draft", "finished", "suspended"), False),
    ("athlete_events", "ck_athlete_events_stroke", "stroke", ESTILOS, False),
    ("resultados", "ck_resultados_stroke", "stroke", ESTILOS, False),
    ("aerobic_tests", "ck_aerobic_tests_test_type", "test_type",
     ("T30", "T15", "CUSTOM", "CSS", "DIRECT"), False),
    ("aerobic_tests", "ck_aerobic_tests_input_mode", "input_mode", ("rep", "clock"), False),
)


def expresion(columna: str, valores: tuple[str, ...], nulo: bool) -> str:
    """`col IN ('a', 'b')`, con `col IS NULL OR` delante si admite NULL. Vale igual
    en SQLite y en PostgreSQL."""
    lista = ", ".join(f"'{v}'" for v in valores)
    dentro = f"{columna} IN ({lista})"
    return f"{columna} IS NULL OR {dentro}" if nulo else dentro


def _tablas() -> dict[str, list[tuple[str, str, tuple[str, ...], bool]]]:
    por_tabla: dict[str, list[tuple[str, str, tuple[str, ...], bool]]] = {}
    for tabla, nombre, columna, valores, nulo in CHECKS:
        por_tabla.setdefault(tabla, []).append((nombre, columna, valores, nulo))
    return por_tabla


def _modo_heredado(activo: bool) -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"PRAGMA legacy_alter_table = {'ON' if activo else 'OFF'}")


def _canonizar_estilos(conn) -> None:
    for tabla, columna in COLUMNAS_DE_ESTILO:
        valores = [v for (v,) in conn.execute(sa.text(f"SELECT DISTINCT {columna} FROM {tabla}"))]
        for valor in valores:
            clave = ALIAS_DE_ESTILO.get(str(valor).strip().lower())
            if clave is not None and clave != valor:
                conn.execute(
                    sa.text(f"UPDATE {tabla} SET {columna} = :clave WHERE {columna} = :valor"),
                    {"clave": clave, "valor": valor},
                )


def upgrade() -> None:
    conn = op.get_bind()
    _canonizar_estilos(conn)
    for tabla, nombre, columna, valores, nulo in CHECKS:
        fuera = conn.execute(sa.text(
            f"SELECT {columna}, COUNT(*) FROM {tabla} "
            f"WHERE NOT ({expresion(columna, valores, nulo)}) GROUP BY {columna}"
        )).all()
        if fuera:
            raise RuntimeError(
                f"{tabla}.{columna} tiene valores fuera de vocabulario y no se puede "
                f"crear {nombre}: {[tuple(f) for f in fuera]}. Corrígelos antes de migrar."
            )
    _modo_heredado(True)
    for tabla, checks in _tablas().items():
        with op.batch_alter_table(tabla, schema=None) as batch_op:
            for nombre, columna, valores, nulo in checks:
                batch_op.create_check_constraint(nombre, expresion(columna, valores, nulo))
    _modo_heredado(False)


def downgrade() -> None:
    _modo_heredado(True)
    for tabla, checks in reversed(list(_tablas().items())):
        with op.batch_alter_table(tabla, schema=None) as batch_op:
            for nombre, *_ in reversed(checks):
                batch_op.drop_constraint(nombre, type_="check")
    _modo_heredado(False)
