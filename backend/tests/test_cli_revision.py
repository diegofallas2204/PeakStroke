"""Lo que el revisor en frío de D1 pidió demostrar (2026-10-14).

Antes, `--dry-run` y la confirmación fallida solo se probaban en algunos
comandos: quitar el `confirmar(...)` de `restablecer-password` dejaba la suite en
verde. Aquí van **todos**, y el criterio es el mismo: la base entera (cuentas,
pertenencias, clubes, fichas y auditoría) queda **idéntica**. Más dos fallos a
mitad de `crear-equipo` y un comando que escribe corrido como proceso de verdad.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import World
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.persistencia.repositorios import RepositorioDeEquipos
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.equipos import Team
from tools.operaciones import Consola, ejecutar
from tools.operaciones import equipos as cli_equipos

BACKEND = Path(__file__).resolve().parents[1]


async def _ops(db, *argv: str, entrada: str = "") -> tuple[int, Consola]:
    consola = Consola(entrada=io.StringIO(entrada), salida=io.StringIO(),
                      errores=io.StringIO(), terminal=False)
    return await ejecutar(argv, consola, db), consola


async def _foto(db) -> dict[str, list]:
    """Todo lo que un comando del CLI puede cambiar, leído de la base."""
    db.expire_all()
    consultas = {
        "users": "SELECT id, email, password_hash, token_version, refresh_rotation FROM users ORDER BY id",
        "team_members": "SELECT user_id, team_id, role, is_active FROM team_members ORDER BY user_id",
        "teams": "SELECT id, name, owner_id FROM teams ORDER BY id",
        "swimmers": "SELECT id, user_id FROM swimmers ORDER BY id",
        "auditoria": "SELECT event_type, actor_email, target_id FROM auditoria ORDER BY id",
    }
    return {k: [tuple(f) for f in (await db.execute(text(q))).all()] for k, q in consultas.items()}


def _comandos(w: World) -> list[tuple[str, list[str], str]]:
    """(nombre, argv, lo que hay que escribir para confirmar)."""
    return [
        ("revocar", ["revocar", "--correo", w.carlos_email], w.carlos_email),
        ("restaurar", ["restaurar", "--correo", w.sofia_email], ""),
        ("liberar", ["liberar", "--correo", w.sofia_email], w.sofia_email),
        ("cortar-sesiones", ["cortar-sesiones", "--correo", w.carlos_email], w.carlos_email),
        ("restablecer-password", ["restablecer-password", "--correo", w.carlos_email],
         w.carlos_email),
        ("transferir", ["transferir", "--a", w.assistant_email], "Club de Prueba"),
        ("crear-equipo", ["crear-equipo", "--nombre-equipo", "Seco", "--correo", "seco@test.dev",
                          "--nombre", "Seco"], ""),
        ("crear-cuenta", ["crear-cuenta", "--correo", "seca@test.dev", "--nombre", "Seca"], ""),
    ]


NOMBRES = ["revocar", "restaurar", "liberar", "cortar-sesiones", "restablecer-password",
           "transferir", "crear-equipo", "crear-cuenta"]
DESTRUCTIVOS = ["revocar", "liberar", "cortar-sesiones", "restablecer-password", "transferir"]


async def _preparar(db, w: World) -> None:
    """Sofía revocada: así `restaurar` y `liberar` tienen algo que hacer."""
    codigo, _ = await _ops(db, "revocar", "--correo", w.sofia_email, entrada=w.sofia_email + "\n")
    assert codigo == 0


@pytest.mark.parametrize("nombre", NOMBRES)
async def test_dry_run_no_cambia_nada_en_ningun_comando(db, world: World, nombre):
    await _preparar(db, world)
    [(_, argv, _)] = [c for c in _comandos(world) if c[0] == nombre]
    antes = await _foto(db)
    codigo, consola = await _ops(db, *argv, "--dry-run")
    assert codigo == 0, consola.errores.getvalue()
    assert consola.salida.getvalue().startswith("[dry-run]")
    assert await _foto(db) == antes


@pytest.mark.parametrize("nombre", DESTRUCTIVOS)
@pytest.mark.parametrize("escrito", ["", "si", "s"])
async def test_sin_escribir_el_nombre_ningun_destructivo_cambia_nada(db, world: World, nombre,
                                                                     escrito):
    await _preparar(db, world)
    [(_, argv, nombre_del_recurso)] = [c for c in _comandos(world) if c[0] == nombre]
    assert nombre_del_recurso                       # los destructivos lo piden
    antes = await _foto(db)
    codigo, consola = await _ops(db, *argv, entrada=escrito + "\n")
    assert codigo == 1 and "Cancelado" in consola.errores.getvalue()
    assert await _foto(db) == antes


@pytest.mark.parametrize("nombre", DESTRUCTIVOS)
async def test_escribiendo_el_nombre_cada_destructivo_escribe_y_audita(db, world: World, nombre):
    await _preparar(db, world)
    [(_, argv, nombre_del_recurso)] = [c for c in _comandos(world) if c[0] == nombre]
    antes = await _foto(db)
    codigo, consola = await _ops(db, *argv, entrada=nombre_del_recurso + "\n")
    assert codigo == 0, consola.errores.getvalue()
    despues = await _foto(db)
    assert despues != antes
    [nuevo] = despues["auditoria"][len(antes["auditoria"]):]
    assert nuevo[1].startswith("os:")


# ── crear-equipo, cuando algo falla a mitad ──────────────────────────────────

async def test_si_la_cuenta_del_dueno_falla_no_queda_club(db, world: World, monkeypatch):
    async def choca(*_a, **_k):
        raise IntegrityError("INSERT", {}, Exception("UNIQUE users.email"))

    monkeypatch.setattr(cli_equipos.auth_service, "create_user", choca)
    antes = await _foto(db)
    codigo, consola = await _ops(db, "crear-equipo", "--nombre-equipo", "Huérfano",
                                 "--correo", "carrera@test.dev", "--nombre", "Carrera")
    assert codigo == 1 and "no se creó nada" in consola.errores.getvalue()
    assert await _foto(db) == antes


async def test_si_falla_ponerle_dueno_queda_auditado_como_sin_dueno(db, world: World, monkeypatch):
    async def rota(*_a, **_k):
        raise RuntimeError("base caída")

    monkeypatch.setattr(RepositorioDeEquipos, "guardar_equipo", rota)
    codigo, consola = await _ops(db, "crear-equipo", "--nombre-equipo", "Sin Dueño",
                                 "--correo", "nodueno@test.dev", "--nombre", "No Dueño")
    assert codigo == 1 and "transferir --equipo" in consola.errores.getvalue()
    club = (await db.execute(select(Team).where(Team.name == "Sin Dueño"))).scalar_one()
    assert club.owner_id is None
    detalles = (await db.execute(
        select(EventoDeAuditoria.event_type, EventoDeAuditoria.detail).order_by(EventoDeAuditoria.id),
    )).all()
    assert [t for t, _ in detalles] == ["equipo.creado", "cuenta.creada"]
    assert "SIN DUEÑO" in detalles[0][1]


# ── Un comando que escribe, como proceso de verdad ───────────────────────────

async def test_ops_py_revoca_de_verdad_leyendo_la_confirmacion_de_stdin(db, world: World):
    await db.commit()
    r = subprocess.run(
        [sys.executable, str(BACKEND / "tools" / "ops.py"), "revocar", "--correo",
         world.carlos_email],
        input=world.carlos_email + "\n", cwd=BACKEND, capture_output=True, text=True,
        encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    foto = await _foto(db)
    assert tuple(e[0] for e in foto["auditoria"]) == ("miembro.revocado",)
    assert foto["auditoria"][0][1].startswith("os:")
