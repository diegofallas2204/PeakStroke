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
> **Cerrado el 2026-08-09**: ~~TODO-4~~ — `SimulatorPage.tsx` bajó de 458 a 100
> líneas; ver abajo. En la misma pasada se borró `components/ui/ZoneTag.tsx`, que
> no importaba nadie.
>
> **Abierto el 2026-08-09**: TODO-16 — cuatro archivos pasan de 300 líneas; dos
> de ellos crecieron con el código de vinculación. Ver abajo.
>
> **Abierto el 2026-08-10** (sesión de salida del test + alta por correo, **307
> tests en verde**): TODO-17 y TODO-18, los dos aplazados a sabiendas por la
> auditoría de seguridad de esa sesión. El hallazgo grave de esa auditoría —una
> pertenencia revocada podía iniciar sesión como cuenta del pool— se introdujo y
> se cerró dentro de la misma sesión, con `tests/test_cuenta_sin_equipo.py`
> fijándolo; no llegó a ninguna rama compartida.
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


## TODO-16 — Cuatro archivos pasan del límite de ~300 líneas (P3)

**Qué:** partir los que se han quedado grandes.

| archivo | líneas | nota |
|---|---:|---|
| `backend/app/domain/engine.py` | 714 | **Excepción legítima**: port verbatim del sandbox, fuente de verdad. No tocar |
| `backend/app/core/dependencies.py` | 386 | Ya estaba en 366; el 2026-08-09 subió al separar `get_current_user` de `get_current_principal` |
| `backend/app/modules/plans/service.py` | 333 | Preexistente. Las reglas ya salieron a `access.py` y `enrollment.py`; queda CRUD + motor |
| `frontend/src/lib/types.ts` | 346 | Ya estaba en 317; subió con `LinkCode` y `AssignableAthlete` |

**Por qué:** ninguno es una violación nueva, pero dos empeoraron en la misma
sesión y el límite existe para que eso no pase inadvertido.

**Por dónde empezar:** `types.ts` es el más fácil y el menos arriesgado —
partirlo por dominio (`types/identity.ts`, `types/plans.ts`, `types/engine.ts`)
con un barrel que reexporte, para no tocar 40 imports. `dependencies.py` podría
separar el `Principal` de las dependencias de FastAPI, pero es el archivo del que
cuelga todo el aislamiento: **cualquier corte ahí se propone antes de aplicarse**.

**Esfuerzo:** S (`types.ts`) · M (los otros dos). **Depende de:** nada.

---

## TODO-17 — La invitación no debería crear la cuenta (P2)

**Qué:** `POST /link-codes/invite` crea la cuenta si el correo no existe y le
devuelve la contraseña temporal al entrenador. Cuando exista registro público,
debería limitarse a dejar la invitación esperando a que esa persona se registre.

**Por qué:** hoy un entrenador puede ocupar cualquier correo que no controle y
además conoce su contraseña. **No es una regresión** —`POST /auth/members` tiene
la misma propiedad desde siempre— pero el alta por correo la hace mucho más
fácil de ejercer, y con registro público pasa de incómoda a explotable: quien
llegue después encuentra su correo tomado.

**Contexto:** hallazgo #3 de la auditoría del 2026-08-10
(`.gstack/security-reports/2026-08-11-040500.json`). Se aceptó a sabiendas
porque hoy no hay registro público: el entrenador es la única forma de entrar.

**Por dónde empezar:** separar `invite` en dos caminos según exista la cuenta.
El de "no existe" solo escribe el `LinkCode` con `invited_email`; `GET
/link-codes/mine` ya busca por correo, así que la invitación aparece sola en
cuanto esa persona se registre. La ficha sí se puede crear desde el principio.

**Esfuerzo:** S. **Depende de:** que exista registro público. **Bloquea:** abrir
el registro.

---

## TODO-18 — Sin límite de intentos en el canje de códigos (P3)

**Qué:** `POST /link-codes/redeem` acepta intentos ilimitados.

**Por qué:** hoy es teórico —30^8 ≈ 6,5e11 combinaciones con TTL de 72 h, y desde
el 2026-08-10 un código dirigido exige además coincidir con el correo invitado—
pero la cuenta de "impracticable" se hace con la app en localhost. Con el login
encendido y la app en internet, la ausencia de límite es lo primero que se prueba.

**Contexto:** hallazgo #4 de la misma auditoría. Los códigos **sin** destinatario
(`POST /link-codes/`, el que se dicta al borde de la piscina) son los expuestos:
valen para quien los tenga.

**Por dónde empezar:** límite por IP y por cuenta sobre el endpoint de canje.
Antes de encender `PEAKSTROKE_AUTH_ENABLED=true` en algo que mire a internet.

**Esfuerzo:** S. **Depende de:** nada. **Bloquea:** exponer la app.

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

## ~~TODO-4 — `SimulatorPage.tsx` excede el límite de tamaño~~ — CERRADO 2026-08-09

458 → **100 líneas**. La página quedó como pura orquestación; cada bloque de resultado
vive en su propio archivo, ninguno pasa de 101 líneas:

| archivo | qué es |
|---|---|
| `SimParams.tsx` | la fila de parámetros y las dos reglas de autocorrección |
| `SimFeasibility.tsx` | veredicto de factibilidad del macro |
| `SimSeason.tsx` | proyección anual (3 macrociclos) |
| `SimCurveChart.tsx` | la gráfica **y** el armado de `chartData` (macro + extensión) |
| `SimPlanTable.tsx` | la tabla semana a semana, compartida por plan y extensión |
| `SimExtension.tsx` | aviso de semanas extra + tabla de extensión |
| `simDefaults.ts` | forma y valores iniciales de los parámetros |

Dos notas para quien lo retome:

- `renderWeekTick` **ya estaba extraído** desde antes (`components/charts/weekAxisTick.tsx`).
  La pista que daba este TODO estaba obsoleta; el bulto real era el JSX de las tarjetas.
- `simDefaults.ts` existe por la regla de fast refresh de ESLint: un archivo de componentes
  no puede exportar además constantes. No lo fusiones de vuelta en `SimParams.tsx`.

**Verificado** con `tsc -b` limpio, `npm run build` en verde y el simulador en el navegador:
el texto renderizado es **byte a byte idéntico** al de antes (6045 chars, mismo hash) con los
parámetros por defecto, y se ejercitaron a mano las ramas alternativas — autocorrección de
estilo/especialidad al pasar a 400m (Tier 1), curva sigmoidal con la científica de
referencia, meta dentro del techo (sin extensión) y modo simple.
