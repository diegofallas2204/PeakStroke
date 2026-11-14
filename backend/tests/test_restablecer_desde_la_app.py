"""Un entrenador restablece la contraseña de un atleta desde la app (2026-11-13).

Era la opción recomendada para «olvidé mi contraseña» (`docs/MODULOS.md`,
`modulo/atletas`): hasta ahora solo podía hacerlo quien opera el servidor, con
`tools/ops.py restablecer-password`, y la pantalla de login decía «pídeselo a
tu entrenador». Lo que fija este archivo:

- el entrenador (dueño o no) recibe **una vez** una temporal; la vieja deja de
  entrar, todas las sesiones del atleta se cortan y la cuenta queda obligada a
  cambiarla (TODO-27);
- **solo sobre atletas**: restablecer la de otro entrenador sería quedarse con
  su cuenta. Un atleta no puede usarlo;
- una cuenta de otro club, o que no existe, es 404 (nunca 403);
- se audita como `cuenta.password_restablecida`, con el entrenador de actor y
  sin la contraseña.
"""
from __future__ import annotations

from conftest import API, PASSWORD, World, como
from sqlalchemy import select

from app.core.auditoria import TipoDeEvento
from app.persistencia.tablas.auditoria import EventoDeAuditoria
from app.persistencia.tablas.usuarios import User


async def _cuenta(db, correo: str) -> User:
    db.expire_all()
    return (await db.execute(select(User).where(User.email == correo))).scalar_one()


def _ruta(user_id: int) -> str:
    return f"{API}/auth/members/{user_id}/reset-password"


async def test_el_entrenador_restablece_la_de_un_atleta(client, db, world: World):
    sofia = await _cuenta(db, world.sofia_email)
    sofia_id, generacion = sofia.id, sofia.token_version

    r = await client.post(_ruta(sofia_id), headers=como(world.assistant_email))
    assert r.status_code == 200, r.text
    temporal = r.json()["temporary_password"]
    assert len(temporal) >= 12

    sofia = await _cuenta(db, world.sofia_email)
    assert sofia.password_temporal is True
    assert sofia.token_version == generacion + 1, "se cortan todas sus sesiones"

    vieja = await client.post(f"{API}/auth/login", json={"email": world.sofia_email, "password": PASSWORD})
    nueva = await client.post(f"{API}/auth/login", json={"email": world.sofia_email, "password": temporal})
    assert (vieja.status_code, nueva.status_code) == (401, 200)
    assert nueva.json()["user"]["must_change_password"] is True

    db.expire_all()
    [evento] = (await db.execute(select(EventoDeAuditoria).where(
        EventoDeAuditoria.event_type == str(TipoDeEvento.PASSWORD_RESTABLECIDA),
    ))).scalars().all()
    assert evento.actor_email == world.assistant_email
    assert (evento.target_type, evento.target_id) == ("user", sofia_id)
    assert temporal not in evento.detail


async def test_no_se_restablece_la_de_otro_entrenador(client, db, world: World):
    asistente = await _cuenta(db, world.assistant_email)
    r = await client.post(_ruta(asistente.id), headers=como(world.owner_email))
    assert r.status_code == 403
    assert (await _cuenta(db, world.assistant_email)).password_temporal is False


async def test_un_atleta_no_puede(client, db, world: World):
    carlos = await _cuenta(db, world.carlos_email)
    r = await client.post(_ruta(carlos.id), headers=como(world.sofia_email))
    assert r.status_code == 403


async def test_una_cuenta_de_otro_club_o_inexistente_es_404(client, db, world: World):
    from app.api.v1.auth.schemas import UserCreate
    from app.persistencia.repositorios import RepositorioDeUsuarios

    ajena = await RepositorioDeUsuarios(db).crear(
        correo="ajena@test.dev", nombre="Sin Club", password_hash="x",
    )
    await db.commit()
    assert UserCreate  # el alta normal pide club; aquí basta una cuenta suelta
    for user_id in (ajena.id, 999_999):
        r = await client.post(_ruta(user_id), headers=como(world.owner_email))
        assert r.status_code == 404, user_id
