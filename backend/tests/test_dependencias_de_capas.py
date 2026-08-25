"""La dirección de dependencias del §2 del rediseño, comprobada.

    api  →  persistencia  →  dominio          dominio → nada

`tests/test_entidades.py` ya comprueba la punta de la flecha (el dominio no
importa nada). Aquí se comprueban los dos tramos de arriba, y sobre todo la
regla que se rompió sola: **una rebanada del API no importa lógica de otra.**

Que la regla estuviera escrita en CLAUDE.md no la sostuvo. `dashboard`,
`aerobic_tests` y `link_codes` la rompían el día que se auditó (P5 del §0), y
las tres lo hacían por la misma razón: necesitaban una regla que vivía en el
`service.py` del vecino. La diferencia entre una convención y una invariante es
si algo falla cuando se viola; esto es lo que falla.

**`VIOLACIONES_CONOCIDAS` está vacía desde que terminó el paso 5** y solo puede
seguir estándolo: cada entrada era una rebanada sin repositorio, y ya no queda
ninguna. La lista se conserva porque el día que alguien necesite añadir una
tendrá que escribirla aquí, con su razón, en vez de colar el import y ya.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

# Rebanadas del API que importan lógica de otra rebanada. **Vacía**, y así se
# queda: la última en caer fue `link_codes → auth.service.normalize_email`, que
# se cerró mudando la función a `persistencia/repositorios/usuarios.py` — donde
# le corresponde, porque normalizar el correo es una regla de almacenamiento.
VIOLACIONES_CONOCIDAS: set[tuple[str, str]] = set()

# Las capas de dentro. `core/` está aquí aunque pueda leer `persistencia/tablas/`:
# `Principal` se compone de dos filas del ORM, y el §2 del rediseño lo pone en
# `core` a propósito. Lo que **no** puede hacer ninguna de estas es conocer
# `app.api`.
ADENTRO = ("dominio", "persistencia", "core", "engine")


def _rebanada(ruta: pathlib.Path) -> str | None:
    """`api/v1/vistas`, `api/v1/atletas`… o None si el archivo no es de ninguna."""
    partes = ruta.relative_to(APP).parts
    if partes[:2] == ("api", "v1") and len(partes) > 3:
        return f"api/v1/{partes[2]}"
    return None


def _es_modulo(punteado: str) -> bool:
    ruta = APP.parent / pathlib.Path(*punteado.split("."))
    return ruta.with_suffix(".py").is_file() or (ruta / "__init__.py").is_file()


def _imports(ruta: pathlib.Path) -> list[str]:
    """Los módulos `app.*` que importa ese archivo, en absoluto.

    `from app.api.v1.auth import service` importa un **módulo**, no un nombre, y
    tiene que contar igual que `from app.api.v1.auth.service import …`. Por eso
    se mira el disco: si `app/api/v1/auth/service.py` existe, el import es del
    módulo. Sin esa comprobación, la única forma de escribir el import que este
    archivo persigue sería también la que se le escapa — y es la forma que
    `auth/sessions.py` usaba antes del paso 5.

    Los relativos (`from .schemas import …`) se ignoran a propósito: por
    definición apuntan dentro de la propia rebanada, que es justo lo permitido.
    """
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            submodulos = [
                f"{nodo.module}.{a.name}" for a in nodo.names
                if _es_modulo(f"{nodo.module}.{a.name}")
            ]
            modulos += submodulos or [nodo.module]
    return [m for m in modulos if m == "app" or m.startswith("app.")]


def _archivos() -> list[pathlib.Path]:
    return [r for r in sorted(APP.rglob("*.py")) if "__pycache__" not in r.parts]


def _rebanada_de(modulo: str) -> str | None:
    p = modulo.split(".")
    if p[:3] == ["app", "api", "v1"] and len(p) > 4:
        return f"api/v1/{p[3]}"
    return None


def test_ninguna_rebanada_importa_logica_de_otra() -> None:
    """Entre rebanadas del API no se importa **nada**.

    Antes la regla admitía "lecturas explícitas de modelos", porque los modelos
    vivían dentro de la rebanada que los estrenó. Ya no hace falta la excepción:
    las tablas están en `persistencia/tablas/`, así que leer una fila ajena es
    mirar hacia abajo y no de lado. Lo que queda prohibido es lo que siempre
    debió estarlo — importar una **decisión** del vecino.
    """
    cruces = []
    for ruta in _archivos():
        propia = _rebanada(ruta)
        if propia is None:
            continue
        for modulo in _imports(ruta):
            ajena = _rebanada_de(modulo)
            if ajena is None or ajena == propia:
                continue
            if (propia, modulo) in VIOLACIONES_CONOCIDAS:
                continue
            cruces.append(f"{ruta.relative_to(APP)}: {propia} importa {modulo}")
    assert not cruces, (
        "Lógica cruzada entre rebanadas del API:\n  " + "\n  ".join(cruces)
        + "\n\nPregunta al repositorio del agregado en vez de importar al vecino."
    )


def test_las_violaciones_conocidas_siguen_existiendo() -> None:
    """Una lista de excepciones que ya no se usan miente sobre lo que falta.

    Sin esto, una entrada obsoleta se quedaría ahí para siempre haciendo creer
    que queda deuda donde ya no la hay — y peor: seguiría autorizando el import
    que alguien vuelva a escribir.
    """
    vivas = set()
    for ruta in _archivos():
        propia = _rebanada(ruta)
        if propia is None:
            continue
        for modulo in _imports(ruta):
            if (propia, modulo) in VIOLACIONES_CONOCIDAS:
                vivas.add((propia, modulo))
    assert vivas == VIOLACIONES_CONOCIDAS, (
        "Estas excepciones ya no las usa nadie; bórralas de la lista: "
        f"{sorted(VIOLACIONES_CONOCIDAS - vivas)}"
    )


def test_las_capas_de_dentro_no_conocen_el_api() -> None:
    """`api → persistencia → dominio`, nunca al revés.

    Si un repositorio importara un schema de Pydantic o un router, la capa que
    existe para no depender del framework dependería del framework.
    """
    malos = []
    for ruta in _archivos():
        if ruta.relative_to(APP).parts[0] not in ADENTRO:
            continue
        malos += [
            f"{ruta.relative_to(APP)}: {m}"
            for m in _imports(ruta) if m.startswith("app.api")
        ]
    assert not malos, "Una capa de dentro importa el API:\n  " + "\n  ".join(malos)


def test_el_dominio_no_importa_hacia_fuera() -> None:
    """Lo simétrico de `test_entidades.py`, dicho desde el otro lado.

    Allí se comprueba que todo import absoluto de `app/dominio/` es de la
    biblioteca estándar; aquí, que ninguno es de `app.*`. Son la misma regla
    vista dos veces a propósito: es la que sostiene que el motor se pueda
    empaquetar y probar sin la aplicación alrededor.
    """
    malos = [
        f"{ruta.relative_to(APP)}: {m}"
        for ruta in _archivos() if ruta.relative_to(APP).parts[0] == "dominio"
        for m in _imports(ruta)
    ]
    assert not malos, "El dominio importa hacia fuera:\n  " + "\n  ".join(malos)


def test_app_modules_ya_no_existe() -> None:
    """`app/modules/` se fue entero: no queda un envoltorio delegando.

    Un envoltorio que delega sigue siendo un import que cruza, y mientras exista
    el sitio al que importar, alguien lo importa. `plans/service.current_week_of`
    era exactamente eso, y por eso el paso 5 lo borró en vez de dejarlo.
    """
    vivos = [
        f"{ruta.relative_to(APP)}: {m}"
        for ruta in _archivos()
        for m in _imports(ruta) if m == "app.modules" or m.startswith("app.modules.")
    ]
    assert not vivos, "Todavía se importa app.modules:\n  " + "\n  ".join(vivos)
    assert not (APP / "modules").exists()


@pytest.mark.parametrize(
    "agregado",
    ["atletas", "codigos", "equipos", "macrociclos", "tests_aerobicos", "usuarios"],
)
def test_cada_agregado_tiene_su_repositorio(agregado: str) -> None:
    """Un agregado, un repositorio. §2 del rediseño.

    Fija el reparto que dejó el paso 5, para que el séptimo agregado no acabe
    colgando de uno de estos seis por ser el que más se le parecía.
    """
    assert (APP / "persistencia" / "repositorios" / f"{agregado}.py").is_file()


def test_las_tablas_viven_todas_en_persistencia() -> None:
    """Ningún modelo de SQLAlchemy fuera de `persistencia/tablas/`.

    Es la condición que hace innecesaria la excepción de "lecturas explícitas de
    modelos": si una rebanada declarara su propia tabla, la siguiente tendría que
    importársela y volveríamos a tener rebanadas que se leen entre sí.
    """
    fuera = []
    for ruta in _archivos():
        if ruta.relative_to(APP).parts[:2] == ("persistencia", "tablas"):
            continue
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id == "Base" for b in nodo.bases
            ):
                fuera.append(f"{ruta.relative_to(APP)}: {nodo.name}")
    assert not fuera, (
        "Hay tablas declaradas fuera de persistencia/tablas/:\n  " + "\n  ".join(fuera)
    )
