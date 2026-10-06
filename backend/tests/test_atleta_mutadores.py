"""C9 punto 1 (REDISENO §5.3): la ficha se escribe a través de `Atleta`.

`dar_de_baja()` / `restaurar()` son del atleta, y `RepositorioDeAtletas.guardar`
es la única puerta que vuelca una ficha a su fila. Decisiones del usuario
(2026-10-05): las transiciones son **idempotentes** —dar de baja a quien ya lo
está no falla— y lo que no cambia **no se audita**; y el estilo y el género se
escriben **canónicos**, aunque la fila viniera con un alias («crol»).
"""
from __future__ import annotations

from conftest import API, World, como
from sqlalchemy import select, update

from app.core.auditoria import TipoDeEvento
from app.dominio.entidades import Atleta
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.auditoria import EventoDeAuditoria

# ── El dominio ───────────────────────────────────────────────────────────────


def test_dar_de_baja_y_restaurar_dicen_si_cambiaron_algo():
    atleta = Atleta(nombre="Sofía")
    assert atleta.dar_de_baja() is True and atleta.activo is False
    assert atleta.dar_de_baja() is False and atleta.activo is False   # idempotente
    assert atleta.restaurar() is True and atleta.activo is True
    assert atleta.restaurar() is False and atleta.activo is True


# ── El API, por la entidad ───────────────────────────────────────────────────

async def _eventos(db, tipo: TipoDeEvento) -> int:
    db.expire_all()
    return len(list((await db.execute(
        select(EventoDeAuditoria).where(EventoDeAuditoria.event_type == str(tipo))
    )).scalars()))


async def test_la_baja_repetida_no_falla_ni_se_audita_dos_veces(client, db, world: World):
    jefe = como(world.owner_email)
    url = f"{API}/swimmers/{world.sin_cuenta_swimmer_id}"
    for _ in range(2):
        r = await client.delete(url, headers=jefe)
        assert r.status_code == 200 and r.json()["is_active"] is False
    assert await _eventos(db, TipoDeEvento.NADADOR_BAJA) == 1

    for _ in range(2):
        r = await client.post(f"{url}/reactivate", headers=jefe)
        assert r.status_code == 200 and r.json()["is_active"] is True
    assert await _eventos(db, TipoDeEvento.NADADOR_RESTAURADO) == 1


async def test_guardar_escribe_canonico_lo_que_venia_crudo(client, db, world: World):
    """Una ficha antigua con «crol» se lee igual, y al guardarla queda «libre»."""
    await db.execute(update(Swimmer).where(Swimmer.id == world.sofia_swimmer_id)
                     .values(main_stroke="crol"))
    await db.commit()

    r = await client.put(f"{API}/swimmers/{world.sofia_swimmer_id}",
                         json={"notes": "nueva nota"}, headers=como(world.owner_email))
    assert r.status_code == 200
    assert (r.json()["main_stroke"], r.json()["notes"]) == ("libre", "nueva nota")


async def test_put_parcial_solo_toca_lo_que_llega_y_null_borra_lo_opcional(client, world: World):
    url = f"{API}/swimmers/{world.sofia_swimmer_id}"
    jefe = como(world.owner_email)
    antes = (await client.get(url, headers=jefe)).json()

    r = await client.put(url, json={"gender": None, "weight_kg": 61.5}, headers=jefe)
    assert r.status_code == 200
    despues = r.json()
    assert (despues["gender"], despues["weight_kg"]) == (None, 61.5)
    for campo in ("name", "birth_date", "specialty", "main_stroke", "user_id", "is_active"):
        assert despues[campo] == antes[campo], campo


async def test_vaciar_un_campo_obligatorio_es_422_no_500(client, world: World):
    """Antes `specialty: null` llegaba a la columna NOT NULL y reventaba en el commit."""
    r = await client.put(f"{API}/swimmers/{world.sofia_swimmer_id}",
                         json={"specialty": None}, headers=como(world.owner_email))
    assert r.status_code == 422


async def test_guardar_no_escribe_la_cuenta_ligada(db, world: World):
    """Ligar ficha y cuenta es del canje del código, no de guardar la ficha:
    aunque la entidad llegue con otro `usuario_id`, la fila conserva el suyo."""
    from app.api.v1.auth.service import get_by_email
    from app.core.dependencies import _principal_for
    from app.persistencia.repositorios import RepositorioDeAtletas

    jefe = await _principal_for(db, await get_by_email(db, world.owner_email))
    repo = RepositorioDeAtletas(db, jefe)
    cuenta = (await repo.fila_de(world.sofia_swimmer_id)).user_id
    assert cuenta is not None

    atleta = await repo.por_id(world.sofia_swimmer_id)
    atleta.usuario_id = None
    fila = await repo.guardar(atleta)
    assert fila.user_id == cuenta


async def test_un_atleta_no_escribe_fichas(client, world: World):
    """`require_coach` va antes que la entidad: el atleta no llega ni a la suya."""
    sofia = como(world.sofia_email)
    for metodo, url in (
        ("put", f"{API}/swimmers/{world.sofia_swimmer_id}"),
        ("delete", f"{API}/swimmers/{world.carlos_swimmer_id}"),
        ("post", f"{API}/swimmers/{world.carlos_swimmer_id}/reactivate"),
    ):
        kwargs = {"json": {"notes": "x"}} if metodo == "put" else {}
        r = await getattr(client, metodo)(url, headers=sofia, **kwargs)
        assert r.status_code == 403, (metodo, url)


async def test_una_ficha_de_otro_equipo_es_404_y_no_se_toca(client, db, world: World):
    """Una ficha que EXISTE en otro club, no un id inventado: así lo que se
    prueba es el filtro por equipo de `por_id`/`guardar`, no que el id no esté."""
    from app.persistencia.repositorios import RepositorioDeEquipos

    otro = await RepositorioDeEquipos(db).crear("Club Rival")
    ajena = Swimmer(team_id=otro.id, name="Nadadora Ajena", notes="original")
    db.add(ajena)
    await db.commit()

    jefe = como(world.owner_email)
    url = f"{API}/swimmers/{ajena.id}"
    for metodo, destino, kwargs in (
        ("put", url, {"json": {"notes": "pisada"}}),
        ("delete", url, {}),
        ("post", f"{url}/reactivate", {}),
    ):
        r = await getattr(client, metodo)(destino, headers=jefe, **kwargs)
        assert r.status_code == 404, (metodo, destino)
        # Después de CADA intento: si no, un /reactivate filtrado taparía la
        # baja que un DELETE filtrado hubiera escrito.
        await db.refresh(ajena)
        assert (ajena.notes, ajena.is_active) == ("original", True), metodo
