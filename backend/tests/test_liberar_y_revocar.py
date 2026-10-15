"""D1 (TODO-26, decidido el 2026-10-14): liberar es echar del todo, y revocar corta.

Las dos decisiones de la persona al empezar D1:

- **Revocar una pertenencia corta las sesiones** de esa cuenta, en el mismo
  commit. Hasta hoy el access token emitido antes valía 15 minutos más.
  Restaurar no corta nada, y revocar a quien ya estaba revocado tampoco.
- **«Liberar» es una operación nueva**, distinta de revocar (lectura 2 de
  TODO-26). Revocado sigue siendo «echado, y de este club»; liberar deja la
  cuenta en el pool **a propósito**: borra la fila de `team_members` (la
  excepción documentada a «nada se borra»: `UNIQUE(user_id)` no deja otra
  salida sin migración), desliga la ficha del club —que se queda allí con su
  histórico— y corta las sesiones. Solo sobre la pertenencia **revocada** de
  un **atleta**: un entrenador deja filas que lo referencian por FK compuesta
  (`link_codes.created_by`, `coach_athletes`, `plan_coaches`).
"""
from __future__ import annotations

import pytest
from conftest import API, PASSWORD, World, como
from sqlalchemy import select

from app.core.config import settings
from app.dominio.entidades import Equipo, OperacionDeEquipoImposible, Pertenencia
from app.persistencia.repositorios import RepositorioDeEquipos, RepositorioDeUsuarios
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.equipos import TeamMember
from app.persistencia.tablas.usuarios import User


def _p(rol: str = "athlete", activa: bool = False, equipo_id: int = 1, usuario_id: int = 5):
    return Pertenencia(usuario_id=usuario_id, equipo_id=equipo_id, rol=rol, activa=activa, id=9)


def _club(dueno: int | None = 1) -> Equipo:
    return Equipo(nombre="Club", id=1, dueno_id=dueno)


async def _usuario(db, correo: str) -> User:
    return (await db.execute(select(User).where(User.email == correo))).scalar_one()


async def _version(db, user_id: int) -> int:
    """Leída de la base, no del objeto: tras `expire_all` el atributo sería una
    carga perezosa, que en async no se puede."""
    return (await db.execute(select(User.token_version).where(User.id == user_id))).scalar_one()


# ── El dominio: qué se puede liberar ─────────────────────────────────────────

@pytest.mark.parametrize(("pertenencia", "mensaje"), [
    (_p(equipo_id=2), "no pertenece a este equipo"),
    (_p(rol="coach"), "Solo se libera a un atleta"),
    (_p(activa=True), "Primero revoca el acceso"),
    (_p(rol="coach", activa=True), "Solo se libera a un atleta"),     # el rol, antes
])
def test_solo_se_libera_la_pertenencia_revocada_de_un_atleta(pertenencia, mensaje):
    with pytest.raises(OperacionDeEquipoImposible, match=mensaje):
        _club().admite_liberar(pertenencia)


def test_la_pertenencia_revocada_de_un_atleta_se_libera():
    _club().admite_liberar(_p())


def test_al_dueno_no_se_le_libera_aunque_la_fila_mienta():
    """Un dueño nunca está revocado ni es atleta (`admite_cambio`), pero si una
    fila corrupta lo dijera, liberar dejaría al club sin dueño: falla cerrado."""
    with pytest.raises(OperacionDeEquipoImposible, match=r"dueñ[oa] del equipo"):
        _club(dueno=5).admite_liberar(_p(usuario_id=5))


# ── El repositorio: borra la fila, desliga la ficha, en el commit de la cuenta ─

