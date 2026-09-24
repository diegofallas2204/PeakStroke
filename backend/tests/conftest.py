"""Harness de tests de API: cliente HTTP, base de datos de prueba y un mundo fijo.

Hasta el 2026-08-06 los 103 tests del proyecto eran todos del motor científico:
funciones puras, sin base de datos ni FastAPI. Eso dejaba sin cubrir justo lo
que más caro sale equivocarse — quién ve qué — y por eso un atleta pudo leer y
escribir los datos de sus compañeros durante meses sin que nada fallara.

Tres decisiones que conviene entender antes de tocar esto:

**La DB de prueba se elige por variable de entorno, antes de importar `app`.**
`settings`, `engine` y `AsyncSessionLocal` se construyen al importarse sus
módulos, así que no hay forma de redirigirlos después. Las tres líneas de
`os.environ` de abajo tienen que ir antes de cualquier `from app...`, y por eso
este archivo desobedece el orden de imports habitual.

**El esquema lo construye Alembic, no `create_all()`.** Es la regla del
CLAUDE.md, y aquí además es una prueba gratis: si alguien añade una columna y
olvida la migración, los tests de API se caen en vez de pasar contra un esquema
que solo existe en los modelos.

**El test y la aplicación comparten la misma sesión.** Con dos sesiones
distintas y `expire_on_commit=False`, un objeto leído en el test antes de una
petición sigue devolviendo el valor viejo después de que la petición lo cambie:
el test verificaría un dato fantasma. Compartir la sesión elimina el problema de
raíz en vez de sembrar `refresh()` por todos lados.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

# --- Antes de importar `app`: apuntar la config a la base de datos de prueba ---
_TEST_DB = Path(tempfile.gettempdir()) / "peakstroke_test.db"
os.environ["PEAKSTROKE_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["PEAKSTROKE_AUTH_ENABLED"] = "false"
os.environ["PEAKSTROKE_ENVIRONMENT"] = "test"
# La cuenta a la que cae una petición sin cabecera de identidad. Apunta al mundo
# de prueba y no a `coach@peakstroke.dev`, que solo existe en la DB de desarrollo.
os.environ["PEAKSTROKE_DEV_USER_EMAIL"] = "owner@test.dev"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.api.v1.auth.schemas import UserCreate  # noqa: E402
from app.api.v1.auth.service import create_user  # noqa: E402
from app.api.v1.macrociclos.nomina import add_athlete  # noqa: E402
from app.api.v1.macrociclos.schemas import (  # noqa: E402
    AddAthleteRequest,
    CompetitionInput,
    EventInput,
    PlanCreate,
)
from app.api.v1.macrociclos.service import create_plan  # noqa: E402
from app.api.v1.tests.schemas import AerobicTestCreate  # noqa: E402
from app.api.v1.tests.service import create_test  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal, Base, engine, get_db  # noqa: E402
from app.core.dependencies import Principal  # noqa: E402
from app.main import app  # noqa: E402
from app.persistencia.repositorios import (  # noqa: E402
    RepositorioDeAtletas,
    RepositorioDeEquipos,
    RepositorioDeMacrociclos,
    RepositorioDeTests,
)
from app.persistencia.tablas.planes import AthleteEvent  # noqa: E402

PASSWORD = "peakstroke-test"
API = "/api/v1"


@dataclass(frozen=True)
class World:
    """Los identificadores del mundo de prueba, para no repetir consultas.

    Cubre a propósito los tres casos que en producción no se ven al desarrollar
    con datos bonitos: el entrenador que no es dueño, el atleta sin ficha de
    nadador y el nadador sin cuenta.
    """

    team_id: int
    owner_email: str            # entrenador dueño del equipo, ve todos los planes
    assistant_email: str        # entrenador asistente, NO está en plan_coaches
    sofia_email: str            # atleta con nadador y plan
    carlos_email: str           # atleta con nadador y plan — la víctima de las pruebas
    huerfano_email: str         # atleta SIN nadador ligado
    sofia_swimmer_id: int
    carlos_swimmer_id: int
    sin_cuenta_swimmer_id: int  # nadador sin cuenta de acceso
    plan_id: int
    sofia_event_id: int
    carlos_event_id: int
    sofia_test_id: int
    carlos_test_id: int


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    """Reconstruye el esquema de la DB de prueba una vez por sesión, con Alembic.

    Es síncrona a propósito: `command.upgrade` abre su propio bucle de eventos
    por dentro (`env.py` llama a `asyncio.run`), así que no puede correr desde
    una fixture async.
    """
    from alembic.config import Config

    from alembic import command

    _TEST_DB.unlink(missing_ok=True)
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    yield
    _TEST_DB.unlink(missing_ok=True)


@pytest.fixture(scope="session", autouse=True)
def _hash_cache() -> None:
    """Memoiza Argon2id durante los tests: 200 ms por hash × 5 cuentas × N tests.

    Esos 200 ms son el punto de Argon2id y no se tocan en producción — aquí solo
    se evita repetir el mismo cálculo con la misma contraseña. El primer hash es
    real, así que `verify_password` y `needs_rehash` siguen ejerciéndose de
    verdad; lo único que se pierde es que las cuentas de prueba comparten salt,
    que a nadie le importa.
    """
    from app.api.v1.auth import service as auth_service

    real = auth_service.hash_password
    cache: dict[str, str] = {}

    def memoizado(password: str) -> str:
        if password not in cache:
            cache[password] = real(password)
        return cache[password]

    auth_service.hash_password = memoizado
    yield
    auth_service.hash_password = real


async def _wipe() -> None:
    """Vacía todas las tablas conservando el esquema.

    En orden inverso de dependencias y con las FKs apagadas: `teams` y
    `team_members` se referencian en ciclo, así que no existe ningún orden de
    borrado que las satisfaga a las dos.

    El `dispose()` final no es opcional. En SQLite `PRAGMA foreign_keys` es un
    no-op dentro de una transacción, así que una vez emitido el primer DELETE ya
    no hay forma de volver a encenderlas en esa conexión. Devolverla al pool
    dejaría el test corriendo sin integridad referencial y sin avisar — justo lo
    que las FKs compuestas del esquema están ahí para impedir. Tirando el pool,
    las conexiones del test nacen otra vez por el listener de `core/database.py`,
    que las enciende.
    """
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        # `auditoria` es append-only por trigger (D0): vaciarla es justo lo que
        # la base rechaza. Se apartan los triggers, se vacía y se reponen con
        # el SQL que guarda la propia base — así el test no tiene una copia
        # que pueda divergir de la migración.
        triggers = (await conn.exec_driver_sql(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'trigger' AND tbl_name = 'auditoria'",
        )).all()
        for nombre, _ in triggers:
            await conn.exec_driver_sql(f"DROP TRIGGER {nombre}")
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
        for _, sql in triggers:
            await conn.exec_driver_sql(sql)
    await engine.dispose()


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Sesión de base de datos limpia, compartida con la aplicación.

    Cada test arranca con las tablas vacías y termina desechando el pool: cada
    test corre en su propio bucle de eventos y una conexión aiosqlite queda
    atada al bucle en el que nació.
    """
    await _wipe()
    async with AsyncSessionLocal() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncClient:
    """Cliente HTTP contra la app en memoria, sin levantar servidor ni red.

    `ASGITransport` no ejecuta el `lifespan`, así que `init_db()` no corre: el
    esquema ya lo puso Alembic y no queremos avisos de "esquema desactualizado"
    en cada test.
    """
    async def _override_get_db():
        # Sin cerrar la sesión: la gobierna la fixture `db`, no la petición.
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _auth_off(monkeypatch) -> None:
    """Estado de partida explícito: sin login, entorno de desarrollo.

    Los tests que necesiten lo contrario lo dicen (`test_dev_identity.py`); el
    resto no debería depender de qué dejó puesto el test anterior.
    """
    monkeypatch.setattr(settings, "auth_enabled", False, raising=False)
    monkeypatch.setattr(settings, "environment", "test", raising=False)


