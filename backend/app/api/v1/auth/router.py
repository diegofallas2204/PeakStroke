"""Endpoints del módulo auth — sin lógica de negocio.

Con `auth_enabled=false` estos endpoints existen y funcionan, pero nadie está
obligado a pasar por ellos: `/me` responde el usuario de desarrollo y el resto
del API sigue accesible. Al encender el interruptor, el frontend ya tiene contra
qué hablar sin tocar el backend.

El módulo se reparte en tres archivos y este los junta: `sessions.py` (abrir,
rotar y cerrar sesión), `members.py` (las cuentas del equipo) y lo que queda
aquí, que es en qué modo está la aplicación y quién soy yo. Las rutas se montan
sin prefijo, así que las URLs son las mismas que cuando estaba todo junto.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import TipoDeEvento, auditar
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import Principal, get_current_principal, get_current_user
from app.core.dev_identity import DEV_BYPASS_HEADER, DEV_USER_HEADER, bypass_pedido
from app.persistencia.tablas.usuarios import User

from . import credenciales, members, service, sessions
from .schemas import AuthConfig, DevIdentity, MemberResponse, PasswordChange, SessionResponse
from .sessions import _issue_session

router = APIRouter()
router.include_router(sessions.router)
router.include_router(members.router)


@router.get("/config", response_model=AuthConfig)
async def auth_config(request: Request):
    """En qué modo está la aplicación: login real, o conmutador de desarrollo.

    Los campos de desarrollo salen a `None`/`False` en cuanto el login se
    enciende, así que el frontend no tiene que saber la regla — le basta con no
    dibujar la barra si no vienen.
    """
    if not settings.dev_identity_enabled:
        return AuthConfig(auth_enabled=settings.auth_enabled)
    return AuthConfig(
        auth_enabled=settings.auth_enabled,
        dev_identities_enabled=True,
        dev_bypass_active=bypass_pedido(request),
        dev_user_header=DEV_USER_HEADER,
        dev_bypass_header=DEV_BYPASS_HEADER,
    )


@router.get("/dev-identities", response_model=list[DevIdentity])
async def dev_identities(db: AsyncSession = Depends(get_db)):
    """Cuentas que el conmutador de desarrollo puede suplantar.

    **404 con la autenticación encendida**, no 403: con login real esto no es un
    endpoint restringido sino un endpoint que no existe, y un 403 anunciaría que
    hay un modo de suplantación en alguna parte.

    Sin dependencia de sesión a propósito: hace falta ANTES de haber elegido
    identidad, y en el único modo en que responde el API está abierto de todas
    formas.
    """
    if not settings.dev_identity_enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
    return await service.dev_identities(db, settings.dev_user_email)


@router.get("/me", response_model=MemberResponse)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Quién soy. **No exige pertenecer a ningún equipo.**

    Es el segundo endpoint que usa `get_current_user` en vez de
    `get_current_principal`, y por la misma razón que el primero (el canje del
    código): quien todavía no está en ningún club tiene que poder entrar y ver
    su perfil, que es donde están sus solicitudes de ingreso. Con `Principal`
    recibiría 403 y se quedaría sin puerta.

    No toca ningún dato de equipo: devuelve la cuenta y, si la hay, su
    pertenencia. Cualquier otro endpoint sí necesita `Principal`.

    Una pertenencia revocada responde 403, igual que `_principal_for`: no es una
    cuenta del pool, es una a la que alguien le quitó el acceso, y presentarla
    como si nunca hubiera estado en un club sería mentir sobre su estado.
    """
    sesion = await service.session_for(db, user)
    if sesion is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Tu acceso a este equipo está revocado",
        )
    return sesion


@router.post("/me/password", response_model=SessionResponse)
async def change_password(
    data: PasswordChange,
    response: Response,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
):
    """Cambia la contraseña **y corta todas las demás sesiones**.

    Cambiar la contraseña y cerrar sesión son las dos mitades del mismo gesto:
    "creo que me han comprometido la cuenta". Cerrar una y dejar la otra abierta
    dejaba al atacante 30 días de refresh token después de que la víctima
    reaccionara.

    Devuelve una sesión nueva en vez de 204 para no echar de la aplicación a
    quien acaba de hacer lo correcto: sus tokens viejos mueren con el resto, y
    en la misma respuesta recibe los nuevos. Las otras pestañas y dispositivos
    sí se quedan fuera, que es justo lo que se pretende.
    """
    if not await credenciales.authenticate(db, principal.user.email, data.current_password):
        auditar(
            TipoDeEvento.PASSWORD_CAMBIADA, principal, fallo=True,
            detalle="password_actual_incorrecta",
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta")
    await credenciales.change_password(db, principal.user, data.new_password)
    auditar(TipoDeEvento.PASSWORD_CAMBIADA, principal, detalle="se revocan las demás sesiones")
    return await _issue_session(db, response, principal.user)
