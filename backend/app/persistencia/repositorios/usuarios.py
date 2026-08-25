"""El agregado Usuario: la identidad, sin más.

Sin `Principal`, por la misma razón que el de equipos: `core/dependencies`
pregunta por el usuario **para construir** la identidad, y un repositorio
acotado por lo que él mismo resuelve sería circular. La cuenta tampoco tiene
frontera de equipo: `users` es identidad pura, y el rol y el club cuelgan de la
pertenencia (`teams.TeamMember`). Quién puede *ver* a quién lo decide el
endpoint, que sí lleva `Principal`.

**`normalizar_correo` vive aquí.** Es una regla de almacenamiento, no de
negocio: `users.email` es `UNIQUE`, y SQLite y PostgreSQL no comparan cadenas
igual, así que el valor tiene que entrar ya en minúsculas — no se delega al
motor. Estaba en `auth/service.py` y `link_codes` la importaba de ahí, que era
la última lógica cruzada entre rebanadas: el correo invitado se compara contra
`users.email`, así que las dos formas de normalizarlo tienen que ser **la
misma**. Copiar el `.strip().lower()` habría funcionado hasta el día en que una
de las dos cambiara.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistencia.tablas.usuarios import User


def normalizar_correo(correo: str) -> str:
    """Los correos se guardan y se buscan siempre en minúsculas y sin espacios."""
    return correo.strip().lower()


class RepositorioDeUsuarios:
    """Las cuentas. Ver la cabecera: no lleva `Principal`."""

    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def por_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def por_correo(self, correo: str) -> User | None:
        stmt = select(User).where(User.email == normalizar_correo(correo))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def correos_de(self, user_ids: list[int]) -> dict[int, str]:
        """id → correo, para pintar una lista sin una consulta por fila."""
        if not user_ids:
            return {}
        stmt = select(User.id, User.email).where(User.id.in_(user_ids))
        return dict((await self.db.execute(stmt)).all())

    # ── Escrituras ───────────────────────────────────────────────────────────

    async def crear(self, *, correo: str, nombre: str, password_hash: str) -> User:
        """Crea la cuenta **sin pertenencia**: eso es del agregado Equipo.

        Quien necesite las dos juntas —el alta de un entrenador— las pide a los
        dos repositorios; `api/v1/auth/service.create_user` es quien lo hace.
        """
        user = User(
            email=normalizar_correo(correo), name=nombre, password_hash=password_hash,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def revocar_sesiones(self, user: User) -> None:
        """Invalida todos los tokens ya emitidos para esa cuenta.

        Sube la generación de sesiones. Cualquier access o refresh que lleve la
        anterior deja de validar en la siguiente petición — no en 15 minutos ni
        en 30 días, en la siguiente.

        Es lo que convierte `logout` en algo más que borrar una cookie del
        navegador. Un refresh token capturado sobrevivía a "cerrar sesión" y
        servía para emitir access tokens nuevos durante un mes.
        """
        user.token_version += 1
        await self.db.commit()

    async def fijar_password_hash(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def marcar_login(self, user: User, *, nuevo_hash: str | None = None) -> User:
        """Sella el último acceso y, si hacía falta, rehashea la contraseña."""
        if nuevo_hash is not None:
            user.password_hash = nuevo_hash
        user.last_login_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def confirmar(self) -> None:
        await self.db.commit()
