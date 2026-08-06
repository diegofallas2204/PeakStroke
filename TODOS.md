# TODOS

Trabajo aplazado con contexto suficiente para retomarlo sin la conversación que lo originó.
Prioridad: P1 = bloquea trabajo en curso · P2 = debería caer pronto · P3 = deuda conocida.

---

## TODO-1 — Especificar la UI de admin (P1)

**Qué:** definir qué administra el rol "admin", sobre qué datos y con qué alcance.

**Por qué:** es el bloqueante directo de la tercera interfaz pedida el 2026-08-06. Hoy
"admin" no existe en ningún sitio: ni en el enum `Role = Literal["coach", "athlete"]`
(`backend/app/modules/teams/models.py`), ni en la base de datos, ni en las notas del
vault, ni en el modelo de negocio SaaS.

**Contexto:** la decisión del 2026-08-04 descartó explícitamente un tercer rol —
"entrenador en jefe = entrenador que además es `teams.owner_id`, no es un tercer rol".
Si "admin" resulta ser un superadmin de plataforma (varios clubes), choca de frente con
dos invariantes que sostienen todo el aislamiento:

- `team_id` sale **siempre** de la sesión (`Principal`), nunca del cuerpo de la petición
- las FKs compuestas contra `(id, team_id)` hacen imposible cruzar equipos a nivel de motor

Cualquiera de las dos que se relaje hay que decidirla antes de escribir código, no después.

**Por dónde empezar:** `/office-hours` o `/spec` para producir la definición; después
`/plan-ceo-review` sobre el resultado.

**Esfuerzo:** M (humano) → S (con CC) para la spec. La implementación depende de qué salga.
**Depende de:** nada. **Bloquea:** la interfaz de admin.

---

## TODO-2 — Tests del aislamiento entre equipos (P1)

**Qué:** cubrir con tests `plans.service.visible_to()`, la política de responder 404 y no
403 ante recursos ajenos, y el scoping por `team_id` en swimmers, plans y aerobic_tests.

**Por qué:** es la promesa más cara del producto —que un club no pueda ver los datos de
otro— y hoy solo está verificada a mano. Los 88 tests de `backend/tests/` son todos del
motor científico: funciones puras, sin base de datos ni FastAPI.

**Contexto:** se cortó deliberadamente del plan del 2026-08-06 para no reintroducir
alcance justo tras recortarlo. Una vez exista el harness de API (fixture de `AsyncClient`,
DB de prueba, override de `get_db`), el coste de estos tests baja mucho.

**Por dónde empezar:** dos equipos en la DB de prueba y verificar que ninguna consulta del
equipo A devuelve una fila del equipo B, por ninguna de las tres puertas (listado, id
directo, semana suelta).

**Esfuerzo:** L (humano) → M (con CC). **Depende de:** el harness de API.

---

## TODO-3 — `useSelectedPlan` aislado por usuario (P2)

**Qué:** el macrociclo seleccionado vive hoy en un `localStorage` global
(`frontend/src/hooks/useSelectedPlan.ts`, clave `ps-selected-plan`). Debe aislarse por
usuario.

**Por qué:** `localStorage` es del navegador, no de la cuenta. Con login real y dos cuentas
usando el mismo equipo, la selección de una se filtra a la otra.

**Contexto:** ya señalado en el paso 5 de la nota 18 del vault y en
`Decisions/Cacheo en el browser y carga del API`. El reset a `null` que introduce el toggle
de desarrollo es un parche: resuelve el síntoma al cambiar de identidad en dev, no la fuga
entre cuentas.

**Por dónde empezar:** namespacear la clave por `user.id`, igual que se hizo con
`IDENTITY_KEYS` en `main.tsx`. Ojo: el id no está disponible en el primer render.

**Esfuerzo:** S (humano) → S (con CC). **Depende de:** que exista login real.

---

## TODO-4 — `SimulatorPage.tsx` excede el límite de tamaño (P3)

**Qué:** 458 líneas contra la regla de "ningún archivo supera ~300 líneas" del `CLAUDE.md`.

**Por qué:** es la regla de organización que el propio proyecto declara no negociable, y
ahora mismo se incumple en silencio. `DashboardPage.tsx` (255) y `WeeklyPlanPage.tsx` (214)
la cruzarán si se les añaden ramas por rol sin extraer subcomponentes.

**Contexto:** pre-existente, no lo causa ningún plan en curso. Detectado en la revisión del
2026-08-06.

**Por dónde empezar:** el candidato obvio a extraer es `renderWeekTick` y la configuración
de gráficas; `SimZones.tsx` ya demuestra que el patrón de extracción funciona aquí.

**Esfuerzo:** S (humano) → S (con CC). **Depende de:** nada.
