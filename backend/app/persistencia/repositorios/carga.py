"""La carga de entrenamiento: el recálculo que la mantiene y las lecturas acotadas.

**`recalcular` es la única función que escribe `carga_diaria`**, y la llaman,
antes de confirmar, las cuatro escrituras que pueden cambiarla: guardar y
borrar una sesión (`sesiones`), y dar de alta o de baja un test aeróbico
(`tests_aerobicos`), porque el test decide el CSS y con él el sTSS. Mismo
transacción: o se confirman el cambio y su carga, o ninguno.

**Incremental.** El modelo es una recurrencia —cada día depende solo del
anterior y de su carga—, así que un cambio en la fecha `d` deja intacto todo lo
de antes. Se retoma del último día guardado anterior a `d` y se rehace hacia
delante. Apuntar la sesión de hoy recalcula un día, no un año. **Se rehace la
serie entera** si no hay día anterior (el cambio toca el primero) o si el
cambio cae en los primeros `DIAS_PARA_EQUILIBRIO`: de esos días sale el estado
de arranque (`banister.estado_inicial`), y moverlos mueve la serie completa.

**Concurrencia.** Dos escrituras del mismo atleta a la vez (él y su entrenador)
se serializan bloqueando la fila del nadador (`FOR UPDATE`) antes de leer. En
PostgreSQL eso hace esperar a la segunda hasta que la primera confirme, y
entonces lee ya lo de la primera. SQLite ignora el `FOR UPDATE`, pero no lo
necesita: solo admite un escritor a la vez, y el cambio ya ha escrito cuando se
recalcula.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.dominio.servicios.banister import (
    DIAS_NEGATIVOS_SEGUIDOS,
    DIAS_PARA_EQUILIBRIO,
    Alerta,
    DiaDeCarga,
    MedicionDeCss,
    alertas,
    carga_por_dia,
    estado_inicial,
    serie,
)
from app.persistencia.mapeo import medicion_desde_test, sesion_desde_fila
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.carga import DailyLoad
from app.persistencia.tablas.sesiones import SwimSession
from app.persistencia.tablas.tests_aerobicos import AerobicTest


def _dia(fila: DailyLoad) -> DiaDeCarga:
    return DiaDeCarga(fila.load_date, fila.stss, fila.ctl, fila.atl)


async def _mediciones(db: AsyncSession, swimmer_id: int) -> list[MedicionDeCss]:
    filas = (await db.execute(select(AerobicTest).where(
        AerobicTest.swimmer_id == swimmer_id, AerobicTest.is_active.is_(True),
        AerobicTest.avg_per100.is_not(None),
    ))).scalars()
    return [medicion_desde_test(f) for f in filas]


async def recalcular(db: AsyncSession, *, team_id: int, swimmer_id: int, desde: date) -> None:
    """Rehace la serie del atleta a partir de `desde`. **No confirma.**

    Idempotente: correrla dos veces con los mismos datos deja la misma tabla,
    que además es la que daría `CargaAcumulada.calcular` desde cero.
    """
    await db.execute(select(Swimmer.id).where(Swimmer.id == swimmer_id).with_for_update())
    await db.flush()

    primero = (await db.execute(select(func.min(DailyLoad.load_date)).where(
        DailyLoad.swimmer_id == swimmer_id))).scalar_one_or_none()
    previo = None
    if primero is not None and desde >= primero + timedelta(days=DIAS_PARA_EQUILIBRIO):
        previo = (await db.execute(
            select(DailyLoad).where(DailyLoad.swimmer_id == swimmer_id, DailyLoad.load_date < desde)
            .order_by(DailyLoad.load_date.desc()).limit(1)
        )).scalar_one_or_none()
    # Con día anterior, basta leer las sesiones de después; sin él, todas.
    stmt = select(SwimSession).where(SwimSession.swimmer_id == swimmer_id)
    if previo is not None:
        stmt = stmt.where(SwimSession.session_date > previo.load_date)
    sesiones = [sesion_desde_fila(f) for f in (await db.execute(stmt)).scalars()]
    cargas, _ = carga_por_dia(sesiones, await _mediciones(db, swimmer_id))

    borrar = delete(DailyLoad).where(DailyLoad.swimmer_id == swimmer_id)
    if previo is not None:
        borrar = borrar.where(DailyLoad.load_date > previo.load_date)
    await db.execute(borrar)

    if cargas:
        if previo is not None:
            inicio, estado = previo.load_date + timedelta(days=1), _dia(previo).estado
        else:
            inicio = min(cargas)
            estado = estado_inicial(cargas, inicio)
        db.add_all(
            DailyLoad(swimmer_id=swimmer_id, team_id=team_id, load_date=d.fecha,
                      stss=d.stss, ctl=d.ctl, atl=d.atl)
            for d in serie(cargas, inicio, max(cargas), estado)
        )
    elif previo is not None:
        # Se borró lo último: la serie termina en el último día con carga, no
        # en un día de descanso que quedó colgando.
        ultimo = (await db.execute(select(func.max(DailyLoad.load_date)).where(
            DailyLoad.swimmer_id == swimmer_id, DailyLoad.stss > 0,
        ))).scalar_one_or_none()
        recorte = delete(DailyLoad).where(DailyLoad.swimmer_id == swimmer_id)
        if ultimo is not None:
            recorte = recorte.where(DailyLoad.load_date > ultimo)
        await db.execute(recorte)
    await db.flush()


@dataclass(frozen=True, slots=True)
class CurvaDeCarga:
    """La curva de un atleta en `[desde, hasta]`, lista para enseñar.

    `dias` empieza en `desde` (o en el primer día con carga, si es posterior) y
    llega a `hasta` aunque no haya nada guardado: sin carga, CTL y ATL solo
    decaen. `alertas` va por fecha y solo trae los días que avisan.
    """

    inicio: date
    dias: list[DiaDeCarga]
    alertas: dict[date, Alerta]


class RepositorioDeCarga:
    """La carga que alcanza un `Principal`: su equipo y, si es atleta, la suya."""

    __slots__ = ("db", "principal")

    def __init__(self, db: AsyncSession, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    def acotar(self, stmt):
        stmt = stmt.where(DailyLoad.team_id == self.principal.team_id)
        return self.principal.scope_to_own_swimmer(stmt, DailyLoad.swimmer_id)

    async def dias(self, swimmer_id: int, desde: date, hasta: date) -> list[DiaDeCarga]:
        """Los días guardados en `[desde, hasta]`, en orden."""
        stmt = self.acotar(select(DailyLoad)).where(
            DailyLoad.swimmer_id == swimmer_id,
            DailyLoad.load_date >= desde, DailyLoad.load_date <= hasta,
        ).order_by(DailyLoad.load_date)
        return [_dia(f) for f in (await self.db.execute(stmt)).scalars()]

    async def extremos(self, swimmer_id: int) -> tuple[date, DiaDeCarga] | None:
        """`(primer día, último día guardado)`, o `None` si no hay serie."""
        base = self.acotar(select(DailyLoad)).where(DailyLoad.swimmer_id == swimmer_id)
        primero = (await self.db.execute(
            base.order_by(DailyLoad.load_date).limit(1))).scalar_one_or_none()
        if primero is None:
            return None
        ultimo = (await self.db.execute(
            base.order_by(DailyLoad.load_date.desc()).limit(1))).scalar_one()
        return primero.load_date, _dia(ultimo)

    async def curva(self, swimmer_id: int, desde: date, hasta: date) -> CurvaDeCarga | None:
        """Lo guardado, más el decaimiento hasta `hasta`, con sus alertas.

        `carga_diaria` llega hasta el último día con carga. De ahí a `hasta` no
        hay nada guardado y no hace falta: se calcula con la misma recurrencia
        (`banister.serie` con cargas vacías). Así la curva llega a hoy sin un
        proceso que escriba una fila por atleta cada noche.

        Vive aquí y no en la rebanada `carga` porque la leen dos: la curva de un
        atleta y la tabla del equipo (`vistas`), que no pueden importarse entre
        sí. `None` si no hay serie o empieza después de `hasta`.
        """
        extremos = await self.extremos(swimmer_id)
        if extremos is None or extremos[0] > hasta:
            return None
        inicio, ultimo = extremos
        # Se leen además los días anteriores que decide la racha de TSB negativo.
        ventana = max(desde - timedelta(days=DIAS_NEGATIVOS_SEGUIDOS), inicio)
        dias = await self.dias(swimmer_id, ventana, hasta)
        if ultimo.fecha < hasta:
            dias += [d for d in serie({}, ultimo.fecha + timedelta(days=1), hasta, ultimo.estado)
                     if d.fecha >= ventana]
        return CurvaDeCarga(
            inicio=inicio,
            dias=[d for d in dias if d.fecha >= desde],
            alertas={a.fecha: a for a in alertas(dias, inicio)},
        )

    async def sesiones_sin_css(self, swimmer_id: int) -> int:
        """Las sesiones anteriores al primer test: no tienen CSS y no cuentan."""
        primer_test = (await self.db.execute(select(func.min(AerobicTest.test_date)).where(
            AerobicTest.swimmer_id == swimmer_id, AerobicTest.is_active.is_(True),
            AerobicTest.team_id == self.principal.team_id,
        ))).scalar_one_or_none()
        stmt = select(func.count()).select_from(SwimSession).where(
            SwimSession.swimmer_id == swimmer_id,
            SwimSession.team_id == self.principal.team_id,
        )
        if primer_test is not None:
            stmt = stmt.where(SwimSession.session_date < primer_test)
        return (await self.db.execute(stmt)).scalar_one()
