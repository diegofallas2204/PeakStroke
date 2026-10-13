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

## Ramas
- **Se trabaja en `Preliminar`.** Todo commit del día a día va ahí
- **`main` recibe solo fases completadas**: cuando lo que se está montando está entero, PR de `Preliminar` contra `main` con merge commit (no squash), y se sigue en `Preliminar` con lo siguiente. Nunca commitear directo en `main`

## Reglas de código (NO negociables)
- **Un agregado se reparte en tres capas, no en una carpeta** (paso 5 del rediseño, 2026-08-25): su tabla en `app/persistencia/tablas/<agregado>.py`, su repositorio en `app/persistencia/repositorios/<agregado>.py`, y su router + schemas + presentación en `app/api/v1/<agregado>/`. **`app/modules/` ya no existe.** Hoy hay ocho agregados —`atletas` · `codigos` · `equipos` · `macrociclos` · `resultados` · `sesiones` · `tests_aerobicos` · `usuarios`— más la tabla derivada `carga_diaria`, y diez rebanadas de API (siete de ellos + `carga`, de solo lectura, + `simulador`, que no tiene tabla, + `vistas`). `resultados` (C6) no tiene rebanada propia: lo leen `macrociclos` y `vistas` por su repositorio. `sesiones` (C7) es el primero cuyo repositorio **recibe y devuelve entidades** (`guardar(Sesion)`), no filas
- **`app/api/v1/vistas/` son pantallas compuestas, NO agregados**: el tablero, la tabla del equipo y la comparación no tienen modelo, no escriben y no imponen ninguna regla. Leen de los repositorios y dan forma. Cuando el tablero era `modules/dashboard/` parecía un módulo de dominio y se comportaba como tal — importaba `plans.access`, `plans.service` y tres modelos para poder preguntar en qué semana iba un plan
- **Feature backend nueva:** una tabla, un repositorio y una rebanada de API. Si no tiene tabla propia (como el simulador) es solo la rebanada; si no impone reglas ni escribe, es una vista
- `router.py` nunca tiene lógica de negocio — recibe, delega al service, retorna
- **El motor científico es UNO y vive en `backend/app/dominio/servicios/`** (paso 4 del rediseño, 2026-08-17): `MotorCientifico` (fachada) sobre `tablas` · `curvas` · `envolvente` · `kilometraje` · `zonas` · `plan` · `temporada`. Funciones puras que no importan nada de fuera, como el resto de `dominio/`.
  Lo que decía este bullet —«`app/domain/` es la FUENTE DE VERDAD y `app/engine/` lo adapta»— **era falso**: `ScienceEngine.generate_plan()` solo corría en los tests y los planes que se guardaban salían de `app/engine/progression.py`. Dos algoritmos que compartían las tablas pero no el cálculo, y por eso divergieron tres veces. **`app/domain/` ya no existe**, y de `app/engine/` solo quedan `aerobic.py` (análisis del test, que no es motor) y `time_utils.py` (formato)
