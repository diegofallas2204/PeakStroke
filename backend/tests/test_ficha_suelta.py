"""`GET /swimmers/{id}` trae lo mismo que esa ficha en la lista (2026-11-10).

La página del atleta (`/atletas/:id`) es la primera pantalla que lee una ficha
suelta de otro, y el correo de su cuenta salía vacío: la lista lo rellenaba y
la lectura por id no. Un atleta con cuenta aparecía como «sin cuenta».
"""
from __future__ import annotations

import pytest
from conftest import API, World


@pytest.mark.parametrize("cual", ["carlos_swimmer_id", "sin_cuenta_swimmer_id"])
async def test_la_ficha_suelta_es_la_de_la_lista(client, world: World, cual):
    swimmer_id = getattr(world, cual)
    lista = {s["id"]: s for s in (await client.get(f"{API}/swimmers/")).json()}
    suelta = (await client.get(f"{API}/swimmers/{swimmer_id}")).json()
    assert suelta == lista[swimmer_id]


async def test_con_cuenta_trae_su_correo(client, world: World):
    suelta = (await client.get(f"{API}/swimmers/{world.carlos_swimmer_id}")).json()
    assert suelta["user_email"] == world.carlos_email
