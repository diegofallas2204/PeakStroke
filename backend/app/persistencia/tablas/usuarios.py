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

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, false, func
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
    #
    # Desde TODO-30 (2026-10-20) cerrar **una** sesión es borrar su fila de
    # `sesiones_abiertas`; la generación es la de «todas»: salir de todas,
    # cambiar la contraseña, revocar y liberar (que además borran sus filas).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # La contraseña la generó el sistema y la vio otra persona (quien invitó o
    # el operador que la restableció): hay que cambiarla antes de usar la app
    # (TODO-27). La pone y la quita `Usuario.cambiar_password`.
    password_temporal: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(),
    )
    # timezone=True desde el principio: en SQLite es cosmético, en PostgreSQL es
    # la diferencia entre timestamptz y un timestamp naive imposible de arreglar.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # pragma: no cover - ayuda en consola/tests
        return f"<User {self.id} {self.email}>"


class OpenSession(Base):
    """Una sesión abierta: un login en un dispositivo, con su rotación (TODO-30).

    Hasta el 2026-10-20 la rotación era una columna de `users`, una por cuenta:
    entrar en el móvil gastaba la cookie del portátil y su siguiente refresh se
    cortaba como robo. Ahora cada login es una fila, y el token lleva su `id`.

    - `refresh_rotation` sube en cada `/auth/refresh` **de esta sesión**, con un
      `UPDATE` condicional (TODO-25). Un refresh que llega con un contador viejo
      es una cookie copiada: se borra esta fila, no las de la cuenta.
    - **Se borra, no se da de baja**: cerrar sesión, el reuso, la purga de las
      caducadas y subir la generación de la cuenta borran filas. Es la excepción
      documentada a «nada se borra», como `sesiones`: el rastro vive en la
      auditoría, y una fila que no fuera una sesión viva solo mentiría.
    - `id` aleatorio y no un entero: SQLite sin `AUTOINCREMENT` reutiliza el
      último rowid borrado, y un refresh viejo habría revivido en otra sesión.

    Sin `team_id`: es identidad, como `users`. Quién puede tocar la de quién lo
    decide la cookie firmada, y cada consulta lleva también el `user_id`.
    """

    __tablename__ = "sesiones_abiertas"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True,
    )
    refresh_rotation: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Se desliza con cada rotación (la cookie dura `refresh_token_days` desde la
    # última). Con índice: cada login purga las caducadas de todas las cuentas.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