- **`backend/app/dominio/` es el rediseño POO y no importa NADA** — ni infraestructura, ni `api/`, ni `persistencia/`, ni `core/`. Lo comprueba `tests/test_entidades.py` al revés: todo import absoluto tiene que ser de la biblioteca estándar. Hoy tiene `valores/` (paso 1, 2026-08-16): `Tiempo`·`Duracion`·`Ritmo`·`Mejora`, `Prueba`·`Estilo`·`Piscina`, `Zona`·`Prescripcion`·`JuegoDeZonas` y las diez escalas, todos `frozen=True, slots=True`; y `entidades/` (paso 2, 2026-08-16): `Atleta`, `Macrociclo`·`FaseDelMacro`·`Competencia`, `TestAerobico`·`Parcial`. Las entidades son mutables y **se comparan por `id`, no por valor** (`base.PorIdentidad`): dos atletas homónimos son dos personas; `roles/` (paso 3, 2026-08-17): `Rol` abstracto con `Administrador`·`EntrenadorEnJefe`·`Entrenador`·`AtletaRol`, objetos **sin estado** que contestan `puede_ver`/`puede_escribir`/`alcance_de_atletas`/`alcance_de_macrociclos`/`secciones_visibles`; y `servicios/` (paso 4, 2026-08-17): el motor científico **único** — `MotorCientifico` de fachada sobre `tablas`·`curvas`·`envolvente`·`kilometraje`·`zonas`·`plan`·`intervalos`·`temporada`
- **La entidad se construye desde la fila; no la envuelve.** La traducción vive en `backend/app/persistencia/mapeo/`, del lado de fuera (`api → persistencia → dominio`, y el dominio no apunta a nada). Un envoltorio con la instancia del ORM dentro escribiría en la sesión al mutarse —dejando sin trabajo a los repositorios del paso 5— y se podría construir alrededor de cualquier fila, que es justo lo que rompe la invariante del `TestAerobico`
- **Las funciones que las entidades sustituyen se quedan como envoltorio y se vacían después**: `core/dates.age_at` → `Atleta.edad_en()`. Ninguna conserva ya su copia de la regla. `plans/service.current_week_of` y `effective_status` **ya no existen**: el paso 5 las borró en vez de dejarlas delegando, porque un envoltorio que delega sigue siendo un import que cruza — y mientras hay un sitio al que importar, alguien importa
- **`Tiempo` es siempre positivo; lo que puede valer 0 o menos es una `Duracion`** — un nado frente a un instante, un hueco o un descanso. La salida de la primera repetición es 0 y el descanso perdido es negativo, así que mezclarlos hacía inconstruible el primer parcial de cualquier serie. Restar dos `Tiempo` da una `Mejora` (rendimiento); restar dos instantes es `Tiempo.diferencia()` (reloj). Y `Mejora.base` lleva su unidad (`Tiempo | Ritmo`): con un `float`, una mejora de ritmo salía convertida en un tiempo absoluto
- **La validez de una prueba es del constructor de `Prueba`, no de una función.** `Prueba(50, "combinado")` levanta `ValueError` y ese es el mensaje del 422; `app/engine/events.py` ya no existe. Mientras la regla convivía con las tablas del motor viejo, `tests/test_valores_vs_motor.py` compara cada tabla nueva **contra la fuente viva** — no contra números tecleados. Al retirar una copia vieja, su pin se borra con ella
- **Entre rebanadas del API no se importa NADA.** Ni siquiera modelos: las tablas están en `persistencia/tablas/`, así que leer una fila ajena es mirar hacia abajo y no de lado. **Ya no es una convención**: `tests/test_dependencias_de_capas.py` lo comprueba por AST, y su lista `VIOLACIONES_CONOCIDAS` está **vacía**. `tools/grafo_de_imports.py` imprime el grafo y marca las flechas que suben (hoy: ninguna)
- **Para preguntarle algo a otro agregado, se pide al repositorio, no se importa al vecino.** `RepositorioDeMacrociclos(db, principal)` devuelve un `Macrociclo` que ya sabe su semana actual y su estado efectivo; `acotar(stmt)` acota cualquier consulta al alcance de quien pregunta. Los repositorios se piden como dependencia de FastAPI desde `app/api/dependencias.py`
- **Tres repositorios NO llevan `Principal`, y está razonado**: `equipos`, `usuarios` y `codigos`. El equipo *es* la frontera que los demás aplican y `Principal` se construye a partir de lo que devuelve; y la mitad de las lecturas de códigos las hace quien todavía no pertenece a ningún club. Lo que las sostiene es la regla de siempre: **el `team_id` sale de la sesión, nunca del cuerpo de la petición**
- **Estos agregados ya se escriben por su entidad**: `sesiones` (C7, `guardar(Sesion)`), las **inscripciones** (C9 punto 2, 2026-10-05: `Macrociclo.inscribir()` exige ficha del club y activa —y devolver (`restore`) también—, `Inscripcion.dar_de_baja()/restaurar()` idempotentes, `RepositorioDeInscripciones` **compone** al de macrociclos y reutiliza su `acotar`; las rutas de nómina viven en `api/v1/macrociclos/router_nomina.py`) y `atletas` (C9 punto 1, 2026-10-05): crear, editar, dar de baja y restaurar una ficha pasan por `Atleta` —`Atleta.nueva(...)`, `dar_de_baja()`/`restaurar()`, idempotentes y que devuelven si cambiaron— y `RepositorioDeAtletas.guardar(atleta)` es la única puerta a la fila (el alta del entrenador, la invitación y el seed por igual). `guardar` **no escribe `user_id`**: ligar ficha y cuenta es del canje del código. **Y las pruebas objetivo** (C9 punto 3, 2026-10-13): `EventInput.a_entidad()` construye la `PruebaObjetivo` (una `Prueba` y dos `Tiempo`; el estilo sale canónico, «crol» → «libre»), `nomina.py` le pide al motor su plan y `RepositorioDeInscripciones.guardar(inscripcion, pruebas=[(prueba, semanas)])` arma las filas en la misma transacción — **`api/v1/macrociclos/nomina.py` no importa ninguna tabla**, y un test lo comprueba. Los umbrales del veredicto de factibilidad viven en `valores.Veredicto.del_uso`, que usan el motor y `PruebaObjetivo.factibilidad(techo)`. **Y la semana** (C9 punto 4, 2026-10-13): `RepositorioDeSemanas` —que **compone** al de macrociclos, como el de inscripciones— entrega un `PlanDePrueba` (macrociclo, inscripción, ficha, prueba y semanas, todo entidades); `semanas.py` les pide a las `Semana` que cambien (`parar`/`reanudar`/`reanclar`) y `guardar` escribe **solo** el recalculado, el parón y su razón. **`Semana.esperado` no se puede reasignar y el repositorio no lo escribe**: «la curva ideal nunca se modifica» ya no depende de que nadie se acuerde. El recálculo se sigue orquestando en `semanas.py` porque llama al motor y las entidades no importan los servicios. **La nómina y las semanas ya no arman filas del ORM desde `api/v1/`** (`nomina.py` y `semanas.py` no importan tablas; un test lo comprueba). **El macrociclo en sí todavía sí**: crear, editar y borrar un plan (`macrociclos/service.py`) construyen `Plan`, `PlanPhase` y `Competition` a mano — `Macrociclo` tiene consultas e `inscribir()`, pero no se escribe por la entidad. Las **vistas** (tablero, tabla del equipo, intervalos) siguen leyendo las semanas como filas por `pruebas_de()`: no escriben. Lo que queda de C9 está en la cabecera de `docs/REDISENO.md`
- **Insertar un hijo por su FK no actualiza la colección del padre ya cargado.** Si una ruta lee una fila con `selectinload`, inserta un hijo con `padre_id=...` y relee para responder, la relectura devuelve el objeto que sigue vivo en la sesión con la colección de antes — o no, según haya pasado el recolector de basura. Le pasó al alta de un atleta (la respuesta salía sin el recién inscrito; 2026-10-13). El repositorio que inserta expira la colección (`_olvidar_la_nomina_de`), y se prueba con `gc.disable()` alrededor de la petición. Quedan rutas por mirar: TODO-22
- Ningún archivo supera ~300 líneas; si crece, extraer submódulo
- Type hints en todo Python; TypeScript strict en el frontend
- Frontend: cada página vive en `frontend/src/features/<feature>/`

