# ruff: noqa: F811 — las fixtures de `carreras` se importan y se piden por nombre
"""TODO-30: una sesión por login, con su propia rotación del refresh.

Con la rotación única por cuenta (`users.refresh_rotation`, de TODO-14 a TODO-30)
entrar en el móvil gastaba la cookie del portátil: su siguiente refresh se trataba
como robo, se cortaban **las dos** y el registro apuntaba un `REFRESH_REUSADO`
falso. No era una carrera: pasaba cada vez que alguien usaba dos dispositivos.

Ahora cada login abre una fila de `sesiones_abiertas` y el token lleva su `sid`:

- el reuso corta **esa** sesión, no la cuenta (decidido el 2026-10-20);
- `logout` cierra la de ese dispositivo, y su access muere en la siguiente
  petición; `logout-all` las cierra todas;
- cambiar la contraseña, revocar y liberar siguen cortando todas (la generación)
  y además borran las filas.

Corren con las fixtures de `carreras.py`: una sesión de base de datos por
petición, SQLite siempre y PostgreSQL si hay `PEAKSTROKE_TEST_POSTGRES_URL`, y
cada caso con una cuenta sin club y otra con club. **No importan nada nuevo
arriba**, para que el archivo colecte contra HEAD: ahí el primer test da 401 en
el refresh del portátil, que es el defecto. Los tokens que no son de ninguna
sesión viva (sin `sid`, de otra cuenta, caducada) están en
`test_sesiones_sin_sesion.py`.
"""
from __future__ import annotations

import pytest
from carreras import (  # noqa: F401  (las fixtures se usan por nombre)
    COOKIE,
    abiertas,
    auth_on,
    bearer,
    cuenta,
    entrar,
    eventos,
    generacion,
    nuevo_cliente,
    sesiones,
)
from conftest import API, PASSWORD

from app.core.auditoria import TipoDeEvento
from app.persistencia.repositorios import RepositorioDeUsuarios


async def _refrescar(nuevo_cliente, cookie: str):
    return await nuevo_cliente(cookie).post(f"{API}/auth/refresh")


async def _filas(sesiones, user_id: int) -> int:
    return len(await abiertas(sesiones, user_id))


# ── Dos dispositivos ─────────────────────────────────────────────────────────

async def test_dos_dispositivos_se_refrescan_los_dos(nuevo_cliente, sesiones, cuenta):
    """**El de TODO-30.** En HEAD el refresh del portátil daba 401 y cortaba los dos."""
    _, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    movil = await entrar(nuevo_cliente(), correo)

    r1 = await _refrescar(nuevo_cliente, portatil.cookies[COOKIE])
    assert r1.status_code == 200, r1.text
    r2 = await _refrescar(nuevo_cliente, movil.cookies[COOKIE])
    assert r2.status_code == 200, r2.text
    assert (await _refrescar(nuevo_cliente, r1.cookies[COOKIE])).status_code == 200
    assert await eventos(correo, TipoDeEvento.REFRESH_REUSADO) == []


async def test_el_reuso_en_un_dispositivo_no_toca_el_otro(nuevo_cliente, sesiones, cuenta):
    """La cookie copiada solo tiene la cadena de ese dispositivo: se corta esa."""
    user_id, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    movil = await entrar(nuevo_cliente(), correo)
    robada = portatil.cookies[COOKIE]
    legitima = await _refrescar(nuevo_cliente, robada)          # el atacante la gasta

    assert (await _refrescar(nuevo_cliente, robada)).status_code == 401
    # Las dos partes de esa sesión quedan fuera: el refresh y el access.
    assert (await _refrescar(nuevo_cliente, legitima.cookies[COOKIE])).status_code == 401
    yo = await nuevo_cliente().get(f"{API}/auth/me", headers=bearer(legitima))
    assert yo.status_code == 401
    # El móvil sigue dentro.
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=bearer(movil))).status_code == 200
    assert (await _refrescar(nuevo_cliente, movil.cookies[COOKIE])).status_code == 200
    assert await _filas(sesiones, user_id) == 1
    assert len(await eventos(correo, TipoDeEvento.REFRESH_REUSADO)) == 1


