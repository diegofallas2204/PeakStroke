"""El agregado TestAerobico: lo que el atleta nadó el día de la medición.

Era la mitad de lectura de `modules/aerobic_tests/service.py`. Lo que hace este
repositorio es lo que ya hacía `_visible()` y que ahora no se puede saltar: las
tres condiciones —equipo, nadador propio y de alta— viven juntas. Repartidas por
cada consulta, tarde o temprano una se queda sin alguna, que es exactamente lo
que pasó con el filtro por nadador.

**Devuelve filas, no entidades**, y es el único que no devuelve ninguna. No es
una omisión: el `TestAerobico` de dominio se construye para *analizar* —base
aeróbica, tendencia, densidad— y quien lo necesita lo pide a
`persistencia/mapeo.test_desde_fila` en el momento (`api/v1/tests/service`). La
respuesta del API se valida sobre la fila, que lleva además los agregados ya
calculados y guardados (`avg_per100`, `std_dev`, `trend`).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.principal import Principal
from app.persistencia.tablas.tests_aerobicos import AerobicTest


class RepositorioDeTests:
    """Los tests aeróbicos que alcanza un `Principal`, y nada más."""

    __slots__ = ("db", "principal")

    def __init__(self, db: AsyncSession, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    # ── El filtro ────────────────────────────────────────────────────────────

    def acotar(self, stmt, *, incluir_de_baja: bool = False):
        """Equipo, nadador propio y de alta. Las tres, en un sitio.

        `incluir_de_baja` es lo que hace que dar de baja no equivalga a borrar.
        Sin él, reactivar un test sería código muerto: uno retirado no se podría
        ni consultar, y desde la aplicación el efecto sería idéntico al borrado
        que esa columna vino a evitar.
        """
        stmt = stmt.where(AerobicTest.team_id == self.principal.team_id)
        if not incluir_de_baja:
            stmt = stmt.where(AerobicTest.is_active.is_(True))
        return self.principal.scope_to_own_swimmer(stmt, AerobicTest.swimmer_id)

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def filas(
        self, *, swimmer_id: int | None = None, plan_id: int | None = None,
        incluir_de_baja: bool = False,
    ) -> list[AerobicTest]:
        """`swimmer_id` filtra dentro de lo visible; nunca lo amplía.

        El parámetro llega del cliente, así que sin acotar antes por sesión
        bastaba con escribir el número de un compañero en la barra de
        direcciones.
        """
        stmt = self.acotar(
            select(AerobicTest).options(selectinload(AerobicTest.splits)),
            incluir_de_baja=incluir_de_baja,
        ).order_by(AerobicTest.test_date.desc(), AerobicTest.id.desc())
        if swimmer_id is not None:
            stmt = stmt.where(AerobicTest.swimmer_id == swimmer_id)
        if plan_id is not None:
            stmt = stmt.where(AerobicTest.plan_id == plan_id)
        return list((await self.db.execute(stmt)).scalars())

    async def fila_de(self, test_id: int) -> AerobicTest | None:
        """`None` si es de otro equipo o de otro atleta — el router: 404 en ambos.

        **Sí devuelve los dados de baja**, igual que la ficha del atleta. Es lo
        que permite mostrar "este test está retirado, ¿lo reactivas?" en vez de
        un 404 que no ofrece salida.
        """
        stmt = self.acotar(
            select(AerobicTest).options(selectinload(AerobicTest.splits)),
            incluir_de_baja=True,
        ).where(AerobicTest.id == test_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def anterior_a(self, fila: AerobicTest) -> AerobicTest | None:
        """Test anterior del mismo atleta, para el gráfico comparativo."""
        stmt = (
            self.acotar(select(AerobicTest).options(selectinload(AerobicTest.splits)))
            .where(
                AerobicTest.swimmer_id == fila.swimmer_id,
                AerobicTest.id != fila.id,
                AerobicTest.test_date <= fila.test_date,
            )
            .order_by(AerobicTest.test_date.desc(), AerobicTest.id.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── Escrituras ───────────────────────────────────────────────────────────

    async def guardar(self, fila: AerobicTest) -> AerobicTest:
        self.db.add(fila)
        await self.db.commit()
        return fila

    async def cambiar_alta(self, fila: AerobicTest, activa: bool) -> AerobicTest:
        """Da de baja (o reactiva) el test. **No lo borra.**

        Sustituye al `db.delete()` que había hasta el 2026-08-06, que iba contra
        la regla del CLAUDE.md ("nada se borra: se da de baja"). Un test aeróbico
        es una medición del atleta en una fecha: se puede retirar de las listas,
        pero rehacerla es imposible.
        """
        fila.is_active = activa
        await self.db.commit()
        return fila