@pytest_asyncio.fixture
async def world(db: AsyncSession) -> World:
    """Un club completo: 2 entrenadores, 3 cuentas de atleta, 3 nadadores, 1 plan.

    Todo se crea por los mismos servicios que usa el API. Si el aislamiento se
    rompiera al construirlo, fallaría aquí antes que en el test.
    """
    equipos = RepositorioDeEquipos(db)
    team = await equipos.crear("Club de Prueba")

    async def cuenta(email: str, nombre: str, rol: str):
        return await create_user(
            db, UserCreate(email=email, name=nombre, password=PASSWORD, role=rol), team.id,
        )

    owner = await cuenta("owner@test.dev", "Entrenadora Dueña", "coach")
    await cuenta("asistente@test.dev", "Entrenador Asistente", "coach")
    sofia_user = await cuenta("sofia@test.dev", "Sofía Test", "athlete")
    carlos_user = await cuenta("carlos@test.dev", "Carlos Test", "athlete")
    await cuenta("huerfano@test.dev", "Atleta Sin Ficha", "athlete")

    team.owner_id = owner.id
    await db.commit()

    # Todo lo que sigue pasa por los mismos repositorios acotados que usa el API:
    # el mundo de pruebas no tiene atajos, así que si el aislamiento se rompiera,
    # fallaría aquí antes que en ningún test.
    como_owner = Principal(
        user=owner, membership=await equipos.pertenencia(owner.id), is_owner=True,
    )
    atletas = RepositorioDeAtletas(db, como_owner)
    repo = RepositorioDeMacrociclos(db, como_owner)
    tests_repo = RepositorioDeTests(db, como_owner)

    async def nadador(nombre: str, user_id: int | None):
        s = await atletas.crear(
            team_id=team.id, nombre=nombre, nacimiento=date(2008, 5, 1),
            genero="F", especialidad="medio_fondo", estilo_principal="libre",
        )
        if user_id is not None:
            s.user_id = user_id
            await db.commit()
        return s

    sofia_sw = await nadador("Sofía Test", sofia_user.id)
    carlos_sw = await nadador("Carlos Test", carlos_user.id)
    sin_cuenta_sw = await nadador("Nadador Sin Cuenta", None)

    lunes = date.today() - timedelta(days=date.today().weekday()) - timedelta(weeks=3)
    plan = await create_plan(repo, PlanCreate(
        name="Macrociclo de Prueba", start_date=lunes, total_weeks=12,
        weeks_per_micro=4, total_km=300,
        competitions=[CompetitionInput(name="Nacional", week_number=12, days=2, is_main=True)],
    ), team.id, owner.id)
    macro = await repo.recargar(plan.id)

    eventos = {}
    for swimmer in (sofia_sw, carlos_sw, sin_cuenta_sw):
        ap = await add_athlete(db, repo, macro, AddAthleteRequest(
            swimmer_id=swimmer.id, aerobic_base=75.0, aerobic_base_source="t30",
            events=[EventInput(
                priority=1, distance=200, stroke="libre",
                current_time=130.0, goal_time=125.0,
            )],
        ))
        # Consulta explícita en vez de `ap.events[0]`: la relación es lazy y
        # tocarla fuera del contexto async revienta con MissingGreenlet.
        eventos[swimmer.id] = (await db.execute(
            select(AthleteEvent.id).where(AthleteEvent.athlete_plan_id == ap.id)
        )).scalar_one()

    # Los tests aeróbicos se crean como el entrenador dueño, por el mismo camino
    # acotado que usa el API.
    tests = {}
    for swimmer in (sofia_sw, carlos_sw):
        t = await create_test(tests_repo, repo, AerobicTestCreate(
            swimmer_id=swimmer.id, plan_id=plan.id, test_type="DIRECT",
            test_date=lunes, direct_per100=75.0, notes="Base de partida",
        ), como_owner)
        tests[swimmer.id] = t.id

    mundo = World(
        team_id=team.id,
        owner_email="owner@test.dev", assistant_email="asistente@test.dev",
        sofia_email="sofia@test.dev", carlos_email="carlos@test.dev",
        huerfano_email="huerfano@test.dev",
        sofia_swimmer_id=sofia_sw.id, carlos_swimmer_id=carlos_sw.id,
        sin_cuenta_swimmer_id=sin_cuenta_sw.id,
        plan_id=plan.id,
        sofia_event_id=eventos[sofia_sw.id], carlos_event_id=eventos[carlos_sw.id],
        sofia_test_id=tests[sofia_sw.id], carlos_test_id=tests[carlos_sw.id],
    )

    # Descartar todo lo que quedó cargado al construir el mundo — después de
    # leer los ids, porque expirar un objeto hace que el siguiente acceso a
    # cualquier atributo dispare una recarga, y una recarga implícita fuera de
    # contexto async revienta con MissingGreenlet.
    #
    # Sin esto, un objeto leído a medio construir —el `Plan`, cuya lista de
    # atletas estaba vacía cuando se creó— se lo sirve la identity map al test
    # tal cual, y el test verificaría un mundo que no existe. En producción no
    # pasa: cada petición trae su propia sesión.
    db.expire_all()
    return mundo


def como(email: str) -> dict[str, str]:
    """Cabeceras que hacen que la petición se atribuya a esa cuenta.

    Solo funciona con la autenticación apagada — que es como corre el proyecto
    en desarrollo. Ver `X-PeakStroke-Dev-User` en `core/dependencies.py`.
    """
    return {"X-PeakStroke-Dev-User": email}
