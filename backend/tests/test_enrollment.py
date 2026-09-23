"""Un atleta, un macrociclo vivo.

La regla la pidió la interfaz ("que no le aparezca a otro entrenador para
meterlo en un macro nuevo") pero se implementó donde vale para todos: en el
POST. Estos tests comprueban las dos mitades — que la lista no lo ofrece y que
el endpoint no lo acepta —, porque esconder el botón sin cerrar la puerta es
justo lo que el CLAUDE.md llama teatro.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from conftest import API, World, como
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _alta_de_atleta(swimmer_id: int) -> dict:
    return {
        "swimmer_id": swimmer_id,
        "aerobic_base": 75.0,
        "aerobic_base_source": "t30",
        "events": [{
            "priority": 1, "distance": 200, "stroke": "libre",
            "current_time": 130.0, "goal_time": 125.0,
        }],
    }


async def _plan_nuevo(client: AsyncClient, email: str, nombre: str) -> int:
    lunes = date.today() - timedelta(days=date.today().weekday())
    r = await client.post(f"{API}/plans/", headers=como(email), json={
        "name": nombre, "start_date": lunes.isoformat(), "total_weeks": 12,
        "weeks_per_micro": 4, "total_km": 300,
        "competitions": [],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_quien_ya_esta_en_un_macro_no_aparece_como_asignable(
    client: AsyncClient, world: World,
):
    """El mundo mete a los tres nadadores en el plan: no queda nadie libre."""
    otro = await _plan_nuevo(client, world.owner_email, "Macrociclo Nuevo")
    r = await client.get(
        f"{API}/plans/{otro}/assignable-athletes", headers=como(world.owner_email),
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_tampoco_le_aparece_al_otro_entrenador(
    client: AsyncClient, world: World,
):
    """El asistente no está en `plan_coaches` del primer macro, así que no lo ve.

    Que no lo vea no lo convierte en un atleta libre: la regla es de dominio, no
    de visibilidad, y por eso la lista le sale igual de vacía que al dueño.
    """
    suyo = await _plan_nuevo(client, world.assistant_email, "Macro del Asistente")
    r = await client.get(
        f"{API}/plans/{suyo}/assignable-athletes", headers=como(world.assistant_email),
    )
    assert r.json() == []


async def test_inscribir_a_quien_ya_esta_en_otro_macro_da_409(
    client: AsyncClient, world: World,
):
    otro = await _plan_nuevo(client, world.owner_email, "Macrociclo Nuevo")
    r = await client.post(
        f"{API}/plans/{otro}/athletes", headers=como(world.owner_email),
        json=_alta_de_atleta(world.sofia_swimmer_id),
    )
    assert r.status_code == 409
    assert "Macrociclo de Prueba" in r.json()["detail"]


async def test_al_sacarlo_del_anterior_vuelve_a_estar_disponible(
    client: AsyncClient, world: World,
):
    plan = (await client.get(
        f"{API}/plans/{world.plan_id}", headers=como(world.owner_email),
    )).json()
    inscripcion = next(
        a for a in plan["athletes"] if a["swimmer_id"] == world.sofia_swimmer_id
    )
    baja = await client.delete(
        f"{API}/plans/{world.plan_id}/athletes/{inscripcion['id']}",
        headers=como(world.owner_email),
    )
    assert baja.status_code == 204

    otro = await _plan_nuevo(client, world.owner_email, "Macrociclo Nuevo")
    disponibles = (await client.get(
        f"{API}/plans/{otro}/assignable-athletes", headers=como(world.owner_email),
    )).json()
    assert [s["id"] for s in disponibles] == [world.sofia_swimmer_id]

    alta = await client.post(
        f"{API}/plans/{otro}/athletes", headers=como(world.owner_email),
        json=_alta_de_atleta(world.sofia_swimmer_id),
    )
    assert alta.status_code == 201


async def test_reactivar_no_es_la_puerta_de_atras_de_la_regla(
    client: AsyncClient, world: World,
):
    """Sacarlo, meterlo en otro macro y pulsar "restaurar" en el primero.

    Sin comprobación en el restore, el atleta acabaría en dos macrociclos vivos
    por un camino que nadie mira.
    """
    plan = (await client.get(
        f"{API}/plans/{world.plan_id}", headers=como(world.owner_email),
    )).json()
    inscripcion = next(
        a for a in plan["athletes"] if a["swimmer_id"] == world.sofia_swimmer_id
    )
    await client.delete(
        f"{API}/plans/{world.plan_id}/athletes/{inscripcion['id']}",
        headers=como(world.owner_email),
    )
    otro = await _plan_nuevo(client, world.owner_email, "Macrociclo Nuevo")
    await client.post(
        f"{API}/plans/{otro}/athletes", headers=como(world.owner_email),
        json=_alta_de_atleta(world.sofia_swimmer_id),
    )

    r = await client.post(
        f"{API}/plans/{world.plan_id}/athletes/{inscripcion['id']}/restore",
        headers=como(world.owner_email),
    )
    assert r.status_code == 409


async def test_un_atleta_no_puede_pedir_la_lista_de_asignables(
    client: AsyncClient, world: World,
):
    r = await client.get(
        f"{API}/plans/{world.plan_id}/assignable-athletes", headers=como(world.sofia_email),
    )
    assert r.status_code == 403
