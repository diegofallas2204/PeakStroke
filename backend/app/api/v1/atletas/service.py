"""La ficha del atleta hacia fuera: solo forma, ninguna consulta propia.

Lo que este archivo tenía antes —`list_swimmers`, `get_swimmer`,
`create_swimmer`, `set_active`— está en `persistencia/repositorios/atletas.py`.
Aquí queda lo que es de la API: convertir una fila en la respuesta y decidir qué
lleva, y traducir la petición a la entidad (`nueva_desde`, `aplicar`) —desde
C9 (2026-10-05) toda escritura de una ficha pasa por `Atleta`—.

Las dos fronteras ya no se recuerdan aquí. El repositorio se construye con el
`Principal` y las aplica siempre; una función que recibiera solo un `swimmer_id`
acabaría tarde o temprano devolviendo lo que no debe, y eso ya pasó.
"""
from __future__ import annotations

from dataclasses import replace

from app.dominio.entidades import Atleta
from app.dominio.valores import Especialidad, Estilo, Genero
from app.persistencia.mapeo import atleta_desde_fila
from app.persistencia.repositorios import RepositorioDeUsuarios
from app.persistencia.tablas.atletas import Swimmer

from .schemas import SwimmerCreate, SwimmerResponse, SwimmerUpdate

# Lo que una ficha no puede dejar de tener: en un PUT, `null` no lo vacía.
_OBLIGATORIOS = ("name", "specialty", "main_stroke")


def nueva_desde(data: SwimmerCreate) -> Atleta:
    return Atleta.nueva(
        data.name, nacimiento=data.birth_date, genero=data.gender,
        especialidad=data.specialty, estilo_principal=data.main_stroke,
        peso_kg=data.weight_kg, altura_cm=data.height_cm, notas=data.notes,
    )


def aplicar(atleta: Atleta, data: SwimmerUpdate) -> Atleta:
    """La ficha con los cambios de un PUT parcial: solo lo que llega se toca.

    `null` borra lo opcional (género, peso, notas…) y es `ValueError` —el
    router: 422— en lo obligatorio. Antes llegaba a la columna `NOT NULL` y
    reventaba en el commit con un 500. `replace` vuelve a pasar por el
    constructor.
    """
    cambios = data.model_dump(exclude_unset=True)
    vacios = [c for c in _OBLIGATORIOS if c in cambios and cambios[c] is None]
    if vacios:
        raise ValueError(f"No se pueden vaciar: {', '.join(vacios)}")
    campos: dict[str, object] = {}
    if "name" in cambios:
        campos["nombre"] = cambios["name"]
    if "birth_date" in cambios:
        campos["nacimiento"] = cambios["birth_date"]
    if "gender" in cambios:
        campos["genero"] = Genero.desde_texto(cambios["gender"]) if cambios["gender"] else None
    if "specialty" in cambios:
        campos["especialidad"] = Especialidad.desde_texto(cambios["specialty"])
    if "main_stroke" in cambios:
        campos["estilo_principal"] = Estilo.desde_texto(cambios["main_stroke"])
    for api, entidad in (("weight_kg", "peso_kg"), ("height_cm", "altura_cm"), ("notes", "notas")):
        if api in cambios:
            campos[entidad] = cambios[api]
    return replace(atleta, **campos)


def to_response(fila: Swimmer) -> SwimmerResponse:
    """La ficha hacia fuera. La edad se la pide al atleta, no a una función."""
    resp = SwimmerResponse.model_validate(fila)
    resp.age = atleta_desde_fila(fila).edad_en()
    return resp


async def with_accounts(
    usuarios: RepositorioDeUsuarios, filas: list[Swimmer],
) -> list[SwimmerResponse]:
    """Las fichas, cada una con el email de su cuenta si la tiene.

    Una consulta para toda la lista en vez de una por ficha: la página de
    atletas pinta el equipo entero y el N+1 se nota enseguida. La consulta es del
    agregado Usuario, así que la hace su repositorio — aquí solo se juntan.
    """
    respuestas = [to_response(f) for f in filas]
    emails = await usuarios.correos_de(
        [f.user_id for f in filas if f.user_id is not None],
    )
    for resp, fila in zip(respuestas, filas, strict=True):
        if fila.user_id is not None:
            resp.user_email = emails.get(fila.user_id)
    return respuestas
