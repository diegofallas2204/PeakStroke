"""La curva que se enseña: lo guardado, más el decaimiento hasta `hasta`.

`carga_diaria` llega hasta el último día con carga. De ahí a `hasta` no hay
nada guardado y no hace falta: sin carga, CTL y ATL solo decaen, y se calcula
con la misma recurrencia (`banister.serie` con cargas vacías). Así la curva
llega a hoy sin un proceso que escriba una fila por atleta cada noche.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.dominio.servicios.banister import (
    DIAS_DE_CALENTAMIENTO,
    DIAS_NEGATIVOS_SEGUIDOS,
    DiaDeCarga,
    alertas,
    serie,
)
from app.persistencia.repositorios import RepositorioDeCarga

from .schemas import LoadDay, TrainingLoadResponse


def _redondeo(x: float) -> float:
    return round(x, 2)


async def curva(
    repo: RepositorioDeCarga, swimmer_id: int, desde: date, hasta: date,
) -> TrainingLoadResponse:
    sin_css = await repo.sesiones_sin_css(swimmer_id)
    extremos = await repo.extremos(swimmer_id)
    if extremos is None or extremos[0] > hasta:
        return TrainingLoadResponse(
            swimmer_id=swimmer_id, desde=desde, hasta=hasta, history_start=None,
            warming_up=True, sessions_without_css=sin_css, days=[],
        )
    inicio, ultimo = extremos
    # Se leen además los días anteriores que decide la racha de TSB negativo.
    ventana = max(desde - timedelta(days=DIAS_NEGATIVOS_SEGUIDOS), inicio)
    dias: list[DiaDeCarga] = await repo.dias(swimmer_id, ventana, hasta)
    if ultimo.fecha < hasta:
        dias += [d for d in serie({}, ultimo.fecha + timedelta(days=1), hasta, ultimo.estado)
                 if d.fecha >= ventana]
    por_fecha = {a.fecha: a for a in alertas(dias, inicio)}
    return TrainingLoadResponse(
        swimmer_id=swimmer_id, desde=desde, hasta=hasta, history_start=inicio,
        warming_up=hasta < inicio + timedelta(days=DIAS_DE_CALENTAMIENTO),
        warmup_until=inicio + timedelta(days=DIAS_DE_CALENTAMIENTO),
        sessions_without_css=sin_css,
        days=[
            LoadDay(
                date=d.fecha, stss=_redondeo(d.stss), ctl=_redondeo(d.ctl),
                atl=_redondeo(d.atl), tsb=_redondeo(d.tsb),
                alert=por_fecha[d.fecha].nivel.value if d.fecha in por_fecha else None,
                reasons=[m.value for m in por_fecha[d.fecha].motivos] if d.fecha in por_fecha else [],
            )
            for d in dias if d.fecha >= desde
        ],
    )
