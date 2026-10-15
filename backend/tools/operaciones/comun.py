"""Lo que comparten los comandos del CLI: quién actúa, confirmar, leer secretos.

**El actor no es una cuenta** (D1, punto 2 de «Antes de ejecutarlo»): quien
corre el CLI es un usuario del sistema operativo en el servidor. Se registra en
`actor_email` con el prefijo `os:` —`os:diego@servidor`— y el origen en
`detail`. Sin columna nueva, así que las vistas de PSAdmin no cambian; y el
prefijo no se confunde con un correo porque ninguno empieza por `os:` sin `@`
antes. `actor_user_id` queda vacío: no hay cuenta a la que apuntar.

**Ninguna contraseña entra por argumento.** Un argumento queda en el historial
del shell y en la lista de procesos (`ps`) de cualquiera en la máquina. Se leen
por la entrada estándar: con terminal, sin eco (`getpass`); por tubería, la
primera línea.

**Lo destructivo se confirma escribiendo el nombre del recurso**, no con «s/n»:
un «s» sale de la memoria muscular, un correo hay que leerlo.
"""
from __future__ import annotations

import getpass
import os
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ORIGEN = "tools/ops.py"
BACKEND = Path(__file__).resolve().parents[2]


class OperacionRechazada(Exception):
    """Lo que el CLI no hace, con el mensaje para quien lo pidió (sale con 1)."""


@dataclass
class Consola:
    """Por dónde habla el CLI. Los tests le pasan `StringIO`; `main`, el sistema."""

    entrada: TextIO = field(default_factory=lambda: sys.stdin)
    salida: TextIO = field(default_factory=lambda: sys.stdout)
    errores: TextIO = field(default_factory=lambda: sys.stderr)
    terminal: bool | None = None

    def __post_init__(self) -> None:
        if self.terminal is None:
            self.terminal = bool(getattr(self.entrada, "isatty", lambda: False)())

    def decir(self, texto: str) -> None:
        print(texto, file=self.salida)

    def avisar(self, texto: str) -> None:
        print(texto, file=self.errores)

    def leer_linea(self, pregunta: str) -> str:
        self.avisar(pregunta)
        return self.entrada.readline().rstrip("\r\n")

    def leer_secreto(self, pregunta: str) -> str:
        if self.terminal:
            return getpass.getpass(pregunta, stream=self.errores)
        return self.leer_linea(pregunta)


def _usuario_del_so() -> str:
    """El usuario efectivo del proceso. En POSIX, por su uid (`pwd`), no por
    `$USER`, que cualquiera cambia; en Windows no hay otra que el entorno."""
    try:
        import pwd

        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        try:
            return getpass.getuser()
        except Exception:  # sin variable de entorno ni entrada en passwd
            return "desconocido"


def actor() -> str:
    """`os:<usuario>@<host>`: quién corrió el comando, para `actor_email`.

    Bajo `sudo` el usuario efectivo es `root`, que no dice quién fue: se añade
    el que lo invocó (`os:root(sudo:diego)@servidor`). `SUDO_USER` es del
    entorno y se puede falsear, pero solo **añade** un nombre; el efectivo sale
    del uid (/cso de D1).
    """
    usuario = _usuario_del_so()
    invocante = os.environ.get("SUDO_USER")
    if invocante and invocante != usuario:
        usuario = f"{usuario}(sudo:{invocante})"
    return f"os:{usuario}@{socket.gethostname()}"[:255]


def detalle(comando: str, texto: str) -> str:
    """El texto del evento más el origen: qué comando del CLI lo produjo."""
    return f"{texto} · {ORIGEN} {comando}"[:200]


def confirmar(consola: Consola, nombre: str, que: str) -> None:
    """Pide escribir `nombre` tal cual. Cualquier otra cosa cancela."""
    escrito = consola.leer_linea(f"{que}\nEscribe «{nombre}» para confirmar:")
    if escrito.strip() != nombre:
        raise OperacionRechazada("Cancelado: lo escrito no coincide. No se cambió nada.")


def leer_password_nueva(consola: Consola) -> str:
    """Una contraseña por la entrada estándar (dos veces si hay terminal)."""
    primera = consola.leer_secreto("Contraseña nueva: ")
    if consola.terminal and consola.leer_secreto("Repítela: ") != primera:
        raise OperacionRechazada("Las dos contraseñas no coinciden. No se cambió nada.")
    return primera


def ensenar_temporal(consola: Consola, password: str) -> None:
    """La contraseña temporal sale **una sola vez**: el hash no es reversible."""
    consola.decir(f"Contraseña temporal: {password}")
    consola.decir("Se muestra una sola vez y no se guarda en ningún sitio: cópiala ahora.")


def head_de_alembic() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


async def version_de_la_base(db: AsyncSession) -> str | None:
    try:
        return (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar()
    except Exception:
        await db.rollback()
        return None


async def exigir_esquema_al_dia(db: AsyncSession) -> None:
    """Un comando que escribe no corre contra una base sin migrar.

    Escribiría sobre un esquema que el código no describe (columnas, CHECK o
    vistas de otra versión), y la auditoría clasificaría mal sus eventos.
    """
    actual, head = await version_de_la_base(db), head_de_alembic()
    if actual != head:
        raise OperacionRechazada(
            f"La base está en {actual or 'ninguna revisión'} y el código en {head}: "
            "migra primero (`alembic upgrade head`) o mira `ops.py salud`.",
        )
