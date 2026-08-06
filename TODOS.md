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

**Contexto:** se cortó del plan del 2026-08-06 para no reintroducir alcance. Con el harness
de API ya montado (fixture de `AsyncClient`, DB de prueba, override de `get_db`), el coste
baja mucho.

**Por dónde empezar:** dos equipos en la DB de prueba y barrer los endpoints de cada módulo.

**Esfuerzo:** L (humano) → M (con CC). **Depende de:** el harness de API.

---

## TODO-5 — Corregir la nota 18 del vault (P1)

**Qué:** el §6 paso 4 de `E:\Obsidian\Inbox\Peakstroke\18 - Perfil, Roles y Autenticación.md`
dice **"✅ Guards y scoping (hecho 2026-08-04)"**. Solo se hizo el scoping por equipo.

**Por qué:** esa línea es la razón por la que el agujero sobrevivió. Una nota que afirma
"resuelto" hace que ninguna sesión futura vuelva a mirar. Una nota que miente cuesta más
que una nota que falta. El §3 de la misma nota ya describe la regla correcta ("toda consulta
suya se filtra por su `swimmer_id`") — el inventario del §7 es el que se contradice.

**Por dónde empezar:** cambiar el ✅ del paso 4 por el alcance real, y añadir el hallazgo
del 2026-08-06 con lo que se verificó en vivo.

**Esfuerzo:** S (humano) → S (con CC). **Depende de:** nada. Hacer junto al arreglo.

---

## TODO-6 — `get_membership` no filtra `is_active` (P2)

**Qué:** `backend/app/modules/teams/service.py:37` resuelve la pertenencia con
`select(TeamMember).where(TeamMember.user_id == user_id)`, sin filtrar `is_active`.
`core/dependencies.py:80` sí lo hace.

**Por qué:** dos funciones que responden la misma pregunta con semánticas distintas es el
patrón que produjo el bug del scoping. Hoy no es explotable porque los tres llamadores
compensan por su cuenta (`auth/router.py:39` comprueba `not membership.is_active`), pero
eso es exactamente lo que hay que dejar de depender.

**Por dónde empezar:** decidir cuál es la semántica correcta y hacerla única. Si algún
llamador necesita ver pertenencias inactivas, que sea un parámetro explícito.

**Esfuerzo:** S (humano) → S (con CC). **Depende de:** el harness de API para probarlo.

---

## TODO-7 — Los tests aeróbicos se borran de verdad (P3)

**Qué:** `DELETE /aerobic-tests/{id}` hace un borrado físico, contra la política del
`CLAUDE.md` ("Nada se borra: se da de baja") que `swimmers.set_active` sí respeta.

**Por qué:** el docstring de `set_active` llama al histórico de entrenamiento "el activo más
valioso de la aplicación" y nombra los tests aeróbicos dentro de él. Hoy un clic lo evapora.

**Contexto:** además, hasta que entre el arreglo del scoping, ese endpoint lo puede llamar
cualquier miembro del equipo sobre el test de cualquier otro.

**Por dónde empezar:** columna `is_active` + migración, y filtrar en los listados igual que
en swimmers.

**Esfuerzo:** M (humano) → S (con CC). **Depende de:** nada.

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
