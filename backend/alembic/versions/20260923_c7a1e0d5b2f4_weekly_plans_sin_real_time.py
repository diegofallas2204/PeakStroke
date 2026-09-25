"""weekly_plans sin real_time: el tiempo de la semana solo vive en resultados (C7)

C6 (`bae825334065`) movió lo nadado a `resultados` y dejó `weekly_plans.real_time`
como sombra: la aplicación la escribía al apuntar un tiempo y nadie la leía. El
criterio de R2 para retirarla («dos despliegues seguidos») no aplica a una
aplicación local y se cambió por «al empezar C7» (bloque C6 de
`docs/PLAN-DE-TRABAJO.md`). Esta es esa retirada.

**Subir aborta si la columna guarda algo que `resultados` no.** Toda semana con
`real_time` tiene que tener al menos un resultado vivo del atleta en esa prueba y
esos siete días; si no, borrar la columna perdería ese tiempo. Con la aplicación
escribiendo los dos desde C6 no debería haber ninguna, y por eso se comprueba en
vez de suponerlo.

**Bajar la rellena desde `resultados`**: el promedio de los vivos de cada semana,
convertido a la piscina del macrociclo. Es lo mismo que la semana enseña hoy
(`real_de_la_semana`), así que tras subir y bajar cada semana vuelve con el
número que la tabla pintaba. Lo que no vuelve es la diferencia entre «un tiempo»
y «el promedio de varios»: el esquema viejo solo sabía guardar uno. Y un
resultado que no cae en ninguna semana no tiene fila donde ir — sigue en
`resultados`, que esta migración no toca.

Las reglas de abajo (alias de estilo, factor corta/larga por perfil) están
**copiadas a propósito** y no importadas de `app.dominio`: una migración es una
foto del momento en que se escribió (mismo criterio que `a3f1c2d4e5b6`).

`batch_alter_table` recrea `weekly_plans` en SQLite. Nada apunta a esa tabla, y
la conexión de Alembic no enciende `PRAGMA foreign_keys`, así que recrearla no
arrastra nada.

Revision ID: c7a1e0d5b2f4
Revises: 82135c6cb2d8
Create Date: 2026-09-23 18:00:00.000000

"""
from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7a1e0d5b2f4"
down_revision: str | Sequence[str] | None = "82135c6cb2d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copia de `valores.prueba._ALIAS_DE_ESTILO` al 2026-09-23.
_ALIAS_DE_ESTILO = {
    "libre": "libre", "crol": "libre", "freestyle": "libre",
    "espalda": "espalda", "dorso": "espalda", "backstroke": "espalda",
    "pecho": "pecho", "braza": "pecho", "breaststroke": "pecho",
    "mariposa": "mariposa", "butterfly": "mariposa",
    "combinado": "combinado", "im": "combinado", "individual_medley": "combinado",
}


def _estilo(crudo: str) -> str:
    texto = str(crudo).strip().lower()
    return _ALIAS_DE_ESTILO.get(texto, texto)


def _factor(piscina: str, distancia: int) -> float:
    """Copia de `Piscina.factor(Perfil.para_distancia(d))` al 2026-09-23."""
    if piscina == "50":
        return 1.0
    if distancia <= 100:
        return 0.982
    if distancia <= 400:
        return 0.979
    return 0.968


def _fecha(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


def _semanas_y_promedios(conn) -> tuple[list, dict[int, float]]:
    """Las semanas con su `real_time`, y `{id de semana: promedio de resultados}`."""
    semanas = conn.execute(sa.text("""
        SELECT w.id, w.week_date, w.real_time, e.distance, e.stroke, ap.swimmer_id, p.pool
        FROM weekly_plans w
        JOIN athlete_events e ON e.id = w.athlete_event_id
        JOIN athlete_plans ap ON ap.id = e.athlete_plan_id
        JOIN plans p ON p.id = ap.plan_id
    """)).all()
    por_atleta_y_prueba: dict[tuple, list[tuple[date, float]]] = defaultdict(list)
    for atleta, distancia, estilo, tiempo, fecha, piscina in conn.execute(sa.text(
        "SELECT swimmer_id, distance, stroke, time, result_date, pool "
        "FROM resultados WHERE is_active"
    )):
        # Se guarda ya en larga: dividir por el factor de origen es la mitad de
        # la conversión que no depende del destino.
        por_atleta_y_prueba[(atleta, distancia, _estilo(estilo))].append(
            (_fecha(fecha), tiempo / _factor(piscina, distancia)),
        )
    promedios: dict[int, float] = {}
    for sid, lunes, _real, distancia, estilo, atleta, piscina in semanas:
        lunes = _fecha(lunes)
        domingo = lunes + timedelta(days=7)
        en_larga = [t for f, t in por_atleta_y_prueba[(atleta, distancia, _estilo(estilo))]
                    if lunes <= f < domingo]
        if en_larga:
            promedios[sid] = sum(t * _factor(piscina, distancia) for t in en_larga) / len(en_larga)
    return semanas, promedios


def upgrade() -> None:
    semanas, promedios = _semanas_y_promedios(op.get_bind())
    huerfanas = [s[0] for s in semanas if s[2] is not None and s[0] not in promedios]
    if huerfanas:
        raise RuntimeError(
            f"C7: {len(huerfanas)} semana(s) tienen real_time y ningún resultado vivo "
            f"que lo respalde (weekly_plans.id {huerfanas[:10]}). Borrar la columna "
            "perdería esos tiempos; no se sigue."
        )
    with op.batch_alter_table("weekly_plans", schema=None) as batch_op:
        batch_op.drop_column("real_time")


def downgrade() -> None:
    with op.batch_alter_table("weekly_plans", schema=None) as batch_op:
        batch_op.add_column(sa.Column("real_time", sa.Float(), nullable=True))
    conn = op.get_bind()
    _, promedios = _semanas_y_promedios(conn)
    for sid, real in promedios.items():
        conn.execute(sa.text("UPDATE weekly_plans SET real_time = :r WHERE id = :i"),
                     {"r": real, "i": sid})
