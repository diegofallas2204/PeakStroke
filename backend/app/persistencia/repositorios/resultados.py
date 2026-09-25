"""El agregado Resultado: lo que el atleta nadó, colgando de él y no del plan.

Mismas tres condiciones que los tests aeróbicos —equipo, nadador propio y de
alta—, juntas en `acotar`.

**Las semanas se preguntan aquí, no a la semana.** `weekly_plans` no guarda
ningún resultado (R2 enmendada, §10.2): cada semana reúne los del atleta en esa
prueba y esos siete días, y enseña su promedio convertido a la piscina del
macrociclo (el de otra piscina entra convertido, no se descarta). La regla de qué cae
dónde es del dominio (`entidades.resultado`); lo que pone este repositorio es la
consulta, **una sola** para todas las semanas que se le pidan, en vez de una por
semana.

**Ya no hay sombra.** `weekly_plans.real_time` convivió una versión como copia
que se escribía y nadie leía, y C7 la retiró (migración `c7a1e0d5b2f4`): el
tiempo de una semana existe **solo** aquí.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.dominio.entidades import (
    DIAS_DE_UNA_SEMANA,
    Contexto,
    Resultado,
    de_la_semana,
    real_de_la_semana,
)
from app.dominio.valores import Estilo, Piscina, Prueba
from app.persistencia.mapeo import resultado_desde_fila
from app.persistencia.tablas.planes import AthleteEvent, WeeklyPlan
from app.persistencia.tablas.resultados import Result


def _prueba_de(evento: AthleteEvent) -> Prueba:
    return Prueba(evento.distance, Estilo.desde_texto(evento.stroke))


class RepositorioDeResultados:
    """Los resultados que alcanza un `Principal`, y nada más."""

    __slots__ = ("db", "principal")

    def __init__(self, db: AsyncSession, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    def acotar(self, stmt):
        stmt = stmt.where(
            Result.team_id == self.principal.team_id, Result.is_active.is_(True),
        )
        return self.principal.scope_to_own_swimmer(stmt, Result.swimmer_id)

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def de_atletas_entre(
        self, atletas: Iterable[int], desde: date, hasta: date,
    ) -> list[Resultado]:
        """Los de esos atletas con fecha en `[desde, hasta)`."""
        ids = set(atletas)
        if not ids:
            return []
        stmt = self.acotar(select(Result)).where(
            Result.swimmer_id.in_(ids),
            Result.result_date >= desde, Result.result_date < hasta,
        )
        return [resultado_desde_fila(f) for f in (await self.db.execute(stmt)).scalars()]

    async def reales_por_semana(
        self, pruebas: Iterable[AthleteEvent], piscina: Piscina,
    ) -> dict[int, float]:
        """`{weekly_plans.id: promedio en segundos}` de las semanas con algún resultado.

        La semana que no tiene ninguno **no está** en el diccionario, así que
        `.get(w.id)` devuelve `None`: la semana no tiene tiempo. Las
        pruebas tienen que traer `weeks` y `athlete_plan` cargados.

        `piscina` es la del macrociclo: un tiempo nadado en otra entra en el
        promedio convertido a esta (`Resultado.tiempo_en`).
        """
        pruebas = list(pruebas)
        semanas = [w for p in pruebas for w in p.weeks]
        if not semanas:
            return {}
        resultados = await self.de_atletas_entre(
            (p.athlete_plan.swimmer_id for p in pruebas),
            min(w.week_date for w in semanas),
            max(w.week_date for w in semanas) + timedelta(days=DIAS_DE_UNA_SEMANA),
        )
        reales: dict[int, float] = {}
        for p in pruebas:
            prueba, atleta = _prueba_de(p), p.athlete_plan.swimmer_id
            for w in p.weeks:
                real = real_de_la_semana(
                    resultados, atleta_id=atleta, prueba=prueba, piscina=piscina,
                    lunes=w.week_date,
                )
                if real is not None:
                    reales[w.id] = real.segundos
        return reales

    # ── Escritura ────────────────────────────────────────────────────────────

    async def apuntar_en_semana(
        self, semana: WeeklyPlan, prueba: AthleteEvent, piscina: Piscina,
        tiempo: float | None,
    ) -> None:
        """Lo que hace hoy `PATCH /weeks/{id}`: fijar **el** tiempo de la semana.

        El contrato del API tiene un solo tiempo por semana, así que apuntar uno
        **reemplaza** los que hubiera en ella —de cualquier piscina, porque todos
        cuentan en el promedio que la celda enseña—: los retira y, si `tiempo` no
        es `None`, apunta uno nuevo con la fecha del lunes y la piscina del plan.
        Borrar el de la semana es `tiempo=None`. Retirar, no borrar: el tiempo
        corregido sigue en la tabla. No confirma: lo hace quien llama.
        """
        atleta = prueba.athlete_plan.swimmer_id
        filas = (await self.db.execute(self.acotar(select(Result)).where(
            Result.swimmer_id == atleta,
            Result.result_date >= semana.week_date,
            Result.result_date < semana.week_date + timedelta(days=DIAS_DE_UNA_SEMANA),
        ))).scalars().all()
        # La misma regla que al leer, para no retirar lo que la semana no enseña
        # (otra prueba del mismo atleta esa misma semana).
        suyos = {r.id for r in de_la_semana(
            (resultado_desde_fila(f) for f in filas),
            atleta_id=atleta, prueba=_prueba_de(prueba), lunes=semana.week_date,
        )}
        for fila in filas:
            if fila.id in suyos:
                fila.is_active = False
        if tiempo is not None:
            self.db.add(Result(
                team_id=prueba.athlete_plan.team_id, swimmer_id=atleta,
                distance=prueba.distance, stroke=prueba.stroke, time=tiempo,
                result_date=semana.week_date, pool=piscina.value,
                context=Contexto.CONTROL.value,
            ))

