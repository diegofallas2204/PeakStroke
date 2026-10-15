"""D1: crear club y cuenta, transferir, salud y el punto de entrada del CLI.

`crear-equipo` y `crear-cuenta` sustituyen a `tools/create_user.py`, que
aceptaba `--password` por argumento y no auditaba. Lo que fija este archivo:
ninguna opción del CLI recibe una contraseña; la temporal sale una sola vez;
`--password-stdin` la lee de la entrada; y las validaciones son las del API.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import World
from sqlalchemy import select

from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.equipos import Team, TeamMember
from app.persistencia.tablas.usuarios import User
from tools import operaciones
from tools.operaciones import Consola, analizar, comun, ejecutar, salud

BACKEND = Path(__file__).resolve().parents[1]


async def _ops(db, *argv: str, entrada: str = "") -> tuple[int, Consola]:
    consola = Consola(entrada=io.StringIO(entrada), salida=io.StringIO(),
                      errores=io.StringIO(), terminal=False)
    return await ejecutar(argv, consola, db), consola


async def _tipos(db) -> list[str]:
    return list((await db.execute(
        select(EventoDeAuditoria.event_type).order_by(EventoDeAuditoria.id),
    )).scalars())


async def _club(db, nombre: str) -> Team | None:
    db.expire_all()
    return (await db.execute(select(Team).where(Team.name == nombre))).scalar_one_or_none()


# ── Ninguna contraseña por argumento ─────────────────────────────────────────

def test_ninguna_opcion_del_cli_recibe_una_contrasena():
    parser = operaciones._parser()
    opciones = {
        o for sub in parser._subparsers._group_actions[0].choices.values()
        for a in sub._actions for o in a.option_strings
    }
    assert {o for o in opciones if "pass" in o} == {"--password-stdin"}
    with pytest.raises(SystemExit):
        analizar(["crear-cuenta", "--correo", "a@b.dev", "--nombre", "Ana", "--password", "x"])


# ── crear-equipo ─────────────────────────────────────────────────────────────

async def test_crear_equipo_con_su_dueno_y_temporal_una_vez(db, world: World):
    codigo, consola = await _ops(db, "crear-equipo", "--nombre-equipo", "Club Nuevo",
                                 "--correo", "  Nueva@Test.dev ", "--nombre", "Dueña Nueva")
    assert codigo == 0, consola.errores.getvalue()
    club = await _club(db, "Club Nuevo")
    dueno = (await db.execute(select(User).where(User.email == "nueva@test.dev"))).scalar_one()
    assert club.owner_id == dueno.id
    miembro = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == dueno.id),
    )).scalar_one()
    assert (miembro.team_id, miembro.role, miembro.is_active) == (club.id, "coach", True)
    salida = consola.salida.getvalue()
    assert salida.count("Contraseña temporal: ") == 1
    assert await _tipos(db) == ["equipo.creado", "cuenta.creada"]


async def test_crear_equipo_con_password_por_stdin_no_la_ensena(db, world: World):
    codigo, consola = await _ops(db, "crear-equipo", "--nombre-equipo", "Club Stdin",
                                 "--correo", "stdin@test.dev", "--nombre", "Por Stdin",
                                 "--password-stdin", entrada="una-clave-larga-1\n")
    assert codigo == 0, consola.errores.getvalue()
    assert "una-clave-larga-1" not in consola.salida.getvalue() + consola.errores.getvalue()
    assert "temporal" not in consola.salida.getvalue()


@pytest.mark.parametrize(("argv", "mensaje"), [
    (["--nombre-equipo", " ", "--correo", "x@test.dev", "--nombre", "Equis"], "name"),
    (["--nombre-equipo", "Club", "--correo", "no-es-correo", "--nombre", "Equis"], "email"),
    (["--nombre-equipo", "Club", "--correo", "x@test.dev", "--nombre", "E"], "name"),
    (["--nombre-equipo", "Club", "--correo", "OWNER@test.dev", "--nombre", "Equis"], "Ya existe"),
])
async def test_crear_equipo_valida_como_el_api_y_no_deja_nada(db, world: World, argv, mensaje):
    antes = len((await db.execute(select(Team))).scalars().all())
    codigo, consola = await _ops(db, "crear-equipo", *argv)
    assert codigo == 1 and mensaje in consola.errores.getvalue()
    assert len((await db.execute(select(Team))).scalars().all()) == antes
    assert await _tipos(db) == []


async def test_password_por_stdin_corta_da_error_sin_crear(db, world: World):
    codigo, consola = await _ops(db, "crear-cuenta", "--correo", "corta@test.dev",
                                 "--nombre", "Corta", "--password-stdin", entrada="abc\n")
    assert codigo == 1 and "password" in consola.errores.getvalue()
    assert (await db.execute(select(User).where(User.email == "corta@test.dev"))).first() is None


# ── crear-cuenta ─────────────────────────────────────────────────────────────

async def test_crear_cuenta_deduce_el_unico_club(db, world: World):
    codigo, consola = await _ops(db, "crear-cuenta", "--correo", "nuevo@test.dev",
                                 "--nombre", "Nuevo Coach")
    assert codigo == 0, consola.errores.getvalue()
    assert f"en #{world.team_id}" in consola.salida.getvalue()
    assert await _tipos(db) == ["cuenta.creada"]


async def test_con_dos_clubes_hay_que_decir_cual(db, world: World):
    await _ops(db, "crear-equipo", "--nombre-equipo", "Otro", "--correo", "o@test.dev",
               "--nombre", "Otra")
    codigo, consola = await _ops(db, "crear-cuenta", "--correo", "z@test.dev", "--nombre", "Zeta")
    assert codigo == 1 and "--equipo" in consola.errores.getvalue()
    codigo, consola = await _ops(db, "crear-cuenta", "--correo", "z@test.dev", "--nombre", "Zeta",
                                 "--equipo", "999")
    assert codigo == 1 and "No hay ningún club con id 999" in consola.errores.getvalue()


# ── transferir ───────────────────────────────────────────────────────────────

async def test_transferir_confirma_con_el_nombre_del_club(db, world: World):
    args = ("transferir", "--a", world.assistant_email)
    assert (await _ops(db, *args, entrada=world.assistant_email + "\n"))[0] == 1
    assert (await _ops(db, *args, "--dry-run"))[0] == 0
    asistente = (await db.execute(
        select(User.id).where(User.email == world.assistant_email),
    )).scalar_one()
    assert (await _club(db, "Club de Prueba")).owner_id != asistente
    assert await _tipos(db) == []

    codigo, consola = await _ops(db, *args, entrada="Club de Prueba\n")
    assert codigo == 0, consola.errores.getvalue()
    assert (await _club(db, "Club de Prueba")).owner_id == asistente
    [evento] = (await db.execute(select(EventoDeAuditoria))).scalars().all()
    assert (evento.event_type, evento.target_id) == ("equipo.propiedad_transferida", asistente)
    assert evento.actor_email.startswith("os:")


async def test_transferir_a_un_atleta_lo_rechaza_la_entidad(db, world: World):
    codigo, consola = await _ops(db, "transferir", "--a", world.sofia_email,
                                 entrada="Club de Prueba\n")
    assert codigo == 1 and "Solo un entrenador" in consola.errores.getvalue()


# ── salud y una base sin migrar ──────────────────────────────────────────────

async def test_salud_solo_lee_y_no_audita(db, world: World):
    codigo, consola = await _ops(db, "salud")
    salida = consola.salida.getvalue()
    assert codigo == 0 and "al día" in salida and "clubes" in salida
    assert await _tipos(db) == []


async def test_una_base_sin_migrar_no_se_escribe(db, world: World, monkeypatch):
    monkeypatch.setattr(comun, "head_de_alembic", lambda: "otra_revision")
    monkeypatch.setattr(salud, "head_de_alembic", lambda: "otra_revision")
    codigo, consola = await _ops(db, "cortar-sesiones", "--correo", world.sofia_email,
                                 entrada=world.sofia_email + "\n")
    assert codigo == 1 and "migra primero" in consola.errores.getvalue()
    assert (await _ops(db, "salud"))[0] == 2
    assert await _tipos(db) == []


# ── El punto de entrada de verdad ────────────────────────────────────────────

def _correr(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BACKEND / "tools" / "ops.py"), *argv],
        cwd=BACKEND, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True, text=True,
        encoding="utf-8", timeout=120,
    )


def test_ops_py_lista_los_comandos():
    r = _correr("--help")
    assert r.returncode == 0
    for comando in ("crear-equipo", "crear-cuenta", "revocar", "restaurar", "liberar",
                    "cortar-sesiones", "restablecer-password", "transferir", "salud"):
        assert comando in r.stdout


async def test_ops_py_contra_la_base_de_pruebas(db, world: World):
    """El proceso de verdad, con su propia sesión: lee la base y sale bien."""
    await db.commit()
    r = _correr("salud")
    assert r.returncode == 0, r.stderr
    assert "clubes" in r.stdout and "al día" in r.stdout
