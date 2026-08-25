"""Pantallas compuestas. **No son agregados.**

El tablero, la tabla del equipo y la comparación no tienen modelo propio, no
escriben y no imponen ninguna regla: leen de los repositorios y dan forma a lo
leído. Cuando esto era `modules/dashboard/`, parecía un módulo de dominio más y
se comportaba como tal — importaba `plans.access`, `plans.service` y cuatro
modelos de `plans` para poder preguntar en qué semana iba un macrociclo. Ese es
P5 del §0 en una carpeta mal puesta.
"""
