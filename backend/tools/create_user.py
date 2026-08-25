"""Crea una cuenta desde la línea de comandos.

Resuelve el problema del huevo y la gallina: el primer entrenador no puede
crearse desde una UI que exige ya ser entrenador, y el primer equipo no puede
crearse sin un entrenador. También sirve para añadir cuentas a una base con
datos sin pasar por `seed.py`, que la borra entera.

    # Primer arranque: crea el equipo y su dueño
    python tools/create_user.py --email coach@club.com --name "Ana" --role coach \
        --new-team "Club Natación Cartago"

    # Cuentas siguientes (si solo hay un equipo, se deduce)
    python tools/create_user.py --email ana@club.com --name "Ana" --team-id 1

Si se omite --password, se genera una temporal y se imprime una sola vez.
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from pathlib import Path

# Permite ejecutarlo como `python tools/create_user.py` desde backend/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.schemas import UserCreate
from app.api.v1.auth.service import create_user, get_by_email
from app.core.database import AsyncSessionLocal, engine
from app.persistencia.tablas.equipos import ROLE_COACH, ROLES, Team


async def _resolve_team(db: AsyncSession, team_id: int | None, new_team: str | None) -> Team | None:
    """Decide en qué equipo entra la cuenta. None = no se pudo determinar."""
    if new_team:
        team = Team(name=new_team)
        db.add(team)
        await db.commit()
        await db.refresh(team)
        print(f"Equipo creado: #{team.id}  {team.name}")
        return team

    if team_id is not None:
        return await db.get(Team, team_id)

    # Sin indicaciones: si solo existe un equipo, es evidente cuál.
    teams = list((await db.execute(select(Team))).scalars())
    if len(teams) == 1:
        return teams[0]
    if not teams:
        print("ERROR: no hay ningún equipo. Crea el primero con --new-team \"Nombre\"",
              file=sys.stderr)
    else:
        print(f"ERROR: hay {len(teams)} equipos; indica cuál con --team-id N:", file=sys.stderr)
        for t in teams:
            print(f"  {t.id}  {t.name}", file=sys.stderr)
    return None


async def main(args: argparse.Namespace) -> int:
    generated = args.password is None
    password = args.password or secrets.token_urlsafe(12)

    async with AsyncSessionLocal() as db:
        if await get_by_email(db, args.email) is not None:
            print(f"ERROR: ya existe una cuenta con el email {args.email}", file=sys.stderr)
            return 1

        team = await _resolve_team(db, args.team_id, args.new_team)
        if team is None:
            return 1

        user = await create_user(db, UserCreate(
            email=args.email, name=args.name, password=password, role=args.role,
        ), team.id)

        # Un equipo recién creado necesita dueño, y solo un entrenador puede serlo.
        if team.owner_id is None and args.role == ROLE_COACH:
            team.owner_id = user.id
            await db.commit()
            print(f"{user.name} queda como dueño de '{team.name}'")

    await engine.dispose()
    print(f"Cuenta creada: #{user.id}  {user.email}  ({args.role})  equipo #{team.id}")
    if generated:
        print(f"Contraseña temporal: {password}")
        print("Se muestra una sola vez — el hash no es reversible.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crea una cuenta de PeakStroke")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", default=ROLE_COACH, choices=ROLES)
    parser.add_argument("--password", help="si se omite, se genera una temporal")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--team-id", type=int, help="equipo existente al que se une")
    grupo.add_argument("--new-team", help="crea un equipo nuevo con este nombre")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
