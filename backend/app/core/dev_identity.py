"""El conmutador de desarrollo: suplantar a alguien y saltarse los guards.

Todo lo que hay aquí **solo existe con `settings.dev_identity_enabled`**, que a
su vez exige el login apagado y estar fuera de producción. Está en un archivo
propio justo por eso: es la única puerta de suplantación del sistema, y conviene
que quepa entera en una pantalla para que ningún diff la abra sin que se note.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.persistencia.tablas.usuarios import User

logger = logging.getLogger(__name__)

# Cabeceras del conmutador de desarrollo. Sus nombres viven aquí para que el
# endpoint que las anuncia, el CORS y los tests no los escriban a mano.
#
# Son dos ejes distintos y esa separación es el punto:
#
#   X-PeakStroke-Dev-User    ──▶  QUIÉN eres.  La interfaz que ves es la de ese
#                                 rol, fielmente: un atleta recibe 403 donde un
#                                 atleta recibe 403. Sin eso no se puede revisar
#                                 la UI de atleta, porque todo respondería 200.
#
#   X-PeakStroke-Dev-Bypass  ──▶  Si además puedes SALTARTE los guards de rol.
#                                 Levanta lo que puedes hacer, no lo que ves: el
#                                 filtro por nadador sigue puesto, así que sigues
#                                 mirando la aplicación con los ojos de esa
#                                 persona mientras te desatascas.
#
# Juntarlas en una sola sería perder justo lo que hace útil al conmutador.
DEV_USER_HEADER = "X-PeakStroke-Dev-User"
DEV_BYPASS_HEADER = "X-PeakStroke-Dev-Bypass"

# Solo ASCII: una cabecera HTTP no puede llevar tildes, así que "sí" nunca
# llegaría hasta aquí aunque lo aceptáramos.
_VERDADERO = {"1", "true", "yes", "on", "si"}


async def dev_user(db: AsyncSession, request: Request) -> User:
    """La cuenta que se suplanta cuando la autenticación está apagada.

    Por defecto, el entrenador de desarrollo. La cabecera `X-PeakStroke-Dev-User`
    permite cambiarla en caliente para ver la aplicación con los ojos de otro
    rol sin reiniciar el proceso ni tocar `.env`.

    **Solo se lee si `settings.dev_identity_enabled`** (ver allí el porqué de
    sus dos condiciones). Con el login encendido esta función ni siquiera se
    llama, así que la cabecera es papel mojado — y `test_dev_identity.py` lo
    fija con un test, porque romper esa línea abriría suplantación arbitraria
    sin que se note leyendo el diff.

    Un email inexistente o una cuenta inactiva (`users.is_active`) **caen al
    usuario por defecto** con un aviso en el log. Devolver 500 convertiría una
    errata en la barra de desarrollo en una aplicación caída.

    Ojo con el caso que **no** cubre ese fallback: la pertenencia revocada
    (`team_members.is_active`) se comprueba después, en `_principal_for`, así
    que suplantar a alguien con el acceso al equipo revocado da 403 y no cae al
    usuario por defecto. Es correcto —esa cuenta no puede operar— pero el
    conmutador del frontend debería no ofrecerla, y por eso
    `service.dev_identities` filtra las dos banderas.
    """
    from app.persistencia.repositorios import RepositorioDeUsuarios

    if settings.dev_identity_enabled:
        pedido = request.headers.get(DEV_USER_HEADER)
        if pedido:
            user = await RepositorioDeUsuarios(db).por_correo(pedido)
            if user is not None and user.is_active:
                return user
            logger.warning(
                "%s: '%s' no existe o está inactivo. Se sigue con %s.",
                DEV_USER_HEADER, pedido, settings.dev_user_email,
            )

    user = await RepositorioDeUsuarios(db).por_correo(settings.dev_user_email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"No existe el usuario de desarrollo '{settings.dev_user_email}'. "
                "Créalo con: python seed.py"
            ),
        )
    return user


def bypass_pedido(request: Request) -> bool:
    """Si esta petición pide modo desarrollador, y si tiene derecho a pedirlo.

    Misma puerta que la cabecera de identidad, a propósito: son la misma
    facilidad de desarrollo y deben apagarse juntas. Con el login encendido —o
    en producción— la cabecera es texto que nadie lee.
    """
    if not settings.dev_identity_enabled:
        return False
    return (request.headers.get(DEV_BYPASS_HEADER) or "").strip().lower() in _VERDADERO
