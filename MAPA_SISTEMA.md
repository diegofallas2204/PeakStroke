# MAPA DEL SISTEMA — PeakStroke

> Glosario de archivos por carpeta. Una referencia rápida para saber qué hace cada archivo,
> cuándo tocarlo, qué importa y qué expone.
>
> **Cómo mantener actualizado:** ejecutar `/context-save` en Claude Code después de
> cualquier sesión de desarrollo. El skill actualiza este archivo automáticamente.
>
> **Última actualización:** 2026-06-02
> **Versión del sistema:** 1.0.0 — MVP Macrociclo

---

## Índice rápido

- [Raíz del proyecto](#raíz-del-proyecto)
- [Backend — Core](#backend--core)
- [Backend — Módulo Auth](#backend--módulo-auth)
- [Backend — Módulo Training Plans (Macrociclo)](#backend--módulo-training-plans-macrociclo)
- [Backend — Alembic](#backend--alembic)
- [Frontend — Shared](#frontend--shared)
- [Frontend — Feature Auth](#frontend--feature-auth)
- [Frontend — Feature Training Plans](#frontend--feature-training-plans)

---

## Raíz del proyecto

```
E:\PeakStroke\PeakStroke\
```

| Archivo | Qué hace | Cuándo tocarlo |
|---------|----------|----------------|
| `CLAUDE.md` | Contexto del proyecto para Claude Code: stack, reglas, flujo gstack, estructura | Al agregar reglas nuevas o cambiar la arquitectura |
| `BITACORA.md` | Registro de decisiones técnicas, reglas empíricas validadas y razonamiento de diseño | Después de cada sesión importante o decisión de arquitectura |
| `MAPA_SISTEMA.md` | **Este archivo.** Glosario de todos los archivos del proyecto | Ejecutar `/context-save` para actualizar automáticamente |
| `README.md` | Instrucciones de instalación y arranque para nuevos desarrolladores | Al agregar pasos de setup o cambiar cómo se arranca |
| `ENUNCIADO_PEAKSTROKE.md` | Especificación original completa del sistema (documento de referencia) | Solo lectura — no modificar |
| `prompt-maestro-swim-app.md` | Plan maestro: arquitectura SaaS, tiers, stack, estructura vertical | Solo lectura — referencia de arquitectura |
| `mockup.html` | Prototipo HTML original (v1) — referencia visual del diseño. Obsoleto como código pero útil como referencia | Solo lectura |
| `test_engine.py` | Pruebas del motor de progresión original (Python legacy) | Obsoleto — las pruebas nuevas van en `backend/tests/` |

---

## Backend — Core

```
backend/app/core/
```

El core son las piezas compartidas por TODOS los módulos. Los módulos importan desde aquí,
nunca entre sí.

| Archivo | Responsabilidad | Expone | Importado por |
|---------|----------------|--------|---------------|
| `config.py` | Lee variables de entorno con Pydantic Settings. Falla en arranque si falta alguna requerida. | `settings` (singleton) | Todo el backend |
| `database.py` | Crea el engine SQLAlchemy async, el `AsyncSessionLocal` y la clase base `Base` para todos los modelos. | `get_db` (dependency FastAPI), `Base` | `main.py`, todos los módulos, `alembic/env.py` |
| `security.py` | Hashing de contraseñas (bcrypt) y JWT encode/decode. Sin estado. | `hash_password()`, `verify_password()`, `create_access_token()`, `decode_access_token()` | `auth/service.py`, `auth/router.py`, `core/dependencies.py` |
| `tier_limits.py` | **Fuente de verdad única de límites por tier.** Dict `TIER_LIMITS` con los valores para `free`, `coach`, `club`. | `TIER_LIMITS`, `get_tier_limit(tier, resource)` | `core/dependencies.py`, `training_plans/service.py` |
| `dependencies.py` | FastAPI dependencies reutilizables. `get_current_user` verifica el JWT y retorna el User. `require_feature` lanza 403 si el tier no tiene el feature. | `get_current_user`, `require_feature(feature)` | Todos los routers |

**Regla:** Si dos módulos necesitan la misma lógica, va aquí — nunca en un módulo específico.

---

## Backend — Módulo Auth

```
backend/app/modules/auth/
```

Gestiona usuarios, registro, login y JWT. Es el módulo más pequeño pero del que dependen todos.

| Archivo | Responsabilidad | Expone | Notas |
|---------|----------------|--------|-------|
| `models.py` | Modelo SQLAlchemy `User`. Campos: `id`, `email`, `name`, `hashed_password`, `role`, `tier`, `stripe_customer_id`, `trial_ends_at`. | `User` | `tier` puede ser `free` / `coach` / `club`. `trial_ends_at` para el trial de 30 días. |
| `schemas.py` | Pydantic schemas de entrada/salida. | `RegisterRequest`, `LoginRequest`, `TokenResponse`, `UserResponse` | `RegisterRequest` valida que la contraseña tenga ≥8 chars. |
| `service.py` | Lógica de registro, autenticación y consulta de usuario. **Aquí se degrada el tier si el trial venció.** | `register_user()`, `authenticate_user()`, `get_user_by_id()` | `register_user` crea el usuario con tier `coach` + trial 30 días. `authenticate_user` compara password y verifica trial. |
| `router.py` | Endpoints: `POST /auth/register`, `POST /auth/login`, `GET /auth/me`. Sin lógica de negocio. | Router con prefijo `/auth` | Solo delega al service. |

**Flujo de registro:** `register_user` → crea User con tier=`coach` y `trial_ends_at=now+30d` → `create_access_token` → devuelve JWT.

**Flujo de degradación:** `authenticate_user` verifica si `trial_ends_at < now` y `stripe_customer_id is None` → si sí, cambia `user.tier = 'free'` antes de retornar.

---

## Backend — Módulo Training Plans (Macrociclo)

```
backend/app/modules/training_plans/
```

El módulo central del sistema. Contiene todo lo relacionado con macrociclos, atletas,
plan semanal, zonas de entrenamiento y tests aeróbicos.

### `models.py`
Define 8 tablas SQLAlchemy. Relaciones:

```
Macrocycle (1)
  └── MacrocyclePhase (N)           — fases configurables (Base/Construcción/Pico/Descenso)
  └── AthleteMacrocycle (N)         — liga un Swimmer a un Macrocycle
        ├── aerobic_base             — pace_100m base aeróbica (editable, fuente: T30/T15/manual)
        └── AthleteEvent (1..3)      — hasta 3 pruebas por atleta
              └── WeeklyPlan (N)    — plan semana × prueba (12 o 18 filas)

Swimmer (1)
  ├── AthleteMacrocycle (N)
  └── AerobicTest (N)
        └── AerobicTestSplit (N)    — parciales individuales del T-30/T-15
```

| Tabla | Propósito | Campos clave |
|-------|-----------|--------------|
| `macrocycles` | Plan de temporada del equipo | `total_weeks`, `total_km`, `progression_curve`, `start_date` |
| `macrocycle_phases` | Fases configurables por el entrenador | `name`, `week_start`, `week_end`, `color` |
| `swimmers` | Perfil del atleta | `birth_date` (para calcular edad), `gender`, `specialty` |
| `athlete_macrocycles` | Relación atleta ↔ macro + base aeróbica | `aerobic_base` (pace_100m), `aerobic_base_source` |
| `athlete_events` | Prueba específica de un atleta en un macro | `priority` (1/2/3), `distance`, `stroke`, `current_time`, `goal_time` |
| `weekly_plans` | Plan calculado semana × prueba | `expected_time`, `expected_time_recalc`, `pace_100m`, `zone_r1..v`, `real_time`, `disabled` |
| `aerobic_tests` | Test T-30 o T-15 completo | `test_type`, `avg_time`, `std_dev` |
| `aerobic_test_splits` | Parciales individuales del test | `rep_number`, `split_time` |

### `progression_engine.py`
**El cerebro del sistema.** Motor de progresión portado del prototipo de escritorio.

| Función/Clase | Qué hace |
|---------------|----------|
| `ProgressionEngine.generate_plan()` | Genera lista de `WeekEntry` para un `AthleteEvent`. Calcula curva ideal, curva recalculada (si hay parones), zonas por semana y distribución de km con taper. |
| `ProgressionEngine._check_feasibility()` | Verifica si el objetivo es realista. Tier 1 (≥400m): compara con regla 1s/micro. Tier 2 (<400m): compara con ventanas fisiológicas por evento. Retorna `ok`/`warning`/`aggressive`. |
| `ProgressionEngine._curve_value()` | Calcula el progreso acumulado normalizado [0,1] para una posición x. Implementa las 4 curvas: `linear`, `exponential`, `logarithmic`, `sigmoid`. |
| `ProgressionEngine._calculate_zones()` | Dado un `pace_100m`, retorna `WeekZones` con R1, R2, MVO2, RL, V multiplicando por los factores de zona. |
| `ProgressionEngine._distribute_km()` | Distribuye el kilometraje total entre semanas con carga progresiva y taper en las últimas semanas. |
| `calculate_aerobic_base(splits)` | Función standalone. Recibe lista de splits (15 o 30) y retorna `avg_time`, `std_dev`, `trend_slope`, `trend_direction`. Usada para T-30/T-15. |

**Constantes de zona (fuente de verdad interna):**
```python
ZONE_FACTORS = {"R1": 1.375, "R2": 1.275, "MVO2": 1.175, "RL": 1.125, "V": 1.075}
```

### `schemas.py`
Todos los Pydantic schemas del módulo. Convención: `XCreate` / `XUpdate` / `XResponse`.

| Schema | Tipo | Propósito |
|--------|------|-----------|
| `MacrocycleCreate` | Create | Validar la creación. Verifica que las fases cubran todas las semanas. |
| `MacrocycleUpdate` | Update | Actualización parcial (todos los campos opcionales). |
| `MacrocycleResponse` | Response | Incluye `phases` y `swimmer_count`. |
| `SwimmerCreate/Update/Response` | CRUD | `SwimmerResponse` incluye `age` calculado (no en DB). |
| `AthleteEventCreate` | Create | Valida que `goal_time < current_time`. Máximo 3 por macro. |
| `AddAthleteRequest` | Create | Agregar atleta al macro: incluye `events` (1-3) y `aerobic_base` opcional. |
| `WeeklyPlanResponse` | Response | Incluye `zones` como objeto `WeekZonesResponse` serializado. |
| `UpdateWeekRequest` | Update | Para ingresar tiempo real o inhabilitar semana con motivo. |
| `AerobicTestCreate` | Create | Valida exactamente 15 o 30 splits. |
| `TeamRowResponse` | Response | Una fila de la tabla del equipo: swimmer + event + week. |

### `service.py`
Toda la lógica de negocio del módulo. Solo recibe `AsyncSession` como parámetro.

| Función | Qué hace | Lanza |
|---------|----------|-------|
| `create_macrocycle()` | Crea macro + fases (default si no se proveen). Verifica límite de tier. | `PermissionError` si el tier no permite más macros |
| `get_macrocycles()` | Lista macros del coach con sus fases. | — |
| `get_macrocycle()` | Detalle completo: macro + fases + atletas + eventos + semanas. | — |
| `update_macrocycle()` | Actualización parcial de metadatos. | — |
| `delete_macrocycle()` | Elimina en cascada (fases, atletas, semanas). | — |
| `create_swimmer()` | Crea atleta para el coach. | — |
| `get_swimmers()` | Lista atletas del coach ordenados por nombre. | — |
| `update_swimmer()` | Actualización parcial del atleta. | — |
| `add_athlete_to_macrocycle()` | **El orquestador central.** Crea `AthleteMacrocycle` + hasta 3 `AthleteEvent` + llama al motor para generar todos los `WeeklyPlan`. | `ValueError` si el atleta ya está o no pertenece al coach |
| `update_week()` | Actualiza tiempo real o inhabilita semana. Si se inhabilita, llama `_regenerate_recalc_curve`. | — |
| `_regenerate_recalc_curve()` | Recalcula `expected_time_recalc` para todas las semanas de un evento tras un cambio de parones. | — |
| `get_team_table()` | Retorna todas las filas (atleta × prueba × semana) para la tabla del equipo. | — |
| `create_aerobic_test()` | Registra un T-30/T-15 completo: llama a `calculate_aerobic_base`, guarda el test y sus splits. | `ValueError` si el swimmer no es del coach |
| `get_aerobic_tests()` | Historial de tests aeróbicos de un atleta. | — |

### `router.py`
14 endpoints en `/api/v1/training-plans/`. Solo recibe, delega y retorna.

| Método | Endpoint | Descripción | Auth |
|--------|----------|-------------|------|
| POST | `/` | Crear macrociclo | `get_current_user` |
| GET | `/` | Listar macrociclos del coach | `get_current_user` |
| GET | `/{macro_id}` | Detalle completo del macrociclo | `get_current_user` |
| PATCH | `/{macro_id}` | Actualizar metadatos | `get_current_user` |
| DELETE | `/{macro_id}` | Eliminar macrociclo | `get_current_user` |
| POST | `/{macro_id}/athletes` | Agregar atleta + pruebas + generar plan | `get_current_user` |
| GET | `/{macro_id}/team?week=N` | Tabla del equipo para la semana N | `get_current_user` |
| PATCH | `/weeks/{week_id}` | Ingresar tiempo real / inhabilitar semana | `get_current_user` |
| POST | `/swimmers` | Crear atleta | `get_current_user` |
| GET | `/swimmers` | Listar atletas del coach | `get_current_user` |
| PATCH | `/swimmers/{swimmer_id}` | Actualizar atleta | `get_current_user` |
| POST | `/aerobic-tests` | Registrar test T-30/T-15 | `get_current_user` |
| GET | `/aerobic-tests/{swimmer_id}` | Historial de tests de un atleta | `get_current_user` |

---

## Backend — Alembic

```
backend/alembic/
```

| Archivo | Qué hace |
|---------|----------|
| `alembic.ini` | Configuración de Alembic: URL de DB, loggers |
| `alembic/env.py` | Setup de Alembic async. Importa TODOS los modelos para que el autogenerate los detecte. **Al agregar un nuevo modelo, hay que importarlo aquí.** |
| `alembic/versions/` | Archivos de migración generados. Nunca editarlos a mano en producción. |

**Comando para crear migración después de cambiar modelos:**
```bash
cd backend
alembic revision --autogenerate -m "descripcion del cambio"
alembic upgrade head
```

---

## Frontend — Shared

```
frontend/src/shared/
```

Código compartido por todos los features. Ningún feature importa de otro feature — solo de `shared/`.

| Archivo | Responsabilidad | Expone |
|---------|----------------|--------|
| `shared/lib/api.ts` | Instancia axios configurada con `baseURL=/api/v1`. Interceptor de request inyecta el Bearer token. Interceptor de response redirige a `/login` en 401. | `api` (instancia axios) |
| `shared/hooks/useAuthStore.ts` | Store Zustand de autenticación. Persiste token y perfil del usuario en `localStorage`. | `useAuthStore` — expone `token`, `user`, `setAuth()`, `logout()` |

---

## Frontend — Feature Auth

```
frontend/src/features/auth/
```

| Archivo | Responsabilidad |
|---------|----------------|
| `pages/LoginPage.tsx` | Pantalla de login y registro. Alterna entre modo `login` y `register` con el mismo formulario. Al registrarse muestra el mensaje del trial de 30 días. Llama directamente a `api` (sin hook de React Query — es una mutación de sesión, no de datos). |

---

## Frontend — Feature Training Plans

```
frontend/src/features/training-plans/
```

El feature más grande. Contiene todo lo del macrociclo.

### `api.ts`
Todas las llamadas al backend del módulo. Los hooks y componentes nunca llaman a `axios` directamente — usan `api.ts` o los hooks de React Query.

| Objeto | Qué contiene |
|--------|-------------|
| `macrocyclesApi` | `list`, `get`, `create`, `update`, `delete`, `addAthlete`, `teamTable`, `updateWeek` |
| `swimmersApi` | `list`, `create`, `update` |
| `aerobicTestsApi` | `list`, `create` |

También exporta los tipos TypeScript: `Macrocycle`, `Swimmer`, `WeeklyPlan`, `AthleteEvent`, `TeamRow`, `Zone`, etc.

### `hooks/useMacrocycles.ts`
Hooks React Query que envuelven `api.ts`. Los componentes consumen datos desde aquí.

| Hook | Qué hace | Invalidaciones |
|------|----------|----------------|
| `useMacrocycles()` | Lista todos los macrociclos | — |
| `useMacrocycle(id)` | Detalle de un macrociclo | — |
| `useCreateMacrocycle()` | Mutación de creación | Invalida `['macrocycles']` |
| `useDeleteMacrocycle()` | Mutación de eliminación | Invalida `['macrocycles']` |
| `useAddAthlete(macroId)` | Agrega atleta al macro | Invalida `['macrocycles', macroId]` |
| `useTeamTable(macroId, week)` | Tabla del equipo para una semana | — |
| `useUpdateWeek(macroId)` | Actualiza una semana (tiempo real / parón) | Invalida `['macrocycles', macroId]` |
| `useSwimmers()` | Lista atletas del coach | — |
| `useCreateSwimmer()` | Crea un atleta nuevo | Invalida `['swimmers']` |

### `utils/timeFormat.ts`
Utilidades de formato de tiempo. Espejo frontend del `time_utils.py` del backend.

| Función | Qué hace |
|---------|----------|
| `formatTime(seconds)` | `65.32` → `'1:05.32'` |
| `formatPace(seconds)` | Igual a `formatTime` pero semánticamente para pace/100m |
| `parseTime(str)` | `'1:05.32'` → `65.32` |
| `formatDelta(delta)` | `-0.32` → `'-0.32s'` con signo |

### Componentes

| Componente | Responsabilidad | Props clave |
|------------|----------------|-------------|
| `MacrocycleWizard.tsx` | Wizard 2 pasos para crear un macrociclo. Paso 1: nombre, fechas, km, curva, sesiones. Paso 2: confirmación + resumen. Las fases se crean automáticamente en el backend. | `onClose()` |
| `TeamTable.tsx` | **La vista operativa central.** Tabla del equipo con navegación por semana. Selector inline de prueba por atleta. Columnas de zonas colapsables. Tiempo real editable inline (Enter para guardar, Escape para cancelar). Botón de parón por semana. Badge de estado (Adelantado/En plan/Atrasado) calculado comparando `real_time` vs `expected_time`. | `macroId`, `totalWeeks` |
| `ProgressionChart.tsx` | Gráfico Recharts con 3 series: curva ideal (gris), curva recalculada (azul), puntos reales (verde). Eje X con fechas `DD/MM`. Eje Y invertido (tiempo menor = más arriba). Línea de referencia en `goalTime`. | `plans`, `goalTime`, `currentTime` |
| `MacrocycleWizard.tsx` | Wizard para crear macrociclos (ver arriba) | `onClose()` |
| `AddAthleteModal.tsx` | Modal de 3 pasos: (1) seleccionar/crear atleta, (2) definir hasta 3 pruebas con tiempos actual/meta, (3) ingresar base aeróbica opcional. | `macroId`, `onClose()` |

### Páginas

| Página | Ruta | Qué muestra |
|--------|------|-------------|
| `MacrocyclesPage.tsx` | `/macrocycles` | Lista de macrociclos del entrenador. Cada card muestra nombre, fechas, semanas, km, cantidad de atletas y barra de fases con color. Botón para crear nuevo. |
| `MacrocycleDetailPage.tsx` | `/macrocycles/:id` | Detalle de un macro: header con info, barra de fases, botón "Agregar atleta" y la `TeamTable`. |

---

## Archivos de configuración del frontend

| Archivo | Qué hace |
|---------|----------|
| `frontend/vite.config.ts` | Configura Vite: plugin React, vite-plugin-pwa (manifest + service worker), proxy `/api → localhost:8000` en dev |
| `frontend/tsconfig.json` | TypeScript: strict mode, JSX react-jsx, alias `@/*` → `src/*` |
| `frontend/package.json` | Dependencias: React 18, React Router 6, TanStack Query 5, Zustand 5, Recharts, date-fns, Tailwind, Vite |
| `frontend/src/index.css` | Tailwind base + componentes custom (`.btn-primary`, `.btn-secondary`, `.input`, `.label`, `.badge-*`) |
| `frontend/src/main.tsx` | Entry point: monta React, configura QueryClient, envuelve App |
| `frontend/src/App.tsx` | Router principal: rutas privadas con `PrivateRoute`, lazy loading de páginas |

---

## Flujos de datos completos

### Flujo: Crear macrociclo + agregar atleta + ver tabla

```
Usuario                    Frontend                     Backend                    DB
  │                           │                             │                       │
  ├─ Rellena wizard ─────────►│                             │                       │
  │                           ├─ POST /training-plans/ ────►│                       │
  │                           │                             ├─ create_macrocycle() ►│ INSERT macrocycles
  │                           │                             │                       │ INSERT macrocycle_phases
  │                           │◄─ MacrocycleResponse ───────┤                       │
  │                           │                             │                       │
  ├─ Agrega atleta ──────────►│                             │                       │
  │                           ├─ POST /{id}/athletes ──────►│                       │
  │                           │                             ├─ add_athlete() ───────►│ INSERT athlete_macrocycles
  │                           │                             ├─ ProgressionEngine ───►│ INSERT athlete_events
  │                           │                             │   .generate_plan()     │ INSERT weekly_plans (N×12/18)
  │                           │◄─ { athlete_macrocycle_id }─┤                       │
  │                           │                             │                       │
  ├─ Ve tabla semana 1 ──────►│                             │                       │
  │                           ├─ GET /{id}/team?week=1 ────►│                       │
  │                           │                             ├─ get_team_table() ────►│ SELECT weekly_plans
  │                           │◄─ [ TeamRow, TeamRow... ] ──┤                       │
  │◄─ Renderiza TeamTable ────┤                             │                       │
```

### Flujo: Inhabilitar semana + ver curva recalculada

```
Entrenador                Frontend                   Backend
     │                        │                          │
     ├─ Click "Parón" ────────►│                          │
     │                        ├─ PATCH /weeks/{id} ─────►│
     │                        │  { disabled: true,       ├─ update_week()
     │                        │    disable_reason }      ├─ _regenerate_recalc_curve()
     │                        │                          │  (recalcula expected_time_recalc
     │                        │                          │   para todas las semanas activas)
     │                        │◄─ WeeklyPlanResponse ────┤
     │                        │ [invalidate macrocycle]  │
     │◄─ Gráfico actualizado ─┤                          │
     │   (curva gris = ideal, │                          │
     │    curva azul = recalc)│                          │
```

---

## Módulos pendientes (próximas versiones)

| Módulo | Versión | Dónde irá |
|--------|---------|-----------|
| `billing/` — Stripe + tiers | v2 | `backend/app/modules/billing/` + `frontend/src/features/billing/` |
| Exportación PDF | v2 | `backend/app/modules/reports/` + endpoint `require_feature("export")` |
| Dashboard del entrenador | v2 | `frontend/src/features/dashboard/` |
| Carga ATL/CTL/TSB | v2 | `backend/app/modules/training_load/` |
| App móvil React Native | v3 | Repositorio separado, reutiliza lógica de `api.ts` |
| Multi-entrenador (Club tier) | v2 | `backend/app/modules/organizations/` |

---

*Generado por `/context-save` — PeakStroke v1.0.0*
*Para actualizar: ejecutar `/context-save` en Claude Code*
