"""Configuración de la aplicación (pydantic-settings, variables PEAKSTROKE_*)."""
from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]

# Valor centinela: si sigue puesto en producción, la app se niega a arrancar.
DEV_JWT_SECRET = "dev-only-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PEAKSTROKE_", env_file=".env", extra="ignore")

    app_name: str = "PeakStroke"
    version: str = "0.1.0"
    environment: str = "development"
    # SQLite local por defecto; para el SaaS basta apuntar a PostgreSQL:
    # postgresql+asyncpg://user:pass@host:5432/peakstroke
    database_url: str = f"sqlite+aiosqlite:///{(_BACKEND_DIR / 'peakstroke.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Identidad -----------------------------------------------------------
    # Interruptor maestro. En False la app NO pide login: `get_current_user`
    # devuelve el usuario de desarrollo (ver dev_user_email) y los guards de rol
    # dejan pasar todo. Sirve para construir roles y UI sin pantalla de login.
    # En producción es obligatorio ponerlo en True (lo valida `_check_production`).
    auth_enabled: bool = False
    # Email del entrenador de desarrollo que se suplanta con auth_enabled=False.
    # Lo crea seed.py; si no existe en la DB, la dependencia falla con un error
    # explícito en vez de inventarse un usuario fantasma.
    # Dominio .dev y no .local: email-validator rechaza los TLD reservados.
    dev_user_email: str = "coach@peakstroke.dev"

    # --- Tokens --------------------------------------------------------------
    jwt_secret: str = DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    # Access corto: vive en memoria del cliente y se renueva con el refresh.
    access_token_minutes: int = 15
    # Refresh largo: viaja en cookie httpOnly, nunca en localStorage.
    refresh_token_days: int = 30
    refresh_cookie_name: str = "peakstroke_refresh"
    # False en desarrollo (http://localhost no es https). True en producción.
    refresh_cookie_secure: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        """Impide desplegar con la configuración de desarrollo puesta."""
        if not self.is_production:
            return self
        if self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError(
                "PEAKSTROKE_JWT_SECRET sigue con el valor de desarrollo. "
                "Genera uno con: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        if not self.auth_enabled:
            raise ValueError(
                "PEAKSTROKE_AUTH_ENABLED=false en producción dejaría el API "
                "completamente abierto. Ponlo en true."
            )
        if not self.refresh_cookie_secure:
            raise ValueError(
                "PEAKSTROKE_REFRESH_COOKIE_SECURE debe ser true en producción "
                "para que la cookie de refresh no viaje por http."
            )
        return self


settings = Settings()
