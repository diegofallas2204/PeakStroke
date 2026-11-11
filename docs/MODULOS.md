# Trabajar y publicar por módulos

> Desde el 2026-11-10. Para repartir lo que falta por módulos, depurar uno sin
> el ruido de los demás y publicar cada uno como su propia versión. **Qué toca
> en cada rama**: [más abajo](#qué-trabajar-en-cada-rama).

## Qué es un módulo

Cada sección del menú, nombrada por su ruta:

| Módulo | Ruta | Sección |
|---|---|---|
| `inicio` | `/` | Inicio |
| `macrociclos` | `/macrociclos` | Macrociclos |
| `atletas` | `/atletas` (y `/atletas/:id`) | Atletas y la página de cada uno |
| `pruebas` | `/pruebas` | Base aeróbica |
| `entrenamiento` | `/entrenamiento` | Entrenamiento |
| `plan-semanal` | `/plan-semanal` | Plan semanal (Plan, Progresión, Zonas) |
| `equipo` | `/equipo` | Tabla del equipo |
| `simulador` | `/simulador` | Simulador |

**No son módulos**, y están en cualquier versión: Perfil, Ajustes, el login y el
cambio de contraseña. Tampoco el **backend**: es uno para todos y ya protege cada
ruta por rol. Un módulo apagado es un alcance de la interfaz, no una frontera de
seguridad.

## Qué pasa con un módulo apagado

- No sale en el menú, ni en el escritorio ni en el móvil.
- Su ruta redirige a la primera sección que sí está, aunque se teclee.
- Los enlaces que llevaban a él dejan de serlo. Por ejemplo, en `modulo/inicio`
  la tarjeta «Atletas en plan» sigue mostrando el número pero no lleva a la
  Tabla del equipo, y el botón «Tabla del equipo» desaparece.
- En **Ajustes** se lee qué módulos trae la versión que tienes delante.

## Cómo se elige

Al arrancar Vite (`npm run dev` o `npm run build`), en este orden:

1. **`VITE_MODULOS`**, si está puesta: `VITE_MODULOS=inicio,atletas npm run dev`.
   `todos` o vacía, todos.
2. **El nombre de la rama**: en `modulo/<nombre>` solo ese módulo. En GitHub
   Actions se lee de `GITHUB_HEAD_REF`/`GITHUB_REF_NAME`.
3. En cualquier otra rama (`Preliminar`, `main`), todos.

Se decide por la rama, y no por un archivo dentro de ella, para que fusionar el
trabajo de `modulo/inicio` de vuelta no traiga el interruptor: si la rama
llevara un `.env` propio, `Preliminar` acabaría con un solo módulo.

Código: `frontend/modulosDeRama.ts` (qué módulos trae la versión) y
`frontend/src/lib/modulos.ts` (qué hace la interfaz con ellos). Tests en
`modulosDeRama.test.ts` y `src/lib/modulos.test.ts` (`npm test`).

## El flujo

```
Preliminar ──┬──────────────●──────────────●─────▶   (todos los módulos)
             │              ▲ merge        ▲ merge
             └─ modulo/inicio ─●──●──●─────┘           (solo Inicio)
                                     │
                                     └─ tag inicio-v0.1.0
```

1. **Rama del módulo**, desde `Preliminar`: `git switch -c modulo/<nombre> Preliminar`.
2. **Se trabaja ahí** lo que falte de ese módulo. Cada tarea o issue va con la
   etiqueta del módulo (`modulo:inicio`) para repartirlas.
3. **Se depura** con `npm run dev` en esa rama: la app solo enseña ese módulo.
4. **Versión del módulo**: con la rama en verde, un tag `<módulo>-v<x.y.z>`
   (`inicio-v0.1.0`) y su build (`npm run build`), que trae solo ese módulo.
5. **De vuelta**: PR de `modulo/<nombre>` a `Preliminar`. Como lo único que la
   rama cambia es código del módulo, se fusiona sin conflictos con los demás.
6. Mantén la rama al día con `git merge Preliminar` (o `rebase`) mientras dure.

**Lo que hay que saber**

- **Un módulo no siempre se basta solo.** Inicio lee datos que se crean en
  Macrociclos y Atletas: en `modulo/inicio`, sin datos sembrados, sale vacío.
  Para depurarlo se usa la base de desarrollo (`seed.py`) o un backend con datos.
- **Un cambio compartido** (componentes de `components/`, `lib/`, el backend)
  hecho en la rama de un módulo afecta a todos al fusionarlo. Si es grande,
  mejor en `Preliminar` y que la rama lo traiga con un merge.
- **El backend no se recorta.** Una versión de Inicio sirve con el mismo backend
  que la versión completa.

---

## Qué trabajar en cada rama

> Repartido el 2026-11-10 a partir de lo que quedaba del plan de rediseño
> (`docs/PLAN-DE-TRABAJO.md`, `docs/REDISENO.md` §10), de `TODOS.md` y de los
> extras del vault. **Esto es el mapa; el detalle de cada punto sigue en su
> origen**, y al cerrarlo se marca allí y aquí.

Leyenda: **🔒** bloquea publicar con usuarios reales · **❓** pide una decisión
tuya antes de construir · **✨** función nueva · **🧹** pulido.

### El orden

```
1. transversal/infra ──────┐   sin esto no se publica nada
   transversal/fronteras ──┤
2. transversal/sesion ─────┘   antes de abrir a usuarios reales
3. modulo/inicio · modulo/simulador · modulo/macrociclos · modulo/atletas
4. modulo/pruebas · modulo/plan-semanal · modulo/entrenamiento · modulo/equipo
5. psadmin (espera a PostgreSQL)          ·   después del release: SaaS
```

**Una versión de un módulo no es un producto entero.** Inicio solo enseña lo que
se crea en Macrociclos y Atletas, así que la primera versión para un club real
es un **paquete**: `VITE_MODULOS=inicio,macrociclos,atletas`, y lo demás a
medida que salga. Cada módulo se publica con su tag; el paquete, con el suyo
(`release-v0.1.0`).

### Trabajo transversal (no es un módulo)

Va en ramas `transversal/<tema>` desde `Preliminar` y vuelve a ella; las ramas
de módulo lo reciben con `git merge Preliminar`.

**`transversal/infra` — publicar** (TODO-34)
- 🔒 Dónde se aloja, guía de despliegue y las tres variables obligatorias
  (`ENVIRONMENT=production`, `JWT_SECRET`, `REFRESH_COOKIE_SECURE`).
- 🔒 HTTPS y cabeceras de seguridad (CSP, `X-Content-Type-Options`, `frame-ancestors`).
- 🔒 El proxy: detrás de uno, el freno de intentos ve a todos como un solo
  origen (`X-Forwarded-For` se ignora a propósito, R11). Hay que declarar el
  proxy de confianza.
- 🔒 PostgreSQL de verdad: probar en él las migraciones `e3b8f1a6c4d2` y
  `f4c2a9d7e1b3` (solo se probaron en SQLite) y la vista `v_admin_cuentas`.
- 🔒 CI que corra pytest, ruff, `tsc`, eslint, vitest y `npm audit` en cada PR.
- 🧹 Fijar las versiones de Python (`requirements.txt` va con `>=`), `pip-audit`,
  y los 10 avisos moderados de npm en la cadena de eslint.

**`transversal/fronteras` — aislamiento entre clubes** (TODO-2)
- 🔒 Barrer todas las rutas desde el club A contra los ids del club B: 404 y
  nunca una fila ajena. Hay tests sueltos, no el barrido, y es la promesa más
  cara del producto.

**`transversal/sesion` — cuenta, login y perfil** (TODO-36, TODO-17)
- ❓ La cuenta sin club no puede cambiar su temporal hasta canjear el código:
  darle `get_current_user` a `/auth/me/password` rompe una regla escrita.
- ❓ «Olvidé mi contraseña»: o el entrenador restablece la de su atleta desde la
  app (ver `modulo/atletas`), o cambia el texto del login — hoy dice «pídeselo a
  tu entrenador» y solo puede hacerlo quien opera el servidor.
- ❓ TODO-17: la invitación crea la cuenta y el entrenador ve su temporal.
  Mitigado (hay que cambiarla al entrar); bloquea abrir el registro público.
- 🧹 El freno por origen con un club entero en la misma wifi (20 fallos en 15 min).
- 🧹 Perfil: `confirm()` del navegador en «cerrar en todos los dispositivos»
  (`AccountCard`) y al revocar un acceso (`MembersCard`).
- 🧹 La marca dice «Performance Planner», en inglés.
- 🧹 Un componente de «no se pudo cargar» con Reintentar, para que ningún módulo
  pinte un fallo como si estuviera vacío (cada rama lo aplica a lo suyo).
- 🧹 Limpiar las cabeceras del conmutador de desarrollo que queden guardadas con
  el login puesto. Sin `navigator.locks` (Safari < 15.4) dos pestañas pueden
  chocar al renovar.

**`psadmin` — la consola de administración** (D2 y D3 del plan; TODO-1)
- ❓ **R10**: túnel SSH o red privada (Tailscale) para entrar.
- ❓ **R12**: espera a PostgreSQL — la barrera 4 (usuario de solo lectura) solo
  existe ahí. Depende de `transversal/infra`.
- ❓ TODO-1: qué administra el rol «admin».
- ✨ D2: proceso aparte, sesión propia con 2FA y sus cuentas por CLI.
- ✨ D3: paneles de accesos, sesiones (refresh reusado), cuentas, equipos y
  salud, sobre las cuatro vistas `v_admin_*`.

### Por módulo

**`modulo/inicio`**
- 🧹 Un fallo de carga se pinta como «Sin macrociclo activo» y ofrece crear uno:
  `DashboardPage` trata cualquier error como vacío. Separar el 404 (no hay
  macro) de un error de verdad.
- Lo demás está hecho (móvil, nombre, icono). **Candidato a primera versión.**

**`modulo/simulador`**
- Sin pendientes conocidos. **Candidato a primera versión** junto con Inicio.

**`modulo/macrociclos`**
- 🧹 El asistente de crear macrociclo y «Agregar atleta» no caben en móvil
  (`PlanWizard`, `AssignAthleteModal`: filas de columnas fijas).
- 🧹 Fechas en ISO (`2026-08-10`) en la tarjeta y en el selector de macrociclo
  (`PlansPage`, `MacroSwitcherModal`). Ojo: `new Date('2026-08-10')` es
  medianoche UTC y en Costa Rica pinta el día anterior; hay que leerla sin zona.
- 🧹 `confirm()` del navegador al eliminar un macro y al quitar un atleta.

**`modulo/atletas`**
- ✨ Restablecer la contraseña de un atleta desde su página (el backend ya tiene
  la operación, en el CLI). Resuelve el «olvidé mi contraseña» de
  `transversal/sesion`.
- ✨ Desde su página, llegar también a su macrociclo (hoy lleva a Plan semanal,
  Base aeróbica y Entrenamiento). Nota 27 del vault.
- 🧹 `confirm()` del navegador al dar de baja (`SwimmersPage`) y al revocar un
  código (`LinkCodeModal`). Dar de baja es reversible: mejor un «Deshacer».

**`modulo/pruebas`** (Base aeróbica)
- ✨ **Test de lactato** como opción del test aeróbico: notas 26 y 28 del vault,
  con su prompt listo (`Workflows/Prompt — Sesión del Test de Lactato`). Es la
  función nueva más grande que ya está desbloqueada.
- ❓ ¿Base aeróbica pasa a ser la cuarta vista de Plan semanal o sigue como
  sección? (la «cuarta pestaña de B1», abierta desde el 2026-08-16).
- 🧹 Fechas en ISO en el historial de tests; `confirm()` al eliminar un test.

**`modulo/plan-semanal`**
- ❓ **N1 y N2** (`REDISENO.md` §10.3): qué entra en el promedio semanal —
  ¿todos los tiempos de la prueba o el que marque el entrenador?, ¿la
  competencia manda? Aparcadas; bloquean el módulo de entrenamiento diario.
- ✨ PDF de la tabla individual del atleta (nota 24: ya existen el del simulador
  y el del equipo).
- 🧹 El motivo del parón se pide con `prompt()` del navegador (`VistaPlan`).

**`modulo/entrenamiento`**
- ❓ TODO-20: ¿borrar una sesión se audita? (probablemente sí cuando el
  entrenador borra la de un atleta).
- ✨ **Módulo de entrenamiento diario** (nota 22): la sesión que sube el
  entrenador y el atleta ve antes de nadar. Depende de **N3/N5** (sesiones por
  semana; texto libre o series) y de N1/N2, y comparte trabajo con `plan-semanal`.
- 🧹 `confirm()` del navegador al borrar una sesión (`SessionsCard`).

**`modulo/equipo`** (Tabla del equipo)
- ✨ Que el nombre de cada atleta lleve a su página (`/atletas/:id`) y no solo a
  Entrenamiento. Nota 27 del vault.

### Aparcado a propósito

- Las tablas de la base en español (§7.2 fila 9 de `REDISENO.md`).
- **Capa SaaS** (pagos, tiers, `billing/`): después del primer release.
