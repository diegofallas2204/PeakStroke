# Plan — Scoping del atleta, toggle de desarrollo e interfaces por rol

Revisado con `/plan-ceo-review` (SCOPE REDUCTION), `/plan-eng-review` y voz externa
independiente el 2026-08-06. Rama: `Preliminar`.

---

## Por qué el scoping va primero

**No es un incidente de seguridad.** No hay usuarios reales y el login está apagado. Es una
**dependencia de orden de construcción**: los endpoints que la UI de atleta va a consumir
devuelven hoy las filas de los 8 atletas del macrociclo. Construir las pantallas primero
significa filtrar en React y rehacerlo después. Que además sea un bug que hay que cerrar
antes de encender el login es cierto, pero es la segunda razón, no la primera.

Verificado ejecutando código contra la base de datos, no leyéndolo:

```
Sofia (atleta, swimmer_id=1, inscrita en el plan 1 junto a otros 7)
  list_swimmers               -> 8 nadadores del club        (debería ser 1)
  list_tests                  -> 12 tests, 10 de otros
  get_week(semana de Carlos)  -> devuelve la semana
  update_week(...real_time=999)  antes=128.57  después=999.0 -> escritura aceptada
```

Escribir el tiempo de otro dispara `_recalculate_event` y le reescribe la curva entera.

### Lo que está bien y no se toca

La frontera **entre clubes** es sólida: FKs compuestas contra `(id, team_id)`,
`PRAGMA foreign_keys=ON` por conexión, `team_id` siempre desde la sesión, `visible_to()` como
puerta única, 404 en vez de 403. El esquema hace imposible mezclar equipos aunque el código
falle. 103 tests del motor pasan en 0.12s.

Lo que faltaba es la frontera **dentro del club**. La nota 18 §6 paso 4 del vault afirma
"✅ Guards y scoping (hecho 2026-08-04)" — solo se hizo la mitad, y esa línea es la razón de
que nadie volviera a mirar (T19).

### Alcance real de un atleta hoy

| Endpoint | Qué obtiene | Cubierto por |
|---|---|---|
| `GET /swimmers/` · `/{id}` | los 8 del club | T3 |
| `GET /plans/` · `/{id}` | **el roster completo con nombres, marcas y objetivos** | T4 |
| `GET /plans/events/{id}/weeks` | semanas de cualquiera del plan | T3 |
| `PATCH /plans/weeks/{id}` | escribe el tiempo de cualquiera | T3 |
| `PATCH /plans/weeks/{id}` | `disabled` = parón del entrenador | **T5** |
| `GET /aerobic-tests/` · `/{id}` · `/{id}/previous` | 12 tests, 10 ajenos | T3, T6 |
| `POST` · `DELETE /aerobic-tests/{id}` | crea a nombre de otro, borra el de otro | T3 |
| `GET /dashboard/summary` | las 8 filas con nombres y tiempos | T3 |
| `GET /dashboard/team-week` | tabla del equipo entero | **T6** |
| `/equipo` por URL directa | `App.tsx` no tiene guardas de ruta | **T15** |

---

## Decisiones

| # | Decisión | Elegido |
|---|---|---|
| CEO-1..6 | Baseline git · cabecera dev · SCOPE REDUCTION · etiqueta desde `/auth/me` · seed ampliado · harness de API | ver historial |
| ENG-2 | Orden | Scoping antes que toggle y UI |
| ENG-3 → **D6** | Forma del scoping | ~~`swimmer_id`~~ → **`visible_swimmer_ids`** *(revertida por la voz externa)* |
| ENG-4 → **D7** | Estructura | `plans/access.py` con la **puerta completa** *(ampliada por la voz externa)* |

**Fuera de alcance:** interfaz de admin (TODO-1), owner puro sin acceso de entrenador,
encender el login real, validación de permisos por rol en modo dev (decisión explícita:
"dev permission"), tests de la frontera entre clubes (TODO-2), harness de tests de frontend.

---

## Fase 1 — La segunda frontera

### El mecanismo (D6)

