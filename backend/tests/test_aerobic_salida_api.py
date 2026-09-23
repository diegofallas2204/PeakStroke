"""El intervalo de salida, de la petición a la base de datos y de vuelta.

Los tests del motor (`test_send_off.py`) fijan la aritmética. Estos fijan lo
otro, que es donde se pierde de verdad: que lo que se guarda es siempre el
tiempo NADADO —venga como venga en la petición—, que el descanso vuelve al
cliente, y que los tests antiguos, sin salida, siguen funcionando.
"""
from __future__ import annotations

import pytest
from conftest import API, World, como


async def _crear(client, world: World, **extra):
    payload = {
        "swimmer_id": world.sofia_swimmer_id,
        "test_type": "CUSTOM",
        "test_date": "2026-08-10",
        "rep_distance": 100,
        "splits": [78.0, 79.0, 80.0],
    }
    payload.update(extra)
    return await client.post(
        f"{API}/aerobic-tests/", json=payload, headers=como(world.owner_email),
    )


class TestGuardarLaSalida:
    async def test_test_sin_salida_sigue_valiendo(self, client, world: World):
        r = await _crear(client, world)
        assert r.status_code == 201
        body = r.json()
        assert body["send_off"] is None
        assert body["avg_per100"] == pytest.approx(79.0)
        assert body["rest_per_rep"] == []
        assert body["density"] is None

    async def test_la_salida_vuelve_con_descanso_y_densidad(self, client, world: World):
        r = await _crear(client, world, send_off=90.0)
        assert r.status_code == 201
        body = r.json()
        assert body["send_off"] == pytest.approx(90.0)
        assert body["rest_per_rep"] == [12.0, 11.0, 10.0]
        assert body["avg_rest"] == pytest.approx(11.0)
        assert body["density"] == pytest.approx(79.0 / 90.0, abs=1e-3)
        assert body["missed_intervals"] == []

    async def test_cada_parcial_sabe_cuando_salio_y_cuando_llego(self, client, world: World):
        r = await _crear(client, world, send_off=90.0)
        splits = r.json()["splits"]
        assert [s["send_off_time"] for s in splits] == [0.0, 90.0, 180.0]
        assert [s["arrival_time"] for s in splits] == [78.0, 169.0, 260.0]

    async def test_sin_salida_no_hay_hora_de_salida_inventada(self, client, world: World):
        splits = (await _crear(client, world)).json()["splits"]
        assert all(s["send_off_time"] is None for s in splits)
        assert all(s["arrival_time"] is None for s in splits)


class TestLlegadasDeReloj:
    """El modo en que el entrenador apunta de verdad."""

    async def test_las_llegadas_se_guardan_como_tiempos_nadados(self, client, world: World):
        r = await _crear(
            client, world, splits=[78.0, 169.0, 260.0],
            send_off=90.0, input_mode="clock",
        )
        assert r.status_code == 201
        body = r.json()
        assert body["avg_per100"] == pytest.approx(79.0)
        # Lo persistido son tiempos de nado, no llegadas: releerlo no vuelve a
        # restar y no hay forma de que la conversión se aplique dos veces.
        assert [s["split_time"] for s in body["splits"]] == [78.0, 79.0, 80.0]

    async def test_releer_el_test_da_lo_mismo_que_crearlo(self, client, world: World):
        creado = (await _crear(
            client, world, splits=[78.0, 169.0, 260.0],
            send_off=90.0, input_mode="clock",
        )).json()
        leido = (await client.get(
            f"{API}/aerobic-tests/{creado['id']}", headers=como(world.owner_email),
        )).json()
        assert leido["avg_per100"] == creado["avg_per100"]
        assert leido["per100_splits"] == creado["per100_splits"]
        assert leido["rest_per_rep"] == creado["rest_per_rep"]

    async def test_llegadas_sin_salida_no_se_aceptan(self, client, world: World):
        r = await _crear(client, world, splits=[78.0, 169.0], input_mode="clock")
        assert r.status_code == 422

    async def test_llegar_antes_de_salir_no_se_acepta(self, client, world: World):
        r = await _crear(
            client, world, splits=[78.0, 85.0], send_off=90.0, input_mode="clock",
        )
        assert r.status_code == 422

    async def test_el_modo_queda_registrado(self, client, world: World):
        r = await _crear(
            client, world, splits=[78.0, 169.0], send_off=90.0, input_mode="clock",
        )
        assert r.json()["input_mode"] == "clock"


