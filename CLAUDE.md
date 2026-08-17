# PeakStroke — Claude Code Context

## Proyecto
Sistema de planificación y predicción de rendimiento para natación competitiva.
Hoy: aplicación web local-first para un entrenador. Mañana: SaaS multi-tenant (PWA).

## Stack
- **Backend:** FastAPI (Python 3.12+) + SQLAlchemy 2 async + SQLite (aiosqlite) + Pydantic v2
- **Frontend:** React 19 + Vite + TypeScript strict + Tailwind CSS v4
- **Estado cliente:** TanStack Query
- **Gráficos:** Recharts (tema custom) · **Animación:** GSAP · **WebGL:** Three.js
- **Iconos:** lucide-react (nunca emojis)
- **Arquitectura:** Vertical slice (feature-based) en ambos lados

## Comandos
```
# Backend (puerto 8000)
cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000

# Frontend (puerto 5173, proxy /api -> 8000)
cd frontend && npm run dev

# Tests del motor
cd backend && .venv\Scripts\python -m pytest tests/ -v

# Re-sembrar datos demo (BORRA la base y la reconstruye por migraciones)
cd backend && .venv\Scripts\python seed.py

# Migraciones — el esquema ya NO se crea solo al arrancar
cd backend && .venv\Scripts\python -m alembic upgrade head
cd backend && .venv\Scripts\python -m alembic revision --autogenerate -m "qué cambia"
cd backend && .venv\Scripts\python -m alembic current

# Crear una cuenta sin borrar datos (bootstrap del primer entrenador)
cd backend && .venv\Scripts\python tools/create_user.py --email x@y.dev --name "Ana" --role coach
```

## Reglas de código (NO negociables)
- Toda feature backend nueva: `backend/app/modules/<feature>/` con models.py / schemas.py / service.py / router.py
- `router.py` nunca tiene lógica de negocio — recibe, delega al service, retorna
- El motor científico vive en `backend/app/domain/` (port verbatim del sandbox, FUENTE DE VERDAD). `backend/app/engine/` lo adapta a los consumidores (zones, feasibility, progression). Ambos son funciones puras: jamás importan DB ni modelos
- **`backend/app/dominio/` es el rediseño POO y no importa NADA** — ni infraestructura, ni `modules/`, ni `core/`, **ni `app/domain/`**. Hoy tiene `valores/` (paso 1 del rediseño, 2026-08-16): `Tiempo`·`Duracion`·`Ritmo`·`Mejora`, `Prueba`·`Estilo`·`Piscina`, `Zona`·`Prescripcion`·`JuegoDeZonas` y las diez escalas. Todos `frozen=True, slots=True`
- **`Tiempo` es siempre positivo; lo que puede valer 0 o menos es una `Duracion`** — un nado frente a un instante, un hueco o un descanso. La salida de la primera repetición es 0 y el descanso perdido es negativo, así que mezclarlos hacía inconstruible el primer parcial de cualquier serie. Restar dos `Tiempo` da una `Mejora` (rendimiento); restar dos instantes es `Tiempo.diferencia()` (reloj). Y `Mejora.base` lleva su unidad (`Tiempo | Ritmo`): con un `float`, una mejora de ritmo salía convertida en un tiempo absoluto
- **La validez de una prueba es del constructor de `Prueba`, no de una función.** `Prueba(50, "combinado")` levanta `ValueError` y ese es el mensaje del 422; `app/engine/events.py` ya no existe. Mientras la regla convivía con las tablas del motor viejo, `tests/test_valores_vs_motor.py` compara cada tabla nueva **contra la fuente viva** — no contra números tecleados. Al retirar una copia vieja, su pin se borra con ella
- Módulos no se importan entre sí salvo lecturas explícitas de modelos; nunca lógica cruzada
- Ningún archivo supera ~300 líneas; si crece, extraer submódulo
- Type hints en todo Python; TypeScript strict en el frontend
- Frontend: cada página vive en `frontend/src/features/<feature>/`

## Reglas de dominio (natación)
- `pace_100m` es la unidad central de todos los cálculos de zonas
- Zonas ancladas al RITMO DE CARRERA × factor[perfil][distancia] (+ corrección de
  estilo, × factor piscina), calibradas con el pool nacional. Fuente de verdad:
  `backend/app/domain/engine.py` (`ZONE_OVER_RACE`); `engine/zones.py` lo adapta a
  la forma {min,mid,max} que consume el frontend
