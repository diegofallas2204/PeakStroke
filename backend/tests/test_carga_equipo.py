"""La carga en la tabla del equipo (TODO-19, 2026-10-01).

Cada fila de `/dashboard/team-week` trae el estado de carga de su atleta **al
cierre de la semana que se mira**, sin pasar de hoy: la semana 3 enseña cómo
estaba el atleta entonces, y una semana futura no enseña nada. El número tiene
que ser el mismo que da la curva individual de ese día — dos cálculos de la
misma cosa son la forma normal de que diverjan.
"""
from __future__ import annotations

from datetime import date, timedelta

from conftest import API, World, como
from sqlalchemy import select

from app.persistencia.tablas.planes import Plan


async def _lunes_del_plan(db, world: World) -> date:
    return (await db.execute(select(Plan.start_date).where(Plan.id == world.plan_id))).scalar_one()


async def _apuntar(client, world: World, dia: date) -> None:
    r = await client.post(f"{API}/sessions/", json={
        "swimmer_id": world.sofia_swimmer_id, "session_date": dia.isoformat(),
        "distance_m": 4000, "duration_s": 4800,
    }, headers=como(world.owner_email))
    assert r.status_code == 201


async def _filas(client, world: World, semana: int) -> dict[int, dict]:
    r = await client.get(
        f"{API}/dashboard/team-week?plan_id={world.plan_id}&week={semana}",
        headers=como(world.owner_email))
    assert r.status_code == 200
    return {f["swimmer_id"]: f for f in r.json()["rows"]}


async def test_cada_fila_trae_la_carga_al_cierre_de_su_semana(client, db, world: World):
    lunes = await _lunes_del_plan(db, world)
    await _apuntar(client, world, lunes + timedelta(days=1))

    filas = await _filas(client, world, 1)
    domingo = lunes + timedelta(days=6)
    carga = filas[world.sofia_swimmer_id]["load"]
    assert carga["date"] == str(domingo)
    assert carga["warming_up"] is True   # una semana de historia: aún sin alertas

    # El mismo número que la curva individual de ese día.
    r = await client.get(
        f"{API}/training-load/{world.sofia_swimmer_id}?desde={domingo}&hasta={domingo}",
        headers=como(world.owner_email))
    [dia] = r.json()["days"]
    assert (carga["ctl"], carga["atl"], carga["tsb"]) == (dia["ctl"], dia["atl"], dia["tsb"])
    assert carga["alert"] == dia["alert"] and carga["reasons"] == dia["reasons"]

    # Sin sesiones no hay curva: la fila dice que no hay dato, no un cero.
    assert filas[world.carlos_swimmer_id]["load"] is None
    assert filas[world.sin_cuenta_swimmer_id]["load"] is None


async def test_la_semana_en_curso_se_corta_en_hoy(client, db, world: World):
    lunes = await _lunes_del_plan(db, world)
    await _apuntar(client, world, lunes + timedelta(days=1))
    semana_actual = (date.today() - lunes).days // 7 + 1

    carga = (await _filas(client, world, semana_actual))[world.sofia_swimmer_id]["load"]
    assert carga["date"] == str(date.today())


async def test_una_semana_futura_no_trae_carga(client, db, world: World):
    lunes = await _lunes_del_plan(db, world)
    await _apuntar(client, world, lunes + timedelta(days=1))
    semana_actual = (date.today() - lunes).days // 7 + 1

    filas = await _filas(client, world, semana_actual + 2)
    assert all(f["load"] is None for f in filas.values())


async def test_antes_de_la_primera_sesion_no_hay_carga(client, db, world: World):
    """La serie empieza con la primera sesión: la semana anterior no la tiene."""
    lunes = await _lunes_del_plan(db, world)
    await _apuntar(client, world, lunes + timedelta(days=8))   # semana 2

    assert (await _filas(client, world, 1))[world.sofia_swimmer_id]["load"] is None
    assert (await _filas(client, world, 2))[world.sofia_swimmer_id]["load"] is not None


async def test_la_curva_del_repositorio_esta_acotada(client, db, world: World):
    """La tabla lee la carga por `RepositorioDeCarga.curva`, no por el router de
    `/training-load` (que comprueba al atleta antes). Así que el repositorio
    tiene que acotar por sí mismo: un atleta no saca la curva de otro aunque
    alguien llame a `curva` con su id.
    """
    from app.api.v1.auth.service import get_by_email
    from app.core.dependencies import _principal_for
    from app.persistencia.repositorios import RepositorioDeCarga

    lunes = await _lunes_del_plan(db, world)
    await _apuntar(client, world, lunes + timedelta(days=1))   # carga de Sofía

    async def curva_como(email: str):
        principal = await _principal_for(db, await get_by_email(db, email))
        return await RepositorioDeCarga(db, principal).curva(
            world.sofia_swimmer_id, lunes, lunes + timedelta(days=6))

    assert await curva_como(world.owner_email) is not None
    assert await curva_como(world.sofia_email) is not None
    assert await curva_como(world.carlos_email) is None


async def test_el_aviso_de_la_tabla_es_el_de_la_curva_que_ve_el_usuario(client, db, world: World):
    """Pasado el calentamiento y con un aviso de verdad: dos semanas tranquilas y
    una tercera de carga alta (S3, lunes a domingo). El estado de la fila de S3
    tiene que ser el día de su domingo en la curva que enseña Entrenamiento —el
    rango por defecto de 90 días—, aviso y motivos incluidos. Comparar contra
    `desde=hasta` sería comparar el cálculo consigo mismo.
    """
    lunes = await _lunes_del_plan(db, world)

    async def apuntar(dia: date, metros: int, segundos: int) -> None:
        r = await client.post(f"{API}/sessions/", json={
            "swimmer_id": world.sofia_swimmer_id, "session_date": dia.isoformat(),
            "distance_m": metros, "duration_s": segundos,
        }, headers=como(world.owner_email))
        assert r.status_code == 201

    for n in range(14):
        await apuntar(lunes + timedelta(days=n), 4000, 4800)       # ~32 sTSS
    for n in range(14, 21):
        await apuntar(lunes + timedelta(days=n), 9000, 6000)       # ~237 sTSS

    domingo = lunes + timedelta(days=20)
    r = await client.get(f"{API}/training-load/{world.sofia_swimmer_id}",
                         headers=como(world.owner_email))
    [dia] = [d for d in r.json()["days"] if d["date"] == str(domingo)]
    assert dia["alert"] is not None, "el escenario no dispara aviso: el test no probaría nada"

    carga = (await _filas(client, world, 3))[world.sofia_swimmer_id]["load"]
    assert carga["warming_up"] is False
    assert (carga["ctl"], carga["atl"], carga["tsb"]) == (dia["ctl"], dia["atl"], dia["tsb"])
    assert (carga["alert"], carga["reasons"]) == (dia["alert"], dia["reasons"])