class TestPreview:
    async def test_el_preview_devuelve_el_descanso(self, client, world: World):
        r = await client.post(
            f"{API}/aerobic-tests/analyze",
            json={"splits": [78.0, 79.0], "rep_distance": 100, "send_off": 90.0},
            headers=como(world.owner_email),
        )
        assert r.status_code == 200
        assert r.json()["avg_rest"] == pytest.approx(11.5)

    async def test_el_preview_convierte_llegadas(self, client, world: World):
        r = await client.post(
            f"{API}/aerobic-tests/analyze",
            json={
                "splits": [78.0, 169.0], "rep_distance": 100,
                "send_off": 90.0, "input_mode": "clock",
            },
            headers=como(world.owner_email),
        )
        assert r.json()["per100_splits"] == [78.0, 79.0]

    async def test_el_preview_incoherente_no_revienta_con_500(self, client, world: World):
        r = await client.post(
            f"{API}/aerobic-tests/analyze",
            json={
                "splits": [78.0, 85.0], "rep_distance": 100,
                "send_off": 90.0, "input_mode": "clock",
            },
            headers=como(world.owner_email),
        )
        assert r.status_code == 422


class TestTiemposDeEntrenamiento:
    async def test_devuelve_ritmo_y_salida_por_zona(self, client, world: World):
        r = await client.get(
            f"{API}/aerobic-tests/{world.sofia_test_id}/training-intervals",
            headers=como(world.owner_email),
        )
        assert r.status_code == 200
        body = r.json()
        assert [z["zone"] for z in body["zones"]] == ["R1", "R2", "MVO2", "RL", "V"]
        for zona in body["zones"]:
            assert zona["interval"] > zona["work"]
            assert zona["interval"] % 5 == 0        # cuadrado al reloj de pared
        assert body["reference_pace"] is not None
        assert body["event_label"] == "200m libre"

    async def test_la_distancia_de_repeticion_escala_el_trabajo(self, client, world: World):
        base = (await client.get(
            f"{API}/aerobic-tests/{world.sofia_test_id}/training-intervals",
            headers=como(world.owner_email),
        )).json()
        doble = (await client.get(
            f"{API}/aerobic-tests/{world.sofia_test_id}/training-intervals"
            "?rep_distance=200",
            headers=como(world.owner_email),
        )).json()
        assert doble["zones"][0]["work"] == pytest.approx(base["zones"][0]["work"] * 2)

    async def test_el_atleta_ve_los_suyos(self, client, world: World):
        r = await client.get(
            f"{API}/aerobic-tests/{world.sofia_test_id}/training-intervals",
            headers=como(world.sofia_email),
        )
        assert r.status_code == 200
        assert r.json()["zones"]

    async def test_el_atleta_no_ve_los_de_un_companero(self, client, world: World):
        """404 y no 403: un 403 confirmaría que ese test existe."""
        r = await client.get(
            f"{API}/aerobic-tests/{world.carlos_test_id}/training-intervals",
            headers=como(world.sofia_email),
        )
        assert r.status_code == 404

    async def test_atleta_sin_macrociclo_recibe_la_lista_vacia(self, client, world: World):
        """Sin ritmo de referencia no se inventa uno: se dice que no hay."""
        creado = (await client.post(
            f"{API}/aerobic-tests/", headers=como(world.owner_email),
            json={
                "swimmer_id": world.sin_cuenta_swimmer_id, "test_type": "DIRECT",
                "test_date": "2026-08-10", "direct_per100": 80.0,
            },
        )).json()
        # El nadador sin cuenta SÍ está en el plan del mundo, así que para
        # ejercer el caso vacío se le saca antes.
        await client.delete(
            f"{API}/plans/{world.plan_id}/athletes/{world.sin_cuenta_swimmer_id}",
            headers=como(world.owner_email),
        )
        r = await client.get(
            f"{API}/aerobic-tests/{creado['id']}/training-intervals",
            headers=como(world.owner_email),
        )
        assert r.status_code == 200
        assert r.json()["zones"] == []

    async def test_la_densidad_medida_viaja_a_la_prescripcion(self, client, world: World):
        creado = (await _crear(client, world, send_off=90.0)).json()
        r = await client.get(
            f"{API}/aerobic-tests/{creado['id']}/training-intervals",
            headers=como(world.owner_email),
        )
        body = r.json()
        assert body["measured_ratio"] == pytest.approx(11.0 / 79.0, abs=1e-3)
        assert all(z["measured_interval"] is not None for z in body["zones"])


class TestZonasDeLaSemana:
    """La salida llega también donde ya vivían las zonas."""

    async def test_la_tabla_del_equipo_trae_la_salida(self, client, world: World):
        r = await client.get(
            f"{API}/dashboard/team-week?plan_id={world.plan_id}",
            headers=como(world.owner_email),
        )
        assert r.status_code == 200
        zonas = r.json()["rows"][0]["zones"]
        assert zonas["R1"]["send_off"] % 5 == 0
        assert zonas["R1"]["send_off"] > zonas["R1"]["mid"]
        assert zonas["R1"]["rest"] > 0