- **Una prescripción son DOS números: el ritmo y la salida.** `calc_zones`
  devuelve además `send_off` y `rest` por zona (`engine/send_off.py`), así que la
  mitad que faltaba llega sola a la tabla del equipo y al plan semanal. El
  descanso es un ratio sobre el trabajo que crece con la intensidad (R1 0.08 →
  V 3.50, con topes en segundos), y la salida se redondea **hacia arriba** al
  múltiplo de 5 s del reloj de pared: hacia abajo recortaría el descanso, que es
  como una zona se convierte en otra
- **Un test aeróbico se nada sobre un intervalo.** `aerobic_tests.send_off` y
  `aerobic_test_splits.send_off_time` lo guardan; `input_mode` dice si los
  números que apuntó el entrenador son tiempos nadados (`rep`) o llegadas
  acumuladas del reloj (`clock`). **En la base de datos siempre se guarda el
  tiempo NADADO**: la conversión la hace `create_test` una vez, al escribir. Sin
  esto, un entrenador que apuntara lo que el reloj marcaba —lo normal— producía
  una base aeróbica acumulada, y con ella zonas y predicción
- Jerarquía de zonas (lento -> rápido): R1 > R2 > MVO2 > RL > V
- Pruebas >= 400m = Tier 1 (regla aeróbica); < 400m = Tier 2 (ventanas de velocidad)
- Eje X de los gráficos: fecha real DD/MM **y** número de semana `S#` (tick de dos
  líneas: `S#` arriba, fecha abajo). El número de semana ayuda a la lectura; la fecha
  sigue siendo el ancla temporal. (Antes la regla era "solo fechas, nunca semana";
  cambiada 2026-06-24 por legibilidad — ver simulador `SimulatorPage` `renderWeekTick`.)
- La curva ideal (`expected_time`) nunca se modifica; los recálculos van en `recalc_time`
- **Curva de progresión por defecto = `"science"`** (distribución F_FASE, back-loaded,
  pico en taper). Fuente única: `domain/engine.py::science_curve_progress`, expuesta
  vía `engine/curves.py`. Sigmoide/exp/log/lineal solo comparan escenarios. La mejora
  por MACROCICLO (`I_max × N/5`) ≠ la anual: la temporada son ~3 macros encadenados
  con degradación `MACROCYCLE_DEGRADATION = 0.60`. Validado en notas 16/17 del vault
- **Proyección anual**: `ScienceEngine.project_season()` (3 macros) → `POST
  /api/v1/simulator/season`. Usa el motor de dominio directamente, no adaptadores

## Identidad y roles (backend completo 2026-08-07)
- `PEAKSTROKE_AUTH_ENABLED=false` por defecto: **la app no pide login**. Toda
  petición se atribuye a `dev_user_email` (`coach@peakstroke.dev`, contraseña
  `peakstroke`). `config.py` impide que ese modo llegue a producción
- Módulo `modules/auth/` + `core/security.py` (Argon2id + JWT) + la identidad
  repartida en cuatro archivos de `core/` (partidos el 2026-08-14):
  `principal.py` (el dataclass `Principal`, sin FastAPI), `dependencies.py`
  (resolver la petición: `get_current_user`, `get_current_principal`),
  `guards.py` (`require_coach`, `require_team_owner`, `exigir_o_bypass`) y
  `dev_identity.py` (las dos cabeceras del conmutador). `Principal` se sigue
  importando de `core.dependencies`; los guards, de `core.guards`
- **Los guards de rol comprueban el rol SIEMPRE**, también con el login apagado.
  Antes se saltaban, y con el conmutador de identidad eso permitía que un atleta
  se ascendiera a entrenador en una petición
- Recurso ajeno (de otro equipo o de otro atleta) → **404, nunca 403**. El 403 se
  reserva para "tu rol no alcanza", que es una afirmación distinta
- Cerrar sesión y cambiar la contraseña **revocan de verdad** (`token_version`),
  y el refresh token **solo sirve una vez** (`refresh_rotation`): reusar uno
  gastado se trata como robo y corta todas las sesiones

### Conmutador de desarrollo — dos cabeceras, dos ejes
Solo con `auth_enabled=false` **y** fuera de producción (`dev_identity_enabled`).
`GET /auth/config` dice en qué modo estás; `GET /auth/dev-identities` lista las
cuentas suplantables (404 con el login puesto).

```
X-PeakStroke-Dev-User: sofia@peakstroke.dev   QUIÉN eres. La interfaz que ves es
                                              la de ese rol, fielmente: un atleta
                                              recibe 403 donde recibiría 403.
X-PeakStroke-Dev-Bypass: true                 Modo desarrollador: te saltas los
                                              guards de rol SIN dejar de ver lo
                                              que ve esa persona.
```