## Reglas de dominio (natación)
- `pace_100m` es la unidad central de todos los cálculos de zonas
- Zonas ancladas al RITMO DE CARRERA × factor[perfil][distancia] (+ corrección de
  estilo, × factor piscina), calibradas con el pool nacional. Fuente de verdad:
  `dominio/valores/zona.py` (`factores_de_zona`), y quien las calcula es
  `MotorCientifico.zonas()`, en la forma {min,mid,max} que consume el frontend
- **Una prescripción son DOS números: el ritmo y la salida.** `MotorCientifico.zonas()`
  devuelve además `send_off` y `rest` por zona (ratios y topes en `valores.Zona`), así que la
  mitad que faltaba llega sola a la tabla del equipo y al plan semanal. El
  descanso es un ratio sobre el trabajo que crece con la intensidad (R1 0.08 →
  V 3.50, con topes en segundos), y la salida se redondea **hacia arriba** al
  múltiplo de 5 s del reloj de pared: hacia abajo recortaría el descanso, que es
  como una zona se convierte en otra
- **Un test aeróbico se nada sobre un intervalo.** `aerobic_tests.send_off` y
  `aerobic_test_splits.send_off_time` lo guardan; `input_mode` dice si los
  números que apuntó el entrenador son tiempos nadados (`rep`) o llegadas
  acumuladas del reloj (`clock`). **En la base de datos siempre se guarda el
  tiempo NADADO**. Sin esto, un entrenador que apuntara lo que el reloj marcaba
  —lo normal— producía una base aeróbica acumulada, y con ella zonas y predicción.
  Desde el paso 2 del rediseño (2026-08-16) **ya no es una regla que `create_test`
  tenga que acordarse de aplicar**: la conversión ocurre en el constructor de
  `dominio.entidades.TestAerobico`, que recibe lo que apuntó el entrenador y el
  modo, y no admite `Parcial` ya hechos. No queda puerta por la que unas llegadas
  sin convertir vuelvan a entrar
