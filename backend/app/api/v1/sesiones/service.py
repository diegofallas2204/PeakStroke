"""De la petición a la entidad y de la entidad a la respuesta.

Toda sesión que se escribe se construye como `Sesion` antes de llegar al
repositorio, así que las reglas del dominio (metros positivos, RPE en la escala)
se aplican siempre en el mismo sitio, también al corregir una: `replace`
vuelve a pasar por el constructor.
"""
from __future__ import annotations

from dataclasses import replace

from app.dominio.entidades import Sesion
from app.dominio.valores import Tiempo
from app.persistencia.repositorios import RepositorioDeAtletas, RepositorioDeSesiones

from .schemas import TrainingSessionCreate, TrainingSessionResponse, TrainingSessionUpdate

# Lo que una sesión no puede dejar de tener: en un PATCH, `null` no los borra.
_OBLIGATORIOS = ("session_date", "distance_m", "duration_s")
# Del nombre del API al de la entidad.
_CAMPO_DE = {
    "session_date": "fecha", "distance_m": "distancia_m", "duration_s": "duracion",
    "rpe": "rpe", "notes": "notas",
}


def to_response(sesion: Sesion) -> TrainingSessionResponse:
    assert sesion.id is not None
    return TrainingSessionResponse(
        id=sesion.id, swimmer_id=sesion.atleta_id, session_date=sesion.fecha,
        distance_m=sesion.distancia_m, duration_s=round(sesion.duracion.segundos),
        rpe=sesion.rpe, notes=sesion.notas,
        pace_100m=round(sesion.ritmo_medio().segundos_por_100, 2),
    )


async def crear(
    sesiones: RepositorioDeSesiones, atletas: RepositorioDeAtletas, data: TrainingSessionCreate,
) -> Sesion | None:
    """`None` si el atleta no existe para quien escribe (el router: 404).

    El atleta llega en el cuerpo, no en la URL, así que hay que preguntarlo: a
    su repositorio, que aplica las dos fronteras —equipo y atleta propio—.
    """
    if await atletas.fila_de(data.swimmer_id) is None:
        return None
    return await sesiones.guardar(Sesion(
        atleta_id=data.swimmer_id, fecha=data.session_date, distancia_m=data.distance_m,
        duracion=Tiempo(data.duration_s), rpe=data.rpe, notas=data.notes,
    ))


async def actualizar(
    sesiones: RepositorioDeSesiones, sesion_id: int, data: TrainingSessionUpdate,
) -> Sesion | None:
    """`None` si la sesión no le corresponde. `ValueError` si el cambio no vale."""
    actual = await sesiones.por_id(sesion_id)
    if actual is None:
        return None
    cambios = data.model_dump(exclude_unset=True)
    vacios = [c for c in _OBLIGATORIOS if c in cambios and cambios[c] is None]
    if vacios:
        raise ValueError(f"No se pueden vaciar: {', '.join(vacios)}")
    if "duration_s" in cambios:
        cambios["duration_s"] = Tiempo(cambios["duration_s"])
    nueva = replace(actual, **{_CAMPO_DE[c]: v for c, v in cambios.items()})
    return await sesiones.guardar(nueva)