# ── Salir ────────────────────────────────────────────────────────────────────

async def test_salir_en_un_dispositivo_lo_cierra_en_el_acto_y_deja_el_otro(
    nuevo_cliente, sesiones, cuenta,
):
    user_id, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    movil = await entrar(nuevo_cliente(), correo)

    salir = await nuevo_cliente(portatil.cookies[COOKIE]).post(f"{API}/auth/logout")
    assert salir.status_code == 204
    # Su access muere en la siguiente petición, no en 15 minutos: también en
    # una ruta con `Principal` (401 antes que el 403 de la cuenta sin club).
    for ruta in ("/auth/me", "/teams/mine"):
        r = await nuevo_cliente().get(f"{API}{ruta}", headers=bearer(portatil))
        assert r.status_code == 401, (ruta, r.text)
    assert (await _refrescar(nuevo_cliente, portatil.cookies[COOKIE])).status_code == 401
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=bearer(movil))).status_code == 200
    assert (await _refrescar(nuevo_cliente, movil.cookies[COOKIE])).status_code == 200
    assert await _filas(sesiones, user_id) == 1
    assert await eventos(correo, TipoDeEvento.REFRESH_REUSADO) == []


async def test_salir_con_una_cookie_gastada_cierra_y_avisa(nuevo_cliente, sesiones, cuenta):
    """Una rotación gastada es una copia igual en `/logout` que en `/refresh`
    (decidido el 2026-10-20): la sesión se cierra y salta la alarma."""
    _, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    movil = await entrar(nuevo_cliente(), correo)
    vieja = portatil.cookies[COOKIE]
    nueva = (await _refrescar(nuevo_cliente, vieja)).cookies[COOKIE]

    assert (await nuevo_cliente(vieja).post(f"{API}/auth/logout")).status_code == 204
    assert (await _refrescar(nuevo_cliente, nueva)).status_code == 401
    assert (await _refrescar(nuevo_cliente, movil.cookies[COOKIE])).status_code == 200
    reusos = await eventos(correo, TipoDeEvento.REFRESH_REUSADO)
    assert len(reusos) == 1 and "logout" in reusos[0], reusos


async def test_salir_de_todas_corta_todos_los_dispositivos(nuevo_cliente, sesiones, cuenta):
    """Lo que hacía `logout` hasta TODO-30, ahora con su propia ruta."""
    user_id, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    movil = await entrar(nuevo_cliente(), correo)

    r = await nuevo_cliente(portatil.cookies[COOKIE]).post(f"{API}/auth/logout-all")
    assert r.status_code == 204, r.text
    for sesion in (portatil, movil):
        assert (await _refrescar(nuevo_cliente, sesion.cookies[COOKIE])).status_code == 401
        assert (await nuevo_cliente().get(f"{API}/auth/me", headers=bearer(sesion))).status_code == 401
    assert await _filas(sesiones, user_id) == 0
    assert any("todas" in d for d in await eventos(correo, TipoDeEvento.LOGOUT))


async def test_salir_de_todas_con_una_cookie_gastada_no_echa_a_los_demas(
    nuevo_cliente, sesiones, cuenta,
):
    """Una copia vieja no puede echar a todos los dispositivos de alguien: se hace
    lo de `/logout` —cerrar esa sesión y avisar—, y la generación no sube (revisor
    de TODO-30)."""
    user_id, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    vieja = portatil.cookies[COOKIE]
    nueva = (await _refrescar(nuevo_cliente, vieja)).cookies[COOKIE]
    movil = await entrar(nuevo_cliente(), correo)
    version = await generacion(sesiones, user_id)

    assert (await nuevo_cliente(vieja).post(f"{API}/auth/logout-all")).status_code == 204
    assert await generacion(sesiones, user_id) == version
    assert (await _refrescar(nuevo_cliente, nueva)).status_code == 401
    assert (await _refrescar(nuevo_cliente, movil.cookies[COOKIE])).status_code == 200
    reusos = await eventos(correo, TipoDeEvento.REFRESH_REUSADO)
    assert len(reusos) == 1 and "logout de todas" in reusos[0], reusos


