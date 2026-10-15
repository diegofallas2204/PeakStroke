"""La curva que se enseña: de `RepositorioDeCarga.curva` a la respuesta.

El cálculo —lo guardado más el decaimiento hasta `hasta`, y las alertas— vive
en el repositorio desde el 2026-10-01, porque la tabla del equipo (`vistas`)
también lo necesita y entre rebanadas no se importa. Aquí solo se da forma.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.dominio.servicios.banister import DIAS_DE_CALENTAMIENTO
from app.persistencia.repositorios import RepositorioDeCarga

from .schemas import LoadDay, TrainingLoadResponse


def _redondeo(x: float) -> float:
    return round(x, 2)


async def curva(
    repo: RepositorioDeCarga, swimmer_id: int, desde: date, hasta: date,
) -> TrainingLoadResponse:
    sin_css = await repo.sesiones_sin_css(swimmer_id)
    c = await repo.curva(swimmer_id, desde, hasta)
    if c is None:
        return TrainingLoadResponse(
            swimmer_id=swimmer_id, desde=desde, hasta=hasta, history_start=None,
            warming_up=True, sessions_without_css=sin_css, days=[],
        )
    fin_del_calentamiento = c.inicio + timedelta(days=DIAS_DE_CALENTAMIENTO)
    return TrainingLoadResponse(
        swimmer_id=swimmer_id, desde=desde, hasta=hasta, history_start=c.inicio,
        warming_up=hasta < fin_del_calentamiento,
        warmup_until=fin_del_calentamiento,
        sessions_without_css=sin_css,
        days=[
            LoadDay(
                date=d.fecha, stss=_redondeo(d.stss), ctl=_redondeo(d.ctl),
                atl=_redondeo(d.atl), tsb=_redondeo(d.tsb),
                alert=c.alertas[d.fecha].nivel.value if d.fecha in c.alertas else None,
                reasons=[m.value for m in c.alertas[d.fecha].motivos] if d.fecha in c.alertas else [],
            )
            for d in c.dias
        ],
    )
