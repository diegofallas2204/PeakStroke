"""Dominio POO de PeakStroke — no importa NADA.

Ni SQLAlchemy, ni FastAPI, ni Pydantic, ni `app.modules`, ni `app.core`, ni el
motor viejo de `app.domain`. Se puede probar, empaquetar y portar sin la
aplicación alrededor (principio 6 de `docs/REDISENO.md` §1).

Paso 1 del rediseño: solo `valores/`. Es **aditivo** — nada del código actual lo
usa todavía. Ver `docs/REDISENO.md` §9 para el orden de construcción.
"""
