# Plan — Scoping del atleta, toggle de desarrollo e interfaces por rol

Revisado con `/plan-ceo-review` (SCOPE REDUCTION) y `/plan-eng-review` el 2026-08-06.
Rama: `Preliminar` · Sustituye al borrador de scratchpad de la misma fecha.

---

## Estado de partida

**Lo que está bien y no hay que tocar.** La frontera entre clubes es sólida: FKs compuestas
reales contra `(id, team_id)`, `PRAGMA foreign_keys=ON` por conexión, `team_id` siempre desde
la sesión, `visible_to()` como puerta única a los macrociclos, 404 en vez de 403. El esquema
hace imposible mezclar equipos aunque el código falle. 103 tests del motor pasan en 0.12s.

**Lo que está roto.** Hay dos fronteras y solo una está implementada:

```
Principal { user, membership, is_owner }
             │         │          │
             │         └─ team_id ──▶ frontera 1: el CLUB          ✅ sólida
             │
             └─ ¿swimmer_id? ────────▶ frontera 2: el ATLETA       ❌ no existe
```

`Principal` no sabe qué nadador es el usuario, así que ningún servicio *puede* filtrar por
nadador. Verificado en vivo contra la base de datos el 2026-08-06:

```
Sofia (atleta, swimmer_id=1, inscrita en el plan 1 junto a otros 7)
  list_swimmers        -> 8 nadadores del club          (debería ser 1)
  list_tests           -> 12 tests, 10 de otros atletas
  get_week(semana de Carlos)  -> DEVUELVE LA SEMANA
  update_week(semana de Carlos, real_time=999)
      real_time antes=128.57  después=999.0            ESCRITURA AJENA ACEPTADA
```

