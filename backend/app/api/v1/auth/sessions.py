"""Ciclo de vida de la sesión: abrirla, rotarla y cerrarla.

Los tres endpoints de aquí son los únicos que emiten o destruyen tokens, y por
eso viven juntos: la rotación del refresh solo se entiende leyendo `login`,
`refresh` y `logout` de una sentada. `_issue_session` es la puerta común, y la
usa además `POST /me/password` desde `router.py`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import TipoDeEvento, auditar
from app.core.config import settings
from app.core.database import get_db
from app.core.security import TokenError, create_access_token, create_refresh_token, decode_token
from app.dominio.entidades import Usuario
from app.persistencia.repositorios import RepositorioDeEquipos, RepositorioDeUsuarios
from app.persistencia.repositorios.usuarios import RotacionPerdida, normalizar_correo
from app.persistencia.tablas.usuarios import User

from . import credenciales, service
from .schemas import LoginRequest, SessionResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_BAD_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Email o contraseña incorrectos",
)

# Cuántas veces una emisión legítima (login, cambio de contraseña) vuelve a
# rotar si otra le gana la rotación. Perder tres seguidas no es una carrera
# normal entre dos pestañas: se contesta 503 y que lo intente otra vez.
_INTENTOS_DE_ROTAR = 3
_SIN_ROTACION = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="No se pudo abrir la sesión: inténtalo de nuevo",
)


async def _issue_session(
    db: AsyncSession, response: Response, user: User, *, reintentar: bool = True,
) -> SessionResponse:
    """Emite el par de tokens: access en el cuerpo, refresh en cookie httpOnly.

    Cada emisión gasta una rotación. El refresh que se acaba de entregar es el
    único válido a partir de aquí; el anterior queda marcado como usado y su
    reaparición se trata como robo.

    Si otra petición gasta la rotación a la vez (TODO-25), `reintentar` dice
    qué es: en login y en el cambio de contraseña, otra emisión legítima —se
    rota sobre la nueva—; en `refresh` (`reintentar=False`), el reuso, y
    `RotacionPerdida` sube hasta él.
    """
    # `include_inactive=True` **no es un detalle**: sin él, `get_membership`
    # devuelve None tanto para "no está en ningún club" como para "está y se lo
    # revocaron", y las dos cosas acabarían entrando. Revocar el acceso dejaría
    # de echar a nadie: la persona seguiría entrando como cuenta del pool y
    # podría canjear un código para volver a meterse en un equipo.
    membership = await RepositorioDeEquipos(db).pertenencia(
        user.id, incluir_inactivas=True,
    )
    if membership is not None and not membership.is_active:
        raise _BAD_CREDENTIALS
    # Sin pertenencia **sí** se entra: es la cuenta que espera invitación, y
    # dejarla fuera del login la dejaría sin poder canjear el código que la
    # metería en el club.

    usuario = await _rotar(db, user, intentos=_INTENTOS_DE_ROTAR if reintentar else 1)

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=create_refresh_token(user.id, usuario.version_de_token, usuario.rotacion_de_refresh),
        httponly=True,                       # invisible para cualquier JS de la página
        secure=settings.refresh_cookie_secure,
        samesite="lax",                      # corta el CSRF de terceros manteniendo la navegación normal
        max_age=settings.refresh_token_days * 24 * 3600,
        path="/api/v1/auth",                 # la cookie solo viaja a los endpoints que la necesitan
    )
    return SessionResponse(
        access_token=create_access_token(user.id, usuario.version_de_token),
        expires_in=settings.access_token_minutes * 60,
        user=await service.get_member(db, user, membership),
    )


async def _rotar(db: AsyncSession, user: User, *, intentos: int) -> Usuario:
    """Gasta una rotación con el `UPDATE` condicional del repositorio. Tras
    perderla, `guardar` ya dejó la fila releída: se rota sobre la que ganó."""
    usuarios = RepositorioDeUsuarios(db)
    for intento in range(intentos):
        usuario = usuarios.entidad(user)
        usuario.rotar_refresh()
        try:
            await usuarios.guardar(usuario)
            return usuario
        except RotacionPerdida:
            if intentos == 1:
                raise
            logger.info("Rotación perdida para %s (intento %s)", user.email, intento + 1)
    raise _SIN_ROTACION


async def _cortar_por_reuso(
    db: AsyncSession, response: Response, user: User, rotacion: int, *, a_la_vez: bool,
) -> HTTPException:
    """Un refresh que reaparece —después o a la vez— corta todas las sesiones."""
    motivo = (
        f"rotación {rotacion} gastada a la vez por otra petición" if a_la_vez
        else f"rotación {rotacion}, esperada {user.refresh_rotation}"
    )
    logger.warning(
        "Refresh token reusado para %s (%s): se revocan todas las sesiones", user.email, motivo,
    )
    await credenciales.revoke_sessions(db, user)
    # El evento más importante del registro: un refresh gastado que vuelve
    # es una cookie copiada. `fallo` porque el refresh se rechazó.
    auditar(
        TipoDeEvento.REFRESH_REUSADO, user, fallo=True,
        detalle=f"{motivo}: se revocan todas las sesiones",
    )
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")
    return _BAD_CREDENTIALS


@router.post("/login", response_model=SessionResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    user, motivo = await credenciales.comprobar_credenciales(db, data.email, data.password)
    if user is None:
        # El correo TECLEADO, exista o no: es lo que deja ver un barrido.
        auditar(
            TipoDeEvento.LOGIN, correo=normalizar_correo(data.email),
            fallo=True, detalle=motivo,
        )
        raise _BAD_CREDENTIALS
    try:
        sesion = await _issue_session(db, response, user)
    except HTTPException as exc:
        # La contraseña era buena, pero el club le revocó el acceso — o la
        # rotación se perdió tres veces seguidas (503).
        if exc is _BAD_CREDENTIALS:
            auditar(TipoDeEvento.LOGIN, user, fallo=True, detalle="acceso_revocado")
        elif exc is _SIN_ROTACION:
            auditar(TipoDeEvento.LOGIN, user, fallo=True, detalle="rotacion_perdida")
        raise
    auditar(TipoDeEvento.LOGIN, user, equipo=sesion.user.team_id)
    return sesion


@router.post("/refresh", response_model=SessionResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Renueva el par de tokens. **Un refresh solo sirve una vez.**

    Rotar de verdad significa que el token entregado deja de valer en cuanto se
    usa. Antes se emitía uno nuevo y el viejo seguía vivo hasta expirar, que es
    reemitir, no rotar — y el docstring afirmaba lo contrario.

    Lo que compra la rotación real es **detectar el robo**. Si un refresh gastado
    reaparece solo hay dos explicaciones, y en las dos la respuesta correcta es
    la misma:

      · alguien copió la cookie y la está usando en paralelo, o
      · alguien copió la cookie, la usó, y ahora vuelve el usuario legítimo con
        la suya, que quedó atrás.

    En ambos casos hay dos partes con el mismo token y no se puede saber cuál es
    la buena, así que se cortan las dos: `revoke_sessions` sube la generación y
    todo lo emitido muere. El usuario legítimo tiene que volver a entrar —
    molesto— y el atacante se queda fuera con la contraseña que no tiene.
    """
    cookie = request.cookies.get(settings.refresh_cookie_name)
    if not cookie:
        raise _BAD_CREDENTIALS
    try:
        claims = decode_token(cookie, "refresh")
    except TokenError:
        raise _BAD_CREDENTIALS from None

    user = await service.get_user(db, claims.user_id)
    if user is None or not user.is_active:
        raise _BAD_CREDENTIALS
    usuario = RepositorioDeUsuarios(db).entidad(user)
    # Un refresh emitido antes del último `logout` no vuelve a la vida.
    if not usuario.acepta_generacion(claims.token_version):
        raise _BAD_CREDENTIALS

    if usuario.refresh_gastado(claims.rotation):
        raise await _cortar_por_reuso(db, response, user, claims.rotation, a_la_vez=False)

    # Comprobar arriba no basta: otra petición con la misma cookie puede pasar
    # la misma comprobación a la vez. Quien gasta la rotación lo decide la base
    # (TODO-25), y la que llega segunda es el mismo reuso.
    try:
        return await _issue_session(db, response, user, reintentar=False)
    except RotacionPerdida:
        # Quien ganó pudo ser un cambio de contraseña o un logout, que suben la
        # generación: entonces esta cookie ya estaba muerta y es el 401 del
        # camino secuencial, que mira la generación antes que la rotación. Sin
        # esto, un refresh de otra pestaña revocaba la sesión recién emitida a
        # quien acababa de cambiar la contraseña (revisor de TODO-25, vuelta 2).
        # `guardar` ya dejó la fila releída.
        if not RepositorioDeUsuarios(db).entidad(user).acepta_generacion(claims.token_version):
            raise _BAD_CREDENTIALS from None
        raise await _cortar_por_reuso(
            db, response, user, claims.rotation, a_la_vez=True,
        ) from None


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Cierra la sesión de verdad: invalida los tokens, no solo la cookie.

    Se identifica por la cookie de refresh y no por el access token a propósito.
    El access dura 15 minutos: exigirlo dejaría sin poder cerrar sesión justo a
    quien lleva un rato con la pestaña abierta, que es el caso normal.

    Una cookie ausente, caducada o falsa **no es un error**: se borra lo que
    haya y se devuelve 204. Cerrar sesión dos veces, o desde una pestaña cuya
    sesión ya expiró, tiene que terminar en "estás fuera" y no en un 401 que
    nadie sabe cómo resolver.
    """
    cookie = request.cookies.get(settings.refresh_cookie_name)
    if cookie:
        try:
            claims = decode_token(cookie, "refresh")
        except TokenError:
            claims = None
        if claims is not None:
            user = await service.get_user(db, claims.user_id)
            if user is not None:
                await credenciales.revoke_sessions(db, user)
                auditar(TipoDeEvento.LOGOUT, user, detalle="se revocan todas las sesiones")
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")
