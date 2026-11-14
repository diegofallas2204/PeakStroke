"""El agregado TestDeLactato: lo que alcanza un `Principal`, y nada más.

Las tres condiciones de siempre en un sitio —equipo, nadador propio si es
atleta, y de alta—, como en `tests_aerobicos.py`. Lactato y FC son datos de
salud: un atleta ve solo los suyos, y uno sin nadador ligado no ve ninguno.

**No recalcula la carga**, a diferencia del test aeróbico: un test de lactato no
decide el CSS de nadie. Que no lo haga es justo lo que lo separa de aquella tabla.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.principal import Principal
from app.persistencia.tablas.tests_de_lactato import LactateTest


class RepositorioDeTestsDeLactato:
    __slots__ = ("db", "principal")

    def __init__(self, db: AsyncSession, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    def acotar(self, stmt, *, incluir_de_baja: bool = False):
        stmt = stmt.where(LactateTest.team_id == self.principal.team_id)
        if not incluir_de_baja:
            stmt = stmt.where(LactateTest.is_active.is_(True))
        return self.principal.scope_to_own_swimmer(stmt, LactateTest.swimmer_id)

    async def filas(self, *, swimmer_id: int | None = None) -> list[LactateTest]:
        """`swimmer_id` filtra dentro de lo visible; nunca lo amplía."""
        stmt = self.acotar(select(LactateTest).options(selectinload(LactateTest.reps))) \
            .order_by(LactateTest.test_date.desc(), LactateTest.id.desc())
        if swimmer_id is not None:
            stmt = stmt.where(LactateTest.swimmer_id == swimmer_id)
        return list((await self.db.execute(stmt)).scalars())

    async def fila_de(self, test_id: int) -> LactateTest | None:
        """`None` si es de otro equipo o de otro atleta: el router responde 404."""
        stmt = self.acotar(
            select(LactateTest).options(selectinload(LactateTest.reps)), incluir_de_baja=True,
        ).where(LactateTest.id == test_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def guardar(self, fila: LactateTest) -> LactateTest:
        self.db.add(fila)
        await self.db.commit()
        # Se relee por la puerta acotada: la respuesta sale de lo que hay en la
        # base, no de la colección en memoria (nota «colección rancia»).
        return await self.fila_de(fila.id)   # type: ignore[return-value]

    async def dar_de_baja(self, fila: LactateTest) -> None:
        fila.is_active = False
        await self.db.commit()
