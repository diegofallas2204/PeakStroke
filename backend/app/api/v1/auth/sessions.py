"""Ciclo de vida de la sesión: abrirla, rotarla y cerrarla.

Los endpoints de aquí son los únicos que emiten o destruyen tokens, y por eso
viven juntos: la rotación del refresh solo se entiende leyendo `login`,
`refresh` y `logout` de una sentada. `_issue_session` es la puerta común, y la
usa además `POST /me/password` desde `router.py`.

**Una sesión por login** (TODO-30, 2026-10-20). Cada login abre una fila de
`sesiones_abiertas` con su propia rotación, y los dos tokens llevan su `sid`.
Hasta entonces la rotación era una por cuenta y entrar en el móvil gastaba la
cookie del portátil: su siguiente refresh se cortaba como robo.

    POST /login ─────▶ sesión abierta (sid, rotación 0) ◀──── 200 /refresh
                            │      │       │                (rotación n → n+1)
         refresh de rotación vieja │       │ POST /logout (de esa cookie)
         o dos a la vez (CAS) ─────┘       │ caduca (purga en cada login)
                  │                        │
                  ▼                        ▼
       se borra ESA sesión,          se borra esa sesión
       REFRESH_REUSADO, 401          (su access muere en la siguiente petición)

    Todas a la vez —sube la generación de la cuenta y se borran sus filas—:
    POST /logout-all · /me/password · revocar o liberar la pertenencia ·
    `tools/ops.py cortar-sesiones`.

**Dos pestañas del mismo navegador comparten sesión**: si refrescan a la vez,
la segunda es el reuso de esa sesión. Lo evita el cliente con un solo refresh en
vuelo por navegador (TODO-31), no el servidor: aceptar la rotación anterior
dejaría pasar la cookie copiada que se usa en el mismo instante (TODO-25).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import TipoDeEvento, auditar
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    TokenClaims,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.dominio.entidades import SesionAbierta
from app.persistencia.repositorios import (
    RepositorioDeEquipos,
    RepositorioDeSesionesAbiertas,
    RepositorioDeUsuarios,
)
from app.persistencia.repositorios.sesiones_abiertas import RotacionPerdida
from app.persistencia.repositorios.usuarios import normalizar_correo
from app.persistencia.tablas.usuarios import User

from . import credenciales, service
from .schemas import LoginRequest, SessionResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_BAD_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Email o contraseña incorrectos",
)


def _vigencia() -> timedelta:
    return timedelta(days=settings.refresh_token_days)


async def _issue_session(
    db: AsyncSession, response: Response, user: User, sesion: SesionAbierta | None = None,
) -> SessionResponse:
    """Emite el par de tokens: access en el cuerpo, refresh en cookie httpOnly.

    Sin `sesion` abre una nueva (login, cambio de contraseña): es un `INSERT`
    con un id aleatorio y no compite con nada. Con `sesion` gasta una rotación
    de esa (refresh); si otra petición la gastó a la vez, `RotacionPerdida`
    sube hasta `refresh`, que decide qué era.
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

    ahora, sesiones = datetime.now(UTC), RepositorioDeSesionesAbiertas(db)
    if sesion is None:
        sesion = RepositorioDeUsuarios(db).entidad(user).abrir_sesion(ahora, _vigencia())
        await sesiones.abrir(sesion)
    else:
        sesion.rotar(ahora, _vigencia())
        await sesiones.rotar(sesion)

    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=create_refresh_token(user.id, user.token_version, sesion.id, sesion.rotacion),
        httponly=True,                       # invisible para cualquier JS de la página
        secure=settings.refresh_cookie_secure,
        samesite="lax",                      # corta el CSRF de terceros manteniendo la navegación normal
        max_age=settings.refresh_token_days * 24 * 3600,
        path="/api/v1/auth",                 # la cookie solo viaja a los endpoints que la necesitan
    )
    return SessionResponse(
        access_token=create_access_token(user.id, user.token_version, sesion.id),
        expires_in=settings.access_token_minutes * 60,
        user=await service.get_member(db, user, membership),
    )


async def _cortar_por_reuso(
    db: AsyncSession, response: Response, user: User, sid: str, motivo: str,
) -> HTTPException:
    """Un refresh gastado que reaparece —después, a la vez o en un logout— es
    una copia de la cookie de **esa** sesión: se borra esa, y las demás siguen
    (decidido el 2026-10-20). Quien copió solo tiene esa cadena."""
    logger.warning("Refresh token reusado para %s (%s): se cierra esa sesión", user.email, motivo)
    await RepositorioDeSesionesAbiertas(db).cerrar(sid, user.id)
    # El evento más importante del registro: un refresh gastado que vuelve
    # es una cookie copiada. `fallo` porque el refresh se rechazó.
    auditar(
        TipoDeEvento.REFRESH_REUSADO, user, fallo=True,
        detalle=f"{motivo}: se cierra esa sesión",
    )
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")
    return _BAD_CREDENTIALS


async def _de_la_cookie(
    db: AsyncSession, request: Request,
) -> tuple[TokenClaims, User, SesionAbierta | None] | None:
    """Lo que dice la cookie de refresh, su cuenta y su sesión (si sigue
    abierta). `None` si no hay cookie, no es un refresh firmado o la cuenta no
    existe: para `logout` eso no es un error."""
    cookie = request.cookies.get(settings.refresh_cookie_name)
    if not cookie:
        return None
    try:
        claims = decode_token(cookie, "refresh")
    except TokenError:
        return None
    user = await service.get_user(db, claims.user_id)
    if user is None:
        return None
    return claims, user, await RepositorioDeSesionesAbiertas(db).de(claims.sid, user.id)


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
        # La contraseña era buena, pero el club le revocó el acceso.
        if exc is _BAD_CREDENTIALS:
            auditar(TipoDeEvento.LOGIN, user, fallo=True, detalle="acceso_revocado")
        raise
    auditar(TipoDeEvento.LOGIN, user, equipo=sesion.user.team_id)
    return sesion


