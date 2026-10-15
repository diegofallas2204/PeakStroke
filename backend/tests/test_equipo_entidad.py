"""C9 (REDISENO §5.2): el club y la pertenencia son entidades.

Hasta el 2026-10-14 quién puede ser dueño lo decidía `api/v1/equipos/service.py`
con `if` sobre filas, la protección del dueño vivía en `auth/members.py`, la
fábrica del rol en `core/principal.rol_de` y revocar era un `membership.is_active
= …` en `auth/service.update_member`. Lo que fija este archivo:

- `Equipo.transferir_propiedad` y sus tres comprobaciones, con los mensajes de
  siempre (son el 400 que ve el entrenador);
- al dueño no se le revoca ni se le baja a atleta;
- `Pertenencia.revocar()/restaurar()` idempotentes, y **revocada ≠ sin club**;
- la fábrica del rol es la de antes, ahora en el dominio;
- un `null` explícito en `PATCH /auth/members/{id}` ya no da 500 (medido en HEAD);
- fuera del mapeo nadie asigna `owner_id` ni `role` (test por AST).
"""
from __future__ import annotations

import pytest
from conftest import API, World, como
from escrituras_ast import escrituras
from sqlalchemy import select

from app.core.principal import rol_de
from app.dominio.entidades import Equipo, OperacionDeEquipoImposible, Pertenencia, rol_para
from app.dominio.entidades.equipo import ROLES_DE_PERTENENCIA
from app.dominio.roles import AtletaRol, Entrenador, EntrenadorEnJefe
from app.persistencia.repositorios import RepositorioDeEquipos
from app.persistencia.tablas.equipos import ROLES, Team, TeamMember
from app.persistencia.tablas.usuarios import User


async def _id(db, correo: str) -> int:
    return (await db.execute(select(User.id).where(User.email == correo))).scalar_one()


def _p(usuario_id: int = 2, equipo_id: int = 1, rol: str = "coach", activa: bool = True) -> Pertenencia:
    return Pertenencia(usuario_id=usuario_id, equipo_id=equipo_id, rol=rol, activa=activa, id=usuario_id)


def _club(dueno: int | None = 1) -> Equipo:
    return Equipo(nombre="Club", id=1, dueno_id=dueno)


# ── El dominio ───────────────────────────────────────────────────────────────


def test_las_claves_del_dominio_son_las_de_la_tabla():
    assert ROLES_DE_PERTENENCIA == ROLES


@pytest.mark.parametrize(("clave", "dueno", "esperado"), [
    ("coach", True, EntrenadorEnJefe), ("coach", False, Entrenador),
    ("athlete", False, AtletaRol), ("athlete", True, AtletaRol),
])
def test_la_fabrica_del_rol_es_la_de_principal(clave, dueno, esperado):
    assert type(rol_para(clave, es_dueno=dueno)) is esperado
    assert type(rol_de(clave, es_dueno=dueno)) is esperado
    assert type(_p(rol=clave).rol_de_dominio(dueno)) is esperado


def test_una_clave_desconocida_falla_cerrado():
    with pytest.raises(ValueError):
        rol_para("developer", es_dueno=True)
    with pytest.raises(ValueError):
        Pertenencia(usuario_id=1, equipo_id=1, rol="admin")
    p = _p()
    with pytest.raises(ValueError):
        p.cambiar_rol("admin")
    assert p.rol == "coach"


def test_revocar_y_restaurar_son_idempotentes_y_dicen_si_cambiaron():
    p = _p()
    assert p.revocar() is True and p.activa is False
    assert p.revocar() is False and p.activa is False
    # Revocada sigue siendo DE ESTE CLUB: no es una cuenta del pool.
    assert p.equipo_id == 1
    assert p.restaurar() is True and p.activa is True
    assert p.restaurar() is False


def test_es_jefe_solo_el_dueno():
    assert _club(dueno=1).es_jefe(1) and not _club(dueno=1).es_jefe(2)
    assert not _club(dueno=None).es_jefe(1)


@pytest.mark.parametrize(("nuevo", "mensaje"), [
    (None, "no pertenece a este equipo"),
    (_p(equipo_id=2), "no pertenece a este equipo"),
    (_p(rol="athlete"), "Solo un entrenador"),
    (_p(activa=False), "acceso revocado"),
    (_p(rol="athlete", activa=False), "Solo un entrenador"),          # el orden de siempre
    (_p(equipo_id=2, rol="athlete", activa=False), "no pertenece"),
])
def test_transferir_exige_entrenador_del_club_y_activo(nuevo, mensaje):
    club = _club()
    with pytest.raises(OperacionDeEquipoImposible, match=mensaje):
        club.transferir_propiedad(nuevo)
    assert club.dueno_id == 1                                         # nada cambió


def test_transferir_cambia_el_dueno_y_sirve_para_el_primero():
    club = _club()
    club.transferir_propiedad(_p(usuario_id=4))
    assert club.dueno_id == 4 and club.es_jefe(4) and not club.es_jefe(1)
    nuevo = _club(dueno=None)
    nuevo.transferir_propiedad(_p(usuario_id=7))
    assert nuevo.dueno_id == 7


@pytest.mark.parametrize(("revocar", "a_atleta"), [(True, False), (False, True), (True, True)])
def test_al_dueno_no_se_le_quita_el_acceso_ni_el_rol(revocar, a_atleta):
    with pytest.raises(OperacionDeEquipoImposible, match="Transfiere la propiedad primero"):
        _club(dueno=2).admite_cambio(_p(usuario_id=2), revocar=revocar, a_atleta=a_atleta)