- Jerarquía de zonas (lento -> rápido): R1 > R2 > MVO2 > RL > V
- Pruebas >= 400m = Tier 1 (regla aeróbica); < 400m = Tier 2 (ventanas de velocidad)
- Eje X de los gráficos: fecha real DD/MM **y** número de semana `S#` (tick de dos
  líneas: `S#` arriba, fecha abajo). El número de semana ayuda a la lectura; la fecha
  sigue siendo el ancla temporal. (Antes la regla era "solo fechas, nunca semana";
  cambiada 2026-06-24 por legibilidad — ver simulador `SimulatorPage` `renderWeekTick`.)
- La curva ideal (`expected_time`) nunca se modifica; los recálculos van en `recalc_time`
- **El nivel del atleta sale de su test aeróbico cuando lo hay** (`AthletePlan.aerobic_base`),
  y solo si no lo hay se estima desde el ritmo de carrera. La tabla de niveles está
  calibrada para un umbral medido de 400/1500: alimentarla con el ritmo de un 200 deja
  un borde de una décima que cambia el volumen prescrito un 45 % (defecto 1 de §10.4,
  cerrado el 2026-08-17). El alta en el macrociclo y el recálculo pasan los dos el
  mismo dato — si solo lo pasara uno, el atleta tendría dos niveles según la puerta
- **La curva de un plan real es SIEMPRE la científica** (R7, 2026-09-23): `Macrociclo.curva`
  es una propiedad fija, `plans` ya no tiene `progression_curve` y el asistente no la
  ofrece. Distribución F_FASE, back-loaded, pico en taper; fuente única
  `dominio/servicios/curvas.py::Cientifica`, que deriva sus tramos de `MACRO_15_FASES`
  y `Fase.f_fase`. Sigmoide/exp/log/lineal **solo existen en el simulador**, porque
  cambian el veredicto que ve el atleta: el mismo nado sale `AHEAD` con la científica
  y `BEHIND` con la exponencial. La mejora
  por MACROCICLO (`I_max × N/5`) ≠ la anual: la temporada son ~3 macros encadenados
  con degradación `MACROCYCLE_DEGRADATION = 0.60`. Validado en notas 16/17 del vault
- **Las fases del macrociclo son las cinco de `Fase`** (P3, 2026-09-22):
  `base_general` · `base_especifica` · `umbral_css` · `pre_competitivo` · `taper`.
  `plan_phases.type` y `weekly_plans.phase` guardan la **clave** (un CHECK lo
  impone), nunca la etiqueta; el nombre del tramo es texto libre del entrenador y
  es lo que se enseña. Los cuatro tramos de antes (`base|build|peak|taper`) ya no
  existen: dan 422. Las fases por defecto las da el motor
  (`servicios/plan.fases_por_defecto`, la forma de `MACRO_15_FASES` escalada) y el
  asistente las pide a `GET /plans/default-phases` — no hay copia en el frontend
- **Carga de entrenamiento = sTSS de la sesión** (`Sesion.carga(css)`), con el CSS
  del último test ≤ esa fecha (T15/libre solo a falta de otro). Banister en
  `dominio/servicios/banister.py`: la serie arranca **en equilibrio** (CTL₀ = ATL₀
  = media de los primeros 14 días; con CTL₀ = 0 las alertas salían falsas durante
  meses), y las alertas son TSB < −25 / < −40, TSB < 0 más de 14 días y CTL +7 en
  una semana — convención de la práctica, no ciencia revisada, y en escala sTSS
- **Proyección anual**: `MOTOR.proyectar_temporada()` (3 macros) → `POST
  /api/v1/simulator/season`. Estilo y piscina no entran: solo lee el techo
  realista de cada macro, que es de la distancia y el nivel

## Identidad y roles (backend completo 2026-08-07)
- `PEAKSTROKE_AUTH_ENABLED=false` por defecto: **la app no pide login**. Toda
  petición se atribuye a `dev_user_email` (`coach@peakstroke.dev`, contraseña
  `peakstroke`). `config.py` impide que ese modo llegue a producción
