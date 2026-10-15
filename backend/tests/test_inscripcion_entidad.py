"""C9 punto 2 (REDISENO §5.4 y §5.6): `Inscripcion` y `Macrociclo.inscribir()`.

Decisiones del usuario (2026-10-05):
- sacar y devolver son **idempotentes**, como la ficha: repetirlos no da 404 y
  no deja un segundo evento de auditoría;
- `inscribir()` exige una ficha **visible y activa** — hasta hoy el POST no
  miraba la ficha y la de baja entraba (la lista de asignables la escondía,
  pero el endpoint la aceptaba: una restricción solo en la UI);
- la regla «un atleta, un macrociclo vivo» se queda en `inscripcion.py`.
"""
from __future__ import annotations

from datetime import date

import pytest
from conftest import API, World, como
from sqlalchemy import select

from app.core.auditoria import TipoDeEvento
from app.dominio.entidades import Atleta, Inscripcion, InscripcionImposible, Macrociclo
from app.dominio.valores import Ritmo
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.planes import AthletePlan

# ── El dominio ───────────────────────────────────────────────────────────────


def test_la_inscripcion_se_da_de_baja_y_vuelve_diciendo_si_cambio():
    ins = Inscripcion(atleta_id=1, macrociclo_id=2)
    assert ins.dar_de_baja() is True and ins.activa is False
    assert ins.dar_de_baja() is False
    assert ins.restaurar() is True and ins.activa is True
    assert ins.restaurar() is False


def _macro(equipo_id: int = 7) -> Macrociclo:
    return Macrociclo(id=3, equipo_id=equipo_id, inicio=date(2026, 9, 7), semanas=12)


def test_inscribir_devuelve_la_inscripcion_con_su_base():
    atleta = Atleta(id=5, equipo_id=7, nombre="Sofía")
    ins = _macro().inscribir(atleta, Ritmo(75.0), "t30")
    assert (ins.atleta_id, ins.macrociclo_id, ins.activa) == (5, 3, True)
    assert (ins.base_aerobica, ins.fuente_de_base, ins.id) == (Ritmo(75.0), "t30", None)


def test_inscribir_rechaza_una_ficha_de_baja_o_de_otro_club():
    de_baja = Atleta(id=5, equipo_id=7, nombre="Bruno", activo=False)
    with pytest.raises(InscripcionImposible, match="baja"):
        _macro().inscribir(de_baja)
    ajena = Atleta(id=6, equipo_id=99, nombre="Ajena")
    with pytest.raises(InscripcionImposible):
        _macro().inscribir(ajena)


# ── El API ───────────────────────────────────────────────────────────────────

_PRUEBA = {"priority": 1, "distance": 200, "stroke": "libre",
           "current_time": 130.0, "goal_time": 125.0}


async def _eventos(db, tipo: TipoDeEvento) -> int:
    db.expire_all()
    return len(list((await db.execute(select(EventoDeAuditoria).where(
        EventoDeAuditoria.event_type == str(tipo)))).scalars()))


async def _inscripcion_de(db, world: World, swimmer_id: int) -> int:
    return (await db.execute(select(AthletePlan.id).where(
        AthletePlan.plan_id == world.plan_id, AthletePlan.swimmer_id == swimmer_id,
    ))).scalar_one()


async def _ficha_nueva(client, world: World, nombre: str = "Nueva Nadadora") -> int:
    r = await client.post(f"{API}/swimmers/", json={"name": nombre},
                          headers=como(world.owner_email))
    assert r.status_code == 201
    return r.json()["id"]


def _inscribir(client, world: World, swimmer_id: int):
    return client.post(f"{API}/plans/{world.plan_id}/athletes", json={
        "swimmer_id": swimmer_id, "aerobic_base": 76.0, "aerobic_base_source": "t30",
        "events": [_PRUEBA],
    }, headers=como(world.owner_email))


async def test_sacar_y_devolver_dos_veces_no_falla_ni_se_audita_dos_veces(client, db, world: World):
    ins = await _inscripcion_de(db, world, world.carlos_swimmer_id)
    jefe = como(world.owner_email)
    url = f"{API}/plans/{world.plan_id}/athletes/{ins}"
    for _ in range(2):
        assert (await client.delete(url, headers=jefe)).status_code == 204
    assert await _eventos(db, TipoDeEvento.INSCRIPCION_BAJA) == 1
    for _ in range(2):
        assert (await client.post(f"{url}/restore", headers=jefe)).status_code == 204
    assert await _eventos(db, TipoDeEvento.INSCRIPCION_RESTAURADA) == 1


async def test_una_inscripcion_real_de_otro_macro_es_404_y_no_se_toca(client, db, world: World):
    """Una inscripción que EXISTE en otro macrociclo del club, no un id inventado:
    así lo que se prueba es la comprobación de que es de este macro."""
    jefe = como(world.owner_email)
    r = await client.post(f"{API}/plans/", json={
        "name": "Otro macro", "start_date": "2027-01-04", "total_weeks": 12,
        "weeks_per_micro": 4, "total_km": 300, "competitions": [],
    }, headers=jefe)
    assert r.status_code == 201, r.text
    otro_plan = r.json()["id"]
    nueva = await _ficha_nueva(client, world)
    r = await client.post(f"{API}/plans/{otro_plan}/athletes", json={
        "swimmer_id": nueva, "aerobic_base": 76.0, "aerobic_base_source": "t30",
        "events": [_PRUEBA],
    }, headers=jefe)
    assert r.status_code == 201, r.text
    ajena = (await db.execute(select(AthletePlan.id).where(
        AthletePlan.plan_id == otro_plan, AthletePlan.swimmer_id == nueva))).scalar_one()

    url = f"{API}/plans/{world.plan_id}/athletes/{ajena}"
    assert (await client.delete(url, headers=jefe)).status_code == 404
    assert (await client.post(f"{url}/restore", headers=jefe)).status_code == 404
    db.expire_all()
    assert (await db.get(AthletePlan, ajena)).is_active is True


