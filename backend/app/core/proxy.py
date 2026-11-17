"""La IP del cliente detrás de un proxy de confianza (TODO-34, 2026-11-16).

Sin configurar nada, la IP es la de quien abre la conexión, y `X-Forwarded-For`
**se ignora** (R11): cualquiera puede escribir esa cabecera, y creerla dejaría
falsificar el origen para esquivar el freno de intentos. El problema es el
contrario detrás de un proxy (el balanceador del alojamiento, Caddy, nginx):
todas las conexiones llegan desde él, así que **todo el mundo comparte origen**
y 20 fallos de cualquiera frenarían a todos.

`PEAKSTROKE_PROXIES_DE_CONFIANZA` declara qué redes son proxies propios. Solo si
la conexión llega desde una de ellas se lee `X-Forwarded-For`, y se recorre **de
derecha a izquierda** saltando las direcciones de confianza: la primera que no
lo es es la del cliente. Lo de más a la izquierda lo escribe el cliente y no se
cree nunca; lo de la derecha lo añadió un proxy propio.
"""
from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Sequence

Red = ipaddress.IPv4Network | ipaddress.IPv6Network


def redes(textos: Iterable[str]) -> tuple[Red, ...]:
    """`['10.0.0.0/8', '127.0.0.1']` → redes. Lanza `ValueError` si una no lo es."""
    return tuple(ipaddress.ip_network(t.strip(), strict=False) for t in textos if t.strip())


def _de_confianza(ip: str, confianza: Sequence[Red]) -> bool:
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(direccion in red for red in confianza)


def ip_del_cliente(
    conexion: str | None, reenviado: str | None, confianza: Sequence[Red],
) -> str | None:
    """La IP con la que se cuenta esta petición.

    `conexion` es quien abrió el socket; `reenviado`, el `X-Forwarded-For` tal
    cual (puede venir con varias direcciones separadas por comas).
    """
    if conexion is None or not confianza or not _de_confianza(conexion, confianza):
        return conexion
    if not reenviado:
        return conexion
    for candidata in reversed([p.strip() for p in reenviado.split(",") if p.strip()]):
        try:
            ipaddress.ip_address(candidata)
        except ValueError:
            # Basura en la cabecera: lo que queda a su izquierda ya no es fiable.
            return conexion
        if not _de_confianza(candidata, confianza):
            return candidata
    # Toda la cadena es de proxies propios: el cliente es el más lejano de ellos.
    return reenviado.split(",")[0].strip() or conexion