Escribir el tiempo de otro dispara `_recalculate_event`, que le reescribe la curva de
progresión entera. Esto contradice la nota 18 §3 del vault ("toda consulta suya se filtra por
su `swimmer_id`"), cuyo §6 paso 4 además afirma incorrectamente que el scoping ya está hecho
(ver TODO-5).

### Alcance real de un atleta hoy

| Endpoint | Qué obtiene | Spec |
|---|---|---|
| `GET /swimmers/` | los 8 del club | solo su ficha |
| `GET /plans/{id}` | el plan con el roster completo | solo lo suyo |
| `GET /plans/events/{id}/weeks` | semanas de cualquiera del plan | solo lo suyo |
| `PATCH /plans/weeks/{id}` | **escribe el tiempo de cualquiera** | solo lo suyo |
| `GET /aerobic-tests/` | 12 tests, 10 ajenos | solo los suyos |
| `POST /aerobic-tests/` | **crea a nombre de otro** | solo los suyos |
| `DELETE /aerobic-tests/{id}` | **borra el de otro** (físico) | no está en la matriz |
| `GET /dashboard/summary` | las 8 filas con nombres y tiempos | versión personal |
| `GET /dashboard/team-week` | tabla del equipo entero | ❌ explícito |

No hay incendio: no hay usuarios reales y el login está apagado. Pero `visible_to` corre
siempre (no consulta `auth_enabled`), así que el bug está vivo, y llega justo cuando íbamos a
construir encima la UI de atleta.

---

## Decisiones

| # | Decisión | Elegido |
|---|---|---|
| CEO-1 | Baseline git antes de tocar código | Hecho: 5 commits, pusheado |
| CEO-2 | Mecanismo del cambio de identidad | Cabecera `X-PeakStroke-Dev-User` |
| CEO-3 | Postura | SCOPE REDUCTION — admin fuera hasta spec |
| CEO-4 | Fuente de verdad de la identidad mostrada | Siempre `/auth/me` |
| CEO-5 | Datos de desarrollo | Ampliar `seed.py` |
| CEO-6 | Tests de la cabecera | Montar harness de API + 4 tests |
| ENG-2 | Orden | **Scoping primero, luego el toggle y la UI** |
| ENG-3 | Arquitectura del scoping | `swimmer_id` en `Principal` + filtro por servicio |
| ENG-4 | Estructura | Extraer `plans/access.py` y endurecer firmas |

**Fuera de alcance:** la interfaz de admin (sin definición: TODO-1), el owner puro sin acceso
de entrenador (el enum es `{coach, athlete}` y `auth/router.py:157` lo prohíbe), encender el
login real (paso 5 de la nota 18), validación de permisos por rol en modo dev (decisión
explícita: "dev permission"), tests de la frontera entre clubes (TODO-2), harness de tests de
frontend (descartado en la revisión).

---

## Fase 1 — La segunda frontera (bloqueante)

Se hace en dos commits, estructural y luego de comportamiento, para que el diff diga qué
regla de acceso cambió.

**1a. Refactor estructural.** `visible_to`, `get_week` y `get_event` salen de
`plans/service.py` (351 líneas, sobre el límite de ~300 del CLAUDE.md) a `plans/access.py`.
`principal` deja de ser opcional en `get_event`; las recargas post-autorización pasan a
`_event_unscoped()`, siguiendo la convención que `_plan_unscoped()` ya establece.

**1b. El filtro.** `_principal_for` resuelve el nadador del usuario igual que ya resuelve
`is_owner`, con un `join` contra la consulta de `TeamMember` que ya se hace (no una consulta
extra). Cada servicio aplica su filtro cuando el rol es `athlete`:

```
_principal_for ──▶ Principal { user, membership, is_owner, swimmer_id }
                                                            │
        ┌───────────────────────────────────────────────────┤
        ▼                    ▼                   ▼           ▼
   plans/access.py      swimmers          aerobic_tests   dashboard
   get_week/get_event   list/get          list/create/    build_summary
   filtran por          filtran por       delete filtran  recibe principal
   swimmer propio       swimmer propio    por swimmer     y acota filas
```

`build_summary(db, plan)` gana `principal`: hoy no lo recibe, por eso carga los 8.

---

## Fase 2 — Toggle de desarrollo

**Backend.** En la rama que ya existe para auth apagada, leer `X-PeakStroke-Dev-User` y
resolver ese email en vez de `settings.dev_user_email`. Se lee solo si `auth_enabled=false`
**y** el entorno es de desarrollo (`_check_production` solo dispara con `environment` en
`production`/`prod`, así que la segunda condición no es redundante). Email inexistente o
inactivo cae al usuario por defecto con `logger.warning`. Nunca 500.

`GET /auth/dev-identities` devuelve las identidades del equipo; **404 con auth encendida**.

**Frontend.** `hooks/useDevIdentity.ts` con el patrón de `useSimpleMode`, exportando el hook
**y un `getDevIdentity()` plano** (`api.ts::request()` no es un componente y no puede llamar
hooks). La cabecera se inyecta en `request()`, punto único que cubre las 30+ llamadas. Al
cambiar: `queryClient.clear()` + `setSelectedPlan(null)` + `reload()`.

**La etiqueta mostrada sale siempre de `/auth/me`**, nunca de localStorage: discrepar es
imposible por construcción. `DevSessionNotice` (ya existe en `AccountCard`) pasa a decir a
quién suplantas.

**Datos.** `seed.py` gana un coach asistente (no dueño), un atleta sin nadador ligado y un
atleta sin macrociclo inscrito.

---

## Fase 3 — Interfaz de atleta

- `navConfig.ts` gana `roles?: Role[]`. El atleta ve Dashboard · Plan semanal · Base aeróbica
  · Comparación · Perfil. `MobileNav` consume `NAV_ITEMS`, así que el móvil llega gratis.
- Mientras `useSession()` es `undefined` el rail no se dibuja vacío (mismo trato que
  `NavContent.tsx:196` da al avatar).
- Versión personal de las 4 páginas. `DashboardPage` (255) y `WeeklyPlanPage` (214) rozan el
  límite de ~300: extraer subcomponentes, no meter `if (isAthlete)` por dentro.
- **Estados vacíos como feature**: sin macrociclo, sin tests, semana en parón, tiempo ya
  registrado, atleta sin ficha. Los datos de la Fase 2 los hacen visibles al desarrollar.

---

## Fase 4 — Capa de owner

Owner = coach + extras, no una UI paralela. `useIsOwner()` junto a `useIsCoach()`, eliminando
el cálculo inline de `ProfilePage.tsx:25`. `TeamCard`, `TransferOwnerModal` y
`CoachAthletesModal` pasan a mostrarse solo al owner. La diferencia de datos ya existe: el
owner ve todos los macrociclos, el coach asistente solo los suyos. Con el coach asistente del
seed se verifica en vivo.

---

## Modos de fallo

```
CODEPATH                        | MODO DE FALLO              | ¿TEST? | ¿VE? | ¿LOG?
--------------------------------|----------------------------|--------|------|------
access.py (atleta)              | pide semana ajena          | S      | 404  | —
access.py (atleta)              | escribe semana ajena       | S CRIT | 404  | —
aerobic_tests (atleta)          | crea a nombre de otro      | S CRIT | 422  | —
aerobic_tests (atleta)          | borra test ajeno           | S CRIT | 404  | —
_principal_for                  | atleta sin nadador ligado  | S      | vacío| —
dev header                      | email inexistente          | S      | /me  | S
dev header                      | auth ON: se ignora         | S CRIT | —    | —
api.ts::request                 | backend caído              | N      | error| N
cambio de identidad             | mutación en vuelo          | N      | reload| —
```

Cero gaps críticos tras el plan: las cuatro escrituras ajenas quedan con test de regresión.

## Paralelización

| Lane | Pasos | Módulos | Depende de |
|---|---|---|---|
| A | 1a → 1b → tests | `backend/app/modules/*`, `core/` | — |
| B | harness de API | `backend/tests/` | — (se puede empezar ya) |
| C | Fase 3 y 4 | `frontend/src/` | Lane A |

**Orden:** A y B en paralelo (B no toca código de producción). Fusionar. Luego Fase 2, luego C.
**Conflicto:** ninguno entre A y B. C toca solo frontend.

---

## Implementation Tasks

- [ ] **T1 (P1, human: ~3h / CC: ~30min)** — backend — Extraer `plans/access.py` y endurecer firmas
  - Surfaced by: Sección 2 — `plans/service.py` en 351 líneas mezcla CRUD, autorización y motor; `get_event(principal=None)` tiene el default inseguro
  - Files: `backend/app/modules/plans/access.py`, `service.py`, `router.py`, `dashboard/service.py`
  - Verify: `pytest tests -q` sigue en verde; el diff no cambia comportamiento
- [ ] **T2 (P1, human: ~4h / CC: ~40min)** — backend — Harness de tests de API
  - Surfaced by: Sección 3 — 103 tests, todos del motor puro; no hay conftest, ni AsyncClient, ni DB de prueba
  - Files: `backend/tests/conftest.py`
  - Verify: un test trivial contra `/api/v1/auth/me` pasa
- [ ] **T3 (P1, human: ~4h / CC: ~45min)** — backend — `swimmer_id` en `Principal` + filtro por servicio
  - Surfaced by: Sección 1 — la segunda frontera no existe; verificado en vivo
  - Files: `backend/app/core/dependencies.py`, `modules/{plans,swimmers,aerobic_tests,dashboard}/`
  - Verify: los tests de regresión de T4 pasan de rojo a verde
- [ ] **T4 (P1, human: ~3h / CC: ~30min)** — backend — Tests de regresión de la escritura ajena **[CRÍTICO]**
  - Surfaced by: Sección 3, regla de regresión — cuatro escrituras ajenas confirmadas contra la DB
  - Files: `backend/tests/test_athlete_scoping.py`
  - Verify: escribir semana ajena, crear y borrar test ajeno → 404; los propios → 200
- [ ] **T5 (P1, human: ~2h / CC: ~20min)** — backend — Cabecera `X-PeakStroke-Dev-User`
  - Surfaced by: CEO-2 — el usuario efectivo es fijo al arrancar el proceso
  - Files: `backend/app/core/dependencies.py`, `core/config.py`
  - Verify: `curl -H "X-PeakStroke-Dev-User: sofia@peakstroke.dev" localhost:8000/api/v1/auth/me`
- [ ] **T6 (P1, human: ~1h / CC: ~15min)** — backend — 4 tests de la cabecera, incluido "auth ON la ignora" **[CRÍTICO]**
  - Surfaced by: CEO-6 — la rotura de esa línea abre suplantación arbitraria y no se ve leyendo el diff
  - Files: `backend/tests/test_dev_identity.py`
  - Verify: `pytest tests/test_dev_identity.py -v`
- [ ] **T7 (P2, human: ~1h / CC: ~15min)** — backend — `GET /auth/dev-identities` (404 con auth on)
  - Surfaced by: Fase 2 — el toggle no debe llevar emails hardcodeados
  - Files: `backend/app/modules/auth/router.py`, `schemas.py`
  - Verify: 200 en dev, 404 con `PEAKSTROKE_AUTH_ENABLED=true`
- [ ] **T8 (P1, human: ~30min / CC: ~15min)** — backend — `seed.py` con coach asistente y atletas incompletos
  - Surfaced by: CEO-5 — los 3 casos hoy invisibles al desarrollar
  - Files: `backend/seed.py`
  - Verify: `python seed.py` y comprobar las 6 cuentas
- [ ] **T9 (P1, human: ~2h / CC: ~20min)** — frontend — `useDevIdentity` + inyección en `api.ts`
  - Surfaced by: Sección 1 — `request()` no es componente, necesita getter plano
  - Files: `frontend/src/hooks/useDevIdentity.ts`, `lib/api.ts`
  - Verify: DevTools, la cabecera viaja en todas las peticiones
- [ ] **T10 (P1, human: ~2h / CC: ~20min)** — frontend — Sección Desarrollo en Ajustes, etiqueta desde `/auth/me`
  - Surfaced by: CEO-4 — fuente de verdad única
  - Files: `frontend/src/components/layout/SettingsModal.tsx`, `features/profile/AccountCard.tsx`
  - Verify: cambiar identidad y confirmar que el rail muestra lo que devolvió el backend
- [ ] **T11 (P2, human: ~1h / CC: ~10min)** — frontend — Limpieza al cambiar identidad
  - Surfaced by: nota 18 §7 — identidad cacheada 24 h en localStorage
  - Files: `frontend/src/hooks/useDevIdentity.ts`, `main.tsx`
  - Verify: cambiar de coach a atleta, no queda dato del anterior
- [ ] **T12 (P1, human: ~2h / CC: ~20min)** — frontend — `roles` en `navConfig` + filtrado sin parpadeo
  - Surfaced by: Sección 1 — `useSession()` es `undefined` en el primer render
  - Files: `frontend/src/components/layout/navConfig.ts`, `NavContent.tsx`, `App.tsx`
  - Verify: recargar como atleta, el rail no aparece vacío ni un frame
- [ ] **T13 (P1, human: ~3d / CC: ~3h)** — frontend — Versión personal de las 4 páginas de atleta
  - Surfaced by: Fase 3 — el núcleo del trabajo pedido
  - Files: `features/{dashboard,weekly,aerobic,comparison}/`
  - Verify: navegar las 4 como Sofía, solo aparecen sus datos
- [ ] **T14 (P1, human: ~1d / CC: ~1h)** — frontend — Estados vacíos de las 4 páginas
  - Surfaced by: Sección 3 — los estados vacíos son la feature, no un descuido
  - Files: mismas que T13
  - Verify: entrar con el atleta sin macrociclo creado en T8
- [ ] **T15 (P2, human: ~2h / CC: ~20min)** — frontend — `useIsOwner()` y capa de owner en `/perfil`
  - Surfaced by: Sección 2 — cuatro sitios calculando el rol a mano
  - Files: `hooks/useSession.ts`, `features/profile/ProfilePage.tsx`
  - Verify: comparar owner contra el coach asistente de T8
- [ ] **T16 (P1, human: ~15min / CC: ~5min)** — docs — Corregir la nota 18 del vault
  - Surfaced by: Sección 1 — el §6 paso 4 afirma que el scoping está hecho, y por eso nadie lo miró
  - Files: `E:\Obsidian\Inbox\Peakstroke\18 - Perfil, Roles y Autenticación.md`
  - Verify: el paso 4 refleja el alcance real y recoge el hallazgo del 2026-08-06

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | mode: SCOPE_REDUCTION, 0 critical gaps |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 9 issues, 1 critical gap (cerrado por el plan) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** CEO + ENG revisados. El hallazgo crítico (frontera atleta inexistente, escritura
ajena verificada en vivo) reordena el plan: el scoping va antes que el toggle y antes que la
UI. Listo para implementar por T1.

**UNRESOLVED DECISIONS:**
- Voz externa no ejecutada en ninguna de las dos revisiones: Codex no está instalado y no se levantó subagente de Claude sin petición explícita del usuario.
