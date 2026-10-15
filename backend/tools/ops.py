"""CLI de operaciones de PeakStroke: lo que no tiene ni tendrá interfaz web.

    python tools/ops.py --help
    python tools/ops.py salud
    python tools/ops.py crear-equipo --nombre-equipo "Club Natación Cartago" \
        --correo ana@club.com --nombre "Ana"
    python tools/ops.py revocar --correo carlos@club.com --dry-run

Cada comando y cuándo usarlo: `tools/README.md`. Se corre en el servidor, desde
`backend/`, contra la base de `PEAKSTROKE_DATABASE_URL`.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Permite ejecutarlo como `python tools/ops.py` desde backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operaciones import Consola, analizar, ejecutar

from app.core import model_registry  # noqa: F401  (las FKs necesitan todas las tablas)
from app.core.database import AsyncSessionLocal, engine


async def main(argv: list[str]) -> int:
    analizar(argv)  # --help y los errores de uso salen antes de abrir la base
    try:
        async with AsyncSessionLocal() as db:
            return await ejecutar(argv, Consola(), db)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    # Que un evento que no se pudo guardar se vea: `volcar` lo deja en el log.
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