def test_a_los_demas_si_y_al_dueno_lo_que_no_le_quita_nada():
    _club(dueno=1).admite_cambio(_p(usuario_id=2), revocar=True, a_atleta=True)
    _club(dueno=2).admite_cambio(_p(usuario_id=2), revocar=False, a_atleta=False)



@pytest.mark.parametrize(("entidad", "campo", "valor"), [
    (lambda: _club(), "dueno_id", 5),
    (lambda: _p(), "rol", "athlete"),
    (lambda: _p(), "activa", False),
    (lambda: _p(), "equipo_id", 2),
    (lambda: _p(), "usuario_id", 3),
])
def test_lo_gobernado_no_se_asigna_a_mano(entidad, campo, valor):
    """Lo vio el revisor: `club.dueno_id = 5` y `guardar_equipo` saltaban las
    tres comprobaciones de `transferir_propiedad`."""
    e = entidad()
    antes = getattr(e, campo)
    with pytest.raises(AttributeError, match="solo cambia por sus métodos"):
        setattr(e, campo, valor)
    assert getattr(e, campo) == antes


# ── El repositorio ───────────────────────────────────────────────────────────


async def test_guardar_escribe_el_dueno_el_nombre_el_rol_y_el_acceso(db, world: World):
    repo = RepositorioDeEquipos(db)
    asistente_id, sofia_id = await _id(db, world.assistant_email), await _id(db, world.sofia_email)
    club = repo.como_equipo(await repo.equipo(world.team_id))
    asistente = await repo.pertenencia(asistente_id)
    club.renombrar("Renombrado")
    club.transferir_propiedad(repo.como_pertenencia(asistente))
    club.activo = False                       # no lo gobierna la entidad: no se escribe
    await repo.guardar_equipo(club)

    p = repo.como_pertenencia(await repo.pertenencia(sofia_id))
    p.revocar()
    with pytest.raises(AttributeError):     # una pertenencia no se muda de club
        p.equipo_id = 999
    await repo.guardar_pertenencia(p)

    db.expire_all()
    assert tuple((await db.execute(select(Team.name, Team.owner_id, Team.is_active)
                                   .where(Team.id == world.team_id))).one()) == (
        "Renombrado", asistente_id, True,
    )
    assert tuple((await db.execute(select(TeamMember.team_id, TeamMember.is_active)
                                   .where(TeamMember.user_id == sofia_id))).one()) == (
        world.team_id, False,
    )


async def test_guardar_lo_que_no_existe_no_crea_nada(db):
    repo = RepositorioDeEquipos(db)
    with pytest.raises(LookupError):
        await repo.guardar_equipo(Equipo(nombre="x", id=999_999))
    with pytest.raises(LookupError):
        await repo.guardar_pertenencia(Pertenencia(usuario_id=1, equipo_id=1, rol="coach", id=999_999))


# ── El API ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("cuerpo", [
    {"name": None}, {"role": None}, {"is_active": None},
    {"name": None, "role": None, "is_active": None},
])
async def test_un_null_en_un_miembro_no_cambia_nada(client, db, world: World, cuerpo):
    """Medido en a9c2317: `{"name": null}` daba 500 (NOT NULL en `users.name`)."""
    jefe = como(world.owner_email)
    sofia_id = await _id(db, world.sofia_email)
    antes = {m["id"]: m for m in (await client.get(f"{API}/auth/members", headers=jefe)).json()}
    r = await client.patch(f"{API}/auth/members/{sofia_id}", json=cuerpo, headers=jefe)
    assert r.status_code == 200, r.text
    assert r.json() == antes[sofia_id]


async def test_revocar_y_restaurar_un_miembro_por_el_api(client, db, world: World):
    jefe = como(world.owner_email)
    url = f"{API}/auth/members/{await _id(db, world.sofia_email)}"
    for activa in (False, False, True, True):
        r = await client.patch(url, json={"is_active": activa}, headers=jefe)
        assert r.status_code == 200 and r.json()["is_active"] is activa


async def test_al_dueno_no_se_le_revoca_por_el_api(client, db, world: World):
    jefe = como(world.owner_email)
    dueno_id = await _id(db, world.owner_email)
    for cuerpo in ({"is_active": False}, {"role": "athlete"}):
        r = await client.patch(f"{API}/auth/members/{dueno_id}", json=cuerpo, headers=jefe)
        assert r.status_code == 400 and "Transfiere la propiedad" in r.json()["detail"]


# ── Nadie más escribe el dueño ni el rol ─────────────────────────────────────



def test_fuera_del_mapeo_nadie_asigna_el_dueno_ni_el_rol():
    """`team.owner_id = …` en el seed o en un service es justo lo que se quita.

    Crear la fila con `TeamMember(role=...)` es un argumento, no una asignación.
    """
    assert escrituras(
        {"owner_id", "role"},
        {"app/persistencia/mapeo/identidad.py"},
    ) == []


async def test_transferir_responde_que_ya_no_eres_el_dueno(client, db, world: World):
    """Visto por el revisor de C9 (viene de HEAD): la respuesta decía `is_owner:
    True` a quien acababa de ceder la propiedad, porque salía del `Principal`
    tomado antes de escribir. El GET siguiente ya decía `False`."""
    jefe = como(world.owner_email)
    asistente = await _id(db, world.assistant_email)
    r = await client.post(f"{API}/teams/mine/transfer", json={"new_owner_id": asistente}, headers=jefe)
    assert r.status_code == 200, r.text
    assert (r.json()["owner_id"], r.json()["is_owner"]) == (asistente, False)
    assert (await client.get(f"{API}/teams/mine", headers=jefe)).json() == r.json()
