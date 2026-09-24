"""Las vistas `v_admin_*`: el único contrato de lectura de PSAdmin (D0).

**La vista es la frontera, no una convención.** Estos tests fijan las dos cosas
que la hacen frontera:

- **qué tablas lee cada vista**: ninguna deportiva. Si alguien añade un `JOIN`
  a `plans` o a `resultados` para "enseñar un dato más", esto falla;
- **qué columnas expone, exactamente**: añadir una es una decisión sobre qué ve
  un administrador, y tiene que pasar por aquí con su razón, no colarse.

Y después, que cada vista dice la verdad sobre el mundo de prueba.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from conftest import API, World, como
from sqlalchemy import select, text

from app.core.auditoria import TIPOS_DE_ACCESO, TipoDeEvento
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.usuarios import User

COLUMNAS = {
    "v_admin_accesos": [
        "id", "occurred_at", "event_type", "outcome", "actor_user_id", "actor_email",
        "team_id", "ip_network", "ip_hash", "user_agent", "detail",
    ],
    "v_admin_cuentas": [
        "user_id", "email", "name", "account_active", "created_at", "last_login_at",
        "team_id", "team_name", "role", "membership_active", "is_owner",
        "has_swimmer_profile", "status",
    ],
    "v_admin_equipos": [
        "team_id", "name", "created_at", "owner_email", "active_coaches",
        "active_athletes", "revoked_members", "active_swimmer_profiles",
        "last_activity_at",
    ],
}

# Lo único que una vista de administración puede leer. `swimmers` entra por
# dos columnas que no son rendimiento (si una cuenta tiene ficha, y cuántas
# fichas activas hay); `claves_de_auditoria` no entra NUNCA: con la clave, la
# huella de una IPv4 se deshace en minutos.
TABLAS_PERMITIDAS = {"auditoria", "users", "team_members", "teams", "swimmers"}

# Cualquier columna que suene a rendimiento es un error, se llame como se llame.
_DEPORTIVO = re.compile(
    r"time|pace|zone|zona|km|css|stss|ctl|atl|tsb|split|goal|meta|plan|test|"
    r"distance|rpe|weight|birth|gender|stroke|specialty",
    re.IGNORECASE,
)


async def _sql_de(db, vista: str) -> str:
    return (await db.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'view' AND name = :n"), {"n": vista},
    )).scalar_one()


@pytest.mark.parametrize("vista", COLUMNAS)
async def test_la_vista_expone_exactamente_sus_columnas(db, vista):
    columnas = [fila[1] for fila in await db.execute(text(f"PRAGMA table_info({vista})"))]
    assert columnas == COLUMNAS[vista]
    assert not [c for c in columnas if _DEPORTIVO.search(c)]


@pytest.mark.parametrize("vista", COLUMNAS)
async def test_la_vista_no_lee_ninguna_tabla_deportiva(db, vista):
    sql = await _sql_de(db, vista)
    tablas = set(re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", sql, flags=re.IGNORECASE))
    assert tablas, "la expresión regular no encontró ninguna tabla: revisarla"
    assert tablas <= TABLAS_PERMITIDAS, f"{vista} lee {tablas - TABLAS_PERMITIDAS}"


async def test_no_hay_mas_vistas_de_admin_que_las_del_contrato(db):
    vistas = (await db.execute(text(
        "SELECT name FROM sqlite_master WHERE type = 'view' AND name LIKE 'v_admin_%'",
    ))).scalars().all()
    assert sorted(vistas) == sorted(COLUMNAS)


async def test_accesos_filtra_exactamente_los_tipos_de_acceso(db, world: World):
    """La vista filtra en SQL (copia de la migración); el código, con el enum."""
    ahora = datetime.now(UTC)
    db.add_all([
        EventoDeAuditoria(occurred_at=ahora, event_type=str(t), outcome="ok", detail="")
        for t in TipoDeEvento
    ])
    await db.commit()
    tipos = set((await db.execute(text("SELECT event_type FROM v_admin_accesos"))).scalars())
    assert tipos == {str(t) for t in TIPOS_DE_ACCESO}


async def test_cuentas_distingue_los_cuatro_estados(client, db, world: World):
    """Revocado ≠ sin equipo ≠ desactivada: la vista no deja confundirlos."""
    carlos = (await db.execute(
        select(User.id).where(User.email == world.carlos_email),
    )).scalar_one()
    await client.patch(
        f"{API}/auth/members/{carlos}", json={"is_active": False},
        headers=como(world.owner_email),
    )
    db.add(User(email="suelto@test.dev", password_hash="x", name="Sin Club"))
    huerfano = (await db.execute(
        select(User).where(User.email == world.huerfano_email),
    )).scalar_one()
    huerfano.is_active = False
    await db.commit()

    filas = {
        f.email: f for f in (await db.execute(text("SELECT * FROM v_admin_cuentas"))).mappings()
    }
    assert filas[world.owner_email]["status"] == "activa"
    assert filas[world.owner_email]["is_owner"] == 1
    assert filas[world.assistant_email]["is_owner"] == 0
    assert filas[world.carlos_email]["status"] == "revocada"
    assert filas["suelto@test.dev"]["status"] == "sin_equipo"
    assert filas["suelto@test.dev"]["team_id"] is None
    assert filas[world.huerfano_email]["status"] == "desactivada"
    assert filas[world.sofia_email]["has_swimmer_profile"] == 1
    assert filas[world.huerfano_email]["has_swimmer_profile"] == 0


async def test_equipos_cuenta_personas_y_la_ultima_actividad(client, db, world: World):
    fila = (await db.execute(text("SELECT * FROM v_admin_equipos"))).mappings().one()
    assert fila["team_id"] == world.team_id
    assert fila["owner_email"] == world.owner_email
    assert (fila["active_coaches"], fila["active_athletes"], fila["revoked_members"]) == (2, 3, 0)
    assert fila["active_swimmer_profiles"] == 3
    assert fila["last_activity_at"] is None

    await client.delete(
        f"{API}/swimmers/{world.carlos_swimmer_id}", headers=como(world.owner_email),
    )
    fila = (await db.execute(text("SELECT * FROM v_admin_equipos"))).mappings().one()
    assert fila["active_swimmer_profiles"] == 2
    assert fila["last_activity_at"] is not None