El bypass levanta **lo que puedes hacer**, no **lo que ves**: el filtro por
nadador sigue puesto. Si levantara los dos, "modo desarrollador" y "modo
entrenador" serían lo mismo y no habrías revisado la UI de atleta. `is_developer`
no existe en la base de datos y no hay forma de persistirlo.

`seed.py` crea 7 cuentas que cubren los casos incómodos: dueño, entrenador
asistente (no dueño), dos atletas normales, atleta sin ficha de nadador, atleta
sin macrociclo y atleta con la ficha dada de baja.

En el frontend, la barra vive en **Ajustes → Desarrollo**. Quién eres se muestra
siempre desde `/auth/me`, nunca desde lo que el cliente crea haber guardado.

## Roles en el frontend
- `navConfig.ts` es la **única** lista de secciones y permisos. La consumen el
  rail, el drawer móvil y la guarda de ruta (`RutaPorRol`): esconder una sección
  del menú no la hace inalcanzable, y dos listas separadas acaban divergiendo
- `useRole()` devuelve `undefined` mientras la sesión carga. **`undefined` no es
  "sin permiso", es "todavía no se sabe"**: el rail sale vacío y las rutas
  esperan, en vez de decidir con un valor que aún no existe
- `useIsCoach()` / `useIsOwner()` / `useIsAthlete()` — nadie calcula el rol a mano
- Lo que cambia entre roles va en un módulo aparte (`dashboard/vistaPorRol.ts`),
  no en `if (isAthlete)` repartidos por la página
- **Nunca una restricción solo en la UI sobre un endpoint abierto.** Esconder un
  botón cuyo endpoint acepta la petición es teatro: se cierra el backend primero

## Equipos, roles y aislamiento (NO negociable)
- El **equipo es la frontera de todo**: `swimmers`, `plans` y `aerobic_tests`
  llevan `team_id` NOT NULL. Una persona pertenece a un equipo y solo a uno
- **El rol vive en `team_members`, no en `users`.** `users` es solo identidad
  (email, hash, nombre). Ser entrenador es algo que se es *en* un club
- **Entrenador en jefe = entrenador que además es `teams.owner_id`.** No es un
  tercer rol. El dueño es único y transferible (`POST /teams/mine/transfer`)
- El **atleta es del equipo**, no de un entrenador: `coach_athletes` (M:N) dice
  quién lo lleva; `plan_coaches` (M:N), qué entrenadores llevan cada macrociclo
- **Ficha (`Swimmer`) y cuenta (`User`) son la misma persona.** Lo único que las
  separa es si alguien canjeó ya el código. El vínculo lo crea
  `modules/link_codes/`: lo emite el entrenador sobre una ficha suya y lo canjea
  la persona desde su perfil — caduca a las 72 h, sirve una vez y emitir uno
  nuevo revoca el anterior. **Ningún endpoint liga las dos por sí solo**; el
  desplegable de `MemberCreate.swimmer_id` se retiró el 2026-08-09
- **Un atleta se da de alta por su correo, en un gesto** (2026-08-10):
  `POST /link-codes/invite` crea la ficha, la cuenta si no la tenía, y el código
  dirigido a ese correo. Reinvitar al mismo correo reutiliza la ficha pendiente y
  reemite. `MemberCreate` quedó para **entrenadores**: son los únicos sin ficha
  deportiva, así que su alta sí es otro gesto. Dos formularios para atleta —uno
  que creaba media persona y otro la otra mitad— es lo que había antes
- **La cuenta sin equipo es un estado legítimo**, no un error: existe en el
  sistema y no pertenece a ningún club. Es el pool global. Entra, ve su perfil y
  sus solicitudes de ingreso, y nada más; `Principal` sigue devolviendo 403 en
  todo lo demás. `role` y `team_id` viajan a `None` juntos
- **Revocado ≠ sin equipo.** `get_membership` filtra `is_active` y devuelve
  `None` en los dos casos, así que quien decida sobre el login o sobre `/auth/me`
  **tiene que pedir `include_inactive=True`** para separarlos. Confundirlos deja
  entrar a quien acabas de echar, ahora como cuenta del pool, y desde ahí puede
  canjear un código para volver a un club
- `get_current_user` en vez de `get_current_principal` solo en **tres**
  endpoints, y los tres por la misma razón (quien llama puede no ser de ningún
  equipo todavía): `POST /link-codes/redeem`, `GET /link-codes/mine` y
  `GET /auth/me`. Cualquier otro uso de esa dependencia es un error — sin
  `Principal` no hay `team_id` que aplicar
