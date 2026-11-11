"""El freno de intentos: login (TODO-33) y canje de códigos (TODO-18).

Vive en `core/` porque lo usan dos rebanadas del API (`auth` y `codigos`), que
no se importan entre sí.

Decidido por la persona el 2026-11-10: **freno por correo + origen y por origen,
sin bloquear cuentas.** Un bloqueo de cuenta dejaría que cualquiera echara a un
entrenador escribiendo mal su contraseña cinco veces; aquí quien falla solo se
frena a sí mismo, y el mismo correo desde otro origen entra.

No hay tabla nueva: **se cuenta sobre la auditoría**, que ya guarda cada fallo
con el correo tecleado y la huella de la IP (`sesion.login` con `fallo`). Lo que
eso implica, a sabiendas:

- La auditoría se escribe **después** de responder. Dos intentos lanzados a la
  vez pueden pasar los dos antes de que el primero cuente. Verificar una
  contraseña son ~200 ms de Argon2 que ocupan el proceso, así que en la práctica
  van de uno en uno; el freno limita el ritmo, no es un contador exacto.
- La huella usa la clave del periodo, que rota cada 30 días: en ese cambio el
  contador de origen empieza de cero. Para una ventana de 15 minutos da igual.
- «Origen» es la IPv4 completa o la `/64` de una IPv6 (`anonimizacion.huella_de`):
  en IPv6 cada abonado puede estrenar dirección en cada intento.
- `X-Forwarded-For` se ignora (R11). Detrás de un proxy **todo el mundo comparte
  origen** y el tope por origen frenaría a todos: es de lo que hay que resolver
  al desplegar (TODO-34), no aquí.

Un intento frenado se audita (`frenado`) pero **no cuenta** como fallo: si
contara, insistir alargaría la espera para siempre y quien se equivocó no
volvería a entrar. Tampoco verifica la contraseña, así que no gasta Argon2.
"""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import TipoDeEvento, huella_del_origen
from app.persistencia.repositorios import RepositorioDeAuditoria

VENTANA = timedelta(minutes=15)
ESPERA_BASE = timedelta(seconds=30)
# Fallos en la ventana a partir de los cuales hay que esperar.
FALLOS_POR_CORREO = 5      # mismo correo, mismo origen
FALLOS_POR_ORIGEN = 20     # cualquier correo, mismo origen: un barrido
FALLOS_DE_CANJE = 5        # misma cuenta probando códigos

# El `detail` del evento de un intento frenado. Es lo que lo deja fuera de la cuenta.
FRENADO = "frenado"


def _ahora() -> datetime:
    return datetime.now(UTC)


def espera_tras(fallos: int, umbral: int) -> timedelta:
    """Cuánto hay que esperar desde el último fallo: nada por debajo del umbral,
    y desde ahí 30 s que se doblan con cada fallo, hasta la ventana entera."""
    if fallos < umbral:
        return timedelta(0)
    return min(ESPERA_BASE * 2 ** min(fallos - umbral, 10), VENTANA)


def _segundos(momentos: list[datetime], umbral: int, ahora: datetime) -> int:
    """Segundos que faltan, dados los fallos de la ventana (el más reciente primero)."""
    if not momentos:
        return 0
    falta = momentos[0] + espera_tras(len(momentos), umbral) - ahora
    # Hacia arriba: «espera 0 s» con medio segundo pendiente sería otro 429.
    return max(0, math.ceil(falta.total_seconds()))


def demasiados_intentos(segundos: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Demasiados intentos. Espera un momento antes de volver a probar.",
        headers={"Retry-After": str(segundos)},
    )


async def espera_de_login(db: AsyncSession, correo: str) -> int:
    """Segundos que le faltan a este origen para volver a intentar ese correo.
    0 = puede. El correo llega ya normalizado, exista o no la cuenta."""
    ahora, repo = _ahora(), RepositorioDeAuditoria(db)
    huella = await huella_del_origen(db)
    if huella is None:
        # Sin origen no hay a quién frenar: contar solo por correo sería el
        # bloqueo de cuenta que se descartó (cualquiera, desde cualquier sitio,
        # dejaría fuera a esa persona). Pasa sin IP —que un servidor de verdad
        # siempre tiene— y antes del primer evento de cada periodo de clave.
        return 0
    tipo = str(TipoDeEvento.LOGIN)
    del_correo = await repo.fallos_recientes(
        tipo, ahora - VENTANA, huella=huella, correo=correo, sin_detalle=FRENADO,
    )
    del_origen = await repo.fallos_recientes(
        tipo, ahora - VENTANA, huella=huella, sin_detalle=FRENADO,
    )
    return max(
        _segundos(del_correo, FALLOS_POR_CORREO, ahora),
        _segundos(del_origen, FALLOS_POR_ORIGEN, ahora),
    )


async def espera_de_canje(db: AsyncSession, user_id: int) -> int:
    """Lo mismo para el canje: por cuenta, que aquí ya se sabe quién es."""
    ahora = _ahora()
    fallos = await RepositorioDeAuditoria(db).fallos_recientes(
        str(TipoDeEvento.CODIGO_CANJEADO), ahora - VENTANA,
        actor_id=user_id, sin_detalle=FRENADO,
    )
    return _segundos(fallos, FALLOS_DE_CANJE, ahora)
