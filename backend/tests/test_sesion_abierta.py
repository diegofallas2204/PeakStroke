"""`SesionAbierta`: un login en un dispositivo, con su propia rotación (TODO-30).

Hasta TODO-30 la rotación era una por cuenta (`users.refresh_rotation`): entrar
en el móvil gastaba la cookie del portátil, y su siguiente refresh se cortaba
como robo. Ahora cada login abre una sesión, y lo que antes hacía `Usuario`
(`rotar_refresh`, `refresh_gastado`) lo hace ella.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.dominio.entidades import SesionAbierta, Usuario

AHORA = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
VIGENCIA = timedelta(days=30)


def _usuario(**kw) -> Usuario:
    datos = {"id": 7, "correo": "ana@x.dev", "nombre": "Ana", "hash_de_password": "h"} | kw
    return Usuario(**datos)


def test_abrir_da_una_sesion_nueva_en_rotacion_cero():
    sesion = _usuario().abrir_sesion(AHORA, VIGENCIA)
    assert (sesion.usuario_id, sesion.rotacion, sesion.abierta, sesion.caduca) == (
        7, 0, AHORA, AHORA + VIGENCIA,
    )
    assert not sesion.roto()


def test_el_id_es_aleatorio_y_no_se_repite():
    """No es un entero: SQLite sin AUTOINCREMENT reutiliza el último rowid
    borrado, y un refresh de una sesión cerrada revivía en la siguiente."""
    ids = {_usuario().abrir_sesion(AHORA, VIGENCIA).id for _ in range(200)}
    assert len(ids) == 200
    assert all(len(i) >= 32 for i in ids)


def test_una_cuenta_sin_guardar_no_abre_sesion():
    with pytest.raises(ValueError, match="guardada"):
        _usuario(id=None).abrir_sesion(AHORA, VIGENCIA)


def test_rotar_gasta_una_y_desliza_la_caducidad():
    sesion = _usuario().abrir_sesion(AHORA, VIGENCIA)
    luego = AHORA + timedelta(days=3)
    assert sesion.rotar(luego, VIGENCIA) == 1
    assert (sesion.rotacion, sesion.rotacion_leida, sesion.caduca) == (1, 0, luego + VIGENCIA)
    assert sesion.roto()


def test_un_refresh_de_otra_rotacion_esta_gastado():
    sesion = SesionAbierta(id="s", usuario_id=7, caduca=AHORA + VIGENCIA, rotacion=3)
    assert not sesion.refresh_gastado(3)
    assert sesion.refresh_gastado(2)
    assert sesion.refresh_gastado(4)


def test_caduca_en_el_instante_exacto_y_acepta_fechas_sin_zona():
    """SQLite devuelve las fechas sin zona: se leen como UTC."""
    sesion = SesionAbierta(id="s", usuario_id=7, caduca=AHORA.replace(tzinfo=None))
    assert not sesion.caducada(AHORA - timedelta(seconds=1))
    assert sesion.caducada(AHORA)


@pytest.mark.parametrize("campo", ["rotacion", "caduca", "rotacion_leida"])
def test_la_rotacion_y_la_caducidad_no_se_asignan_a_mano(campo):
    sesion = _usuario().abrir_sesion(AHORA, VIGENCIA)
    with pytest.raises(AttributeError, match="solo cambia por sus métodos"):
        setattr(sesion, campo, 99)


def test_se_compara_por_id():
    a = SesionAbierta(id="s", usuario_id=7, caduca=AHORA)
    b = SesionAbierta(id="s", usuario_id=7, caduca=AHORA + VIGENCIA)
    assert a == b
    assert a != SesionAbierta(id="t", usuario_id=7, caduca=AHORA)
