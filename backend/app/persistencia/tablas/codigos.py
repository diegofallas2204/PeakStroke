"""Códigos de vinculación: la única forma de ligar una cuenta a una ficha.

Ficha deportiva (`Swimmer`) y cuenta (`User`) son la misma persona vista desde
dos sitios, y hasta el 2026-08-09 el entrenador las unía él solo eligiendo un
nombre de un desplegable. Eso convertía "quién eres" en una decisión
unilateral: nadie del otro lado confirmaba nada, y un clic mal dado le daba a
una persona el histórico de otra.

El código cierra esa puerta con las tres propiedades que le faltaban:

  · **Caduca** — un código olvidado deja de servir solo (`expires_at`).
  · **Se gasta** — un solo canje (`used_at`), así que reenviarlo no vale.
  · **Tiene dos lados** — lo emite el entrenador y lo canjea la persona desde
    su cuenta. La relación no existe hasta que ambos han actuado.

**El código se guarda en claro, a propósito.** Es la única forma de que el
entrenador pueda volver a leerlo para dictárselo al nadador; hasheado, cada
consulta obligaría a emitir uno nuevo. Lo que compra ese texto plano está
acotado: vale para *una* ficha concreta de *un* equipo, muere en
`CodigoDeVinculacion.HORAS_DE_VIDA` y se invalida al usarse. No es una credencial de acceso —
quien lo canjea sigue necesitando su propia cuenta y su contraseña.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LinkCode(Base):
    __tablename__ = "link_codes"
    __table_args__ = (
        # La ficha y el código son del MISMO equipo, impuesto por el motor.
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_link_codes_swimmer_in_team", ondelete="CASCADE",
        ),
        # Quien lo emite es entrenador de ese equipo. Misma idea.
        ForeignKeyConstraint(
            ["created_by", "team_id"], ["team_members.user_id", "team_members.team_id"],
            name="fk_link_codes_issuer_in_team", ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    swimmer_id: Mapped[int] = mapped_column(Integer, index=True)
    created_by: Mapped[int] = mapped_column(Integer, index=True)
    # Normalizado: mayúsculas y sin guiones. El guion es solo presentación.
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    # A quién va dirigido, si el entrenador lo emitió desde el correo. Es lo que
    # convierte el código en una INVITACIÓN: sin él, cualquiera con la cadena en
    # la mano se lleva la ficha; con él, además hay que ser esa persona. También
    # es lo que permite al atleta ver su solicitud pendiente antes de canjearla.
    # Nullable por los códigos emitidos sobre una ficha suelta, que siguen
    # existiendo — ahí la única prueba de identidad es el propio código.
    invited_email: Mapped[str | None] = mapped_column(String(255), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Las tres columnas de abajo son el ciclo de vida. Un código servible es el
    # que tiene las tres a NULL y no ha caducado; no hay ningún otro estado.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
    )

    def __repr__(self) -> str:  # pragma: no cover - ayuda en consola/tests
        return f"<LinkCode {self.code} s{self.swimmer_id} t{self.team_id}>"
