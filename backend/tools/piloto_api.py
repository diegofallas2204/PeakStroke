"""Arranca el API del piloto con su configuración (`piloto.ps1 levantar`).

`piloto.ps1` lo lanza como proceso independiente (por WMI), que no hereda las
variables de entorno de quien lo llama: por eso lee él mismo `.env.piloto`. Así
el secreto no viaja en la línea de comandos, que cualquiera de la máquina puede
ver en la lista de procesos.

    python tools/piloto_api.py <.env.piloto> <archivo de log> <puerto>
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def cargar_entorno(ruta: Path) -> None:
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ[clave.strip()] = valor.strip()


def main() -> None:
    entorno, log, puerto = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
    cargar_entorno(entorno)
    # Antes de importar uvicorn: su logging escribe en el stderr de este momento.
    salida = log.open("a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = salida
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))

    import uvicorn

    # Sin `proxy_headers`: la IP real la decide PEAKSTROKE_PROXIES_DE_CONFIANZA
    # (`core/proxy.py`) y nadie más, como en docs/DESPLIEGUE.md §3.
    uvicorn.run("app.main:app", host="127.0.0.1", port=puerto, proxy_headers=False)


if __name__ == "__main__":
    main()
