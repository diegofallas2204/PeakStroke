"""Quién escribe un campo, buscado en el código: el detector de los guardas por AST.

Lo usan `test_usuario_entidad.py`, `test_equipo_entidad.py` y
`test_codigo_entidad.py` para afirmar que un campo solo lo asigna el mapeo de
su entidad. La primera versión (2026-10-14) solo miraba `obj.campo = …`, y el
revisor del bloque encontró cinco formas de escribirlo sin que saltara; esta las
cubre todas:

    obj.campo = x                 obj.campo += x        obj.campo: int = x
    a.campo, b.otro = x, y        for obj.campo in …    with … as obj.campo
    setattr(obj, "campo", x)      obj.__dict__["campo"] = x
    update(T).values(campo=x)     T.__table__.update().values({"campo": x})

Y comprueba que **miró algo**: si la raíz se moviera y el recorrido saliera
vacío, el guarda pasaría sin haber leído un archivo.
"""
from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _archivos() -> list[Path]:
    return [*(RAIZ / "app").rglob("*.py"), RAIZ / "seed.py", *(RAIZ / "tools").glob("*.py")]


def _destinos(nodo: ast.AST) -> Iterable[ast.AST]:
    if isinstance(nodo, ast.Assign):
        yield from nodo.targets
    elif isinstance(nodo, ast.AugAssign | ast.AnnAssign | ast.For | ast.AsyncFor | ast.comprehension):
        yield nodo.target
    elif isinstance(nodo, ast.withitem) and nodo.optional_vars is not None:
        yield nodo.optional_vars
    elif isinstance(nodo, ast.NamedExpr):
        yield nodo.target


def _aplanar(destino: ast.AST) -> Iterable[ast.AST]:
    if isinstance(destino, ast.Tuple | ast.List):
        for elt in destino.elts:
            yield from _aplanar(elt)
    elif isinstance(destino, ast.Starred):
        yield from _aplanar(destino.value)
    else:
        yield destino


def _texto(nodo: ast.AST) -> str | None:
    return nodo.value if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) else None


def escrituras_en(fuente: str, campos: set[str]) -> list[tuple[int, str]]:
    """`(línea, campo)` de cada escritura de `campos` en ese código fuente."""
    encontradas: list[tuple[int, str]] = []
    for nodo in ast.walk(ast.parse(fuente)):
        linea = getattr(nodo, "lineno", None) or getattr(getattr(nodo, "target", None), "lineno", 0)
        escritos: list[str] = []
        for destino in _destinos(nodo):
            for d in _aplanar(destino):
                if isinstance(d, ast.Attribute) and d.attr in campos:
                    escritos.append(d.attr)
                # obj.__dict__["campo"] = …
                if (isinstance(d, ast.Subscript) and isinstance(d.value, ast.Attribute)
                        and d.value.attr == "__dict__" and _texto(d.slice) in campos):
                    escritos.append(_texto(d.slice))
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            # setattr(obj, "campo", x)
            if (isinstance(funcion, ast.Name) and funcion.id == "setattr"
                    and len(nodo.args) >= 2 and _texto(nodo.args[1]) in campos):
                escritos.append(_texto(nodo.args[1]))
            # update(T).values(campo=x) / .values({"campo": x})
            if isinstance(funcion, ast.Attribute) and funcion.attr == "values":
                escritos += [k.arg for k in nodo.keywords if k.arg in campos]
                for arg in nodo.args:
                    if isinstance(arg, ast.Dict):
                        escritos += [t for k in arg.keys if (t := _texto(k)) in campos]
        encontradas += [(linea, c) for c in escritos]
    return encontradas


def escrituras(campos: set[str], permitidos: set[str]) -> list[str]:
    """`archivo:línea campo` de cada escritura de `campos` fuera de `permitidos`."""
    archivos = _archivos()
    assert len(archivos) > 50 and (RAIZ / "app/persistencia/mapeo/identidad.py").exists(), (
        "el guarda no está mirando el árbol que cree"
    )
    culpables = []
    for archivo in archivos:
        relativo = archivo.relative_to(RAIZ).as_posix()
        if relativo in permitidos:
            continue
        culpables += [
            f"{relativo}:{linea} {campo}"
            for linea, campo in escrituras_en(archivo.read_text(encoding="utf-8"), campos)
        ]
    return culpables
