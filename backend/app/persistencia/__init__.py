"""Persistencia: donde vive el ORM y la traducción tabla ↔ entidad de dominio.

Nace en el paso 2 con lo mínimo —`mapeo/`— porque las entidades tienen que
poder construirse desde una fila sin que el dominio se entere de que existe
SQLAlchemy. El paso 5 (2026-08-25) añade `tablas/` y `repositorios/`, **de un
agregado cada vez**: hoy está el de planificación (`Macrociclo`), y `swimmers`,
`teams`, `auth`, `aerobic_tests` y `link_codes` siguen en `app/modules/`.

Dirección de dependencias (`docs/REDISENO.md` §2), sin excepciones:

    api  →  persistencia  →  dominio
    dominio  →  nada

El repositorio es lo que hace que esa flecha baste. Sin él, una vista que
necesita saber en qué semana va un macrociclo tiene que importar la función de
otro módulo; con él, pide el macrociclo y recibe un objeto que ya lo sabe.
"""
