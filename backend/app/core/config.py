"""Configuración de la aplicación (pydantic-settings, variables PEAKSTROKE_*)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PEAKSTROKE_", env_file=".env", extra="ignore")

    app_name: str = "PeakStroke"
    version: str = "0.1.0"
    environment: str = "development"
    # SQLite local por defecto; para el SaaS basta apuntar a PostgreSQL:
    # postgresql+asyncpg://user:pass@host:5432/peakstroke
    database_url: str = f"sqlite+aiosqlite:///{(_BACKEND_DIR / 'peakstroke.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
