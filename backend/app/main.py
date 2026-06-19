"""PeakStroke API — registra routers y configura la aplicación."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.modules.aerobic_tests.router import router as aerobic_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.plans.router import router as plans_router
from app.modules.simulator.router import router as simulator_router
from app.modules.swimmers.router import router as swimmers_router


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
    allow_headers=["Content-Type"],
)

app.include_router(swimmers_router, prefix="/api/v1/swimmers", tags=["swimmers"])
app.include_router(plans_router, prefix="/api/v1/plans", tags=["plans"])
app.include_router(aerobic_router, prefix="/api/v1/aerobic-tests", tags=["aerobic-tests"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(simulator_router, prefix="/api/v1/simulator", tags=["simulator"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.version}