`Principal` no expone "qué nadador soy" sino **"qué nadadores puedo ver"**, resuelto una vez
donde ya se resuelven `team_id` e `is_owner`:

```
_principal_for ─▶ Principal { user, membership, is_owner, visible_swimmers }
                                                              │
                                            entrenador ──▶ todos los del equipo
                                            atleta     ──▶ [el suyo]
                                            atleta sin ficha ──▶ []
                                                              │
                    ┌─────────────────────┬──────────────────┴────────┐
                    ▼                     ▼                           ▼
              plans/access.py        aerobic_tests               dashboard
              swimmers               .where(swimmer_id.in_(...))  build_summary
              .where(id.in_(...))                                 acota filas
```

Los servicios escriben **un filtro sin rama de rol**. No hay `if role == athlete` que alguien
pueda olvidar en el siguiente endpoint. Se implementa como subconsulta, no como lista
materializada, para no arrastrar cientos de ids por petición en un club grande.

> El mapeo cuenta↔nadador **ya existe dos veces**: el join de `visible_to`
> (`service.py:108-112`) y `auth/service.py:103`, que es por lo que `/auth/me` ya devuelve
> `swimmer_id`. Ambas pasan a consumir `Principal`; no se añade una tercera resolución.
> `Swimmer.user_id` es `unique=True` y `TeamMember` tiene `UNIQUE(user_id)`, así que el outer
> join da como mucho una fila y `_principal_for` se queda en dos consultas.

### La estructura (D7)

`plans/access.py` se lleva **la puerta entera**: `visible_to`, `get_plan`, `list_plans`,
`get_week`, `get_event`. Un módulo de acceso sin `get_plan` organizaría peor que hoy.
`principal` deja de ser opcional en `get_event` (`service.py:224` — el default `None` es el
camino inseguro); las recargas post-autorización usan `_event_unscoped()`.

Va **al final** de la fase, no al principio: mover el único código de autorización de la app
sin cobertura encima es exactamente el orden equivocado.

---

## Fase 2 — Toggle de desarrollo

Cabecera `X-PeakStroke-Dev-User` leída solo con `auth_enabled=false`. Email inexistente o
inactivo cae al usuario por defecto con `logger.warning`, nunca 500.
`GET /auth/dev-identities` con 404 si auth está encendida.

En cliente: `useDevIdentity` con el patrón de `useSimpleMode`, exportando el hook **y un
getter plano** (`api.ts::request()` no es un componente). La etiqueta mostrada sale siempre de
`/auth/me`, nunca de localStorage.

> **Lo que el toggle NO prueba.** `require_role` sigue en bypass por decisión explícita, así
> que suplantando a Sofía siguen abiertos `POST /swimmers/`, `PATCH /plans/{id}` y
> `GET /auth/members`. Los verify de T16/T17/T18 prueban scoping de **datos**, no de permisos.

---

## Fase 3 y 4 — UI de atleta y capa de owner

Rail filtrado por rol **y guardas de ruta en `App.tsx`**: hoy registra todas las rutas
incondicionalmente, así que ocultar el ítem del rail no impide teclear `/equipo`. Versión
personal de las 4 páginas con estados vacíos como feature. Owner = coach + extras.

---

## Implementation Tasks

### Fase 1 — scoping (bloqueante)

- [ ] **T1 (P1, human: ~6h / CC: ~1h)** — backend — Harness de tests de API
  - Surfaced by: Sección 3 — 103 tests, todos del motor puro; no hay conftest ni fixture de DB
  - **Tres trampas que la voz externa verificó:** (1) `engine` y `AsyncSessionLocal` se
    construyen en import desde el singleton `settings`, y el listener `PRAGMA foreign_keys=ON`
    cuelga de *ese* engine — un engine de prueba corre con **FKs apagadas** salvo que se
    re-registre, y entonces TODO-2 pasaría en verde contra una DB sin constraints.
    (2) `init_db()` ya no crea tablas y `seed.py` documenta que Alembic no corre dentro de
    `asyncio.run`. (3) `pyproject.toml` no fija `asyncio_mode` con pytest-asyncio 1.4 instalado.
  - Files: `backend/tests/conftest.py`, `pyproject.toml`
  - Verify: un test que inserte una fila con FK inválida **falla**; si pasa, las FKs están apagadas
