"""La identidad efectiva de una petición.

Este archivo no sabe de FastAPI ni de peticiones: solo dice **qué es** una
identidad y qué alcanza. Quién la resuelve está en `dependencies.py` y qué se le
exige, en `guards.py`. Separarlo permite leer entero el objeto del que cuelga
todo el aislamiento de datos sin el ruido del framework alrededor.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import false

from app.modules.auth.models import User
from app.modules.teams.models import ROLE_ATHLETE, ROLE_COACH, TeamMember


@dataclass(frozen=True, slots=True)
class Principal:
    """La identidad efectiva de una petición: persona + pertenencia + propiedad.

    Dos fronteras cuelgan de aquí, y hasta el 2026-08-06 solo existía la primera:

        Principal { user, membership, is_owner, swimmer_id }
                     │         │          │          │
                     │         └─ team_id ──▶ el CLUB
                     │
                     └─ swimmer_id ──────────▶ el ATLETA

    Sin `swimmer_id`, ningún servicio *podía* filtrar por nadador aunque
    quisiera, y por eso un atleta leía y escribía los datos de sus compañeros.
    """

    user: User
    membership: TeamMember
    is_owner: bool
    # El nadador al que va ligada esta cuenta, si va ligada a alguno. None en un
    # entrenador (normal) y también en un atleta al que nadie le creó la ficha
    # (anomalía de datos, y por eso el filtro de abajo falla cerrado).
    swimmer_id: int | None = None
    # Modo desarrollador: los guards de rol dejan pasar. Es un tercer eje,
    # ortogonal al rol, y **nunca sale de la base de datos**: ni de una columna,
    # ni de un campo del usuario, ni del cuerpo de la petición. Solo de una
    # cabecera, y solo cuando `settings.dev_identity_enabled`. Que no exista
    # ninguna forma de persistirlo es lo que garantiza que no pueda llegar a
    # producción por un dato mal puesto.
    is_developer: bool = False

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def team_id(self) -> int:
        return self.membership.team_id

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def is_coach(self) -> bool:
        return self.membership.role == ROLE_COACH

    @property
    def is_athlete(self) -> bool:
        return self.membership.role == ROLE_ATHLETE

    @property
    def sees_every_plan(self) -> bool:
        """El dueño llega a todos los macrociclos de su equipo.

        Sin esta excepción, los planes de un entrenador que se va quedarían sin
        nadie capaz de verlos ni reasignarlos.
        """
        return self.is_owner

    def scope_to_own_swimmer(self, stmt, column):
        """Acota una consulta al nadador propio **si quien pregunta es atleta**.

        Un entrenador pasa sin tocar: ver a todo su equipo es su trabajo.

        El caso que importa es el segundo. Un atleta sin nadador ligado no ve
        NADA, no lo ve todo: la consulta se vuelve imposible en vez de quedarse
        sin filtro. Es la diferencia entre que un dato mal ligado no enseñe
        nada y que filtre el club entero, y el modo de fallo hay que elegirlo
        antes de que ocurra, no después.

        `column` es la columna con el `swimmer_id` en el `stmt` que se le pasa,
        porque no todas las tablas lo llaman igual ni lo tienen a la misma
        distancia (`Swimmer.id`, `AerobicTest.swimmer_id`, `AthletePlan.swimmer_id`).

        **Esa columna tiene que pertenecer a una tabla del `stmt`.** Si no,
        SQLAlchemy no protesta: la añade al FROM y produce un producto
        cartesiano, con lo que el filtro deja de acotar y la consulta devuelve
        la tabla entera — el modo de fallo ABIERTO, en un helper que existe para
        lo contrario. No se comprueba aquí porque hacerlo cuesta 1,3 ms por
        consulta (obliga a compilar el statement); se comprueba en los tests,
        donde `pyproject.toml` convierte el aviso de producto cartesiano de
        SQLAlchemy en un fallo. Ver `test_scope_helper.py`.
        """
        if not self.is_athlete:
            return stmt
        if self.swimmer_id is None:
            return stmt.where(false())
        return stmt.where(column == self.swimmer_id)

    def owns_swimmer(self, swimmer_id: int) -> bool:
        """Si esta identidad puede actuar sobre ese nadador.

        Para las escrituras cuyo destinatario llega en el CUERPO de la petición
        y no en la URL — crear un test aeróbico a nombre de alguien — donde no
        hay consulta que acotar y hace falta preguntarlo directamente.
        """
        if not self.is_athlete:
            return True
        return self.swimmer_id is not None and self.swimmer_id == swimmer_id
