"""La prueba imposible se rechaza en la frontera, no solo en el dominio.

`test_dominio_valores.py` fija que `Prueba(50, combinado)` no se puede construir.
Eso es la regla. Esto es lo otro: que la regla **llega al usuario** por los tres
sitios que la aplican, y con qué mensaje.

Hasta el 2026-08-16 los tres validadores llamaban a `engine.events.is_valid_event`
y componían el texto a mano; ahora construyen una `Prueba` y el `ValueError` del
constructor es el cuerpo del 422. Ese cambio no tenía ni un test: la regla estaba
cubierta y el camino hasta el cliente, no.
"""
from __future__ import annotations

from conftest import API, World, como

SIMULACION = {
    "distance": 200, "stroke": "libre", "current_time": 130.0, "goal_time": 125.0,
    "total_weeks": 15, "total_km": 450.0,
}
TEMPORADA = {"distance": 200, "stroke": "libre", "current_time": 130.0}


def _mensaje(respuesta) -> str:
    return " ".join(d["msg"] for d in respuesta.json()["detail"])


class TestElMacrocicloRechazaLaPruebaImposible:
    async def test_no_se_puede_inscribir_a_alguien_en_un_50_combinado(
        self, client, world: World
    ):
        r = await client.post(
            f"{API}/plans/{world.plan_id}/athletes",
            json={
                "swimmer_id": world.carlos_swimmer_id,
                "events": [{
                    "distance": 50, "stroke": "combinado",
                    "current_time": 30.0, "goal_time": 28.5,
                }],
            },
            headers=como(world.owner_email),
        )
        assert r.status_code == 422
        assert "50 combinado" in _mensaje(r)

    async def test_una_prueba_valida_pasa_el_validador(self, client, world: World):
        # `crol` es alias de libre: el validador normaliza y deja pasar. No se
        # afirma el código de éxito porque la inscripción tiene reglas propias
        # (un atleta, un macrociclo vivo); lo que se fija es que el rechazo no
        # viene de la prueba.
        r = await client.post(
            f"{API}/plans/{world.plan_id}/athletes",
            json={
                "swimmer_id": world.carlos_swimmer_id,
                "events": [{
                    "distance": 200, "stroke": "crol",
                    "current_time": 130.0, "goal_time": 125.0,
                }],
            },
            headers=como(world.owner_email),
        )
        assert r.status_code != 422


class TestElSimuladorRechazaLaPruebaImposible:
    async def test_no_hay_800_mariposa(self, client, world: World):
        r = await client.post(
            f"{API}/simulator/run",
            json={**SIMULACION, "distance": 800, "stroke": "mariposa"},
            headers=como(world.owner_email),
        )
        assert r.status_code == 422
        assert "800 mariposa" in _mensaje(r)

    async def test_la_proyeccion_anual_aplica_la_misma_regla(self, client, world: World):
        # El alias inglés entra por la misma puerta: `im` es combinado.
        r = await client.post(
            f"{API}/simulator/season",
            json={**TEMPORADA, "distance": 50, "stroke": "im"},
            headers=como(world.owner_email),
        )
        assert r.status_code == 422
        assert "50 combinado" in _mensaje(r)

    async def test_un_estilo_que_no_existe_da_un_mensaje_distinto(
        self, client, world: World
    ):
        # Antes los dos casos caían en el mismo texto genérico. Un estilo
        # inexistente y un combo imposible son errores distintos.
        r = await client.post(
            f"{API}/simulator/run",
            json={**SIMULACION, "stroke": "mariposilla"},
            headers=como(world.owner_email),
        )
        assert r.status_code == 422
        assert "Estilo no reconocido" in _mensaje(r)

    async def test_el_simulador_sigue_corriendo_con_una_prueba_valida(
        self, client, world: World
    ):
        r = await client.post(
            f"{API}/simulator/run", json=SIMULACION, headers=como(world.owner_email),
        )
        assert r.status_code == 200
        assert r.json()["weeks"]
