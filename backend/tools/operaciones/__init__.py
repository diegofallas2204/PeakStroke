"""El CLI de operaciones de PeakStroke (D1, 2026-10-14). Se ejecuta con `tools/ops.py`.

Las operaciones peligrosas no tienen interfaz web: van por aquí, en el servidor,
con superficie de red cero. Cada comando que escribe **audita** (tipo, actor del
sistema operativo, objetivo), y los destructivos piden escribir el nombre del
recurso y tienen `--dry-run`. Ver `tools/README.md`.

`ejecutar(argv, consola, db)` es la puerta para los tests: corre el comando
sobre la sesión que le den, dentro de un contexto de auditoría propio que se
vuelca al terminar (como `tools/purgar_auditoria.py`).
"""
from __future__ import annotations

import argparse
from collections.abc import Awaitable, Callable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import contexto_de_auditoria
from app.persistencia.tablas.equipos import ROLE_COACH, ROLES

from . import acceso, equipos, salud
from .comun import ORIGEN, Consola, OperacionRechazada, exigir_esquema_al_dia

Comando = Callable[[AsyncSession, argparse.Namespace, Consola], Awaitable[int]]


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ops.py", description="Operaciones de PeakStroke.")
    sub = p.add_subparsers(dest="comando", required=True, metavar="COMANDO")

    def comando(
        nombre: str, ayuda: str, funcion: Comando, *, escribe: bool = True,
    ) -> argparse.ArgumentParser:
        c = sub.add_parser(nombre, help=ayuda, description=ayuda)
        c.set_defaults(funcion=funcion, escribe=escribe)
        if escribe:
            c.add_argument("--dry-run", action="store_true",
                           help="enseña lo que haría, sin escribir ni auditar")
        return c

    def alta(c: argparse.ArgumentParser) -> None:
        c.add_argument("--correo", required=True)
        c.add_argument("--nombre", required=True, help="nombre de la persona")
        c.add_argument("--password-stdin", action="store_true",
                       help="lee la contraseña de la entrada estándar; sin esto se genera "
                            "una temporal que se enseña una vez")

    c = comando("crear-equipo", "crea un club y su dueño (un entrenador)", equipos.crear_equipo)
    c.add_argument("--nombre-equipo", required=True)
    alta(c)

    c = comando("crear-cuenta", "da de alta una cuenta en un club", equipos.crear_cuenta)
    alta(c)
    c.add_argument("--rol", choices=ROLES, default=ROLE_COACH)
    c.add_argument("--equipo", type=int, help="id del club (si hay uno solo, se deduce)")

    for nombre, ayuda, funcion in (
        ("revocar", "le quita el acceso al club y corta sus sesiones", acceso.revocar),
        ("restaurar", "le devuelve el acceso al club", acceso.restaurar),
        ("liberar", "deja en el pool a un atleta revocado (borra la pertenencia)", acceso.liberar),
        ("cortar-sesiones", "invalida todos sus tokens", acceso.cortar_sesiones),
        ("restablecer-password", "emite una contraseña temporal", acceso.restablecer_password),
    ):
        comando(nombre, ayuda, funcion).add_argument("--correo", required=True)

    c = comando("transferir", "cede la propiedad de un club", equipos.transferir)
    c.add_argument("--a", required=True, metavar="CORREO", help="el nuevo dueño")
    c.add_argument("--equipo", type=int, help="id del club (si hay uno solo, se deduce)")

    comando("salud", "versión, migraciones y conteos (solo lee)", salud.salud, escribe=False)
    return p


def analizar(argv: Sequence[str]) -> argparse.Namespace:
    return _parser().parse_args(list(argv))


async def ejecutar(argv: Sequence[str], consola: Consola, db: AsyncSession) -> int:
    """Corre un comando. 0 bien, 1 rechazado (con el motivo en stderr), 3 hecho
    pero **sin auditar**: la escritura del evento falló (y el log dice cuál).

    En una petición web, que la auditoría falle no tumba nada (D0); aquí no
    puede pasar en silencio: una revocación sin rastro con salida 0 es lo que
    un operador no tiene que poder hacer sin enterarse (/cso de D1).
    """
    args = analizar(argv)
    async with contexto_de_auditoria(user_agent=ORIGEN) as ctx:
        try:
            if args.escribe:
                await exigir_esquema_al_dia(db)
            codigo = await args.funcion(db, args, consola)
        except OperacionRechazada as exc:
            await db.rollback()
            consola.avisar(f"ERROR: {exc}")
            codigo = 1
    if ctx.perdidos:
        consola.avisar(
            f"ERROR: la operación se hizo, pero {ctx.perdidos} evento(s) de auditoría "
            "no se guardaron. Están en el log de arriba: apúntalos a mano.",
        )
        return 3
    return codigo
