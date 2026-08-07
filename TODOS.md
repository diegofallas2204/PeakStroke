# TODOS

Trabajo aplazado con contexto suficiente para retomarlo sin la conversación que lo originó.
Prioridad: P1 = bloquea trabajo en curso · P2 = debería caer pronto · P3 = deuda conocida.

> **Cerrados el 2026-08-07** (sesión de backend, **219 tests en verde**):
> ~~TODO-8 a TODO-15~~ — las ocho fugas que destapó la revisión independiente
> sobre el diff. Cada una con test de regresión; ver el historial de git.
> ~~TODO-6~~ `get_membership` ya filtra `is_active` por defecto, con
> `include_inactive=True` explícito para `transfer_ownership`.
> ~~TODO-7~~ `DELETE /aerobic-tests/{id}` da de baja (`is_active` + migración
> `f565acec2845`) en vez de borrar.
> ~~TODO-5~~ La nota 18 del vault dice ya el alcance real del paso 4 y recoge el
> hallazgo de la escritura ajena.
> **TODO-2 sigue abierto y ahora tiene harness**: ver TODO-2 más abajo.
>
> **Frontend cerrado el 2026-08-07**: conmutador de identidad y modo
> desarrollador en Ajustes, navegación filtrada por rol con guardas de ruta,
> versión de atleta de las 4 páginas y estados vacíos por rol (T12–T18 del plan).
> ~~TODO-3~~ sigue abierto pero cambió de forma: ver abajo.

---

## ~~TODO-8 — Quitar un atleta del macrociclo borra su histórico~~ — CERRADO 2026-08-07

---


## ~~TODO-9 — `DELETE /plans/{id}` responde 500 si el macrociclo tiene tests~~ — CERRADO 2026-08-07

---


## ~~TODO-10 — Cambiar la contraseña no revoca las sesiones~~ — CERRADO 2026-08-07

---


## ~~TODO-11 — `create_test` no valida el `plan_id` que llega del cuerpo~~ — CERRADO 2026-08-07

---


## ~~TODO-12 — `scope_to_own_swimmer` falla ABIERTO si la columna no es del `stmt`~~ — CERRADO 2026-08-07

---


## ~~TODO-13 — Un test aeróbico dado de baja es irrecuperable~~ — CERRADO 2026-08-07

---


## ~~TODO-14 — `/auth/refresh` dice que rota el refresh y no lo hace~~ — CERRADO 2026-08-07

---


## ~~TODO-15 — Dos derivaciones distintas de "mi nadador"~~ — CERRADO 2026-08-07

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

## TODO-2 — Tests de la frontera ENTRE equipos (P1)

> **Alcance corregido el 2026-08-06** por `/plan-eng-review`. La versión anterior decía
> "aislamiento entre equipos" a secas y daba por hecho que era la única frontera. Hay dos:
>
> - **Entre clubes** (`team_id`) — implementada y sólida (FKs compuestas reales, `visible_to`,
>   `team_id` siempre desde la sesión). Sin tests. **Eso es este TODO.**
> - **Dentro del club** (atleta ↔ atleta) — **no existía**. Un atleta leía y escribía los datos
>   de sus compañeros. Verificado en vivo. Ya NO es un TODO: entró al plan activo como
>   trabajo bloqueante.

**Qué:** cubrir con tests que ninguna consulta del equipo A devuelva una fila del equipo B,
por ninguna de las tres puertas (listado, id directo, semana suelta), y que un recurso ajeno
responda 404 y no 403.

**Por qué:** es la promesa más cara del producto y hoy solo está verificada a mano. Los 103
tests de `backend/tests/` son todos del motor científico: funciones puras, sin DB ni FastAPI.

**Contexto:** se cortó del plan del 2026-08-06 para no reintroducir alcance. **El harness ya
está montado** (2026-08-07): `backend/tests/conftest.py` con `AsyncClient`, DB de prueba
migrada por Alembic, override de `get_db` y un mundo fijo. El coste bajó mucho.

**Lo que la revisión independiente señaló el 2026-08-07:** el `World` del harness monta **un
solo equipo**, así que la primera frontera —la que sostiene todo el diseño— no la ejerce ni
un test. Se verificó a mano montando un segundo club y aguanta (swimmer, plan y dashboard de
otro club → 404; tests → lista vacía), pero **la suite no lo sabe**: un `visible_to` al que
se le cayera el `Plan.team_id` seguiría en verde.

**Por dónde empezar:** una fixture `otro_club` junto a `world` en `conftest.py` (la revisión
dejó una escrita y funcionando, ver el commit de esta sesión en el historial de la sesión) y
barrer los endpoints de cada módulo desde el club A contra los ids del club B.

**Esfuerzo:** M (humano) → S (con CC), ahora que el harness existe. **Depende de:** nada.

---

## ~~TODO-5 — Corregir la nota 18 del vault~~ — CERRADO 2026-08-07

Ver la nota del principio del archivo.

---


## ~~TODO-6 — `get_membership` no filtra `is_active`~~ — CERRADO 2026-08-07

Ver la nota del principio del archivo.

---


## ~~TODO-7 — Los tests aeróbicos se borran de verdad~~ — CERRADO 2026-08-07

Ver la nota del principio del archivo.

---


## TODO-3 — `useSelectedPlan` aislado por usuario (P2)

**Qué:** el macrociclo seleccionado vive hoy en un `localStorage` global
(`frontend/src/hooks/useSelectedPlan.ts`, clave `ps-selected-plan`). Debe aislarse por
usuario.

**Por qué:** `localStorage` es del navegador, no de la cuenta. Con login real y dos cuentas
usando el mismo equipo, la selección de una se filtra a la otra.

**Contexto:** ya señalado en el paso 5 de la nota 18 del vault y en
`Decisions/Cacheo en el browser y carga del API`.

**Actualizado el 2026-08-07:** el conmutador de desarrollo ya llama a
`limpiarCacheDeIdentidad()` (`lib/queryClient.ts`) antes de recargar, que borra la entrada
de localStorage además de vaciar la memoria — sin eso, la escritura pendiente del persister
(throttle de 1 s) rehidrataba los datos del anterior. Eso cierra la fuga **al cambiar de
identidad en desarrollo**, pero NO la de dos cuentas reales compartiendo navegador: la clave
`ps-selected-plan` sigue siendo global. Falta namespacearla por `user.id`.

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