- [ ] **T2 (P1, human: ~3h / CC: ~30min)** — backend — Tests de regresión del scoping **[CRÍTICO]**
  - Surfaced by: regla de regresión — cuatro escrituras ajenas confirmadas contra la DB
  - **Mecanismo:** tests a nivel de servicio construyendo `Principal` directamente, no por HTTP.
    Con `auth_enabled=false` toda petición se atribuye a `dev_user_email`, así que un test de
    API no puede *ser* Sofía hasta T8. Construir el `Principal` sí ejercita el código real de
    acceso — es como se verificó el bug hoy.
  - Files: `backend/tests/test_athlete_scoping.py`
  - Verify: rojo antes de T3, verde después. Semana ajena, test ajeno, borrado ajeno → None/404
- [ ] **T3 (P1, human: ~5h / CC: ~1h)** — backend — `visible_swimmers` en `Principal` + filtro
  - Surfaced by: Sección 1 + D6 — la segunda frontera no existe
  - Files: `core/dependencies.py`, `modules/{plans,swimmers,aerobic_tests,dashboard}/`
  - Incluye los dos aeróbicos que faltaban en el mapa: `GET /aerobic-tests/{id}` y
    `/{id}/previous`; `previous_test` (`service.py:77-89`) además no filtra por equipo en absoluto
  - Verify: T2 pasa a verde
- [ ] **T4 (P1, human: ~2h / CC: ~20min)** — backend — Recortar el roster en `to_plan_response`
  - Surfaced by: Voz externa #1 — `AthletePlanResponse` lleva `swimmer_name`, `specialty`,
    `aerobic_base` y los `events` con `current_time`/`goal_time` de cada compañero, y
    `EventPicker.tsx:58` construye su desplegable con eso. Es la fuga más rica y la UI de
    atleta no puede esquivarla
  - Files: `plans/service.py:72-86`, `plans/schemas.py:94-102`
  - Verify: como Sofía, `plan.athletes` trae una entrada; T16 no necesita filtrar en React
- [ ] **T5 (P1, human: ~2h / CC: ~20min)** — backend — Autorización por campo en `WeekUpdateRequest`
  - Surfaced by: Voz externa #3 — tras el filtro por nadador la fila **es suya**, así que
    escribir `disabled`/`disable_reason` pasa a ser legítimo. Es el parón del entrenador y
    redispara `_recalculate_event`
  - Files: `plans/schemas.py:148-153`, `plans/router.py:124-126`
  - Verify: atleta escribe `real_time` → 200; escribe `disabled` → 403
- [ ] **T6 (P1, human: ~1h / CC: ~15min)** — backend — `team-week` fuera del alcance del atleta
  - Surfaced by: Voz externa #2 — marcado ❌ en la tabla pero sin tarea ni mecanismo
  - Files: `dashboard/router.py:42-51`
  - Verify: como Sofía, `GET /dashboard/team-week` → 403
- [ ] **T7 (P2, human: ~3h / CC: ~30min)** — backend — Extraer `plans/access.py` (puerta completa)
  - Surfaced by: Sección 2 + D7 — la autorización vive entre CRUD y motor; el default
    `principal=None` de `service.py:224` es el camino inseguro
  - Files: `plans/access.py`, `service.py`, `router.py`, `dashboard/service.py`
  - Verify: T2 sigue en verde (ahora sí prueba algo: existe cobertura sobre lo que se mueve)

### Fase 2 — toggle

- [ ] **T8 (P1, ~2h / CC: ~20min)** — backend — Cabecera `X-PeakStroke-Dev-User`
- [ ] **T9 (P1, ~1h / CC: ~15min)** — backend — 4 tests de la cabecera **[CRÍTICO: "auth ON la ignora"]**
  - La condición extra de entorno que propuse no compra nada (`_check_production` ya lo cubre);
    el presupuesto crítico va a la línea que sí importa
