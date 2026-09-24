"""Lo que la auditoría guarda de la IP y del navegador, y nada más (R11, opción C).

Funciones puras: ninguna toca la base de datos. La clave del HMAC se la da quien
llama (`core/auditoria.py`, que la pide al repositorio).

Una **IP completa nunca llega al disco**. Se guardan dos derivados:

- **la red** (`/24` en IPv4, `/48` en IPv6): suficiente para ver "todo esto viene
  de la red de un club" o "de otro país", insuficiente para señalar un hogar;
- **la huella**: HMAC-SHA256 de la IP completa con la clave del periodo,
  recortado a 128 bits. Dentro de un periodo, dos eventos desde la misma IP
  tienen la misma huella; entre periodos, no se pueden relacionar.

**Lo que la huella NO protege**, y hay que saberlo: las IPv4 son 2³², así que
quien tenga la clave del periodo en curso puede recalcular la huella de todas
en minutos y deshacerla. La clave vive en `claves_de_auditoria`, que **no está
en ninguna vista**: PSAdmin no la ve. Quien se lleve la base entera sí, pero
solo la del periodo en curso — las anteriores ya se borraron.

**`X-Forwarded-For` se ignora a propósito**: sin un proxy de confianza
configurado, esa cabecera la escribe el cliente, y cualquiera podría firmar sus
intentos con la IP de otro. Cuando haya proxy delante, se lee de ahí y en ese
único sitio.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
from datetime import UTC, datetime

_PREFIJO_V4 = 24
_PREFIJO_V6 = 48
_EPOCA = datetime(1970, 1, 1, tzinfo=UTC)


def _ip(texto: str | None) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    if not texto:
        return None
    try:
        ip = ipaddress.ip_address(texto)
    except ValueError:
        return None
    # Una IPv4 que llega envuelta en IPv6 (`::ffff:1.2.3.4`) es una IPv4: si no
    # se desenvuelve, la misma persona tendría dos redes y dos huellas.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def red_de(texto: str | None) -> str | None:
    """`203.0.113.77` → `203.0.113.0/24`. None si no es una IP."""
    ip = _ip(texto)
    if ip is None:
        return None
    prefijo = _PREFIJO_V4 if ip.version == 4 else _PREFIJO_V6
    return str(ipaddress.ip_network(f"{ip}/{prefijo}", strict=False))


def huella_de(texto: str | None, clave: bytes) -> str | None:
    """HMAC de la IP completa con la clave del periodo. None si no es una IP."""
    ip = _ip(texto)
    if ip is None:
        return None
    return hmac.new(clave, ip.packed, hashlib.sha256).hexdigest()[:32]


def periodo_de(momento: datetime, dias: int) -> int:
    """El número de periodo de `dias` días al que pertenece ese momento."""
    return (momento - _EPOCA).days // dias


# Orden importante: Edge y Opera dicen "Chrome" en su cadena, y Chrome dice
# "Safari". Se mira primero lo más específico.
_NAVEGADORES = (
    ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"), ("Chrome/", "Chrome"), ("Safari/", "Safari"),
    ("python-httpx", "httpx"), ("curl/", "curl"), ("python-requests", "requests"),
)
_SISTEMAS = (
    ("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iOS"), ("iPad", "iOS"),
    ("Mac OS X", "macOS"), ("Macintosh", "macOS"), ("CrOS", "ChromeOS"), ("Linux", "Linux"),
)


def familia_de(user_agent: str | None) -> str | None:
    """`Mozilla/5.0 (Windows NT 10.0…) … Chrome/128…` → `Chrome · Windows`.

    Sin versiones: la cadena completa, con sus números, es media huella del
    dispositivo, y para leer un registro de accesos basta con la familia.
    """
    if not user_agent:
        return None
    navegador = next((n for marca, n in _NAVEGADORES if marca in user_agent), "otro")
    sistema = next((s for marca, s in _SISTEMAS if marca in user_agent), None)
    return f"{navegador} · {sistema}" if sistema else navegador
