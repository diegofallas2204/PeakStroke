"""PeakStroke API — registra routers y configura la aplicación."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.atletas.router import router as swimmers_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.codigos.router import router as link_codes_router
from app.api.v1.equipos.router import router as teams_router
from app.api.v1.macrociclos.router import router as plans_router
from app.api.v1.sesiones.router import router as sessions_router
from app.api.v1.simulador.router import router as simulator_router
from app.api.v1.tests.router import router as aerobic_router
from app.api.v1.vistas.router import router as dashboard_router

# Importado por su efecto: registra todos los modelos en Base.metadata para que
# SQLAlchemy pueda resolver las FKs entre módulos (p. ej. swimmers -> teams).
from app.core import model_registry  # noqa: F401
from app.core.config import settings
from app.core.database import init_db
from app.core.dev_identity import DEV_BYPASS_HEADER, DEV_USER_HEADER


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    # Acotado a lo que el frontend realmente usa (defensa en profundidad) en vez de
    # comodines: los 5 verbos del cliente HTTP y la única cabecera que envía.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Authorization se suma para cuando el cliente empiece a mandar el access
    # token; hasta entonces simplemente no se usa.
    #
    # Las dos del conmutador de desarrollo. Hoy no hacen falta
    # porque `vite.config.ts` proxya `/api` al 8000 y todo es mismo origen, pero
    # sin declararla el preflight la tumba en cuanto alguien sirva el `dist/`
    # construido desde otro puerto — y el conmutador dejaría de funcionar sin un
    # error que lo explique. El endpoint que la lee ya responde 404 con el login
    # encendido, así que declararla no abre nada.
    allow_headers=["Content-Type", "Authorization", DEV_USER_HEADER, DEV_BYPASS_HEADER],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(teams_router, prefix="/api/v1/teams", tags=["teams"])
app.include_router(swimmers_router, prefix="/api/v1/swimmers", tags=["swimmers"])
app.include_router(link_codes_router, prefix="/api/v1/link-codes", tags=["link-codes"])
app.include_router(plans_router, prefix="/api/v1/plans", tags=["plans"])
app.include_router(aerobic_router, prefix="/api/v1/aerobic-tests", tags=["aerobic-tests"])
app.include_router(sessions_router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(simulator_router, prefix="/api/v1/simulator", tags=["simulator"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.version}
