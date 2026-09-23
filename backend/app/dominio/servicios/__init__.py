"""Servicios de dominio: el cálculo que no cabe en una sola entidad.

Paso 4 del rediseño (`docs/REDISENO.md` §6). Lo que vive aquí es la ciencia —
cuánto puede mejorar un atleta, con qué forma, a cuántos kilómetros por semana y
a qué ritmos— que hasta ahora estaba repartida entre `app/domain/engine.py`
(la teoría, que solo corría en los tests) y `app/engine/` (el adaptador, que era
quien de verdad generaba los planes guardados).

Como el resto de `app/dominio/`, no importa nada de fuera.
"""
from __future__ import annotations
