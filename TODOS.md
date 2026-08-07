# TODOS

Trabajo aplazado con contexto suficiente para retomarlo sin la conversación que lo originó.
Prioridad: P1 = bloquea trabajo en curso · P2 = debería caer pronto · P3 = deuda conocida.

> **Cerrados el 2026-08-07** (sesión de backend, 157 tests en verde):
> ~~TODO-6~~ `get_membership` ya filtra `is_active` por defecto, con
> `include_inactive=True` explícito para `transfer_ownership`.
> ~~TODO-7~~ `DELETE /aerobic-tests/{id}` da de baja (`is_active` + migración
> `f565acec2845`) en vez de borrar.
> ~~TODO-5~~ La nota 18 del vault dice ya el alcance real del paso 4 y recoge el
> hallazgo de la escritura ajena.
> **TODO-2 sigue abierto y ahora tiene harness**: ver TODO-2 más abajo.

---

## TODO-8 — Quitar un atleta del macrociclo borra su histórico (P1)

**Qué:** `DELETE /plans/{plan_id}/athletes/{athlete_plan_id}` hace `db.delete(ap)`
(`backend/app/modules/plans/service.py:174`). `AthletePlan` cascadea a `athlete_events` y
de ahí a `weekly_plans`.

**Por qué:** va contra la regla del `CLAUDE.md` ("nada se borra: se da de baja") que el
mismo día se aplicó a `aerobic_tests`, y destruye estrictamente más histórico. El docstring
de `swimmers.set_active` llama a eso "el activo más valioso de la aplicación".

**Reproducido** el 2026-08-07 con el harness de tests:

```
registrar un tiempo real en la semana 2 de Carlos   -> 200
DELETE /plans/1/athletes/{ap_de_carlos}             -> 204
weekly_plans: 36 filas antes  ->  24 después
athlete_events de Carlos: 1 antes  ->  0 después   (con el tiempo recién puesto)
```

**Por dónde empezar:** `athlete_plans.is_active` + migración, y filtrar en `to_plan_response`
y en `_load_events` igual que se hizo con `aerobic_tests._visible()`. Ojo: la baja lógica
aquí interactúa con TODO-9 (el plan pasa a ser aún más indestructible).

**Esfuerzo:** M (humano) → S (con CC). **Depende de:** nada.

---

## TODO-9 — `DELETE /plans/{id}` responde 500 si el macrociclo tiene tests (P1)

**Qué:** `fk_aerobic_tests_plan_in_team` no lleva `ondelete`, así que un plan referenciado
por un test aeróbico no se puede borrar. `plans/service.py:131` hace `db.delete(plan)` sin
capturar nada, y el cliente recibe una traza.

**Por qué:** es un camino normal del entrenador y el fallo depende del dato — un plan sin
tests borra bien (204), así que aparece en producción y no al desarrollar. **Además la baja
lógica de TODO-7 lo empeoró**: antes el entrenador tenía salida (borraba los tests, que era
borrado físico, y luego el plan); ahora las filas nunca salen de `aerobic_tests` y el plan
queda indestructible.

**Reproducido:** `DELETE /plans/1` → `sqlite3.IntegrityError: FOREIGN KEY constraint failed`.

**Por dónde empezar:** decidir la semántica antes de tocar nada. O el borrado se impide con
un 409 que explique ("tiene N tests asociados"), o borrar el plan desliga los tests
(`plan_id` a NULL, que el esquema ya permite). La primera es más conservadora y encaja mejor
con "nada se borra".

**Esfuerzo:** S (humano) → S (con CC). **Depende de:** nada. **Relacionado:** TODO-8.

---

## TODO-10 — Cambiar la contraseña no revoca las sesiones (P1)

**Qué:** `POST /auth/me/password` cambia el hash y nada más. `users.token_version` y
`auth.service.revoke_sessions()` ya existen (se añadieron el 2026-08-07 para `logout`), pero
no están cableados aquí.

**Por qué:** cambiar la contraseña y cerrar sesión son las dos mitades del mismo gesto
("creo que me han comprometido la cuenta"). Se cerró una y no la otra.

**Reproducido** con `auth_enabled=True`: tras cambiar la contraseña, el access token viejo
devuelve 200, la cookie de refresh vieja devuelve 200 y `token_version` sigue en 0. El
atacante conserva 30 días de refresh.

**Por dónde empezar:** una línea — `await service.revoke_sessions(db, principal.user)` en
`auth/router.py::change_password`. Efecto: al cambiar la contraseña te pide volver a entrar,
que es lo que hace todo el mundo. Si se quiere evitar ese corte, hay que reemitir la sesión
en la misma respuesta.

**Esfuerzo:** S (humano) → S (con CC). **Depende de:** nada. El login real aún no está
encendido: hoy es gratis.

---

