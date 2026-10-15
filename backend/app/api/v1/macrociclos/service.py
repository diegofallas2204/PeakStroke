"""El macrociclo como objeto del API: crearlo, editarlo y borrarlo.

Las reglas de **acceso** (quién ve qué) están en
`persistencia/repositorios/macrociclos.py`, y la de **inscripción** (un atleta,
un macrociclo vivo) en `inscripcion.py`. Este módulo asume que las dos ya se
comprobaron.

**Este archivo ya no importa ninguna tabla** (C9, 2026-10-13). Traduce el
formulario a la entidad —`aplicar` le pide al `Macrociclo` que cambie— y quien
guarda es el repositorio. Construirlo es de `PlanCreate.a_entidad()` desde el
2026-10-14 (TODO-24): el schema lo construye al validar, como `EventInput`, para
que lo que no cabe salga como un 422. Antes armaba la fila con
`Plan(**data.model_dump())` y la editaba con un `setattr` por campo. Cómo se
presenta el resultado está en `presentacion.py`.

**Lo que este archivo dejó de tener antes.** Hasta el paso 5 vivían aquí
`current_week_of()` y `effective_status()`: dos reglas puras que el tablero y
`aerobic_tests` importaban de un módulo hermano. Hoy la respuesta viaja dentro
del `Macrociclo` (`semana_actual()`, `estado_efectivo()`).
"""
from __future__ import annotations

from app.dominio.entidades import Macrociclo
from app.dominio.valores import EstadoDeMacro, Piscina
from app.persistencia.repositorios import RepositorioDeMacrociclos

from .schemas import PlanUpdate


def aplicar(macro: Macrociclo, data: PlanUpdate) -> None:
    """Le pide al macrociclo los cambios que el formulario **envió**.

    Un campo que no viaja no cambia. `notes` y `main_event` sí admiten `null`
    —es borrarlos—; en los otros cuatro un `null` explícito tampoco cambia nada:
    no pueden quedar vacíos, y hasta el 2026-10-13 llegaban como `None` a una
    columna `NOT NULL` y salían como un 500.
    """
    enviados = data.model_dump(exclude_unset=True)
    if enviados.get("name") is not None:
        macro.renombrar(enviados["name"])
    if "notes" in enviados:
        macro.anotar(enviados["notes"])
    if enviados.get("status") is not None:
        macro.cambiar_estado(EstadoDeMacro.desde_texto(enviados["status"]))
    if "main_event" in enviados:
        macro.fijar_meta(enviados["main_event"])
    if enviados.get("pool") is not None:
        macro.cambiar_piscina(Piscina.desde_texto(enviados["pool"]))
    if enviados.get("n_mac") is not None:
        macro.numerar(enviados["n_mac"])


async def delete_plan(repo: RepositorioDeMacrociclos, macro: Macrociclo) -> int:
    """Borra el macrociclo. Devuelve **cuántos tests aeróbicos lo impidieron**.

    0 significa borrado. Cualquier otro número es la razón por la que no, y el
    router la convierte en un 409 que se puede leer. El porqué de preguntar
    antes en vez de capturar el `IntegrityError` está en el repositorio, que es
    quien cuenta.
    """
    bloqueantes = await repo.tests_que_bloquean_el_borrado(macro.id)
    if bloqueantes:
        return bloqueantes
    await repo.borrar(macro)
    return 0
