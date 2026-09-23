"""Quién importa a quién dentro de `app/`, por capas.

    .venv\\Scripts\\python tools/grafo_de_imports.py

Una flecha que sube es un archivo de una capa de dentro que conoce una de
fuera. Desde que terminó el paso 5 (2026-08-25) **no queda ninguna**: las siete
rebanadas están en `api/v1/` y las tablas en `persistencia/tablas/`.

`core` sale como capa lateral y no como una de dentro: el §2 del rediseño pone
`principal` ahí, y `Principal` se compone de dos filas del ORM. Puede leer
`dominio` y `persistencia/tablas`; lo que no puede es conocer `api`.

Esto informa; lo que **falla** cuando alguien cruza una frontera es
`tests/test_dependencias_de_capas.py`.
"""
from __future__ import annotations

import ast
import collections
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "app"

# Cuanto más bajo, más adentro. Una flecha de un número bajo a uno alto sube.
CAPA_FIJA = {"dominio": 0, "engine": 1, "persistencia": 2, "core": 2}


def paquete(modulo: str) -> str:
    """El nodo del grafo al que pertenece un módulo `app.*`. Cadena vacía si no lo es."""
    p = modulo.split(".")
    if len(p) < 2 or p[0] != "app":
        return ""
    if p[1] == "api":
        return f"api/v1/{p[3]}" if len(p) > 3 and p[2] == "v1" else "api"
    if p[1] == "persistencia":
        return f"persistencia/{p[2]}" if len(p) > 2 else "persistencia"
    if p[1] == "dominio":
        return "dominio"
    return p[1]


def capa(nodo: str) -> int:
    if nodo in CAPA_FIJA:
        return CAPA_FIJA[nodo]
    if nodo.startswith("persistencia"):
        return 2
    return 3          # `api/…`: las rebanadas de entrada


def aristas() -> dict[str, set[str]]:
    grafo: dict[str, set[str]] = collections.defaultdict(set)
    for ruta in sorted(RAIZ.rglob("*.py")):
        if "__pycache__" in ruta.parts:
            continue
        origen = paquete("app." + ".".join(ruta.relative_to(RAIZ).with_suffix("").parts))
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
                modulos = [nodo.module]
            else:
                continue
            for m in modulos:
                destino = paquete(m)
                if destino and destino != origen:
                    grafo[origen].add(destino)
    return grafo


def main() -> None:
    grafo = aristas()
    for origen in sorted(grafo, key=lambda n: (-capa(n), n)):
        for destino in sorted(grafo[origen]):
            marca = "  <-- SUBE" if capa(destino) > capa(origen) else ""
            print(f"{origen:28s} -> {destino}{marca}")


if __name__ == "__main__":
    main()
