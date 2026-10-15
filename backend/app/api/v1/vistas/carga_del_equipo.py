"""El estado de carga de cada atleta en la tabla del equipo (TODO-19).

**De qué día.** Del cierre de la semana que se mira —su domingo—, sin pasar de
hoy: navegar a la semana 3 enseña cómo estaba el atleta entonces, y una semana
que aún no ha empezado no enseña nada. Decisión del usuario, 2026-10-01.

El número sale de `RepositorioDeCarga.curva`, el mismo cálculo que la curva de
un atleta: un test compara los dos para el mismo día.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.dominio.servicios.banister import DIAS_DE_CALENTAMIENTO
from app.persistencia.repositorios import RepositorioDeCarga

from .schemas import LoadSnapshot


def dia_de_la_carga(lunes_de_la_semana: date, hoy: date) -> date | None:
    """El domingo de esa semana, o hoy si cae antes. `None` si la semana es futura."""
    if lunes_de_la_semana > hoy:
        return None
    return min(lunes_de_la_semana + timedelta(days=6), hoy)


async def estados(
    repo: RepositorioDeCarga, swimmer_ids: set[int], dia: date | None,
) -> dict[int, LoadSnapshot]:
    """`{nadador: estado}` el `dia` dado. Quien no tiene serie ese día, no sale.

    Una curva por atleta (tres consultas cada una): una tabla de equipo son unas
    decenas de nadadores. Si algún día pesa, el sitio para juntarlas es el
    repositorio, no aquí.
    """
    if dia is None:
        return {}
    out: dict[int, LoadSnapshot] = {}
    for swimmer_id in sorted(swimmer_ids):
        c = await repo.curva(swimmer_id, dia, dia)
        if c is None or not c.dias:
            continue
        d = c.dias[-1]
        alerta = c.alertas.get(d.fecha)
        out[swimmer_id] = LoadSnapshot(
            date=d.fecha, ctl=round(d.ctl, 2), atl=round(d.atl, 2), tsb=round(d.tsb, 2),
            alert=alerta.nivel.value if alerta else None,
            reasons=[m.value for m in alerta.motivos] if alerta else [],
            warming_up=d.fecha < c.inicio + timedelta(days=DIAS_DE_CALENTAMIENTO),
        )
    return out
