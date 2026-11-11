"""C9 (REDISENO §5.1): las sesiones de una cuenta son comportamiento de `Usuario`.

Hasta el 2026-10-14 los dos contadores se subían a mano en tres sitios —
`auth/sessions.py` (`user.refresh_rotation += 1`), el repositorio
(`token_version += 1`) y el router de la contraseña, que la cambiaba y
revocaba en dos pasos y dos `commit`—. Lo que fija este archivo:

- cada contador sube por su método y solo por él (la rotación del refresh ya no
  es de la cuenta sino de cada `SesionAbierta`, TODO-30: `test_sesion_abierta.py`);
- cambiar la contraseña revoca, sin forma de hacer una cosa sin la otra;
- renovar el hash al entrar **no** revoca (la contraseña es la misma);
- fuera de la entidad y su mapeo, nadie asigna esos campos (test por AST).

El comportamiento de cara al API —el replay del refresh, el logout, el cambio
de contraseña— lo fijan `test_session_revocation.py` y, desde TODO-30,
`test_sesiones_por_dispositivo.py`.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import API, PASSWORD, World
from escrituras_ast import escrituras
from sqlalchemy import select

from app.core.config import settings
from app.core.security import verify_password
from app.dominio.entidades import Usuario
from app.persistencia.repositorios import RepositorioDeUsuarios
from app.persistencia.tablas.usuarios import User


def _usuario(**cambios) -> Usuario:
    base = {"correo": "a@b.dev", "nombre": "Ana", "hash_de_password": "h0", "id": 7}
    return Usuario(**(base | cambios))


# ── El dominio ───────────────────────────────────────────────────────────────


def test_revocar_sube_la_generacion():
    u = _usuario(version_de_token=3)
    u.revocar_sesiones()
    assert u.version_de_token == 4
    assert not u.acepta_generacion(3) and u.acepta_generacion(4)


def test_abrir_una_sesion_no_toca_la_generacion():
    """Antes `rotar_refresh` (TODO-30): abrir o rotar una sesión no echa a las demás."""
    u = _usuario(version_de_token=3)
    sesion = u.abrir_sesion(datetime(2026, 10, 20, tzinfo=UTC), timedelta(days=30))
    assert (sesion.usuario_id, sesion.rotacion, u.version_de_token) == (7, 0, 3)


def test_cambiar_la_password_cambia_el_hash_y_revoca_a_la_vez():
    u = _usuario(version_de_token=3)
    u.cambiar_password("h1")
    assert (u.hash_de_password, u.version_de_token) == ("h1", 4)


def test_un_hash_vacio_no_entra_y_no_revoca_nada():
    u = _usuario(version_de_token=3)
    with pytest.raises(ValueError):
        u.cambiar_password("")
    assert (u.hash_de_password, u.version_de_token) == ("h0", 3)


def test_entrar_sella_el_acceso_y_renovar_el_hash_no_revoca():
    u = _usuario(version_de_token=3)
    cuando = datetime(2026, 10, 14, 9, 30, tzinfo=UTC)
    u.registrar_login(cuando)
    assert (u.ultimo_login, u.hash_de_password, u.version_de_token) == (cuando, "h0", 3)
    u.registrar_login(cuando, nuevo_hash="h2")
    assert (u.hash_de_password, u.version_de_token) == ("h2", 3)


def test_dos_cuentas_con_los_mismos_datos_son_dos_si_tienen_otro_id():
    assert _usuario(id=1) != _usuario(id=2)
    assert _usuario(id=1) == _usuario(id=1, nombre="Otro nombre")



@pytest.mark.parametrize("campo", [
    "hash_de_password", "version_de_token", "ultimo_login",
])
def test_los_contadores_y_el_hash_no_se_asignan_a_mano(campo):
    u = _usuario()
    with pytest.raises(AttributeError, match="solo cambia por sus métodos"):
        setattr(u, campo, 99)


# ── El repositorio ───────────────────────────────────────────────────────────


async def test_guardar_escribe_los_contadores_el_hash_y_el_acceso(db, world: World):
    repo = RepositorioDeUsuarios(db)
    fila = await repo.por_correo(world.sofia_email)
    antes = fila.token_version
    fila_id, nombre = fila.id, fila.name
    u = repo.entidad(fila)
    u.cambiar_password("hash-nuevo")
    u.registrar_login(datetime(2026, 10, 14, tzinfo=UTC))
    # Lo que la entidad no gobierna no se escribe aunque venga cambiado.
    u.correo, u.nombre, u.activo = "otro@x.dev", "Otro", False
    await repo.guardar(u)

    db.expire_all()
    leida = (await db.execute(select(
        User.token_version, User.password_hash, User.email, User.name, User.is_active,
    ).where(User.id == fila_id))).one()
    assert tuple(leida) == (antes + 1, "hash-nuevo", world.sofia_email, nombre, True)


async def test_guardar_una_cuenta_que_no_existe_no_crea_nada(db):
    with pytest.raises(LookupError):
        await RepositorioDeUsuarios(db).guardar(_usuario(id=999_999))


# ── El API ───────────────────────────────────────────────────────────────────


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True, raising=False)
    monkeypatch.setattr(settings, "jwt_secret", "secreto-de-prueba-" + "x" * 48, raising=False)


async def test_cambiar_la_password_revoca_una_vez_y_abre_una_sesion(
    client, db, world: World, auth_on,
):
    """Una generación nueva por el cambio, y de las sesiones de la cuenta queda
    solo la que devuelve (TODO-30: subir la generación borra las demás)."""
    from app.core.security import decode_token
    from app.persistencia.tablas.usuarios import OpenSession

    r = await client.post(f"{API}/auth/login", json={"email": world.sofia_email, "password": PASSWORD})
    token = r.json()["access_token"]
    consulta = select(User.id, User.token_version).where(User.email == world.sofia_email)
    user_id, version = (await db.execute(consulta)).one()

    r = await client.post(
        f"{API}/auth/me/password", headers={"Authorization": f"Bearer {token}"},
        json={"current_password": PASSWORD, "new_password": "otra-clave-larga-1"},
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    v2, hash_nuevo = (await db.execute(
        select(User.token_version, User.password_hash).where(User.id == user_id),
    )).one()
    assert v2 == version + 1
    assert verify_password("otra-clave-larga-1", hash_nuevo)
    sids = (await db.execute(select(OpenSession.id).where(OpenSession.user_id == user_id))).scalars()
    assert list(sids) == [decode_token(r.cookies[settings.refresh_cookie_name], "refresh").sid]
    # El access de antes murió; el que vino en la respuesta vale.
    assert (await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401
    nuevo = r.json()["access_token"]
    assert (await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {nuevo}"})).status_code == 200


# ── Nadie más escribe esos campos ────────────────────────────────────────────



def test_fuera_del_mapeo_nadie_asigna_los_contadores_ni_el_hash():
    """`user.token_version += 1` en un router es justo lo que este bloque quita.

    Crear la fila con `User(password_hash=...)` es un argumento, no una
    asignación, y sigue siendo del repositorio (`crear`).
    """
    assert escrituras(
        {"token_version", "refresh_rotation", "expires_at", "password_hash",
         "password_temporal"},
        {"app/persistencia/mapeo/identidad.py"},
    ) == []


@pytest.mark.parametrize("fuente", [
    "u.token_version = 1",
    "u.token_version += 1",
    "u.token_version: int = 1",
    "u.token_version, u.otro = 1, 2",
    "for u.token_version in range(3): pass",
    "setattr(u, 'token_version', 3)",
    "u.__dict__['token_version'] = 3",
    "update(User).values(token_version=User.token_version + 1)",
    "t.update().values({'token_version': 1})",
])
def test_el_detector_ve_todas_las_formas_de_escribir(fuente):
    """Las cinco que el revisor del bloque encontró sin cubrir, y las de antes."""
    from escrituras_ast import escrituras_en
    assert escrituras_en(fuente, {"token_version"}) != []
    assert escrituras_en("x = u.token_version + 1\nf(token_version=1)", {"token_version"}) == []
