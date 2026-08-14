"""Que el harness de `conftest.py` sea de fiar, antes de construir nada encima.

Un harness roto no falla: pasa. Si la DB de prueba no estuviera migrada, si las
FKs quedaran apagadas o si el test y la aplicación vieran datos distintos, los
tests de aislamiento darían verde sin comprobar nada. Estos cuatro los fijan.
"""
from __future__ import annotations

from conftest import API, World, como
from sqlalchemy import text


async def test_la_app_responde_y_se_atribuye_al_usuario_pedido(client, world: World):
    r = await client.get(f"{API}/auth/me", headers=como(world.sofia_email))
    assert r.status_code == 200
    assert r.json()["email"] == world.sofia_email
    assert r.json()["role"] == "athlete"


async def test_el_esquema_viene_de_alembic_no_de_create_all(db):
    """`alembic_version` solo existe si el esquema lo construyeron migraciones.

    Si alguien cambia el harness a `Base.metadata.create_all()`, este test
    protesta — y con él se perdería la comprobación gratis de que toda columna
    nueva trae su migración.
    """
    revision = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
    assert revision


async def test_las_claves_foraneas_estan_activas(db):
    """Sin esto, las FKs compuestas contra `(id, team_id)` serían decorativas.

    Son la última línea de defensa del aislamiento entre clubes: aunque el
    código falle, la base de datos hace imposible mezclar equipos. Un harness
    que las deje apagadas verificaría un mundo que no es el de producción.
    """
    assert (await db.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1


async def test_el_test_y_la_aplicacion_comparten_la_misma_sesion(client, db, world: World):
    """Lo que escribe una petición se ve desde el test sin `refresh()`."""
    from app.modules.swimmers.models import Swimmer

    r = await client.put(
        f"{API}/swimmers/{world.sofia_swimmer_id}",
        json={"notes": "escrito por el API"},
        headers=como(world.owner_email),
    )
    assert r.status_code == 200
    assert (await db.get(Swimmer, world.sofia_swimmer_id)).notes == "escrito por el API"
