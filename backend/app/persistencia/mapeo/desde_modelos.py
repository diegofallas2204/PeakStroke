"""De fila de SQLAlchemy a entidad de dominio.

**La entidad se construye desde la fila; no la envuelve.** La diferencia importa
por tres razones:

* un envoltorio con la instancia del ORM dentro escribe en la sesión al mutarse,
  así que el repositorio del paso 5 se quedaría sin trabajo y `dominio → nada`
  sería mentira de hecho aunque no hubiera ningún `import`;
* un envoltorio se construye alrededor de *cualquier* fila, y entonces
  `TestAerobico` vuelve a poder tener llegadas de reloj sin convertir — que es
  justo la invariante que el paso 2 viene a instalar;
* la traducción `birth_date → nacimiento` tiene que vivir en algún sitio, y ese
  sitio es este, no el dominio.

Todos los modelos viven ya en `persistencia/tablas/` (paso 5, 2026-08-25) y
este archivo los lee de al lado: `app/modules/` no existe, y con él desapareció
el último import que miraba hacia arriba.

**Conversión estricta a propósito.** `specialty`, `main_stroke`, `pool`, `status`
y `gender` son vocabularios cerrados por Pydantic en la entrada, así que un valor
que no case es una fila corrupta y tiene que romper con un error legible aquí, no
convertirse en un valor por defecto que camufle el problema tres capas más allá.
"""
from __future__ import annotations

from sqlalchemy import inspect

from app.dominio.entidades import (
    Atleta,
    Competencia,
    Contexto,
    FaseDelMacro,
    Macrociclo,
    Resultado,
    TestAerobico,
)
from app.dominio.valores import (
    Especialidad,
    EstadoDeMacro,
    Estilo,
    Fase,
    Genero,
    ModoDeIngreso,
    Piscina,
    Prueba,
    Tiempo,
    TipoDeTest,
)
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.planes import Competition, Plan, PlanPhase
from app.persistencia.tablas.resultados import Result
from app.persistencia.tablas.tests_aerobicos import AerobicTest


def _cargado(fila: object, relacion: str) -> bool:
    """Si esa relación ya está en memoria.

    Tocar una relación no cargada dentro de una sesión async revienta con
    `MissingGreenlet`, y no todos los llamadores traen el plan con sus fases.
    Mapear lo que hay —en vez de exigir que todo venga cargado— permite que
    `semana_actual()` funcione sobre un plan pelado, que es como llega desde el
    dashboard.
    """
    return relacion not in inspect(fila).unloaded


def atleta_desde_fila(fila: Swimmer) -> Atleta:
    return Atleta(
        id=fila.id,
        equipo_id=fila.team_id,
        nombre=fila.name,
        usuario_id=fila.user_id,
        nacimiento=fila.birth_date,
        genero=Genero.desde_texto(fila.gender) if fila.gender else None,
        especialidad=Especialidad.desde_texto(fila.specialty),
        estilo_principal=Estilo.desde_texto(fila.main_stroke),
        peso_kg=fila.weight_kg,
        altura_cm=fila.height_cm,
        notas=fila.notes,
        activo=fila.is_active,
    )


def _fase_desde_fila(fila: PlanPhase) -> FaseDelMacro:
    # La columna guarda la clave de `Fase` desde P3 (y un CHECK lo impone), así
    # que aquí no se traduce nada: una fila con otro texto es un error, no un caso.
    return FaseDelMacro(
        fase=Fase.desde_texto(fila.type),
        id=fila.id,
        nombre=fila.name,
        semana_inicio=fila.week_start,
        semana_fin=fila.week_end,
        color=fila.color,
        orden=fila.sort,
    )


def _competencia_desde_fila(fila: Competition) -> Competencia:
    return Competencia(
        id=fila.id,
        nombre=fila.name,
        semana=fila.week_number,
        dias=fila.days,
        es_principal=fila.is_main,
    )


def macrociclo_desde_fila(fila: Plan) -> Macrociclo:
    return Macrociclo(
        inicio=fila.start_date,
        semanas=fila.total_weeks,
        id=fila.id,
        equipo_id=fila.team_id,
        nombre=fila.name,
        semanas_por_micro=fila.weeks_per_micro,
        km_totales=fila.total_km,
        curva=fila.progression_curve,
        piscina=Piscina.desde_texto(fila.pool),
        n_mac=fila.n_mac,
        prueba_principal=fila.main_event,
        estado=EstadoDeMacro.desde_texto(fila.status),
        notas=fila.notes,
        fases=[_fase_desde_fila(f) for f in fila.phases] if _cargado(fila, "phases") else [],
        competencias=(
            [_competencia_desde_fila(c) for c in fila.competitions]
            if _cargado(fila, "competitions") else []
        ),
    )


def test_desde_fila(fila: AerobicTest) -> TestAerobico | None:
    """`None` si esa fila no es un test de parciales (CSS, ingreso directo).

    **Se construye siempre en modo `REP`**, y no con el `input_mode` guardado.
    No es un descuido: en la base de datos está el tiempo NADADO, porque la
    conversión la hizo el constructor una sola vez al escribir. `input_mode` se
    guarda por trazabilidad —para saber cómo lo apuntó el entrenador—, no porque
    el cálculo dependa de él. Releer con el modo original volvería a restar la
    salida a unos números que ya la tienen restada.
    """
    if not fila.rep_distance or not _cargado(fila, "splits") or not fila.splits:
        return None
    tipo = TipoDeTest.desde_texto(fila.test_type)
    if not tipo.tiene_parciales:
        return None
    return TestAerobico(
        id=fila.id,
        atleta_id=fila.swimmer_id,
        macrociclo_id=fila.plan_id,
        tipo=tipo,
        fecha=fila.test_date,
        distancia_rep=fila.rep_distance,
        salida=Tiempo(fila.send_off) if fila.send_off else None,
        modo=ModoDeIngreso.REP,
        numeros=[s.split_time for s in fila.splits],
        notas=fila.notes,
        activo=fila.is_active,
    )


def resultado_desde_fila(fila: Result) -> Resultado:
    """El estilo pasa por `Estilo.desde_texto`, así que una fila con el estilo
    crudo (`"crol"`) sigue siendo la misma prueba que una con `"libre"`."""
    return Resultado(
        id=fila.id,
        atleta_id=fila.swimmer_id,
        prueba=Prueba(fila.distance, Estilo.desde_texto(fila.stroke)),
        tiempo=Tiempo(fila.time),
        fecha=fila.result_date,
        piscina=Piscina.desde_texto(fila.pool),
        contexto=Contexto.desde_texto(fila.context),
        competencia_id=fila.competition_id,
    )