- **Un atleta, un macrociclo vivo** (`plans/enrollment.py`). Es una regla de
  dominio, no de permisos: dos macros a la vez son dos planes contradictorios
  para las mismas fechas, así que bloquea **a todos, dueño incluido**. De ahí
  sale, de rebote, que un atleta ya inscrito no le aparezca a otro entrenador
  para meterlo en uno nuevo. `GET /plans/{id}/assignable-athletes` enseña la
  regla por adelantado; el POST y el `restore` la imponen
- **`plan_coaches` decide visibilidad**: un entrenador que no esté en la lista no
  ve ni edita ese macrociclo. **Excepción: el dueño**, que llega a todos — sin eso
  los planes de un entrenador que se va quedarían huérfanos
- **Toda consulta pasa por `Principal`** (`core/principal.py`): usuario +
  pertenencia + propiedad. `plans.service.visible_to()` es la única puerta a los
  macrociclos; nada la esquiva
- `team_id` sale **siempre de la sesión**, nunca del cuerpo de la petición
- Recurso de otro equipo → **404, nunca 403**: un 403 confirmaría que existe
- El primer equipo y su dueño se crean con
  `python tools/create_user.py --new-team "Nombre" --role coach`

## Integridad y borrado
- **Las FKs se aplican de verdad**: `core/database.py` activa `PRAGMA
  foreign_keys=ON` en cada conexión SQLite. Sin eso son decorativas en local y
  solo se aplicarían en PostgreSQL — el peor sitio para descubrirlo
- **FKs compuestas contra `(id, team_id)`** en toda tabla de relación: la base de
  datos hace imposible mezclar equipos aunque el código tenga un bug
- **Nada se borra: se da de baja.** `swimmers.is_active`, `team_members.is_active`,
  `users.is_active`. `DELETE /swimmers/{id}` desactiva y devuelve el atleta
- `ondelete=CASCADE` solo donde hay composición real (plan → fases, test →
  parciales). El resto usa el defecto, que impide borrar mientras algo lo referencie

## Esquema de base de datos
- **Alembic es la única fuente del esquema.** `init_db()` ya no hace `create_all()`:
  solo avisa por log si la DB no está en `head`
- **Todo modelo nuevo va en `app/core/model_registry.py`.** SQLAlchemy resuelve
  las FKs contra `Base.metadata`, no contra los imports: un modelo que nadie
  importe hace reventar cualquier FK que lo apunte con `NoReferencedTableError`
  al primer INSERT, aunque la tabla exista en la DB. Antes lo cubría de rebote el
  `create_all()` de `init_db()`
- El registry también lo importa **`seed.py`**, y no es decorativo: `reset_schema`
  usa `drop_all`, que solo conoce el metadata. Sin el import, la tabla de un
  módulo que el seed no toca sobrevive al borrado y `alembic upgrade` revienta
  con "table already exists" (le pasó a `link_codes` el 2026-08-10)
- Toda tabla o columna nueva requiere su migración; `--autogenerate` compara contra
  los modelos importados en `alembic/env.py` (si no está importado ahí, es invisible)
- `render_as_batch=True` para SQLite (no sabe hacer `ALTER COLUMN`)
- Reglas de portabilidad SQLite→PostgreSQL: nada de `JSONB`/`citext`/enums nativos,
  emails normalizados a minúsculas en el service, `DateTime(timezone=True)` siempre

## Camino al SaaS (parcialmente montado)
- DB: SQLite en local; `docker-compose.yml` (raíz) trae PostgreSQL 17 listo para
  cuando toque desplegar — basta `pip install asyncpg` y apuntar
  `PEAKSTROKE_DATABASE_URL`. El código no cambia
- Falta el módulo `billing/` (Stripe) y los tier guards:
  `core/tier_limits.py` + dependencia `require_feature()`

## Archivos de referencia
- README.md — bitácora completa del proyecto
- ../oficial/PLAN_IMPLEMENTACION.md — plan de fases SaaS
- ../mockup.html — prototipo visual original (referencia, no copiar)

## Agent skills

### Issue tracker

Issues y PRDs viven en GitHub Issues de `diegofallas2204/PeakStroke` (vía `gh`). Los PRs externos NO son superficie de triage. Ver `docs/agents/issue-tracker.md`.

### Triage labels

Vocabulario canónico (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`); aún no existen en el repo — crear con `gh label create` la primera vez. Ver `docs/agents/triage-labels.md`.

### Domain docs

Single-context: un `CONTEXT.md` + `docs/adr/` en la raíz cubren todo el producto. Ver `docs/agents/domain.md`.
