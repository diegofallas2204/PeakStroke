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

**Aquí se arman las filas de sus pruebas** (C9 punto 3, 2026-10-13). Una
inscripción nace con sus pruebas objetivo y el plan semanal de cada una, y
`guardar` las recibe como `PruebaObjetivo` + las semanas que generó el motor:
quien inscribe ya no construye un `AthleteEvent` ni un `WeeklyPlan`. Las semanas
viajan como `SemanaGenerada` hasta que `Semana` (§5.8) sea entidad, el punto 4.
"""
from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.dominio.entidades import Inscripcion, Macrociclo, PruebaObjetivo
from app.dominio.servicios.motor import SemanaGenerada
from app.persistencia.mapeo import inscripcion_desde_fila, macrociclo_desde_fila
from app.persistencia.tablas.planes import AthleteEvent, AthletePlan, Plan, WeeklyPlan

from .macrociclos import RepositorioDeMacrociclos

# Una prueba objetivo con el plan semanal que el motor generó para ella.
PruebaConSuPlan = tuple[PruebaObjetivo, Sequence[SemanaGenerada]]


def _fila_de_prueba(prueba: PruebaObjetivo, semanas: Sequence[SemanaGenerada]) -> AthleteEvent:
    """La fila de una prueba nueva con sus semanas. El estilo se guarda canónico.

    De cada semana se persiste lo que es un hecho del plan —fecha, kilómetros,
    tiempo esperado y la clave de la fase—; el ritmo y las mejoras se derivan.
    """
    fila = AthleteEvent(
        priority=prueba.prioridad,
        distance=prueba.prueba.distancia, stroke=prueba.prueba.estilo.value,
        current_time=prueba.actual.segundos, goal_time=prueba.meta.segundos,
    )
    fila.weeks.extend(
        WeeklyPlan(
            week_number=s.numero, week_date=s.fecha, planned_km=s.km,
            expected_time=s.tiempo_esperado, phase=s.fase.value,
        )
        for s in semanas
    )
    return fila


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
        self, inscripcion: Inscripcion, *, pruebas: Sequence[PruebaConSuPlan] = (),
    ) -> AthletePlan | None:
        """Crea la inscripción (sin `id`) o guarda su estado (con `id`). Confirma.

        Al crear, `pruebas` son sus pruebas objetivo, cada una con las semanas
        que el motor generó para ella, y entran en la **misma** transacción: una
        inscripción sin sus pruebas no es un estado que deba existir ni un
        instante. Cada `PruebaObjetivo` sale con su `id` y el de su inscripción.

        **Solo al crear**: una prueba no se añade ni se cambia por aquí (ninguna
        ruta lo hace hoy), y pasarlas al sobrescribir levanta `ValueError` en vez
        de ignorarlas en silencio.

        Al sobrescribir, escribe **solo lo que la entidad puede cambiar** —hoy,
        si está activa—: atleta y macrociclo no se mueven, y la base aeróbica no
        tiene todavía quien la cambie. Así una baja no reescribe de paso un dato
        que nadie tocó. `None` si no es visible para quien escribe.

        El equipo sale del `Principal`, nunca de la entidad.
        """
        filas_de_pruebas: list[AthleteEvent] = []
        es_nueva = inscripcion.id is None
        if es_nueva:
            filas_de_pruebas = [_fila_de_prueba(p, semanas) for p, semanas in pruebas]
            fila = AthletePlan(
                team_id=self.macros.principal.team_id,
                plan_id=inscripcion.macrociclo_id, swimmer_id=inscripcion.atleta_id,
                aerobic_base=(inscripcion.base_aerobica.segundos_por_100
                              if inscripcion.base_aerobica else None),
                aerobic_base_source=inscripcion.fuente_de_base,
                is_active=inscripcion.activa,
            )
            fila.events.extend(filas_de_pruebas)
            self.macros.db.add(fila)
        else:
            if pruebas:
                raise ValueError("Las pruebas objetivo solo entran al crear la inscripción")
            fila = await self._fila(inscripcion.id)
            if fila is None:
                return None
            fila.is_active = inscripcion.activa
        # Los `id` de las pruebas se leen tras el `flush` y antes de confirmar:
        # una sesión que expire al confirmar los recargaría con una consulta
        # fuera del contexto async (`MissingGreenlet`).
        await self.macros.db.flush()
        ids_de_pruebas = [f.id for f in filas_de_pruebas]
        await self.macros.db.commit()
        await self.macros.db.refresh(fila)
        if es_nueva:
            self._olvidar_la_nomina_de(fila.plan_id)
        inscripcion.id = fila.id
        for (prueba, _), id_de_prueba in zip(pruebas, ids_de_pruebas, strict=True):
            prueba.id, prueba.inscripcion_id = id_de_prueba, fila.id
        return fila

    def _olvidar_la_nomina_de(self, plan_id: int) -> None:
        """Que la próxima lectura de ese macrociclo traiga la nómina de la base.

        La inscripción nueva entra por su `plan_id`, no por la relación, así que
        un `Plan` que ya estuviera cargado en esta sesión conserva la nómina de
        antes del alta — y SQLAlchemy no repuebla una colección ya cargada de un
        objeto vivo. Que siguiera vivo dependía del recolector de basura (`Plan`
        y sus fases se referencian en ciclo): la respuesta del alta traía o no al
        recién inscrito según cuándo pasara. Expirar la colección lo quita de
        en medio; quien relea el macrociclo la carga con su `selectinload`.

        Mira solo el mapa de identidad: **no consulta**. Un `db.get` habría
        sido una lectura de `Plan` sin `acotar`, y aquí no hace falta leer nada.
        """
        sesion = self.macros.db
        plan = sesion.identity_map.get(sesion.identity_key(Plan, plan_id))
        if plan is not None:
            sesion.expire(plan, ["athlete_plans"])
