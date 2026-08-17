"""Persistencia: donde vive el ORM y la traducción tabla ↔ entidad de dominio.

Nace en el paso 2 con lo mínimo —`mapeo/`— porque las entidades tienen que
poder construirse desde una fila sin que el dominio se entere de que existe
SQLAlchemy. El paso 5 lo completa con `tablas/` (los modelos, hoy todavía en
`app/modules/<feature>/models.py`) y `repositorios/`.

Dirección de dependencias (`docs/REDISENO.md` §2), sin excepciones:

    api  →  persistencia  →  dominio
    dominio  →  nada
"""
