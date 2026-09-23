"""Un atleta, un macrociclo vivo. Quién puede inscribirse dónde.

Vive aparte de `service.py` por la misma razón que el repositorio: es una
invariante corta que casi nunca cambia, y enterrarla entre 300 líneas de CRUD y
motor la haría invisible en el primer diff que la rompa.

La regla es de dominio, no de permisos. Un macrociclo es un bloque de 12-18
semanas con su propia curva, su distribución de kilómetros y su taper; una
temporada son ~3 encadenados. Estar en dos a la vez no significa "entrenar el
doble", significa tener dos planes contradictorios para el mismo cuerpo y las
mismas fechas. Por eso el bloqueo aplica **a todos, dueño incluido**: no es un
tema de a quién le toca el atleta, sino de que ese plan no existe.

De ahí sale, de rebote, lo que se pedía en la interfaz: un atleta que ya está en
un macrociclo no le aparece a otro entrenador para meterlo en uno nuevo. No hace
falta un filtro por entrenador — no le aparece a nadie, porque no se puede.
Para moverlo hay que sacarlo del anterior, que es un gesto explícito y
reversible (`POST .../athletes/{id}/restore`).

**Quién decide si un macrociclo reserva al atleta es este archivo**, no el
repositorio: el repositorio trae todas las inscripciones vivas del equipo y aquí
se descartan las de macrociclos terminados. Un macrociclo terminado ya no
reserva a nadie; los demás estados sí, el borrador incluido — si se está
planificando, el atleta está comprometido.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.entidades import Macrociclo
from app.dominio.valores import EstadoDeMacro
from app.persistencia.repositorios import RepositorioDeMacrociclos
from app.persistencia.tablas.atletas import Swimmer


async def live_enrollments(
    repo: RepositorioDeMacrociclos, *, excluding_plan_id: int | None = None,
) -> dict[int, Macrociclo]:
    """swimmer_id → el macrociclo vivo que ya lo tiene inscrito.

    `excluding_plan_id` deja fuera el macrociclo sobre el que se está
    trabajando: estar en él no puede ser motivo para no poder estar en él.
    """
    ocupados: dict[int, Macrociclo] = {}
    for swimmer_id, macro in await repo.inscripciones_vivas():
        if macro.id == excluding_plan_id:
            continue
        if macro.estado_efectivo() is EstadoDeMacro.TERMINADO:
            continue
        ocupados[swimmer_id] = macro
    return ocupados


async def blocking_plan(
    repo: RepositorioDeMacrociclos, swimmer_id: int, *, target_plan_id: int,
) -> Macrociclo | None:
    """El macrociclo que impide inscribir a ese atleta, si lo hay."""
    ocupados = await live_enrollments(repo, excluding_plan_id=target_plan_id)
    return ocupados.get(swimmer_id)


async def blocking_plan_for(
    repo: RepositorioDeMacrociclos, athlete_plan_id: int,
) -> Macrociclo | None:
    """Lo mismo, para una inscripción que se quiere **reactivar**.

    Reactivar es inscribir otra vez: entre la baja y la vuelta puede haber
    entrado en otro macrociclo, y sin esta comprobación el `restore` sería la
    puerta trasera de la regla que `add_athlete` cierra por delante.
    """
    ap = await repo.inscripcion(athlete_plan_id)
    if ap is None:
        return None
    return await blocking_plan(repo, ap.swimmer_id, target_plan_id=ap.plan_id)


async def assignable_swimmers(
    db: AsyncSession, repo: RepositorioDeMacrociclos, macro: Macrociclo,
) -> list[Swimmer]:
    """Las fichas activas del equipo que hoy pueden entrar en `macro`.

    Fuera quedan las dadas de baja, las que ya están en este macrociclo y las
    comprometidas con otro que sigue vivo. Es la misma condición que comprueba
    `blocking_plan` al inscribir: la lista no es una sugerencia de la interfaz,
    es la regla enseñada por adelantado.
    """
    ocupados = await live_enrollments(repo, excluding_plan_id=macro.id)
    ya_dentro = await repo.inscritos_en(macro.id)
    stmt = (
        select(Swimmer)
        .where(Swimmer.team_id == macro.equipo_id, Swimmer.is_active.is_(True))
        .order_by(Swimmer.name)
    )
    return [
        s for s in (await db.execute(stmt)).scalars()
        if s.id not in ocupados and s.id not in ya_dentro
    ]
