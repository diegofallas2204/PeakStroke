"""La jerarquía de `Rol` y las tres cosas que NO puede llegar a ser (paso 3).

Los permisos ya estaban cubiertos de punta a punta —`test_role_guards.py`,
`test_athlete_scoping.py`, `test_scope_helper.py`— y esos tests no cambian: si
el paso 3 estuviera mal, fallarían ellos. Lo que se fija aquí es lo que la
jerarquía añade y ninguna petición HTTP puede comprobar:

  · que `EntrenadorEnJefe` **solo** amplía el alcance de macrociclos, que es la
    única razón por la que existe como subclase;
  · que `Administrador` sigue siendo un hueco: **nada lo construye** (R3);
  · que el modo desarrollador no se ha convertido en un rol por la puerta de
    atrás — no hay clave, ni subclase, ni fila que lo produzca;
  · y que las secciones del backend y las del menú del frontend dicen lo mismo,
    porque mientras sean dos listas es cuestión de tiempo que digan cosas
    distintas.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import World

from app.core.principal import rol_de
from app.dominio.roles import (
    Administrador,
    Alcance,
    AtletaRol,
    Entrenador,
    EntrenadorEnJefe,
    Recurso,
    Rol,
    Seccion,
)
from app.persistencia.tablas.equipos import ROLE_ATHLETE, ROLE_COACH

_TODOS_LOS_ROLES = (Administrador(), EntrenadorEnJefe(), Entrenador(), AtletaRol())


async def _principal(db, email: str):
    from app.api.v1.auth.service import get_by_email
    from app.core.dependencies import _principal_for

    return await _principal_for(db, await get_by_email(db, email))


# ── La composición: de la pertenencia al rol ─────────────────────────────────

@pytest.mark.parametrize(("clave", "es_dueno", "esperado"), [
    (ROLE_COACH, True, EntrenadorEnJefe),
    (ROLE_COACH, False, Entrenador),
    (ROLE_ATHLETE, False, AtletaRol),
    # Un atleta no se vuelve jefe por ser dueño: la propiedad AMPLÍA a un
    # entrenador, no asciende a nadie. Hoy el caso no se puede dar (el dueño se
    # crea entrenador), y por eso conviene dejar escrito qué pasaría si se diera.
    (ROLE_ATHLETE, True, AtletaRol),
])
def test_la_pertenencia_se_traduce_a_su_rol(clave, es_dueno, esperado):
    assert type(rol_de(clave, es_dueno=es_dueno)) is esperado


def test_una_clave_desconocida_revienta_en_vez_de_adivinar():
    """Fallar cerrado. El modo silencioso sería devolver algo parecido a un
    atleta que el filtro por nadador no reconociera: un rol sin acotar."""
    with pytest.raises(ValueError, match="Rol desconocido"):
        rol_de("developer", es_dueno=False)


async def test_el_principal_compone_el_rol_de_cada_cuenta(db, world: World):
    assert type((await _principal(db, world.owner_email)).rol) is EntrenadorEnJefe
    assert type((await _principal(db, world.assistant_email)).rol) is Entrenador
    assert type((await _principal(db, world.sofia_email)).rol) is AtletaRol
    # Sin ficha de nadador ligada sigue siendo un atleta: el rol es de la
    # pertenencia, no de tener datos deportivos.
    assert type((await _principal(db, world.huerfano_email)).rol) is AtletaRol


# ── El jefe solo amplía el alcance de macrociclos ────────────────────────────

def test_el_jefe_es_un_entrenador():
    assert isinstance(EntrenadorEnJefe(), Entrenador)


def test_el_jefe_llega_a_todos_los_macrociclos_y_el_asistente_a_los_suyos():
    """La regla que justifica la subclase: sin ella, los macrociclos de un
    entrenador que se va del club no los podría rescatar nadie."""
    assert EntrenadorEnJefe().alcance_de_macrociclos() is Alcance.TODOS
    assert Entrenador().alcance_de_macrociclos() is Alcance.LOS_MIOS


def test_el_jefe_no_amplia_nada_mas():
    """**El test que fija §4.2.** Cada método que el jefe sobrescribiera de más
    sería una diferencia jefe/asistente que la capa de acceso tendría que
    aprender por separado — y hoy no la hay: renombrar el club o transferir la
    propiedad son de dueño, y el dueño es `teams.owner_id`, no un rol.
    """
    jefe, asistente = EntrenadorEnJefe(), Entrenador()
    assert jefe.alcance_de_atletas() == asistente.alcance_de_atletas()
    assert jefe.secciones_visibles() == asistente.secciones_visibles()
    for recurso in Recurso:
        assert jefe.puede_ver(recurso) == asistente.puede_ver(recurso)
        assert jefe.puede_escribir(recurso) == asistente.puede_escribir(recurso)


# ── El atleta: lo suyo, y solo lo suyo ───────────────────────────────────────

def test_el_atleta_solo_se_alcanza_a_si_mismo():
    atleta = AtletaRol()
    assert atleta.alcance_de_atletas() is Alcance.SOLO_YO
    assert atleta.alcance_de_macrociclos() is Alcance.SOLO_YO
    # La derivada que consume el filtro por nadador.
    assert atleta.alcanza_solo_lo_suyo
    assert not Entrenador().alcanza_solo_lo_suyo
    assert not EntrenadorEnJefe().alcanza_solo_lo_suyo


@pytest.mark.parametrize("recurso", [
    Recurso.ATLETA,          # su ficha la mantiene el entrenador
    Recurso.MACROCICLO,      # el plan es del entrenador
    Recurso.PARON_DE_SEMANA, # parar una semana redistribuye la mejora del macro
    Recurso.EQUIPO,
])
def test_lo_que_un_atleta_no_escribe(recurso):
    assert not AtletaRol().puede_escribir(recurso)
    assert Entrenador().puede_escribir(recurso)


@pytest.mark.parametrize("recurso", [Recurso.SEMANA, Recurso.TEST_AEROBICO])
def test_lo_que_un_atleta_si_escribe(recurso):
    """Las dos escrituras que los routers dejan pasar sin `require_coach`:
    apuntar el tiempo real de su semana y registrar sus tests aeróbicos."""
    assert AtletaRol().puede_escribir(recurso)


def test_el_atleta_no_ve_la_tabla_del_equipo():
    """Enseña nombres, ritmos y marcas de todos los compañeros."""
    assert not AtletaRol().puede_ver(Recurso.EQUIPO)
    assert Seccion.TABLA_DEL_EQUIPO not in AtletaRol().secciones_visibles()


# ── El administrador: el hueco, y solo el hueco (R3) ─────────────────────────

def test_la_jerarquia_deja_la_puerta_abierta_a_un_rol_que_cruce_equipos():
    assert Administrador().alcance_de_atletas() is Alcance.TODOS
    assert Administrador().alcance_de_macrociclos() is Alcance.TODOS


@pytest.mark.parametrize("clave", [ROLE_COACH, ROLE_ATHLETE, "admin", "staff", "owner"])
@pytest.mark.parametrize("es_dueno", [True, False])
def test_ninguna_pertenencia_produce_un_administrador(clave, es_dueno):
    """R3: contemplado, no implementado. Un administrador cruza equipos y el
    equipo es la frontera de todo, así que **no puede salir de `team_members`**.
    Cuando exista, vendrá por otro sitio y este test tendrá que cambiar a mano.
    """
    try:
        rol = rol_de(clave, es_dueno=es_dueno)
    except ValueError:
        return
    assert not isinstance(rol, Administrador)


def test_el_administrador_no_esta_en_la_base_de_datos():
    from app.persistencia.tablas.equipos import ROLES

    assert "admin" not in ROLES and "administrador" not in ROLES


# ── El modo desarrollador es un eje, no un rol ───────────────────────────────

def test_no_hay_rol_de_desarrollador():
    """`is_developer` levanta lo que PUEDES HACER, no lo que ves, y no existe
    forma de persistirlo (ver `test_dev_bypass.py`). Un rol lo haría persistible
    en cuanto alguien escribiera su clave en `team_members.role`.
    """
    nombres = {type(r).__name__.lower() for r in _TODOS_LOS_ROLES}
    assert not any("desarroll" in n or "dev" in n for n in nombres)


async def test_el_bypass_no_cambia_el_rol(db, world: World):
    """El conmutador se aplica sobre el `Principal`, y el rol sigue siendo el de
    la persona suplantada: por eso se puede revisar la UI de atleta con él."""
    from dataclasses import replace

    p = await _principal(db, world.sofia_email)
    con_bypass = replace(p, is_developer=True)
    assert con_bypass.rol == p.rol == AtletaRol()
    assert con_bypass.is_athlete  # el filtro por nadador sigue puesto


# ── Las secciones no pueden divergir del menú ────────────────────────────────

_NAV = (
    Path(__file__).resolve().parents[2]
    / "frontend" / "src" / "components" / "layout" / "navConfig.ts"
)
# nav('/ruta', 'Etiqueta', Icono)  ó  nav('/ruta', 'Etiqueta', Icono, ['coach'])
_ENTRADA = re.compile(r"nav\(\s*'([^']+)'\s*,\s*'[^']*'\s*,\s*\w+\s*(?:,\s*\[([^\]]*)\])?\s*\)")


def _menu_del_frontend() -> dict[str, set[str]]:
    """Ruta → roles que la ven, leído de `NAV_ITEMS`. Sin roles, la ven todos."""
    texto = _NAV.read_text(encoding="utf-8")
    bloque = texto.split("export const NAV_ITEMS")[1].split("\n]")[0]
    menu = {}
    for ruta, roles in _ENTRADA.findall(bloque):
        menu[ruta] = set(re.findall(r"'([^']+)'", roles)) or {"coach", "athlete"}
    return menu


def test_el_catalogo_de_secciones_es_el_mismo_que_el_del_menu():
    assert _NAV.exists(), f"No se encontró {_NAV}: el test pasaría en vacío"
    assert {s.value for s in Seccion} == set(_menu_del_frontend())


@pytest.mark.parametrize(("rol", "clave"), [
    (Entrenador(), "coach"), (EntrenadorEnJefe(), "coach"), (AtletaRol(), "athlete"),
])
def test_cada_rol_ve_las_mismas_secciones_que_su_menu(rol: Rol, clave: str):
    """Esconder una sección del rail no la hace inalcanzable —`/equipo` se puede
    teclear—, así que las dos listas tienen que decir lo mismo. Mientras el
    backend no sirva el menú, esto es lo único que las mantiene juntas.
    """
    del_menu = {r for r, roles in _menu_del_frontend().items() if clave in roles}
    assert {s.value for s in rol.secciones_visibles()} == del_menu


# ── La interfaz completa, para cualquier rol futuro ──────────────────────────

@pytest.mark.parametrize("rol", _TODOS_LOS_ROLES, ids=lambda r: type(r).__name__)
def test_todo_rol_contesta_las_cinco_preguntas(rol: Rol):
    """Un rol nuevo que se olvide de una no se puede instanciar (son abstractas);
    esto comprueba además que lo que contesta es del vocabulario cerrado.
    """
    assert isinstance(rol.alcance_de_atletas(), Alcance)
    assert isinstance(rol.alcance_de_macrociclos(), Alcance)
    assert rol.secciones_visibles() <= frozenset(Seccion)
    for recurso in Recurso:
        assert isinstance(rol.puede_ver(recurso), bool)
        assert isinstance(rol.puede_escribir(recurso), bool)


def test_un_rol_no_tiene_estado():
    """Sin campos y comparables por su clase: se pueden reusar como constantes
    sin que dos peticiones se pisen."""
    assert Entrenador() == Entrenador()
    assert Entrenador() != EntrenadorEnJefe()
    assert len({Entrenador(), Entrenador(), AtletaRol()}) == 2


def test_el_rol_abstracto_no_se_instancia():
    with pytest.raises(TypeError):
        Rol()  # type: ignore[abstract]
