# PeakStroke — Performance Planner para Natación Competitiva

Sistema de planificación de macrociclos y predicción de rendimiento para
entrenadores de natación de alto rendimiento. Hoy es una aplicación web
local-first para un club; está construida para convertirse en SaaS multi-club
sin reescrituras: equipos aislados, roles, auditoría y PostgreSQL ya probados.

![Stack](https://img.shields.io/badge/FastAPI-Python_3.12+-009688) ![Frontend](https://img.shields.io/badge/React_19-TypeScript_strict-3178c6) ![UI](https://img.shields.io/badge/Tailwind_v4-GSAP_·_Three.js-8b5cf6) ![DB](https://img.shields.io/badge/SQLite_·_PostgreSQL_17-Alembic-336791)

![Dashboard](docs/dashboard.png)
*Capturas de junio de 2026, anteriores al rediseño del frontend:
[tabla del equipo](docs/tabla-equipo.png) · [comparación](docs/comparacion.png) ·
[base aeróbica](docs/base-aerobica.png) · [simulador](docs/simulador.png)*

---

## 1. Qué hace el sistema

PeakStroke responde las preguntas centrales de un entrenador:

- *¿Es realista bajar de 1:07.8 a 1:04.5 en 12 semanas?* → **Factibilidad**
- *¿Qué tiempo exijo cada semana, a qué ritmo y con qué salida en cada zona?* → **Plan semanal y tabla del equipo**
- *¿El atleta va adelantado o atrasado respecto al plan?* → **Progresión real vs. esperada**
- *¿Cuál es la base aeróbica real del atleta?* → **Tests T-30 / T-15 / N×D / CSS**
- *¿Está acumulando fatiga?* → **Carga de entrenamiento (Banister: CTL / ATL / TSB)**
- *¿Qué pasa si cambio semanas, kilómetros o la meta? ¿Y en la temporada entera?* → **Simulador**

---

## 2. Estado — octubre de 2026

| | |
|---|---|
| **Rediseño POO** (`docs/REDISENO.md`) | Los ocho pasos son código. Todo agregado se escribe por su entidad; quedan solo decisiones aparcadas (tablas en español, N1/N2) |
| **Plan de trabajo** (`docs/PLAN-DE-TRABAJO.md`) | Partes A, B y C hechas; D0 (auditoría) y D1 (CLI de operaciones) hechos. Quedan **D2** y **D3** (PSAdmin) |
| **Identidad** | Backend completo: login, refresh rotado, una sesión por dispositivo, revocación. **El frontend aún no tiene pantalla de login**: la app corre con `PEAKSTROKE_AUTH_ENABLED=false` |
| **Tests** | 1516 en el backend (pytest); en el frontend, `tsc` y `eslint` |
| **Base de datos** | SQLite en local; la cadena de migraciones corre también en PostgreSQL 17 |

Lo que falta está en `TODOS.md` (los abiertos: TODO-1, 2, 3, 17, 18, 20, 21, 27,
28, 29 y 31) y en la sección [12](#12-qué-queda).

---

## 3. Secciones de la aplicación

Las secciones dependen del rol. La lista única de secciones y permisos es
`frontend/src/components/layout/navConfig.ts`: la usan el menú, el drawer móvil
y la guarda de ruta, así que esconder una sección y bloquearla son la misma cosa.

| Sección | Rol | Qué hace |
|---|---|---|
| **Dashboard** | todos | Pulso del macrociclo de trabajo: semana actual, franja de fases, estados del equipo, cumplimiento de registro, desviación media y próxima competencia. El atleta ve su versión (`dashboard/vistaPorRol.ts`) |
| **Macrociclos** | entrenador | Asistente de creación: semanas, micros 3:1 o 4:1, km totales, piscina. Las **cinco fases de la ciencia** (base general · base específica · umbral CSS · pre-competitivo · taper) llegan propuestas por el motor y el entrenador les pone nombre. Competencias por semana, nómina de atletas, estados (activo, completado, suspendido) |
| **Atletas** | entrenador | El pool del club. Alta **por correo en un gesto**: crea la ficha, la cuenta y el código de vinculación. Cada tarjeta dice si la persona tiene cuenta, código pendiente o ninguno |
| **Base aeróbica** | todos | Cinco modos de ingreso: T-30, T-15, test N×D (p. ej. 12×400), CSS 400/50 (Wakayoshi) e ingreso directo. Guarda la **salida** del test y si los números son tiempos nadados o llegadas del reloj. Promedio, desviación, tendencia, comparación contra el test anterior y **tiempos de entrenamiento** por zona |
| **Entrenamiento** | todos | El atleta apunta lo que nadó cada día (metros, duración, RPE CR-10); el entrenador lo ve y lo corrige. Carga sTSS por sesión y curva CTL/ATL/TSB con alertas |
| **Plan semanal** | todos | Tres vistas (`?vista=`): **Plan** (fecha, fase, km, tiempo esperado, proyección recalculada, tiempo real, diferencia, estado, parones), **Progresión** (curva ideal vs. proyección vs. reales, tabla de desviación) y **Zonas** |
| **Tabla del equipo** | entrenador | Todos los atletas en una semana: ritmo y **salida** por zona (R1–V), km sugeridos y la forma de cada atleta. Exportable a PDF |
| **Simulador** | entrenador | Sin persistencia: cambia parámetros y el motor recalcula. Factibilidad con su tier, las cinco curvas comparadas, extensión del macro si la meta no cabe, plan completo, **proyección de temporada** (3 macros). Exportable a PDF |
| **Perfil** | todos | Cuenta y contraseña, ficha deportiva, canje de código, solicitudes de ingreso. El dueño gestiona miembros, qué atletas lleva cada entrenador y la transferencia del club |
| **Ajustes** | todos | Tema (azul marino / negro / blanco) y, en desarrollo, el **conmutador de identidad** (ver §6.4) |

Una cuenta sin club solo ve Perfil: existe en el sistema y todavía no pertenece
a ningún equipo.

---

## 4. El motor científico

Uno solo, en `backend/app/dominio/servicios/`, como funciones puras que no
importan nada fuera de la biblioteca estándar. `MotorCientifico` (`motor.py`)
es la fachada; el cálculo está repartido en:

| Módulo | Qué calcula |
|---|---|
| `tablas.py` | Las constantes científicas que no pertenecen a ningún objeto de valor, cada una con su referencia |
| `curvas.py` | La forma de la progresión. **La de un plan real es siempre la científica** (distribución F_FASE, cargada hacia el final, pico en el taper). Sigmoide, exponencial, logarítmica y lineal existen solo en el simulador, porque a mitad de plan cambian el veredicto que ve el atleta |
| `envolvente.py` | El techo de mejora del macro (I_max) y el ritmo máximo de una semana; la **factibilidad**: tier 1 (≥ 400 m, regla aeróbica) y tier 2 (< 400 m, ventanas de velocidad), con semanas recomendadas si la meta es agresiva |
| `kilometraje.py` | Envolvente del volumen (rampa hasta ~70 % y descenso de 40–60 %) × onda 3:1 / 4:1. **El total lo pone el entrenador**; la banda científica es un aviso, no un valor |
| `zonas.py` · `intervalos.py` | `zona = ritmo de carrera × factor[perfil][distancia] (+ estilo) × piscina`. Cada zona sale con **dos números**: ritmo y salida. El descanso es un ratio sobre el trabajo que crece con la intensidad, y la salida se redondea **hacia arriba** al múltiplo de 5 s |
| `plan.py` | El plan semana a semana, su extensión y el recálculo desde un tiempo real. Ninguna semana mejora más rápido que el pico fisiológico: lo que no cabe se difiere a las siguientes |
| `temporada.py` | Tres macrociclos encadenados con re-test y degradación del potencial (0,60) |
| `banister.py` | CTL/ATL/TSB sobre el sTSS de las sesiones. La serie arranca en equilibrio; alertas TSB < −25 / < −40, TSB < 0 más de 14 días y CTL +7 en una semana |

Reglas que el modelo impone por construcción, no por convención:

- **La curva ideal nunca se modifica**: `Semana.esperado` no se puede reasignar y
  el repositorio no lo escribe. La proyección viva va en `recalc_time`.
- **El nivel del atleta sale de su test aeróbico cuando lo hay**; solo si no, se
  estima desde el ritmo de carrera.
- **En la base de datos va siempre el tiempo nadado**: la conversión de llegadas
  del reloj ocurre en el constructor de `TestAerobico`.
- `Tiempo` es siempre positivo; lo que puede ser cero o negativo es una
  `Duracion`. La validez de una prueba la decide el constructor de `Prueba`.
- Estados con tolerancia ±0,4 %: adelantado / en plan / atrasado.

El análisis del test (`engine/aerobic.py`) y el formato de tiempos
(`engine/time_utils.py`) son lo único que queda de la carpeta `engine/` original.

---

## 5. Arquitectura

```
peakstroke/
├── backend/                        FastAPI · SQLAlchemy 2 async · Pydantic v2
│   ├── app/
│   │   ├── main.py                 routers, CORS, middleware de auditoría
│   │   ├── dominio/                ★ el modelo. No importa NADA de fuera
│   │   │   ├── valores/            Tiempo, Duracion, Ritmo, Mejora, Prueba, Estilo,
│   │   │   │                       Piscina, Zona, Fase, Nivel, Veredicto… (inmutables)
│   │   │   ├── entidades/          Atleta, Macrociclo, Inscripcion, PruebaObjetivo,
│   │   │   │                       Semana, Resultado, Sesion, TestAerobico, Usuario,
│   │   │   │                       SesionAbierta, Equipo, CodigoDeVinculacion
│   │   │   ├── roles/              Rol → EntrenadorEnJefe · Entrenador · AtletaRol
│   │   │   └── servicios/          el motor científico (§4)
│   │   ├── persistencia/
│   │   │   ├── tablas/             modelos SQLAlchemy por agregado + vocabularios (CHECK)
│   │   │   ├── repositorios/       la única puerta a cada agregado
│   │   │   └── mapeo/              fila ↔ entidad, en las dos direcciones
│   │   ├── api/v1/                 una rebanada por agregado: router · schemas · service
│   │   │   ├── atletas/  codigos/  equipos/  macrociclos/  sesiones/  tests/  auth/
│   │   │   ├── carga/              solo lectura (CTL/ATL/TSB)
│   │   │   ├── simulador/          sin tabla
│   │   │   └── vistas/             pantallas compuestas: tablero y tabla del equipo
│   │   ├── core/                   config, base de datos, Principal, guards,
│   │   │                           seguridad (Argon2id + JWT), auditoría
│   │   └── engine/                 aerobic.py · time_utils.py
│   ├── alembic/                    20 migraciones; la única fuente del esquema
│   ├── tools/                      ops.py y herramientas de servidor (§8)
│   ├── tests/                      1516 tests
│   └── seed.py                     datos demo
│
├── frontend/                       React 19 · Vite · TS strict · Tailwind v4
│   └── src/
│       ├── lib/                    api.ts (cliente tipado), types/, constants, format, pdf
│       ├── hooks/                  useSession, useSelectedPlan, useTheme, useDevIdentity…
│       ├── components/             layout (rail, drawer, navConfig) · ui · charts · three
│       └── features/               dashboard · plans · swimmers · aerobic · training ·
│                                   weekly · team · simulator · profile · settings
│
├── docker-compose.yml              PostgreSQL 17 para cuando toque desplegar
├── start-peakstroke.bat            lanzador de doble clic (backend + frontend)
└── docs/                           REDISENO.md, PLAN-DE-TRABAJO.md, capturas
```

### Principios

- **Las dependencias apuntan hacia dentro**: `api → persistencia → dominio`, y el
  dominio no apunta a nada. `tests/test_dependencias_de_capas.py` lo comprueba
  por AST y su lista de violaciones conocidas está vacía.
- **Entre rebanadas del API no se importa nada.** Para preguntarle algo a otro
  agregado se pide a su repositorio.
- **La entidad se construye desde la fila, no la envuelve.** Los campos de
  estado de la identidad (generación de sesión, hash, dueño, rol, ciclo de vida
  del código) solo cambian por sus métodos; un guarda por AST lo impide fuera
  del mapeo.
- **Router sin lógica**: recibe, delega y responde.
- Ningún archivo pasa de ~300 líneas; type hints en todo Python.

---

## 6. Equipos, roles e identidad

### 6.1 El equipo es la frontera de todo
- Fichas, macrociclos y tests llevan `team_id` NOT NULL, y las tablas de relación
  tienen FKs compuestas contra `(id, team_id)`: la base de datos hace imposible
  mezclar clubes aunque el código tenga un bug.
- Toda consulta pasa por un `Principal` (usuario + pertenencia + propiedad). Los
  repositorios se construyen con él, así que el alcance no se puede olvidar.
- `team_id` sale **siempre** de la sesión, nunca del cuerpo de la petición.
- Recurso de otro equipo → **404, nunca 403**. El 403 es «tu rol no alcanza».

### 6.2 Roles
- El rol vive en `team_members`, no en `users`: se es entrenador *en* un club.
- **Entrenador en jefe** = entrenador que además es dueño del club. El dueño es
  único y transferible.
- El atleta es del equipo; `coach_athletes` dice quién lo lleva y `plan_coaches`
  qué entrenadores llevan cada macrociclo. El dueño llega a todos.
- Borrar un macrociclo y cambiar su meta son de dueño.
- **Un atleta, un macrociclo vivo**: regla de dominio que bloquea a todos, dueño
  incluido.

### 6.3 Ficha y cuenta, la misma persona
La ficha deportiva y la cuenta se ligan solo con un **código de vinculación**: lo
emite el entrenador, lo canjea la persona, caduca a las 72 h, sirve una vez y
emitir uno nuevo revoca el anterior. Ningún endpoint las liga por sí solo.

**Revocado no es lo mismo que sin equipo**: un atleta revocado sigue siendo del
club y no puede canjear el código de otro. Para que cambie de club, el operador
lo **libera** con `tools/ops.py liberar`.

### 6.4 Sesiones
- Argon2id para las contraseñas; access JWT de 15 min y refresh de 30 días en
  cookie httpOnly.
- **Una sesión por login** (`sesiones_abiertas`), cada una con su rotación. El
  refresh sirve una vez y se gasta con un `UPDATE` condicional: reusarlo, aunque
  sea a la vez, cierra esa sesión y deja un `REFRESH_REUSADO` en la auditoría.
  Los demás dispositivos siguen.
- **Cortan todas las sesiones**: `POST /auth/logout-all`, cambiar la contraseña,
  revocar, liberar y `ops.py cortar-sesiones`.

### 6.5 Modo de desarrollo
Con `PEAKSTROKE_AUTH_ENABLED=false` (el defecto) la app no pide login y toda
petición se atribuye a `coach@peakstroke.dev`. `config.py` impide que ese modo
llegue a producción. Dos cabeceras permiten probar cualquier rol:

```
X-PeakStroke-Dev-User: sofia@peakstroke.dev   quién eres: ves la interfaz de ese rol, con sus 403
X-PeakStroke-Dev-Bypass: true                 te saltas los guards de rol sin dejar de ver lo que ve esa persona
```

En el frontend, el conmutador vive en **Ajustes → Desarrollo**.

---

## 7. Integridad y auditoría

- **Las FKs se aplican de verdad** también en SQLite (`PRAGMA foreign_keys=ON`).
- **Nada se borra: se da de baja** (fichas, miembros, cuentas, tests). Las dos
  excepciones razonadas son las sesiones de entrenamiento —registros que su dueño
  corrige— y las filas de `sesiones_abiertas`.
- **El tiempo nadado es del atleta, no del plan**: vive en `resultados`, sin FK al
  plan, así que sacar a alguien del macro o borrar el macro no lo toca.
- **Los vocabularios cerrados tienen `CHECK`** (fase, rol, estilo, piscina,
  estado…), generados desde los enums del dominio.
- Un número no finito en el cuerpo de una petición da 422 (`api.entrada.Entrada`).
- **Auditoría append-only**: los eventos de seguridad se escriben después de
  responder; un trigger rechaza `UPDATE` y `DELETE` de lo que tenga menos de
  24 meses. La IP nunca llega entera al disco: red truncada + HMAC con una clave
  que rota cada 30 días y se borra al rotar.
- Las vistas `v_admin_accesos`, `v_admin_actividad`, `v_admin_cuentas` y
  `v_admin_equipos` son el único contrato de lectura del futuro panel PSAdmin.

---

## 8. API (REST, `/api/v1`)

```
auth          POST   /auth/login · /auth/refresh · /auth/logout · /auth/logout-all
              GET    /auth/me · /auth/config · /auth/dev-identities
              POST   /auth/me/password
              GET/POST /auth/members        PATCH /auth/members/{user_id}
teams         GET/PATCH /teams/mine         POST /teams/mine/transfer
              GET/PUT   /teams/mine/coaches/{coach_id}/athletes
swimmers      GET/POST  /swimmers/          GET/PUT/DELETE /swimmers/{id}
              POST      /swimmers/{id}/reactivate
link-codes    GET/POST  /link-codes/        POST /link-codes/invite · /link-codes/redeem
              GET       /link-codes/mine    DELETE /link-codes/{id}
plans         GET/POST  /plans/             GET/PATCH/DELETE /plans/{id}
              GET       /plans/default-phases · /plans/{id}/assignable-athletes
              POST      /plans/{id}/athletes
              DELETE    /plans/{id}/athletes/{athlete_plan_id}   POST …/restore
              GET       /plans/events/{event_id}/weeks
              PATCH     /plans/weeks/{week_id}           tiempo real / parón → recalcula
aerobic-tests GET/POST  /aerobic-tests/     POST /aerobic-tests/analyze (sin persistir)
              GET/DELETE /aerobic-tests/{id}   POST …/reactivate
              GET       /aerobic-tests/{id}/previous · /aerobic-tests/{id}/training-intervals
sessions      GET/POST  /sessions/          GET/PATCH/DELETE /sessions/{id}
training-load GET       /training-load/{swimmer_id}
dashboard     GET       /dashboard/summary · /dashboard/team-week
simulator     POST      /simulator/run · /simulator/season
              GET       /health
```

Documentación interactiva: `http://localhost:8000/docs`.

---

## 9. Cómo correr el proyecto

### Requisitos
- Python 3.12+ · Node.js 20+

### Primera vez
```powershell
cd peakstroke\backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python seed.py        # BORRA la base y la reconstruye por migraciones, con datos demo

cd ..\frontend
npm install
```

### Arrancar
Doble clic en `start-peakstroke.bat`: levanta backend (`:8000`) y frontend
(`:5173`), abre el navegador y, al cerrar la ventana, apaga los dos.

A mano, en dos terminales:
```powershell
cd peakstroke\backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
```powershell
cd peakstroke\frontend
npm run dev
```

Abrir **http://localhost:5173**. El proxy de Vite enruta `/api` → `:8000`.

### Migraciones
El esquema **no** se crea al arrancar: `init_db()` solo avisa si la base no está
en el head.
```powershell
cd peakstroke\backend
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m alembic revision --autogenerate -m "qué cambia"
```
Todo modelo nuevo se registra en `app/core/model_registry.py`.

### Tests
```powershell
cd peakstroke\backend
.venv\Scripts\python -m pytest tests/ -q

cd ..\frontend
npx tsc -b
npm run lint
```
Dos `pytest` a la vez en el mismo árbol se pisan: dale a cada uno su propio
`TMP`/`TEMP`.

### PostgreSQL
```powershell
docker compose up -d db
.venv\Scripts\pip install asyncpg
$env:PEAKSTROKE_DATABASE_URL = "postgresql+asyncpg://peakstroke:peakstroke@localhost:5432/peakstroke"
.venv\Scripts\python -m alembic upgrade head
```

---

## 10. Herramientas de servidor (`backend/tools/`)

| Herramienta | Para qué |
|---|---|
| `ops.py` | **CLI de operaciones**: `crear-equipo`, `crear-cuenta`, `revocar`, `restaurar`, `liberar`, `cortar-sesiones`, `restablecer-password`, `transferir` y `salud`. Todo lo que escribe audita (`os:<usuario>@<host>`), tiene `--dry-run` y los destructivos piden escribir el nombre del recurso. Ninguna contraseña entra por argumento |
| `purgar_auditoria.py` | Borra los eventos de más de 24 meses (cron mensual) |
| `recalcular_carga.py` | Reconstruye `carga_diaria` desde cero |
| `grafo_de_imports.py` | Imprime el grafo de capas y marca las flechas que suben |

El primer club y su dueño se crean así:
```powershell
cd peakstroke\backend
.venv\Scripts\python tools/ops.py crear-equipo --nombre-equipo "Club" --correo dueño@club.com --nombre "Ana"
```
Cada comando, con sus códigos de salida, en `backend/tools/README.md`.

---

## 11. Datos demo (seed)

`python seed.py` crea **7 cuentas** de desarrollo (contraseña `peakstroke`),
10 fichas de nadador, un macrociclo activo de 12 semanas cursando la semana 7,
tests aeróbicos y tiempos reales de las semanas 1–6 con ruido plausible.

Cuatro de las cuentas existen para que los casos incómodos se vean al
desarrollar: un entrenador que no es dueño, un atleta sin ficha, un atleta con
ficha pero sin macrociclo y un atleta con la ficha dada de baja.

---

## 12. Qué queda

| Qué | Dónde |
|---|---|
| **Login en el frontend** y un solo `/auth/refresh` en vuelo por navegador (Web Locks), que bloquea encenderlo en producción | TODO-31 |
| **D2 y D3**: el panel PSAdmin, con R10 y R12 por decidir | `docs/PLAN-DE-TRABAJO.md` |
| Especificar la UI de administración · tests de la frontera entre equipos | TODO-1 · TODO-2 |
| `useSelectedPlan` aislado por usuario · la invitación no debería crear la cuenta · límite de intentos en el canje | TODO-3 · 17 · 18 |
| Billing (Stripe) y límites por plan (`core/tier_limits.py`, `require_feature()`) | camino al SaaS |
| **Después del rediseño, ya desbloqueados**: test de lactato, interconexión de secciones por atleta, módulo de entrenamiento diario | notas del vault |
| Aparcados a propósito: tablas en español, N1/N2 (qué entra en el promedio semanal) | `docs/REDISENO.md` |

---

## 13. Fundamentos teóricos aplicados

| Concepto | Fuente | Dónde se aplica |
|---|---|---|
| CSS = 350 / (T400 − T50) | Wakayoshi et al. (1992) | `engine/aerobic.py`, modo CSS del test |
| Periodización y fases | Matveyev (1964), Bompa & Haff (2009) | `valores.Fase` (las cinco fases y su F_FASE) |
| Supercompensación 3:1 / 4:1 | Bompa & Haff (2009) | `servicios/kilometraje.py` |
| Taper de 40–60 % del volumen | Mujika | Envolvente del kilometraje |
| Distribución por especialidad | Seiler (2010), Issurin (2008) | `MEZCLA_DE_ZONAS_POR_ESPECIALIDAD` en `servicios/tablas.py` |
| Dominio aeróbico por prueba | Gastin (2001), Maglischo (2011) | Factibilidad (`servicios/envolvente.py`) |
| Factores de zona por perfil y distancia | Calculadora de entrenadores, calibrada con el pool nacional | `valores/zona.py` (`factores_de_zona`) |
| Carga CTL / ATL / TSB | Banister (1975), Hellard et al. (2005), Mitchell et al. (2020) | `servicios/banister.py` |

---

## 14. Decisiones técnicas

| Decisión | Razón |
|---|---|
| **Un solo motor, en el dominio** | Había dos que compartían tablas y no algoritmo, y divergieron tres veces. La forma la pone la ciencia; los límites, el entrenador |
| **Rediseño POO con capas** (`dominio` / `persistencia` / `api`) | Las reglas vivían repartidas en servicios que se las tenían que acordar. Hoy las impone el constructor o el método de la entidad |
| **La curva de un plan real es siempre la científica** | Las otras cambian el veredicto que ve el atleta a mitad de plan; se quedan en el simulador |
| **`expected_time` inmutable + `recalc_time`** | El entrenador ve a la vez el plan original y la proyección viva |
| **SQLite en local, PostgreSQL probado** | Local-first sin fricción; las migraciones valen en los dos motores (comprobado el 2026-09-25) |
| **Alembic como única fuente del esquema** | Con datos reales, el esquema se versiona; el local recorre el mismo camino que producción |
| **Argon2id + PyJWT** | Recomendación OWASP actual; `python-jose` lleva años sin mantenimiento |
| **Una sesión por login, sin ventana de gracia** | Dos dispositivos no se echan; una ventana de gracia dejaría pasar una cookie copiada usada en el mismo instante |
| **El CLI de operaciones en lugar de una web de admin** | Se corre por SSH: no hay puerto, endpoint ni sesión que robar |
| **Auditoría fuera de la transacción de la petición** | No añade latencia a la respuesta; si falla, el log dice qué eventos se perdieron |
| **TanStack Query** | Registrar un tiempo real refresca semanas y dashboard sin estado manual |
| **PDF armado en el cliente** (jsPDF) | Sin dependencia en el servidor; solo Latin-1 llega bien al PDF |
| **Tailwind v4 con `@theme`** | Tokens en CSS nativo; tres temas por `data-theme` |
| **Three.js solo decorativo** | Un shader de ondas ligero que se pausa con la pestaña oculta |

---

## 15. Historia

| Fecha | Hito |
|---|---|
| 2026-06 | v0.1: planificador de macrociclos, motor de predicción, simulador. Temas azul marino / negro / blanco, selector de macrociclo de trabajo |
| 2026-08-07 | Equipos, roles e identidad en el backend; navegación por rol y conmutador de desarrollo |
| 2026-08-09/10 | Código de vinculación ficha ↔ cuenta, alta de atletas por correo, pool global. La salida, mitad de cada prescripción |
| 2026-08-14/16 | Red de seguridad del motor (snapshot de 153 casos), plan de trabajo, objetos de valor. Plan semanal absorbe Comparación |
| 2026-08-17 | Entidades, roles como objetos y **un solo motor** (C2–C4) |
| 2026-08-25 | Repositorios por agregado: `app/modules/` desaparece (C5) |
| 2026-09-22/24 | Cinco fases de la ciencia (P3), `Resultado` (C6), curva científica fija (R7), sesiones (C7), carga de Banister (C8), exportación a PDF, permisos de dueño (R4) |
| 2026-09-24/25 | Auditoría append-only y vistas de PSAdmin (D0); cadena de migraciones probada en PostgreSQL |
| 2026-10-01 | Sección Entrenamiento en el frontend; la forma de cada atleta en la tabla del equipo |
| 2026-10-05/14 | Todo agregado se escribe por su entidad, identidad incluida; `CHECK` de vocabularios (C9) |
| 2026-10-14/15 | CLI de operaciones (D1); revocar corta sesiones. Fusionado en `main` (PR #4) |
| 2026-10-20 | Rotación del refresh con `UPDATE` condicional (TODO-25) y una sesión por login (TODO-30) |

La bitácora detallada de cada bloque está en `docs/PLAN-DE-TRABAJO.md`, y las
decisiones de modelo, en `docs/REDISENO.md`.

---

## 16. Ramas

Se trabaja en **`Preliminar`**. A **`main`** solo llega una fase completada, por PR
con merge commit.

---

*Construido con Claude Code · junio–octubre de 2026*
