"""Modelo de usuario: la identidad, sin más.

Deliberadamente NO tiene rol ni equipo. Ambos describen la relación de una
persona con un club, no a la persona: viven en `teams.TeamMember`. Así el mismo
usuario podría mañana ser entrenador en un club y atleta en otro sin tocar esta
tabla.

Es también una entidad distinta de `Swimmer` (el perfil deportivo): un nadador
puede existir sin cuenta, y darle acceso consiste en crear su User y ligarlo.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Guardado SIEMPRE en minúsculas (lo normaliza el service). SQLite y
    # PostgreSQL no comparan strings igual, así que el unique solo es fiable si
    # el valor entra ya normalizado; no delegamos eso al motor.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    # Desactivar la cuenta cierra el acceso a toda la aplicación. Para quitar el
    # acceso solo a un equipo se desactiva la pertenencia (`TeamMember`).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Generación de sesiones. Va dentro de cada token emitido y se compara al
    # validarlo: subirla invalida de golpe todo lo que se emitió antes.
    #
    # Es lo que hace que "cerrar sesión" cierre algo. Sin esto, `logout` solo
    # borraba la cookie del navegador y el refresh token seguía siendo válido
    # sus 30 días completos — justo cuando el usuario lo pulsa porque cree que
    # le han comprometido la cuenta. Un entero es más barato que una lista de
    # revocación y no necesita almacenamiento aparte.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Contador de rotación del refresh token, distinto del de revocación a
    # propósito. Sube en CADA uso de `/auth/refresh` y solo lo mira el refresh,
    # nunca el access.
    #
    # Separarlos es lo que hace que la rotación no eche a nadie: si el refresh
    # subiera `token_version`, todos los access tokens vivos —el de las otras
    # pestañas incluido— morirían en el acto y cada pestaña saldría a refrescar,
    # invalidándose entre ellas.
    #
    # Un refresh que llega con un contador viejo es un **replay**: alguien está
    # reusando un token que ya se gastó. Ver `auth/router.py::refresh`.
    refresh_rotation: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # timezone=True desde el principio: en SQLite es cosmético, en PostgreSQL es
    # la diferencia entre timestamptz y un timestamp naive imposible de arreglar.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # pragma: no cover - ayuda en consola/tests
        return f"<User {self.id} {self.email}>"
