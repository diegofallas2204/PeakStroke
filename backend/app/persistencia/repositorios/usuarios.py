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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.entidades import Usuario
from app.persistencia.mapeo.identidad import usuario_desde_fila, volcar_usuario
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

    def entidad(self, fila: User) -> Usuario:
        """La cuenta como `Usuario`, para pedirle que cambie (§5.1).

        Las lecturas siguen devolviendo filas: `Principal` y las dependencias
        las llevan encima en cada petición. La entidad es para escribir.
        """
        return usuario_desde_fila(fila)

    async def anotar(self, usuario: Usuario) -> None:
        """Vuelca lo que la entidad cambió **sin confirmar**: lo confirma quien
        cierre la unidad de trabajo, en el mismo commit.

        Existe para que cortar las sesiones viaje con el gesto que las corta
        (D1, 2026-10-14): revocar una pertenencia (`guardar_pertenencia`) y
        liberarla (`RepositorioDeEquipos.liberar`) confirman la sesión entera.
        Dos commits dejarían, si el segundo fallara, a alguien echado del club y
        con su token vivo — o con el token muerto y todavía dentro.
        """
        fila = await self.db.get(User, usuario.id) if usuario.id is not None else None
        if fila is None:
            raise LookupError(f"No hay ninguna cuenta con id {usuario.id}")
        volcar_usuario(usuario, fila)

    async def guardar(self, usuario: Usuario) -> User:
        """Escribe lo que la entidad gobierna —sesiones, hash, último acceso— y
        confirma. Devuelve la fila, que es la misma que ya tenga la sesión: quien
        la llevaba encima ve los contadores nuevos sin volver a leerla.

        Hasta el 2026-10-14 había un método por cambio (`revocar_sesiones`,
        `fijar_password_hash`, `marcar_login`) y `auth/sessions.py` subía la
        rotación a mano. Ahora el cambio lo decide la entidad y aquí solo se
        persiste.
        """
        fila = await self.db.get(User, usuario.id) if usuario.id is not None else None
        if fila is None:
            raise LookupError(f"No hay ninguna cuenta con id {usuario.id}")
        volcar_usuario(usuario, fila)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila
