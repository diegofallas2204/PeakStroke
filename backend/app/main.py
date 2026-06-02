"""
main.py — Entry point de la API FastAPI.

Solo registra routers y configura CORS/middleware.
Ninguna lógica de negocio aquí.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.auth.router import router as auth_router
from app.modules.training_plans.router import router as training_plans_router

app = FastAPI(
    title="PeakStroke API",
    description="Sistema de planificación y predicción de rendimiento para natación competitiva",
    version="1.0.0",
)

# CORS — en producción restringir a los dominios del frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers — una línea por módulo, sin más
app.include_router(auth_router, prefix="/api/v1")
app.include_router(training_plans_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "PeakStroke API"}
