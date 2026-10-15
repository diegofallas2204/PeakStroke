"""El agregado CodigoDeVinculacion: qué invitaciones siguen en pie.

Sin `Principal`, como los de equipos y usuarios, y por su misma razón: la mitad
de las lecturas de aquí las hace quien **todavía no pertenece a ningún club**
—`GET /link-codes/mine` y `POST /link-codes/redeem` son dos de los tres
endpoints del sistema que usan `get_current_user` en vez de `get_current_principal`—.
Un repositorio que exigiera `team_id` no podría contestarles. El equipo, cuando
aplica, entra como argumento explícito y sale siempre de la sesión.

**Si un código sigue vivo lo decide la entidad** (`CodigoDeVinculacion.es_servible`,
§5.13, 2026-10-14), y también gastarlo y revocarlo. Aquí quedan las consultas,
la traducción (`como_codigo`) y `guardar`. Las lecturas siguen devolviendo filas:
la presentación (`_to_response`) y el canje las llevan encima. De qué símbolos
se hace el código y cómo se dicta sigue en `api/v1/codigos/codigos.py`.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.entidades import CodigoDeVinculacion
from app.persistencia.mapeo.identidad import codigo_desde_fila, fila_de_codigo, volcar_codigo
from app.persistencia.repositorios.usuarios import normalizar_correo
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.codigos import LinkCode


def _normalizar_codigo(crudo: str) -> str:
    """Mayúsculas, sin guiones ni espacios. El guion es solo presentación.

    Privada: la única forma de buscar un código es `por_codigo()`, que la aplica
    siempre. Expuesta, sería una segunda puerta por la que buscar sin normalizar.
    """
    return "".join(c for c in crudo.strip().upper() if c.isalnum())


def ahora_utc() -> datetime:
    return datetime.now(UTC)




class RepositorioDeCodigos:
    """Los códigos de vinculación. Ver la cabecera: no lleva `Principal`."""

    __slots__ = ("db",)

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Lecturas ─────────────────────────────────────────────────────────────

    def _sin_gastar(self, stmt):
        """Ni canjeados ni revocados. La caducidad se filtra en Python.

        En SQL sería comparar un `datetime` con zona contra una columna que
        SQLite devuelve naive; el filtro de arriba es exacto y este es barato,
        porque un equipo tiene invitaciones vivas del orden de las decenas.
        """
        return stmt.where(LinkCode.used_at.is_(None), LinkCode.revoked_at.is_(None))

    async def _vivos(self, stmt) -> list[LinkCode]:
        ahora = ahora_utc()
        filas = (await self.db.execute(self._sin_gastar(stmt))).scalars()
        return [c for c in filas if codigo_desde_fila(c).es_servible(ahora)]

    async def activos_del_equipo(self, team_id: int) -> list[LinkCode]:
        """Los códigos que todavía sirven, del equipo entero."""
        return await self._vivos(
            select(LinkCode).where(LinkCode.team_id == team_id)
            .order_by(LinkCode.created_at.desc()),
        )

    async def dirigidos_a(self, correo: str) -> list[LinkCode]:
        """Las invitaciones vivas dirigidas a ese correo.

        Se busca por **correo** y no por usuario porque el entrenador invita
        antes de que exista la cuenta tan a menudo como después: quien se
        registre luego con ese correo encuentra su solicitud esperando.

        Solo salen las dirigidas (`invited_email`). Un código emitido sobre una
        ficha suelta no va dirigido a nadie, y listarlo aquí sería enseñárselo a
        quien no tiene por qué saber que existe.
        """
        return await self._vivos(
            select(LinkCode)
            .where(LinkCode.invited_email == normalizar_correo(correo))
            .order_by(LinkCode.created_at.desc()),
        )

    async def por_codigo(self, crudo: str) -> LinkCode | None:
        stmt = select(LinkCode).where(LinkCode.code == _normalizar_codigo(crudo))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def del_equipo(self, code_id: int, team_id: int) -> LinkCode | None:
        """El código, solo si es de ese equipo. `None` si no — el router: 404."""
        stmt = select(LinkCode).where(
            LinkCode.id == code_id, LinkCode.team_id == team_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def sin_gastar_de_la_ficha(self, swimmer_id: int) -> list[LinkCode]:
        """Los códigos de esa ficha que aún no se han canjeado ni revocado."""
        stmt = self._sin_gastar(select(LinkCode).where(LinkCode.swimmer_id == swimmer_id))
        return list((await self.db.execute(stmt)).scalars())

    async def ficha_pendiente(self, correo: str, team_id: int) -> Swimmer | None:
        """La ficha ya creada para ese correo en este equipo y todavía pendiente.

        Existe para que reinvitar a la misma persona reemita el código en vez de
        dejar dos fichas suyas en la lista de atletas. Es el caso normal: se
        manda la invitación, se pierde, y el entrenador vuelve a mandarla.
        """
        stmt = (
            self._sin_gastar(
                select(Swimmer).join(LinkCode, LinkCode.swimmer_id == Swimmer.id)
            )
            .where(
                LinkCode.invited_email == normalizar_correo(correo),
                LinkCode.team_id == team_id,
                Swimmer.user_id.is_(None),
                Swimmer.is_active.is_(True),
            )
            .order_by(LinkCode.created_at.desc())
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalars().first()

    async def ficha_de_la_cuenta(self, user_id: int) -> Swimmer | None:
        """La ficha ya ligada a esa cuenta, si la hay. **Sin acotar por equipo.**

        A propósito: quien pregunta puede no ser de ningún club todavía, y la
        respuesta a "¿tu cuenta ya está ligada?" no depende de dónde esté.
        `Swimmer.user_id` es único global, así que es una ficha o ninguna.
        """
        stmt = select(Swimmer).where(Swimmer.user_id == user_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── Escrituras ───────────────────────────────────────────────────────────

    def como_codigo(self, fila: LinkCode) -> CodigoDeVinculacion:
        return codigo_desde_fila(fila)

    async def anotar(self, codigo: CodigoDeVinculacion) -> None:
        """Escribe el ciclo de vida en su fila **sin confirmar**: lo confirma el
        `guardar` que venga después en la misma petición (reemitir revoca los
        anteriores y crea el nuevo en un solo commit)."""
        fila = await self.db.get(LinkCode, codigo.id) if codigo.id is not None else None
        if fila is None:
            raise LookupError(f"No hay ningún código con id {codigo.id}")
        volcar_codigo(codigo, fila)

    async def guardar(self, codigo: CodigoDeVinculacion) -> LinkCode:
        """Inserta uno recién emitido o escribe su ciclo de vida, y confirma.

        **Confirma la sesión entera**: el canje deja en la misma unidad de
        trabajo la pertenencia nueva y la ficha ligada, y los tres van juntos.
        Devuelve la fila, que es lo que pinta la respuesta.
        """
        if codigo.id is None:
            fila = fila_de_codigo(codigo)
            self.db.add(fila)
        else:
            fila = await self.db.get(LinkCode, codigo.id)
            if fila is None:
                raise LookupError(f"No hay ningún código con id {codigo.id}")
            volcar_codigo(codigo, fila)
        await self.db.commit()
        await self.db.refresh(fila)
        codigo.id = fila.id
        return fila
