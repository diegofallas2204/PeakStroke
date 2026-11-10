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
from app.persistencia.mapeo.identidad import (
    acceso_condicional,
    asentar_generacion,
    cambio_condicional,
    subir_generacion,
    usuario_desde_fila,
    volcar_usuario,
)
from app.persistencia.tablas.usuarios import User

from .sesiones_abiertas import RepositorioDeSesionesAbiertas


class CredencialesCambiadas(Exception):
    """La contraseña cambió entre verificarla y escribir el acceso: el login que
    la verificó ya no vale (revisor de TODO-30)."""


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
        await self._volcar(usuario, await self._fila(usuario))

    async def guardar(self, usuario: Usuario) -> User:
        """Escribe lo que la entidad gobierna —generación, hash, último acceso— y
        confirma. Devuelve la fila, que es la misma que ya tenga la sesión: quien
        la llevaba encima ve los contadores nuevos sin volver a leerla.

        Hasta el 2026-10-14 había un método por cambio (`revocar_sesiones`,
        `fijar_password_hash`, `marcar_login`) y `auth/sessions.py` subía la
        rotación a mano. Ahora el cambio lo decide la entidad y aquí solo se
        persiste. La rotación del refresh ya no pasa por aquí: es de cada
        sesión abierta (TODO-30, `RepositorioDeSesionesAbiertas.rotar`).
        """
        fila = await self._fila(usuario)
        await self._volcar(usuario, fila)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila

    async def registrar_acceso(self, usuario: Usuario) -> User:
        """Escribe el acceso de un login (`Usuario.registrar_login`) y confirma,
        **solo si la contraseña sigue siendo la verificada** (`acceso_condicional`).

        Con 0 filas confirma la transacción vacía —no `rollback`, por lo mismo
        que la rotación: caducaría lo cargado— y levanta `CredencialesCambiadas`.
        Exige la sesión limpia: lo pendiente se confirmaría aunque se perdiera.
        """
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "El acceso se escribe con la sesión limpia: confirma antes lo pendiente",
            )
        fila = await self._fila(usuario)
        if (await self.db.execute(acceso_condicional(usuario))).rowcount != 1:
            await self.db.commit()
            raise CredencialesCambiadas(usuario.id)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila

    async def cambiar_password(self, usuario: Usuario) -> User:
        """Escribe un cambio de contraseña (`Usuario.cambiar_password`) y
        confirma, **solo si la contraseña sigue siendo la verificada**
        (`cambio_condicional`); en la misma transacción borra las sesiones
        abiertas de la cuenta. Con 0 filas, como `registrar_acceso`: confirma
        vacío y `CredencialesCambiadas`.
        """
        if self.db.new or self.db.dirty or self.db.deleted:
            raise ValueError(
                "La contraseña se cambia con la sesión limpia: confirma antes lo pendiente",
            )
        fila = await self._fila(usuario)
        if (await self.db.execute(cambio_condicional(usuario))).rowcount != 1:
            await self.db.commit()
            raise CredencialesCambiadas(usuario.id)
        await RepositorioDeSesionesAbiertas(self.db).cerrar_todas_de(fila.id)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila

    async def _volcar(self, usuario: Usuario, fila: User) -> None:
        """Si la generación sube —revocar, liberar, salir de todas y cortar
        sesiones desde el CLI pasan por aquí—, la sube **relativa en SQL**
        (`subir_generacion`) y **borra las sesiones abiertas de la cuenta** en la
        misma transacción (decidido el 2026-10-20). El cambio de contraseña no
        pasa por aquí: tiene su `UPDATE` condicional (`cambiar_password`).

        La generación es la defensa —un login que abriera sesión a la vez dejaría
        una fila con tokens de la generación vieja, que no validan—; borrar es
        que la tabla diga la verdad. Relativa porque escribirla como «la leída +
        1» dejaba que un corte pisara la subida de un cambio de contraseña
        hecho entre su lectura y su escritura (vuelta 3 del revisor de TODO-30).
        """
        subir = subir_generacion(usuario, fila)
        if subir is not None and fila.id is not None:
            await self.db.execute(subir)
            asentar_generacion(usuario, fila)
            await RepositorioDeSesionesAbiertas(self.db).cerrar_todas_de(fila.id)
        volcar_usuario(usuario, fila)

    async def _fila(self, usuario: Usuario) -> User:
        fila = await self.db.get(User, usuario.id) if usuario.id is not None else None
        if fila is None:
            raise LookupError(f"No hay ninguna cuenta con id {usuario.id}")
        return fila