- [ ] **T10 (P2, ~1h / CC: ~15min)** — backend — `GET /auth/dev-identities` (404 con auth on)
- [ ] **T11 (P1, ~45min / CC: ~15min)** — backend — `seed.py`: coach asistente, atleta sin ficha,
  atleta sin macrociclo, **y atleta con `swimmer.is_active=False`** (`list_swimmers` excluye
  inactivos, y `AerobicPage.tsx:29` resuelve a null → página en blanco)
- [ ] **T12 (P1, ~2h / CC: ~20min)** — frontend — `useDevIdentity` + inyección en `api.ts`
  - `lib/api.ts:10-13` esparce `...options` **después** de `headers`: hacer merge, no spread,
    o un llamador con `headers` propios tira `Content-Type` en silencio
- [ ] **T13 (P1, ~2h / CC: ~20min)** — frontend — Ajustes + etiqueta desde `/auth/me`
- [ ] **T14 (P2, ~1h / CC: ~10min)** — frontend — Limpieza real al cambiar identidad
  - Surfaced by: Voz externa #9 — `createSyncStoragePersister` escribe con throttle de 1s, y
    `dashboard`/`plans`/`swimmers`/`weeks` **sí** se persisten. `clear()` + `reload()` inmediato
    deja que la escritura pendiente rehidrate los datos del anterior, y con `staleTime` de 5min
    se quedan en pantalla. Hace falta `persister.removeClient()` antes del reload

### Fases 3 y 4 — UI

- [ ] **T15 (P1, ~3h / CC: ~30min)** — frontend — `roles` en navConfig **+ guardas de ruta**
  - `App.tsx:54-64` registra todas las rutas; `/equipo` es alcanzable tecleando la URL.
    `activeNavItem` (`navConfig.ts:29`) además rotula mal en rutas ocultas
- [ ] **T16 (P1, ~3d / CC: ~3h)** — frontend — Versión personal de las 4 páginas
- [ ] **T17 (P1, ~1d / CC: ~1h)** — frontend — Estados vacíos
  - Incluye `ps-selected-plan` viejo apuntando a un plan invisible → 404 →
    `DashboardPage.tsx:37-47` pinta el CTA de entrenador "Crea tu primer macrociclo"
- [ ] **T18 (P2, ~2h / CC: ~20min)** — frontend — `useIsOwner()` y capa de owner
- [ ] **T19 (P1, ~15min / CC: ~5min)** — docs — Corregir la nota 18 del vault
  - El §6 paso 4 afirma que el scoping está hecho, y por eso nadie lo miró

## Paralelización

| Lane | Tareas | Depende de |
|---|---|---|
| A | T1 → T2 → T3 → T4/T5/T6 → T7 | — |
| B | T8 → T9 → T10 → T11 | T1 (para T9) |
| C | T12 → T18 | T3, T8 |

T4, T5 y T6 son independientes entre sí y pueden ir en paralelo tras T3. Lane C toca solo
frontend, sin conflicto con A ni B.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | mode: SCOPE_REDUCTION, 0 critical gaps |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | voz externa vía subagente Claude: 11 hallazgos + 5 menores |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 9 issues, 1 critical gap |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**CODEX:** no ejecutado (CLI ausente). La voz externa corrió como subagente de Claude: mismo
modelo base, así que comparte puntos ciegos, pero con contexto fresco y sin anclaje al
razonamiento de la revisión principal.

**CROSS-MODEL:** dos tensiones resueltas a favor de la voz externa — `visible_swimmer_ids` en
lugar de `swimmer_id` (D6) y `access.py` con la puerta completa (D7). Confirmó además que el
orden T1-antes-de-tests era incorrecto, y aportó cinco hallazgos que la revisión principal no
vio: la fuga de `to_plan_response`, la ausencia de guardas de ruta, la autorización por campo
en `WeekUpdateRequest`, la trampa de FKs apagadas en el conftest y el spread de cabeceras en
`api.ts`.

**VERDICT:** CEO + ENG + voz externa completados. Plan reordenado: harness → tests en rojo →
scoping → verde. Listo para implementar por T1.

NO UNRESOLVED DECISIONS
