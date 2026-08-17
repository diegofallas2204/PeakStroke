"""Dominio POO de PeakStroke — no importa NADA.

Ni SQLAlchemy, ni FastAPI, ni Pydantic, ni `app.modules`, ni `app.core`, ni el
motor viejo de `app.domain`. Se puede probar, empaquetar y portar sin la
aplicación alrededor (principio 6 de `docs/REDISENO.md` §1).

Pasos 1 y 2 del rediseño: `valores/` (objetos inmutables sin identidad) y
`entidades/` (identidad + ciclo de vida). Ver `docs/REDISENO.md` §9 para el orden
de construcción.

Los dos son **aditivos**: las funciones que sustituyen siguen en pie como
envoltorio delegando aquí (`core/dates.age_at`, `engine/progression.monday_of`,
`plans/service.current_week_of` y `effective_status`), así que ningún llamador se
rompió. La traducción fila ↔ entidad vive fuera, en `app/persistencia/mapeo/`:
el dominio no sabe que existe una base de datos, y `tests/test_entidades.py`
comprueba que siga sin saberlo.
"""
