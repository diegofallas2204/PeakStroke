"""La ficha del atleta hacia fuera: solo forma, ninguna consulta propia.

Lo que este archivo tenía antes —`list_swimmers`, `get_swimmer`,
`create_swimmer`, `set_active`— está en `persistencia/repositorios/atletas.py`.
Aquí queda lo que es de la API: convertir una fila en la respuesta y decidir qué
lleva.

Las dos fronteras ya no se recuerdan aquí. El repositorio se construye con el
`Principal` y las aplica siempre; una función que recibiera solo un `swimmer_id`
acabaría tarde o temprano devolviendo lo que no debe, y eso ya pasó.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistencia.mapeo import atleta_desde_fila
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.usuarios import User

from .schemas import SwimmerResponse


def to_response(fila: Swimmer) -> SwimmerResponse:
    """La ficha hacia fuera. La edad se la pide al atleta, no a una función."""
    resp = SwimmerResponse.model_validate(fila)
    resp.age = atleta_desde_fila(fila).edad_en()
    return resp


async def with_accounts(db: AsyncSession, filas: list[Swimmer]) -> list[SwimmerResponse]:
    """Las fichas, cada una con el email de su cuenta si la tiene.

    Una consulta para toda la lista en vez de una por ficha: la página de
    atletas pinta el equipo entero y el N+1 se nota enseguida.
    """
    respuestas = [to_response(f) for f in filas]
    user_ids = [f.user_id for f in filas if f.user_id is not None]
    if not user_ids:
        return respuestas

    stmt = select(User.id, User.email).where(User.id.in_(user_ids))
    emails = dict((await db.execute(stmt)).all())
    for resp, fila in zip(respuestas, filas, strict=True):
        if fila.user_id is not None:
            resp.user_email = emails.get(fila.user_id)
    return respuestas