async def test_liberar_deja_la_cuenta_sin_club_y_la_ficha_en_el_suyo(db, world: World):
    equipos, usuarios = RepositorioDeEquipos(db), RepositorioDeUsuarios(db)
    carlos = await _usuario(db, world.carlos_email)
    carlos_id, version = carlos.id, carlos.token_version
    fila = await equipos.pertenencia(carlos_id)
    pertenencia = equipos.como_pertenencia(fila)
    pertenencia.revocar()
    await equipos.guardar_pertenencia(pertenencia)

    usuario = usuarios.entidad(carlos)
    usuario.revocar_sesiones()
    await usuarios.anotar(usuario)
    ficha = await equipos.liberar(pertenencia)

    assert ficha == world.carlos_swimmer_id
    db.expire_all()
    assert await equipos.pertenencia(carlos_id, incluir_inactivas=True) is None
    nadador = (await db.execute(
        select(Swimmer.user_id, Swimmer.team_id).where(Swimmer.id == world.carlos_swimmer_id),
    )).one()
    assert nadador.user_id is None and nadador.team_id == world.team_id
    assert await _version(db, carlos_id) == version + 1


async def test_anotar_no_confirma_por_si_solo(db, world: World):
    """`anotar` vuelca en la fila y deja el commit a quien cierre la unidad de
    trabajo: así cortar las sesiones va en el MISMO commit que revocar."""
    usuarios = RepositorioDeUsuarios(db)
    sofia = await _usuario(db, world.sofia_email)
    sofia_id, version = sofia.id, sofia.token_version
    usuario = usuarios.entidad(sofia)
    usuario.revocar_sesiones()
    await usuarios.anotar(usuario)
    await db.rollback()
    assert await _version(db, sofia_id) == version


async def test_liberar_una_pertenencia_activa_no_toca_nada(db, world: World):
    """El repositorio no decide (eso es `admite_liberar`), pero tampoco borra a
    ciegas: una pertenencia activa no se libera ni por error de quien llama."""
    equipos = RepositorioDeEquipos(db)
    sofia = await _usuario(db, world.sofia_email)
    pertenencia = equipos.como_pertenencia(await equipos.pertenencia(sofia.id))
    with pytest.raises(OperacionDeEquipoImposible):
        await equipos.liberar(pertenencia)
    assert await equipos.pertenencia(sofia.id) is not None


# ── El API: revocar corta las sesiones ───────────────────────────────────────

async def test_revocar_por_el_api_sube_la_generacion_una_vez(client, db, world: World):
    jefe = como(world.owner_email)
    sofia = await _usuario(db, world.sofia_email)
    sofia_id, version = sofia.id, sofia.token_version
    url = f"{API}/auth/members/{sofia_id}"

    for activa, esperada in ((False, version + 1), (False, version + 1),
                             (True, version + 1), (False, version + 2)):
        r = await client.patch(url, json={"is_active": activa}, headers=jefe)
        assert r.status_code == 200, r.text
        db.expire_all()
        assert await _version(db, sofia_id) == esperada, activa


async def test_renombrar_o_cambiar_el_rol_no_corta_nada(client, db, world: World):
    jefe = como(world.owner_email)
    sofia = await _usuario(db, world.sofia_email)
    sofia_id, version = sofia.id, sofia.token_version
    for cuerpo in ({"name": "Sofía Renombrada"}, {"role": "athlete"}, {"is_active": True}):
        assert (await client.patch(
            f"{API}/auth/members/{sofia_id}", json=cuerpo, headers=jefe,
        )).status_code == 200
    db.expire_all()
    assert await _version(db, sofia_id) == version


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


async def _token(client, email: str) -> str:
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def test_el_token_del_revocado_muere_en_la_siguiente_peticion(
    client, db, world: World, auth_on,
):
    """Era el hueco de TODO-26: 15 minutos de `/link-codes/redeem` tras revocar."""
    del_atleta = {"Authorization": f"Bearer {await _token(client, world.carlos_email)}"}
    del_jefe = {"Authorization": f"Bearer {await _token(client, world.owner_email)}"}
    assert (await client.get(f"{API}/link-codes/mine", headers=del_atleta)).status_code == 200

    carlos = await _usuario(db, world.carlos_email)
    r = await client.patch(
        f"{API}/auth/members/{carlos.id}", json={"is_active": False}, headers=del_jefe,
    )
    assert r.status_code == 200, r.text

    for ruta in ("/auth/me", "/link-codes/mine"):
        assert (await client.get(f"{API}{ruta}", headers=del_atleta)).status_code == 401
    assert (await client.get(f"{API}/auth/me", headers=del_jefe)).status_code == 200
    miembro = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == carlos.id),
    )).scalar_one()
    assert miembro.is_active is False
