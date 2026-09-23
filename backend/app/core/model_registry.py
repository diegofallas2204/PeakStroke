"""Importa TODOS los modelos para poblar `Base.metadata`.

SQLAlchemy resuelve las claves foráneas por nombre de tabla contra el metadata,
no contra el import. Si un modelo no se ha importado, cualquier FK que lo
apunte revienta al primer INSERT con `NoReferencedTableError` — aunque la tabla
exista en la base de datos.

Antes esto lo hacía de rebote `init_db()` al llamar a `create_all()`. Desde que
el esquema lo gobierna Alembic, hace falta un sitio explícito: este.

Lo importan `app/main.py` (arranque de la app) y `alembic/env.py` (autogenerate).
**Todo módulo con modelos nuevos tiene que añadirse aquí.**
"""
from app.persistencia.tablas import atletas as _atletas  # noqa: F401
from app.persistencia.tablas import codigos as _codigos  # noqa: F401
from app.persistencia.tablas import equipos as _equipos  # noqa: F401
from app.persistencia.tablas import planes as _planes  # noqa: F401
from app.persistencia.tablas import resultados as _resultados  # noqa: F401
from app.persistencia.tablas import sesiones as _sesiones  # noqa: F401
from app.persistencia.tablas import tests_aerobicos as _tests  # noqa: F401
from app.persistencia.tablas import usuarios as _usuarios  # noqa: F401