- Rebanada `api/v1/auth/` + repositorio `persistencia/repositorios/usuarios.py` + `core/security.py` (Argon2id + JWT) + la identidad
  repartida en cuatro archivos de `core/` (partidos el 2026-08-14):
  `principal.py` (el dataclass `Principal`, sin FastAPI), `dependencies.py`
  (resolver la petición: `get_current_user`, `get_current_principal`),
  `guards.py` (`require_coach`, `require_team_owner`, `exigir_o_bypass`) y
  `dev_identity.py` (las dos cabeceras del conmutador). `Principal` se sigue
  importando de `core.dependencies`; los guards, de `core.guards`
- **El rol es un objeto, no una cadena** (paso 3 del rediseño, 2026-08-17).
  `Principal` **compone** un `Rol` de `app/dominio/roles/` —`principal.rol`, que
  `core/principal.rol_de` construye desde `team_members.role` + si es
  `teams.owner_id`— y los servicios preguntan al rol en vez de encadenar `if`:
  `visible_to` mira `alcance_de_macrociclos()`, el parón de la semana mira
  `puede_escribir(Recurso.PARON_DE_SEMANA)`. Quedan dos ejes FUERA de la
  jerarquía y a propósito: ser dueño es una columna (`require_owner` sigue
  preguntando `is_owner`) y `is_developer` no es un rol. `Administrador` existe
  solo como hueco: ninguna clave lo construye, y una clave desconocida levanta
  `ValueError` en vez de adivinar
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
  `api/v1/codigos/`: lo emite el entrenador sobre una ficha suya y lo canjea
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
- **Un atleta, un macrociclo vivo** (`api/v1/macrociclos/inscripcion.py`). Es una regla de
  dominio, no de permisos: dos macros a la vez son dos planes contradictorios
  para las mismas fechas, así que bloquea **a todos, dueño incluido**. De ahí
  sale, de rebote, que un atleta ya inscrito no le aparezca a otro entrenador
  para meterlo en uno nuevo. `GET /plans/{id}/assignable-athletes` enseña la
  regla por adelantado; el POST y el `restore` la imponen
- **`plan_coaches` decide visibilidad**: un entrenador que no esté en la lista no
  ve ni edita ese macrociclo. **Excepción: el dueño**, que llega a todos — sin eso
  los planes de un entrenador que se va quedarían huérfanos
- **Ver no es poder borrar** (R4, 2026-09-24): borrar un macrociclo y cambiar
  su meta (`main_event`) son **de dueño**, aunque el asistente lo lleve
- **Toda consulta pasa por `Principal`** (`core/principal.py`): usuario +
  pertenencia + propiedad. `RepositorioDeMacrociclos.acotar()` es la única
  puerta a los macrociclos; nada la esquiva. El repositorio **se construye con
  el `Principal`**, así que el alcance no es un argumento que se pueda olvidar
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
- **El tiempo nadado es del atleta, no del plan** (C6, 2026-09-22): vive en
  `resultados`, con FK al nadador y **ninguna** al plan, así que ni sacar a
  alguien del macro ni borrar el macro lo tocan. La semana **no** guarda su
  tiempo: promedia los resultados del atleta en esa prueba y esa semana,
  convertidos a la piscina del macro. `weekly_plans.real_time` **ya no existe**
  (C7, migración `c7a1e0d5b2f4`)
- **La sesión guarda hechos, no derivados** (C7, 2026-09-23): `sesiones` lleva
  fecha, metros, duración total (descansos incluidos) y RPE CR-10 del atleta.
  El ritmo medio y la carga (sTSS) se calculan al leer, y las zonas y
  prescripciones no se guardan en ningún sitio. Cuelga del atleta y **no apunta
  a la semana ni al macro**: se encuentran por fecha. **Es la excepción a «nada
  se borra»**: se borra de verdad, porque es un registro que su dueño corrige y
  la carga de C8 se recalcula desde lo que haya
- **`carga_diaria` es un derivado materializado** (C8, 2026-09-23): sTSS del día,
  CTL y ATL de Banister. **La escribe solo `persistencia/repositorios/carga.recalcular`**,
  y la llaman —antes de confirmar, en la misma transacción— las cuatro escrituras
  que la cambian: guardar/borrar sesión y alta/baja de test aeróbico (el test fija
  el CSS). Una escritura nueva que toque sesiones o tests **tiene que llamarla**;
  `tests/test_carga.py` comprueba que la tabla es el cálculo desde cero