async def test_salir_de_todas_con_una_cookie_de_otra_generacion_no_hace_nada(
    nuevo_cliente, sesiones, cuenta,
):
    """La fila sigue (la generación subió sin borrarla, como en la carrera D6),
    pero la cookie es de la generación vieja: ni sube otra vez ni cierra nada."""
    from sqlalchemy import update

    from app.persistencia.tablas.usuarios import User

    user_id, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    async with sesiones() as s:
        await s.execute(update(User).where(User.id == user_id).values(
            token_version=User.token_version + 1,
        ))
        await s.commit()
    movil = await entrar(nuevo_cliente(), correo)
    version = await generacion(sesiones, user_id)

    assert (await nuevo_cliente(portatil.cookies[COOKIE]).post(
        f"{API}/auth/logout-all")).status_code == 204
    assert await generacion(sesiones, user_id) == version
    assert (await _refrescar(nuevo_cliente, movil.cookies[COOKIE])).status_code == 200
    assert not any("todas" in d for d in await eventos(correo, TipoDeEvento.LOGOUT))


async def test_salir_de_todas_sin_cookie_valida_no_es_un_error(nuevo_cliente, sesiones, cuenta):
    _, correo = cuenta
    movil = await entrar(nuevo_cliente(), correo)
    for cookie in (None, "no-es-un-jwt"):
        assert (await nuevo_cliente(cookie).post(f"{API}/auth/logout-all")).status_code == 204
    assert (await _refrescar(nuevo_cliente, movil.cookies[COOKIE])).status_code == 200


# ── Cortar todas desde otro gesto ────────────────────────────────────────────

async def test_cambiar_la_contrasena_echa_a_los_demas_dispositivos(
    nuevo_cliente, sesiones, cuenta, request,
):
    if request.node.callspec.params["cuenta"] == "sin_club":
        pytest.skip("/me/password exige club (Principal); sin club es 403")
    user_id, correo = cuenta
    portatil = await entrar(nuevo_cliente(), correo)
    movil = await entrar(nuevo_cliente(), correo)

    cambio = await nuevo_cliente().post(
        f"{API}/auth/me/password", headers=bearer(portatil),
        json={"current_password": PASSWORD, "new_password": "otra-clave-larga-1"},
    )
    assert cambio.status_code == 200, cambio.text
    assert (await _refrescar(nuevo_cliente, movil.cookies[COOKIE])).status_code == 401
    assert (await nuevo_cliente().get(f"{API}/auth/me", headers=bearer(movil))).status_code == 401
    assert (await _refrescar(nuevo_cliente, cambio.cookies[COOKIE])).status_code == 200
    assert await _filas(sesiones, user_id) == 1, "quedaron filas de la generación vieja"


@pytest.mark.parametrize("como", ["guardar", "anotar"])
async def test_subir_la_generacion_borra_las_filas_de_la_cuenta(
    nuevo_cliente, sesiones, cuenta, como,
):
    """Revocar, liberar y cortar sesiones (CLI) suben la generación por `guardar`
    o por `anotar`: las dos borran las filas en la misma transacción."""
    user_id, correo = cuenta
    await entrar(nuevo_cliente(), correo)
    await entrar(nuevo_cliente(), correo)
    assert await _filas(sesiones, user_id) == 2
    async with sesiones() as s:
        repo = RepositorioDeUsuarios(s)
        usuario = repo.entidad(await repo.por_id(user_id))
        usuario.revocar_sesiones()
        if como == "guardar":
            await repo.guardar(usuario)
        else:
            await repo.anotar(usuario)
            await s.commit()
    assert await _filas(sesiones, user_id) == 0


async def test_lo_que_no_sube_la_generacion_no_borra_sesiones(nuevo_cliente, sesiones, cuenta):
    """Entrar sella `last_login_at` por `guardar`: no puede cerrar el otro dispositivo."""
    user_id, correo = cuenta
    await entrar(nuevo_cliente(), correo)
    await entrar(nuevo_cliente(), correo)
    assert await _filas(sesiones, user_id) == 2