@router.post("/refresh", response_model=SessionResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Renueva el par de tokens. **Un refresh solo sirve una vez.**

    Rotar de verdad significa que el token entregado deja de valer en cuanto se
    usa. Lo que compra es **detectar el robo**: si un refresh gastado reaparece,
    o alguien copió la cookie y la está usando en paralelo, o la usó y ahora
    vuelve el legítimo con la suya, que quedó atrás. En los dos casos hay dos
    partes con la misma cadena y no se sabe cuál es la buena, así que se cierra
    **esa sesión**: las dos partes quedan fuera de ese dispositivo, y los demás
    dispositivos de la cuenta siguen dentro (TODO-30).
    """
    datos = await _de_la_cookie(db, request)
    if datos is None:
        raise _BAD_CREDENTIALS
    claims, user, sesion = datos
    if not user.is_active:
        raise _BAD_CREDENTIALS
    # Un refresh emitido antes de la última vez que se cortaron todas no vuelve.
    if not RepositorioDeUsuarios(db).entidad(user).acepta_generacion(claims.token_version):
        raise _BAD_CREDENTIALS
    # Cerrada (logout, reuso, generación) o caducada: un 401 simple, no un robo.
    if sesion is None or sesion.caducada(datetime.now(UTC)):
        raise _BAD_CREDENTIALS
    if sesion.refresh_gastado(claims.rotation):
        raise await _cortar_por_reuso(
            db, response, user, sesion.id,
            f"rotación {claims.rotation}, esperada {sesion.rotacion}",
        )

    # Comprobar arriba no basta: otra petición con la misma cookie puede pasar
    # la misma comprobación a la vez. Quien gasta la rotación lo decide la base
    # (TODO-25), y la que llega segunda es el mismo reuso.
    try:
        return await _issue_session(db, response, user, sesion)
    except RotacionPerdida:
        # Quien ganó pudo cerrar la sesión (un logout) o subir la generación
        # (un cambio de contraseña, que además la borra): entonces esta cookie
        # ya estaba muerta y es el 401 del camino secuencial. Se relee de la
        # base: la cuenta por `refresh` (nunca se borra) y la sesión por un
        # `select`, que da None si ya no existe (revisor de TODO-25, vuelta 2;
        # voz externa de TODO-30).
        await db.refresh(user)
        viva = await RepositorioDeSesionesAbiertas(db).de(claims.sid, user.id)
        if viva is None or not RepositorioDeUsuarios(db).entidad(user).acepta_generacion(
            claims.token_version,
        ):
            raise _BAD_CREDENTIALS from None
        raise await _cortar_por_reuso(
            db, response, user, viva.id,
            f"rotación {claims.rotation} gastada a la vez por otra petición",
        ) from None


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Cierra **la sesión de este dispositivo** de verdad: borra su fila, y su
    access muere en la siguiente petición (`get_current_user` mira que siga
    abierta). Las demás sesiones de la cuenta siguen; para cerrarlas todas está
    `/logout-all`. Hasta TODO-30 este endpoint las cortaba todas.

    Se identifica por la cookie de refresh y no por el access token a propósito.
    El access dura 15 minutos: exigirlo dejaría sin poder cerrar sesión justo a
    quien lleva un rato con la pestaña abierta, que es el caso normal.

    Una cookie ausente, caducada o falsa **no es un error**: se borra lo que
    haya y se devuelve 204. Cerrar sesión dos veces, o desde una pestaña cuya
    sesión ya expiró, tiene que terminar en "estás fuera" y no en un 401 que
    nadie sabe cómo resolver. Una cookie de **rotación gastada** cierra la
    sesión igual, pero es una copia como en `/refresh`, y se audita como tal.
    """
    datos = await _de_la_cookie(db, request)
    if datos is not None and datos[2] is not None:
        claims, user, sesion = datos
        if sesion.refresh_gastado(claims.rotation):
            await _cortar_por_reuso(
                db, response, user, sesion.id,
                f"rotación {claims.rotation} gastada, en el logout",
            )
        else:
            await RepositorioDeSesionesAbiertas(db).cerrar(sesion.id, user.id)
            auditar(TipoDeEvento.LOGOUT, user, detalle="se cierra esta sesión")
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")


@router.post("/logout-all", status_code=204)
async def logout_all(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Cierra **todas** las sesiones de la cuenta: sube la generación —todo token
    emitido muere en la siguiente petición— y borra sus filas. Es lo que hacía
    `/logout` hasta TODO-30, y la salida de quien pierde un dispositivo.

    Solo con la cookie **vigente** de una sesión abierta y de la generación
    actual: una copia vieja no puede echar a todos los dispositivos de alguien.
    Con una de rotación gastada se hace lo de `/logout` (cerrar esa y avisar);
    sin cookie válida, nada. Siempre 204, como `/logout`.
    """
    datos = await _de_la_cookie(db, request)
    if datos is not None and datos[2] is not None:
        claims, user, sesion = datos
        if sesion.refresh_gastado(claims.rotation):
            await _cortar_por_reuso(
                db, response, user, sesion.id,
                f"rotación {claims.rotation} gastada, en el logout de todas",
            )
        elif RepositorioDeUsuarios(db).entidad(user).acepta_generacion(claims.token_version):
            await credenciales.revoke_sessions(db, user)
            auditar(TipoDeEvento.LOGOUT, user, detalle="se cortan todas las sesiones")
    response.delete_cookie(settings.refresh_cookie_name, path="/api/v1/auth")