- `ondelete=CASCADE` solo donde hay composición real (plan → fases, test →
  parciales). El resto usa el defecto, que impide borrar mientras algo lo referencie

## Auditoría (D0, 2026-09-24)
- **Un evento de seguridad = `auditar(TipoDeEvento.X, quien, ...)`** (`core/auditoria.py`),
  llamado en el router **después** de que la operación se confirme. Es síncrona y
  no toca la base: apunta en el contexto de la petición, y `MiddlewareDeAuditoria`
  lo escribe en una sesión propia **cuando la respuesta ya salió**. Si escribir
  falla, la petición ya terminó bien y el log recibe un `ERROR` con los eventos
  perdidos. Medido: +0,03 ms en una petición sin eventos; con uno, la respuesta
  sale igual de rápido y el volcado ocupa ~11 ms del proceso después
- **Una operación nueva que sea de seguridad** (acceso, pertenencia, propiedad,
  bajas, borrados de verdad) **añade su `TipoDeEvento` y su `auditar`**. Si es de
  acceso, va también en `TIPOS_DE_ACCESO` y en el filtro de las dos vistas de
  eventos (`test_auditoria_vistas.py` compara los tres)
- `auditoria` es **append-only por trigger**: la base rechaza `UPDATE`, y `DELETE`
  de lo que tenga menos de 24 meses. La única escritura que borra es
  `tools/purgar_auditoria.py` (cron mensual). Sin FKs: el rastro sobrevive a lo
  que describe, y el correo del actor va denormalizado
- **Una IP nunca llega entera al disco** (R11, opción C): red truncada (/24, /48)
  + HMAC con una clave que rota cada 30 días y se BORRA al rotar
  (`claves_de_auditoria`). El user-agent, solo como familia («Chrome · Windows»).
  `X-Forwarded-For` se ignora hasta que haya un proxy de confianza
- **`v_admin_accesos` · `v_admin_actividad` · `v_admin_cuentas` · `v_admin_equipos`
  son el único contrato de lectura de PSAdmin.** Ninguna lee tablas deportivas
  ni la de claves; `test_auditoria_vistas.py` fija qué tablas lee y qué columnas
  expone cada una. Accesos y actividad se reparten los tipos de evento sin
  solaparse (un test lo comprueba), y actividad no lleva IP. Cambiar una vista es
  una migración, no un `CREATE VIEW` a mano

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
- **Las vistas no están en el metadata**: `seed.py` las borra aparte antes de
  `drop_all` (si no, la migración que las crea revienta con "view already
  exists"). Y `env.py` llama a `fileConfig(..., disable_existing_loggers=False)`:
  con el valor por defecto, migrar dentro del proceso (tests, seed) apagaba
  todos los loggers de la app
- Reglas de portabilidad SQLite→PostgreSQL: nada de `JSONB`/`citext`/enums nativos,
  emails normalizados a minúsculas en el service, `DateTime(timezone=True)` siempre
- **El SQL crudo de una migración tiene que valer en los dos motores** (la cadena
  corrió por primera vez en PostgreSQL el 2026-09-25 y se rompió en tres sitios):
  booleanos como `TRUE`/`WHERE is_active`, nunca `1`/`= 1`; nada de `IS NOT 'x'`
  (solo SQLite); lo que sea de un motor, detrás de `op.get_bind().dialect.name`.
  Y en `op.create_table`, **una FK con `use_alter=True` no se crea en PostgreSQL**,
  y una clave primaria que forma parte de una FK compuesta necesita
  `autoincrement=True` también en la migración — si no, nace sin secuencia (le
  pasó a `teams`, arreglado en `b2d7f5a8c1e4`)

## Camino al SaaS (parcialmente montado)
- DB: SQLite en local; `docker-compose.yml` (raíz) trae PostgreSQL 17 listo para
  cuando toque desplegar — `docker compose up -d db`, `pip install asyncpg` y
  apuntar `PEAKSTROKE_DATABASE_URL`. **Probado el 2026-09-25**: la cadena de
  migraciones sube y baja entera, `alembic check` limpio y `seed.py` corre
  (resetea con `DROP SCHEMA public CASCADE`). Hizo falta arreglar tres
  migraciones y añadir una; la suite de tests sigue corriendo solo en SQLite
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