async def test_quien_esta_de_baja_en_el_macro_no_sale_en_asignables(client, db, world: World):
    """La lista enseña la regla del POST: quien está de baja AQUÍ se devuelve,
    no se reinscribe, así que no se ofrece."""
    ins = await _inscripcion_de(db, world, world.carlos_swimmer_id)
    jefe = como(world.owner_email)
    assert (await client.delete(f"{API}/plans/{world.plan_id}/athletes/{ins}",
                                headers=jefe)).status_code == 204
    r = await client.get(f"{API}/plans/{world.plan_id}/assignable-athletes", headers=jefe)
    assert world.carlos_swimmer_id not in [a["id"] for a in r.json()]


async def test_no_se_devuelve_al_macro_una_ficha_de_baja(client, db, world: World):
    """Devolver es inscribir otra vez: la ficha tiene que seguir activa."""
    ins = await _inscripcion_de(db, world, world.carlos_swimmer_id)
    jefe = como(world.owner_email)
    url = f"{API}/plans/{world.plan_id}/athletes/{ins}"
    assert (await client.delete(url, headers=jefe)).status_code == 204
    assert (await client.delete(f"{API}/swimmers/{world.carlos_swimmer_id}",
                                headers=jefe)).status_code == 200
    r = await client.post(f"{url}/restore", headers=jefe)
    assert r.status_code == 409 and "baja" in r.json()["detail"]


async def test_una_base_aerobica_cero_es_sin_base_como_antes(client, world: World):
    """No era decisión de este bloque cambiarlo: 0 sigue entrando como «sin base»."""
    r = await client.post(f"{API}/plans/{world.plan_id}/athletes", json={
        "swimmer_id": await _ficha_nueva(client, world), "aerobic_base": 0,
        "events": [_PRUEBA],
    }, headers=como(world.owner_email))
    assert r.status_code == 201, r.text


async def test_inscribir_una_ficha_nueva_funciona(client, world: World):
    r = await _inscribir(client, world, await _ficha_nueva(client, world))
    assert r.status_code == 201


async def test_una_ficha_de_baja_no_se_inscribe(client, world: World):
    nueva = await _ficha_nueva(client, world)
    jefe = como(world.owner_email)
    assert (await client.delete(f"{API}/swimmers/{nueva}", headers=jefe)).status_code == 200
    r = await _inscribir(client, world, nueva)
    assert r.status_code == 409 and "baja" in r.json()["detail"]


async def test_una_ficha_inexistente_o_ajena_es_404_no_500(client, db, world: World):
    from app.persistencia.repositorios import RepositorioDeEquipos

    otro = await RepositorioDeEquipos(db).crear("Club Rival")
    ajena = Swimmer(team_id=otro.id, name="Ajena")
    db.add(ajena)
    await db.commit()
    for swimmer_id in (999_999, ajena.id):
        assert (await _inscribir(client, world, swimmer_id)).status_code == 404, swimmer_id


async def test_quien_esta_de_baja_en_este_macro_se_devuelve_no_se_reinscribe(client, db, world: World):
    """La pareja (macro, atleta) es única: inscribir otra vez a quien sacaron
    reventaba en la UNIQUE con un 500. Ahora dice qué hacer: devolverlo."""
    ins = await _inscripcion_de(db, world, world.carlos_swimmer_id)
    jefe = como(world.owner_email)
    assert (await client.delete(f"{API}/plans/{world.plan_id}/athletes/{ins}",
                                headers=jefe)).status_code == 204
    r = await _inscribir(client, world, world.carlos_swimmer_id)
    assert r.status_code == 409 and "devu" in r.json()["detail"].lower()


async def test_la_inscripcion_por_id_esta_acotada(db, world: World):
    """`por_id` pasa por el alcance del macrociclo y por el filtro del atleta:
    hasta hoy `inscripcion(id)` era un `db.get` sin acotar."""
    from app.api.v1.auth.service import get_by_email
    from app.core.dependencies import _principal_for
    from app.persistencia.repositorios import (
        RepositorioDeInscripciones,
        RepositorioDeMacrociclos,
    )

    ins_carlos = await _inscripcion_de(db, world, world.carlos_swimmer_id)

    async def ve(email: str) -> bool:
        p = await _principal_for(db, await get_by_email(db, email))
        repo = RepositorioDeInscripciones(RepositorioDeMacrociclos(db, p))
        return await repo.por_id(ins_carlos) is not None

    assert await ve(world.owner_email)          # el dueño llega a todos
    assert await ve(world.carlos_email)         # la suya
    assert not await ve(world.sofia_email)      # la del compañero, no
    assert not await ve(world.assistant_email)  # no está en plan_coaches
