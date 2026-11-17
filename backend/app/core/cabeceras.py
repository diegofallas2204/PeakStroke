"""Las cabeceras de seguridad de cada respuesta del API (TODO-34, 2026-11-16).

ASGI puro, como la auditoría. El API solo sirve JSON, así que su CSP es la más
cerrada posible: nada se carga y nadie lo enmarca. La documentación interactiva
(`/docs`, `/redoc`) carga su JavaScript de un CDN y queda fuera; en producción
ni existe (`main.py`).

`Cache-Control: no-store` en todo `/api`: son datos personales (de menores, y de
salud en el lactato), y ningún intermediario debe guardarlos. HSTS solo en
producción: en local no hay https y el navegador lo recordaría para `localhost`.

Las del **frontend** (`dist/`) las pone quien lo sirva: `frontend/public/_headers`
y `docs/DESPLIEGUE.md`.
"""
from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

SIEMPRE = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
SIN_CACHE = (b"cache-control", b"no-store")
DOCUMENTACION = ("/docs", "/redoc", "/openapi.json")


class MiddlewareDeCabeceras:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        ruta: str = scope.get("path", "")

        async def con_cabeceras(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                cabeceras = list(mensaje.get("headers", []))
                presentes = {k.lower() for k, _ in cabeceras}
                extra = list(SIEMPRE)
                if not ruta.startswith(DOCUMENTACION):
                    extra.append(CSP)
                if ruta.startswith("/api/"):
                    extra.append(SIN_CACHE)
                if settings.is_production:
                    extra.append(HSTS)
                cabeceras += [(k, v) for k, v in extra if k not in presentes]
                mensaje["headers"] = cabeceras
            await send(mensaje)

        await self.app(scope, receive, con_cabeceras)
