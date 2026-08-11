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
from app.modules.aerobic_tests import models as _aerobic  # noqa: F401
from app.modules.auth import models as _auth  # noqa: F401
from app.modules.link_codes import models as _link_codes  # noqa: F401
from app.modules.plans import models as _plans  # noqa: F401
from app.modules.swimmers import models as _swimmers  # noqa: F401
from app.modules.teams import models as _teams  # noqa: F401