## TODO-11 — `create_test` no valida el `plan_id` que llega del cuerpo (P2)

**Qué:** `aerobic_tests/service.py::create_test` comprueba `principal.owns_swimmer(swimmer_id)`
pero no comprueba nada sobre `data.plan_id`.

**Por qué:** la FK compuesta solo impide cruzar equipos, no cruzar macrociclos dentro del
equipo. **Reproducido:** Sofía recibe 404 en `GET /plans/2` (no está inscrita) y **201** al
crear un test con `plan_id=2`; su fila aparece luego en el `GET /aerobic-tests/?plan_id=2`
del entrenador de ese macrociclo.

**Por dónde empezar:** si `data.plan_id` no es None, pasarlo por `plans.access.get_plan(db,
plan_id, principal)` y devolver None (→404) si no lo ve. Ojo con el import cruzado entre
módulos: hoy `aerobic_tests` no importa nada de `plans`.

**Esfuerzo:** S (humano) → S (con CC).

---

## TODO-12 — `scope_to_own_swimmer` falla ABIERTO si la columna no es del `stmt` (P2)

**Qué:** `core/dependencies.py::Principal.scope_to_own_swimmer` promete en su docstring que
"la consulta se vuelve imposible en vez de quedarse sin filtro". Eso solo vale para el caso
`swimmer_id is None`. Si un llamador pasa una columna que no está en el FROM, SQLAlchemy no
protesta: añade la tabla y produce un producto cartesiano.

**Por qué:** el helper existe justo para que equivocarse sea difícil, y su modo de error es
el peligroso. **Verificado:** `select(AerobicTest).where(Swimmer.id == 7)` compila a
`FROM aerobic_tests, swimmers`. Los 5 llamadores actuales pasan la columna correcta.

**Por dónde empezar:** o el helper deja de recibir la columna (un mapa
`{modelo: columna}` interno), o se valida que la columna pertenezca a alguna entidad del
`stmt` y se revienta con `AssertionError` si no. Lo segundo es más barato.

**Esfuerzo:** S (humano) → S (con CC).

---

## TODO-13 — Un test aeróbico dado de baja es irrecuperable (P3)

**Qué:** `_visible()` filtra por `is_active`, no hay parámetro `include_inactive` ni endpoint
de reactivación. `service.set_active(..., True)` no tiene ninguna ruta que lo llame: es
código muerto.

**Por qué:** `swimmers` tiene las dos cosas (`?include_inactive=` y `POST /{id}/reactivate`).
Aquí la regla se cumple en la tabla pero desde la aplicación el efecto es idéntico al
borrado, que es justo lo que TODO-7 quería evitar.

**Por dónde empezar:** copiar el patrón de `swimmers`: parámetro en el listado + endpoint de
reactivación, ambos solo para entrenadores.

**Esfuerzo:** S (humano) → S (con CC).

---

## TODO-14 — `/auth/refresh` dice que rota el refresh y no lo hace (P2)

**Qué:** el docstring afirma "rota el refresh (cada uso emite uno nuevo)". Emite uno nuevo,
sí, pero **el viejo sigue valiendo hasta que expire**: no hay `jti`, ni lista de revocación,
ni nada que detecte el replay.

**Por qué:** rotar sin invalidar no es rotar. Lo que la rotación real compra es detectar que
un refresh robado se está reusando, y eso hoy no ocurre. **Verificado:** reusar la cookie
anterior tras un `/refresh` devuelve 200. (La cookie reemitida además sale idéntica byte a
byte cuando login y refresh caen en el mismo segundo: mismo `sub`, mismo `ver`, `iat` con
resolución de segundo.)

**Por dónde empezar:** con `token_version` ya en el esquema la pieza que falta es pequeña.
Lo mínimo honesto mientras tanto es corregir el docstring para que no afirme lo que no hace.

**Esfuerzo:** M (humano) → S (con CC).

---

## TODO-15 — Dos derivaciones distintas de "mi nadador" (P3)

**Qué:** `plans/access.py::visible_to` deriva el nadador del usuario con
`Swimmer.user_id == principal.id`. `core/dependencies.py::_principal_for` lo deriva con
`(Swimmer.user_id == TeamMember.user_id) & (Swimmer.team_id == TeamMember.team_id)`.

**Por qué:** hoy coinciden porque `Swimmer.user_id` es UNIQUE global. `teams/models.py:8`
anticipa explícitamente quitar la restricción de un-usuario-un-equipo; ese día las dos
condiciones dejan de decir lo mismo y solo una lleva el equipo. Es el mismo patrón de TODO-6
(dos funciones respondiendo la misma pregunta con semánticas distintas) que ya produjo un bug.

**Por dónde empezar:** que `visible_to` use `principal.swimmer_id`, que ya está resuelto y
lleva el equipo dentro.

**Esfuerzo:** S (humano) → S (con CC).

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
