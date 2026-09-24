"""La auditoría: qué pasó, quién lo hizo y desde dónde (D0, 2026-09-24).

Un evento por fila y **append-only**: la base de datos rechaza cualquier
`UPDATE`, y solo deja borrar filas de más de `RETENCION_MESES` (lo imponen los
triggers de la migración `e3a9d0c41b7f`, no una convención del código).

Tres decisiones que conviene entender antes de tocar esto:

**El actor va denormalizado.** `actor_email` es el correo de ese momento, no
una referencia a `users`: si mañana cambia el correo o la cuenta se archiva, el
registro no puede cambiar de significado. Por la misma razón **ninguna columna
lleva FK**. Una FK tendría que borrar en cascada —y el rastro desaparecería con
lo que describe— o impedir el borrado de lo referenciado, y entonces una tabla
de log bloquearía operaciones legítimas. `actor_user_id`, `team_id` y
`target_id` son enteros sin más: el rastro sobrevive a lo que describe.

**La IP nunca se guarda entera** (decisión R11, opción C, 2026-09-24). Hay
cuentas de menores, y en un login fallido todavía no se sabe de quién es la
cuenta, así que una regla "solo para menores" no se podría aplicar. Se guardan
dos cosas: la red truncada (`/24` en IPv4, `/48` en IPv6) y una huella HMAC de
la IP completa con una clave que rota cada `PERIODO_DE_CLAVE_DIAS`. La huella
deja ver "cincuenta fallos desde el mismo origen" dentro de un periodo; al rotar
la clave se borra la anterior, y lo de antes deja de poder relacionarse con lo
de después. Ver `core/auditoria.py`.

**El user-agent se guarda como familia** ("Chrome · Windows"), no como cadena
entera: la cadena completa, con versiones, es media huella del dispositivo.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

OK = "ok"
FALLO = "fallo"

RETENCION_MESES = 24
PERIODO_DE_CLAVE_DIAS = 30


class EventoDeAuditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (
        CheckConstraint("outcome IN ('ok', 'fallo')", name="ck_auditoria_outcome"),
        Index("ix_auditoria_occurred_at", "occurred_at"),
        Index("ix_auditoria_actor", "actor_user_id", "occurred_at"),
        Index("ix_auditoria_team", "team_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # El momento del HECHO, que pone la aplicación al anotarlo — no el de la
    # escritura, que llega después de responder.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(String(5))
    actor_user_id: Mapped[int | None] = mapped_column(Integer)
    # El correo de ese momento. En un login fallido es el que se TECLEÓ, exista
    # o no la cuenta: es lo que deja ver un ataque de relleno de credenciales.
    actor_email: Mapped[str | None] = mapped_column(String(255))
    team_id: Mapped[int | None] = mapped_column(Integer)
    target_type: Mapped[str | None] = mapped_column(String(30))
    target_id: Mapped[int | None] = mapped_column(Integer)
    ip_network: Mapped[str | None] = mapped_column(String(50))
    ip_hash: Mapped[str | None] = mapped_column(String(32))
    user_agent: Mapped[str | None] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(String(200), default="")


class ClaveDeAuditoria(Base):
    """La clave HMAC de un periodo. Vive solo mientras su periodo está en curso.

    Borrarla es lo que anonimiza: sin ella, la huella de una IP de un periodo
    pasado no se puede recalcular ni comparar con nada. Por eso **no** sale de
    una clave maestra de la configuración, que dejaría rederivar cualquier
    periodo para siempre.
    """

    __tablename__ = "claves_de_auditoria"

    period: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    key_hex: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
