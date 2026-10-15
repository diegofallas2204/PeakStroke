"""Lo que el /cso de D1 encontró en el CLI (2026-10-14), fijado con un test cada uno.

1. **Un evento que no se guarda no puede pasar en silencio.** La auditoría de
   una petición web no tumba nada si falla al escribir (D0): la respuesta ya
   salió y el log se queda con lo perdido. En el CLI eso dejaba una revocación
   o una contraseña restablecida **sin rastro y con salida 0**. Ahora sale con 3
   y lo dice: la operación ya se hizo, pero hay que mirar el log.
2. **Un atleta que fue entrenador deja historia**: quién llevaba a quién, códigos
   que emitió. Borrar su pertenencia viola la FK compuesta; antes salía la traza
   de un `IntegrityError` y ahora un rechazo que se entiende, sin tocar nada.
3. **Bajo `sudo` el actor era `root`**: se apunta también quién lo invocó.
"""
from __future__ import annotations

import io

from conftest import API, World, como
from sqlalchemy import select

from app.core import auditoria
from app.persistencia.repositorios import RepositorioDeEquipos
from app.persistencia.tablas.atletas import Swimmer
from app.persistencia.tablas.equipos import TeamMember
from app.persistencia.tablas.usuarios import User
from tools.operaciones import Consola, comun, ejecutar


async def _ops(db, *argv: str, entrada: str = "") -> tuple[int, Consola]:
    consola = Consola(entrada=io.StringIO(entrada), salida=io.StringIO(),
                      errores=io.StringIO(), terminal=False)
    return await ejecutar(argv, consola, db), consola


async def test_si_la_auditoria_no_se_guarda_sale_con_3_y_lo_dice(db, world: World, monkeypatch):
    def rota(*_args, **_kw):
        raise RuntimeError("disco lleno")

    monkeypatch.setattr(auditoria, "_fila", rota)
    codigo, consola = await _ops(db, "revocar", "--correo", world.carlos_email,
                                 entrada=world.carlos_email + "\n")
    assert codigo == 3
    assert "no se guard" in consola.errores.getvalue()
    db.expire_all()
    activa = (await db.execute(
        select(TeamMember.is_active).join(User, User.id == TeamMember.user_id)
        .where(User.email == world.carlos_email),
    )).scalar_one()
    assert activa is False                       # la operación sí se hizo


async def test_un_atleta_con_historia_de_entrenador_no_se_libera(client, db, world: World):
    jefe = como(world.owner_email)
    sofia_id = (await db.execute(
        select(User.id).where(User.email == world.sofia_email),
    )).scalar_one()
    # Fue entrenadora y llevó a Carlos; después volvió a atleta y la revocaron.
    assert (await client.patch(f"{API}/auth/members/{sofia_id}", json={"role": "coach"},
                               headers=jefe)).status_code == 200
    await RepositorioDeEquipos(db).fijar_atletas_de(
        world.team_id, sofia_id, [world.carlos_swimmer_id],
    )
    assert (await client.patch(f"{API}/auth/members/{sofia_id}",
                               json={"role": "athlete", "is_active": False},
                               headers=jefe)).status_code == 200

    codigo, consola = await _ops(db, "liberar", "--correo", world.sofia_email,
                                 entrada=world.sofia_email + "\n")
    assert codigo == 1 and "historia" in consola.errores.getvalue()
    assert "Traceback" not in consola.errores.getvalue()
    db.expire_all()
    miembro = (await db.execute(
        select(TeamMember).where(TeamMember.user_id == sofia_id),
    )).scalar_one()
    assert miembro.is_active is False
    ficha = (await db.execute(
        select(Swimmer.user_id).where(Swimmer.id == world.sofia_swimmer_id),
    )).scalar_one()
    assert ficha == sofia_id                     # nada se desligó
    eventos = (await db.execute(
        select(auditoria.EventoDeAuditoria.event_type)
        .where(auditoria.EventoDeAuditoria.event_type == "miembro.liberado"),
    )).all()
    assert eventos == []


def test_bajo_sudo_el_actor_dice_quien_lo_invoco(monkeypatch):
    monkeypatch.setattr(comun, "_usuario_del_so", lambda: "root")
    monkeypatch.setenv("SUDO_USER", "diego")
    assert comun.actor().startswith("os:root(sudo:diego)@")
    monkeypatch.delenv("SUDO_USER")
    assert comun.actor().startswith("os:root@")
    monkeypatch.setattr(comun, "_usuario_del_so", lambda: "diego")
    monkeypatch.setenv("SUDO_USER", "diego")
    assert comun.actor().startswith("os:diego@")  # sin sudo de verdad, no se repite
