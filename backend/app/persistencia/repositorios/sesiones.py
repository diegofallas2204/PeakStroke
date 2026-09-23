"""El agregado Sesion: lo que el atleta nadó cada día, colgando de él.

Las dos fronteras de siempre, juntas en `acotar`: el equipo de la sesión y, si
quien pregunta es atleta, solo las suyas. Un atleta apunta, corrige y borra lo
que nadó él; el entrenador, lo de cualquiera de su equipo.

**Recibe y devuelve entidades, no filas.** `Sesion` nació entidad, así que no
hay nada que traducir a medias: la rebanada del API construye una `Sesion` —y
con ella pasa las validaciones del dominio— y este repositorio la persiste.

**Borrar es borrar** (C7, 2026-09-23). Ver `persistencia/tablas/sesiones.py`.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.dominio.entidades import Sesion
from app.persistencia.mapeo import sesion_desde_fila
from app.persistencia.tablas.sesiones import SwimSession


class RepositorioDeSesiones:
    """Las sesiones que alcanza un `Principal`, y nada más."""

    __slots__ = ("db", "principal")

    def __init__(self, db: AsyncSession, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    def acotar(self, stmt):
        stmt = stmt.where(SwimSession.team_id == self.principal.team_id)
        return self.principal.scope_to_own_swimmer(stmt, SwimSession.swimmer_id)

    async def _fila(self, sesion_id: int) -> SwimSession | None:
        stmt = self.acotar(select(SwimSession)).where(SwimSession.id == sesion_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def listar(
        self, *, atleta_id: int | None = None,
        desde: date | None = None, hasta: date | None = None,
    ) -> list[Sesion]:
        """Las visibles, de la más reciente a la más antigua. Fechas en `[desde, hasta]`.

        `atleta_id` filtra dentro de lo visible; nunca lo amplía.
        """
        stmt = self.acotar(select(SwimSession)).order_by(
            SwimSession.session_date.desc(), SwimSession.id.desc(),
        )
        if atleta_id is not None:
            stmt = stmt.where(SwimSession.swimmer_id == atleta_id)
        if desde is not None:
            stmt = stmt.where(SwimSession.session_date >= desde)
        if hasta is not None:
            stmt = stmt.where(SwimSession.session_date <= hasta)
        return [sesion_desde_fila(f) for f in (await self.db.execute(stmt)).scalars()]

    async def por_id(self, sesion_id: int) -> Sesion | None:
        """`None` si es de otro equipo o de otro atleta — el router: 404 en ambos."""
        fila = await self._fila(sesion_id)
        return sesion_desde_fila(fila) if fila is not None else None

    # ── Escrituras ───────────────────────────────────────────────────────────

    async def guardar(self, sesion: Sesion) -> Sesion | None:
        """Crea la sesión (sin `id`) o la sobrescribe (con `id`). Confirma.

        `None` si no le corresponde a quien escribe: la que se quiere
        sobrescribir no es visible, o es una nueva a nombre de otro atleta. Que
        el atleta sea del equipo lo impone la FK compuesta; que exista y sea
        visible lo comprueba quien llama, preguntando a su repositorio. El
        equipo sale de la sesión, nunca de la petición.
        """
        if sesion.id is None:
            if not self.principal.owns_swimmer(sesion.atleta_id):
                return None
            fila = SwimSession(team_id=self.principal.team_id, swimmer_id=sesion.atleta_id)
            self.db.add(fila)
        else:
            fila = await self._fila(sesion.id)
            if fila is None or fila.swimmer_id != sesion.atleta_id:
                return None
        fila.session_date = sesion.fecha
        fila.distance_m = sesion.distancia_m
        fila.duration_s = round(sesion.duracion.segundos)
        fila.rpe = sesion.rpe
        fila.notes = sesion.notas
        await self.db.commit()
        return sesion_desde_fila(fila)

    async def borrar(self, sesion_id: int) -> bool:
        """Borra la fila. `False` si no le corresponde (el router: 404)."""
        fila = await self._fila(sesion_id)
        if fila is None:
            return False
        await self.db.delete(fila)
        await self.db.commit()
        return True
