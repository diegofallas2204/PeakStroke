"""Reconstruye `carga_diaria` desde cero para todos los atletas (o uno).

La tabla es un derivado y se mantiene sola: cada escritura de sesiones y tests
la recalcula. Esta herramienta es para lo que no pasa por esas escrituras —la
migración que la crea, o una sospecha de que se desincronizó—. Recalcular dos
veces deja lo mismo.

    python tools/recalcular_carga.py              # todos
    python tools/recalcular_carga.py --swimmer 7  # uno
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core import model_registry  # noqa: F401
from app.core.database import AsyncSessionLocal, engine
from app.persistencia.repositorios.carga import recalcular
from app.persistencia.tablas.atletas import Swimmer


async def main(swimmer_id: int | None) -> None:
    async with AsyncSessionLocal() as db:
        stmt = select(Swimmer.id, Swimmer.team_id)
        if swimmer_id is not None:
            stmt = stmt.where(Swimmer.id == swimmer_id)
        nadadores = (await db.execute(stmt)).all()
        for sid, team_id in nadadores:
            # `date.min` no tiene ningún día anterior guardado: serie entera.
            await recalcular(db, team_id=team_id, swimmer_id=sid, desde=date.min)
            await db.commit()
        print(f"carga_diaria recalculada para {len(nadadores)} atleta(s)")
    await engine.dispose()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--swimmer", type=int, default=None)
    asyncio.run(main(p.parse_args().swimmer))
