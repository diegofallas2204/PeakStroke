"""Las inscripciones: quién está en qué macrociclo (C9, 2026-10-05).

Se separó de `macrociclos.py`, que pasaba de 300 líneas y cuya división natural
—avisada desde C5— era justo esta. **No es otro agregado**: la inscripción
cuelga del macrociclo (§5.4, raíz del agregado de planificación), y por eso
este repositorio **compone** al de macrociclos en vez de tener su propio
alcance. Lo que ve de una inscripción es lo que su macrociclo deja ver:

    macros.acotar()          ──▶  ¿es un macrociclo que te toca?   (el club)
    scope_to_own_swimmer()   ──▶  ¿es TU inscripción dentro de él?  (el atleta)

Hasta el 2026-10-05 `inscripcion(id)` era un `db.get` sin ninguno de los dos:
no fugaba porque el router comprobaba antes el macrociclo, pero una lectura de
repositorio que no se acota es una fuga esperando a su primer llamador nuevo.

**La regla «un atleta, un macrociclo vivo» no está aquí** (`inscripciones_vivas`
devuelve todas sin juzgar): vive en `api/v1/macrociclos/inscripcion.py`.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.dominio.entidades import Inscripcion, Macrociclo
from app.persistencia.mapeo import inscripcion_desde_fila, macrociclo_desde_fila
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, Plan

from .macrociclos import RepositorioDeMacrociclos


class RepositorioDeInscripciones:
    """Las inscripciones que alcanza quien pregunta, a través de su macrociclo."""

    __slots__ = ("macros",)

    def __init__(self, macros: RepositorioDeMacrociclos) -> None:
        self.macros = macros

    def acotar(self, stmt):
        """Los dos filtros: el macrociclo visible y, si es atleta, la suya."""
        stmt = self.macros.acotar(stmt.join(Plan, Plan.id == AthletePlan.plan_id))
        return self.macros.principal.scope_to_own_swimmer(stmt, AthletePlan.swimmer_id)

    async def _fila(self, inscripcion_id: int) -> AthletePlan | None:
        stmt = self.acotar(select(AthletePlan)).where(AthletePlan.id == inscripcion_id)
        return (await self.macros.db.execute(stmt)).scalar_one_or_none()

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def por_id(self, inscripcion_id: int) -> Inscripcion | None:
        """`None` si no es visible (el router: 404), activa o de baja."""
        fila = await self._fila(inscripcion_id)
        return inscripcion_desde_fila(fila) if fila is not None else None

    async def de(self, plan_id: int, swimmer_id: int) -> Inscripcion | None:
        """La de ese atleta en ese macrociclo, **también si está de baja**.

        La pareja es única (`uq_athlete_plans_pair`): quien está de baja en un
        macrociclo no se vuelve a inscribir en él, se devuelve (`restore`).
        """
        stmt = self.acotar(select(AthletePlan)).where(
            AthletePlan.plan_id == plan_id, AthletePlan.swimmer_id == swimmer_id,
        )
        fila = (await self.macros.db.execute(stmt)).scalar_one_or_none()
        return inscripcion_desde_fila(fila) if fila is not None else None

    async def inscritos_en(self, plan_id: int, *, incluir_de_baja: bool = False) -> set[int]:
        """Los `swimmer_id` inscritos en ese macrociclo (vivos, o también de baja).

        Acotado como todo lo demás: hoy su único llamador ya resolvió el
        macrociclo, pero una lectura sin acotar espera a su primer llamador nuevo.
        """
        stmt = self.acotar(select(AthletePlan.swimmer_id)).where(AthletePlan.plan_id == plan_id)
        if not incluir_de_baja:
            stmt = stmt.where(AthletePlan.is_active.is_(True))
        return set((await self.macros.db.execute(stmt)).scalars())

    async def inscripciones_vivas(self) -> list[tuple[int, Macrociclo]]:
        """(swimmer_id, macrociclo) de cada inscripción activa del equipo.

        Devuelve **todas** sin juzgar cuáles reservan al atleta: eso es la regla
        de «un atleta, un macrociclo vivo» y vive en
        `api/v1/macrociclos/inscripcion.py`, que es donde está explicada.

        Del **equipo** entero y no solo de los macrociclos visibles: la regla
        bloquea también con un macrociclo que este entrenador no lleva.

        Pares y no un diccionario a propósito. Colapsar aquí por nadador daría
        por buena justo la invariante que el llamador viene a comprobar: si
        alguien apareciera en dos macrociclos, el último leído taparía al otro y
        el bloqueo dependería del orden de las filas.
        """
        stmt = (
            select(AthletePlan.swimmer_id, Plan)
            .join(Plan, Plan.id == AthletePlan.plan_id)
            .where(
                Plan.team_id == self.macros.principal.team_id,
                AthletePlan.is_active.is_(True),
            )
        )
        return [
            (swimmer_id, macrociclo_desde_fila(fila))
            for swimmer_id, fila in (await self.macros.db.execute(stmt)).all()
        ]

    # ── Escritura ────────────────────────────────────────────────────────────

    async def guardar(
        self, inscripcion: Inscripcion, *, pruebas: Sequence[AthleteEvent] = (),
    ) -> AthletePlan | None:
        """Crea la inscripción (sin `id`) o guarda su estado (con `id`). Confirma.

        Al crear, `pruebas` son las filas de sus pruebas objetivo con sus semanas
        ya generadas, y entran en la **misma** transacción: una inscripción sin
        sus pruebas no es un estado que deba existir ni un instante. Son filas
        porque `PruebaObjetivo` y `Semana` (§5.7-5.8) son los puntos 3 y 4 de C9.

        Al sobrescribir, escribe **solo lo que la entidad puede cambiar** —hoy,
        si está activa—: atleta y macrociclo no se mueven, y la base aeróbica no
        tiene todavía quien la cambie. Así una baja no reescribe de paso un dato
        que nadie tocó. `None` si no es visible para quien escribe.

        El equipo sale del `Principal`, nunca de la entidad.
        """
        if inscripcion.id is None:
            fila = AthletePlan(
                team_id=self.macros.principal.team_id,
                plan_id=inscripcion.macrociclo_id, swimmer_id=inscripcion.atleta_id,
                aerobic_base=(inscripcion.base_aerobica.segundos_por_100
                              if inscripcion.base_aerobica else None),
                aerobic_base_source=inscripcion.fuente_de_base,
                is_active=inscripcion.activa,
            )
            fila.events.extend(pruebas)
            self.macros.db.add(fila)
        else:
            fila = await self._fila(inscripcion.id)
            if fila is None:
                return None
            fila.is_active = inscripcion.activa
        await self.macros.db.commit()
        await self.macros.db.refresh(fila)
        inscripcion.id = fila.id
        return fila
