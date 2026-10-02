"""El vocabulario con el que un rol contesta: alcance, recurso y sección.

Tres enums y ninguna regla. Las reglas viven en las subclases de `Rol`; aquí
está solo el idioma en el que responden, para que ese idioma sea cerrado y
comprobable en vez de tres conjuntos de cadenas sueltas repartidas por los
servicios.
"""
from __future__ import annotations

from enum import Enum


class Alcance(Enum):
    """Hasta dónde llega un rol sobre una colección.

    `NINGUNO` no lo devuelve nadie hoy, y eso es un dato, no un olvido: la cuenta
    sin equipo —el único caso que lo merecería— nunca llega a tener un `Rol`,
    porque `_principal_for` la corta antes con un 403. Se declara igualmente
    porque el día que exista un rol de solo-lectura sin colección propia, el
    valor tiene que estar en el idioma y no inventarse como `SOLO_YO` con un
    comentario al lado.
    """

    TODOS = "todos"
    LOS_MIOS = "los_mios"
    SOLO_YO = "solo_yo"
    NINGUNO = "ninguno"


class Recurso(Enum):
    """Sobre qué se pregunta `puede_ver` / `puede_escribir`.

    La lista es la de las decisiones que el código toma HOY, no un catálogo de
    todo lo que existe: un recurso que nadie pregunta es una respuesta que nadie
    comprueba, y esa es la clase de permiso que se descubre estando mal.

    `PARON_DE_SEMANA` es un recurso aparte de `SEMANA` a propósito. La semana la
    escriben los dos —el atleta apunta su tiempo real— pero el parón redistribuye
    la mejora restante del macrociclo entero, así que es del entrenador. Sin
    separarlos, la única respuesta posible para `SEMANA` sería la del más
    permisivo de los dos campos.
    """

    ATLETA = "atleta"                    # la ficha del nadador
    MACROCICLO = "macrociclo"            # el plan: fases, competencias, inscripciones
    SEMANA = "semana"                    # la semana de una prueba objetivo
    PARON_DE_SEMANA = "paron_de_semana"  # `disabled` / `disable_reason` de esa semana
    TEST_AEROBICO = "test_aerobico"
    SESION = "sesion"                    # lo que el atleta nadó un día (C7)
    EQUIPO = "equipo"                    # el club: miembros, códigos, tabla del equipo


class Seccion(Enum):
    """Las secciones de la aplicación, por su ruta.

    Espejo de `frontend/src/components/layout/navConfig.ts`, que hoy es la única
    lista viva. `tests/test_roles.py` compara las dos y falla si se separan:
    mientras el backend no sirva el menú, dos listas que dicen cosas distintas
    son la forma normal de que una sección se esconda del rail y siga siendo
    alcanzable tecleando la ruta.

    Perfil no está, igual que no está en `NAV_ITEMS`: vive en el pie del rail y
    lo ve todo el mundo, incluida la cuenta sin equipo, que no tiene rol.
    """

    DASHBOARD = "/"
    MACROCICLOS = "/macrociclos"
    ATLETAS = "/atletas"
    BASE_AEROBICA = "/pruebas"
    ENTRENAMIENTO = "/entrenamiento"
    PLAN_SEMANAL = "/plan-semanal"
    TABLA_DEL_EQUIPO = "/equipo"
    SIMULADOR = "/simulador"
