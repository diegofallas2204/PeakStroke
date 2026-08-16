# PeakStroke — Plan de trabajo

> Todo lo que salió de la sesión del **2026-08-12**, ordenado para trabajarlo por
> partes. Cada bloque trae una explicación para leer y un **prompt listo para
> copiar** en una sesión nueva de Claude Code.
>
> **Estado: A0 y A1 hechos** (2026-08-13 y 2026-08-14, ver cada bloque). El resto
> sigue sin empezar y la beta sigue intacta. Este documento es el mapa.

---

## Cómo usar este documento

Está partido en tres partes, y el orden importa:

| Parte | Qué es | Toca el rediseño |
|---|---|---|
| **A — Correcciones** | Defectos concretos que ya existen en la beta. Baratos, independientes | no |
| **B — Consolidación de la UI** | Fusionar las secciones que dibujan lo mismo | no |
| **C — Rediseño POO** | La versión limpia: objetos, entidades, roles, un solo motor | sí |
| **D — PSAdmin** | Auditoría, CLI de operaciones y app de administración separada de verdad | parcial |

**Cada bloque es una sesión.** No los encadenes: cada prompt está escrito para
funcionar en una sesión que arranca en frío, sin saber nada de esta conversación.

**Y una sesión a la vez.** El 2026-08-14 se corrieron A0 y el backend de TODO-16
en paralelo sobre el mismo directorio de trabajo. Las dos tocaron `conftest.py`,
un `git checkout` de una sesión se llevó por delante trabajo sin commitear de la
otra, y el primer commit salió roto porque importaba un módulo que la otra sesión
todavía no había commiteado. Se recuperó todo, pero el rato se perdió: git no
arbitra dos sesiones sobre el mismo árbol. Si hacen falta dos a la vez, que cada
una tenga su `git worktree`.

**Regla de oro antes de cualquier bloque de la parte C:** haz primero **A0**. Es
la red de seguridad y sin ella la fusión de motores es a ciegas.

### Documentos que acompañan

| Documento | Qué contiene |
|---|---|
| `docs/REDISENO.md` | El modelo objetivo completo: objetos, entidades, roles, esquema |
| `E:/Obsidian/Inbox/Peakstroke/20 - Modelo del Rediseño.md` | El porqué y el análisis de riesgo |
| `CLAUDE.md` (raíz de `peakstroke/`) | Las reglas vigentes del proyecto |
| `TODOS.md` | Trabajo aplazado con contexto |

---

## Estado de partida (medido el 2026-08-12)

Esto es lo que hay hoy, comprobado, no estimado:

> Las cifras de abajo son las del 2026-08-12 y se dejan como quedaron. Lo que se
> movió desde entonces: A1 (**442 tests** al 2026-08-13), y A0 más el backend de
> TODO-16 (**478 tests en verde** al 2026-08-14, y el lint del backend ya no es
> «no existe»: `ruff check .` limpio).
>
> **Medido de nuevo el 2026-08-16, cerrada la parte A y B1** — es la línea de
> salida real de la parte C: **478 tests en verde** (62 s) · `ruff check .`
> limpio · `tsc --noEmit`, `eslint .` y `vite build` limpios · backend **7.753
> líneas / 15 modelos / 1 archivo >300** (`domain/engine.py`, la excepción
> declarada) · frontend **8.583 líneas / 0 archivos >300 / 7 secciones** +
> Perfil y Ajustes. Las dos filas de abajo que ya no valen son las dos últimas.

| | |
|---|---|
| Tests backend | **307 en verde** (97 s) |
| Tipos frontend | `tsc -b` **limpio** |
| Lint frontend | `eslint .` **limpio** |
| Lint backend | **no existe** — no hay `ruff` configurado |
| `generate_plan` (15 sem) | 0,31 ms |
| `ScienceEngine.generate_plan` | 0,19 ms |
| `project_season` (3 macros) | 0,59 ms |
| Objeto de valor `frozen`+`slots` | 0,24 µs |
| Backend | 7.464 líneas · 14 modelos · 5 archivos >300 líneas |
| Frontend | 8.356 líneas · 8 secciones + Perfil + Ajustes |

**Traducción:** el programa está sano y es rápido. Todo el cálculo científico
cuesta menos de 1 ms, contra 30–80 ms que tarda una petición con su ida y vuelta
a la base de datos. **El rendimiento no es un problema y el rediseño no lo va a
volver uno.** Lo que está mal es dónde vive el comportamiento.

---

# PARTE A — CORRECCIONES

Defectos reales que ya existen. Se pueden arreglar hoy, no dependen del rediseño,
y dejan el terreno limpio para él.

---

## A0 · Red de seguridad — ✅ HECHO (2026-08-14)

**Prioridad: PRIMERO. Nada de la parte C debería empezar sin esto.**

### Qué pasaba

Dos huecos en las herramientas:

**1. Los tests no protegen contra deriva numérica.** De 165 asserts en los tests
del motor, **75 comparan valores concretos**; los otros 90 son estructurales
(que la curva sea monótona, que el valor caiga en un rango, que el orden sea el
correcto). Eso caza un motor roto, pero **no caza un motor que devuelve otro
número plausible**.

Esto importa muchísimo para el bloque C4 (fusionar los dos motores), donde el
riesgo no es que reviente sino que los objetivos semanales de tus atletas
**cambien sin que nadie lo note**.

**2. No hay linter de Python.** El frontend tiene `eslint` y `tsc`; el backend
no tiene nada equivalente. `pyproject.toml` solo configura `pytest`.

### Qué se hace

Un **snapshot de referencia**: generar los planes de una batería de atletas
representativos con el motor actual, guardar la salida completa en disco, y un
test que compare contra ella. A partir de ahí, cualquier cambio en el motor que
mueva un número **falla el test**, y decides si esa diferencia era intencionada.

Más `ruff` configurado y en verde.

### Cómo quedó

**El snapshot: 153 casos, 162 tests, un fichero de referencia por camino de
cálculo** — mezclarlos en uno haría el diff ilegible, que es justo lo único que
tiene que hacer bien:

| Camino | Casos | Referencia (`backend/tests/snapshots/`) |
|---|---|---|
| `engine.progression.generate_plan` | 61 | `motor_progression.json` |
| `engine.progression.recalculate_remaining` | 14 | `motor_recalculo.json` |
| `domain.ScienceEngine.generate_plan` | 61 | `motor_science.json` |
| `domain.ScienceEngine.project_season` | 17 | `motor_temporada.json` |

Ejes cubiertos: los 5 niveles × las 6 distancias, los 5 estilos, piscina 25 y 50,
`n_mac` 1 y 3, edad de menor (14 y 16), metas factibles y agresivas (con
extensión), las 5 curvas, duraciones de 10/15/20 semanas, parones por lesión de 2
y 4 semanas, y el macro plano de meta = tiempo actual.

**Las entradas son literales congelados, no derivados del motor.** Si mañana
cambian los factores de zona, lo que se mueve es la salida —visible en el diff— y
no la entrada, que se movería en silencio. Un test comprueba que cada tiempo
literal sigue clasificando en el nivel bajo el que está escrito. El catálogo de
casos vive aparte, en `tests/motor_casos.py`: qué se congela se decide allí, cómo
se compara en `test_motor_snapshot.py`.

**Regenerar es un gesto explícito:** `PEAKSTROKE_UPDATE_SNAPSHOTS=1`. Después hay
que leer el diff en git, que es la lista exacta de lo que cambió de comportamiento.

**Ya se ganó el sueldo dos veces el mismo día**: A1 (fuente única de los estilos y
del tope de extensión) y el backend de TODO-16 (partir los cuatro archivos de
+300 líneas) pasaron por encima del motor sin mover **ni un número** de los 153
casos. Eso es la diferencia entre «los tests pasan» y «se demostró que la salida
es idéntica» — que es lo que hará falta poder decir en C4.

**Qué NO cubre**, y conviene cerrarlo antes de C4:

- `analyze_feasibility` — y A1 acabó de cambiarle el comportamiento (26 → 30)
- `generate_extension` del adaptador (la del `ScienceEngine` sí, vía metas agresivas)
- `performance_status`, `aerobic.*`, `zone_km_distribution`, `training_intervals`
- `rep_distance ≠ 100`, `weeks_per_micro = 5`, fases personalizadas y el `profile`
  explícito en `generate_plan` (en `project_season` sí está cubierto)

**Ruff configurado y en verde** en `backend/pyproject.toml`:
`E,W,F,I,UP,B,C4,SIM,ANN,RUF`, objetivo de 100 columnas con **tope duro en 120** —
partir las tablas científicas alineadas (`I_MAX_TABLE`, `ZONE_OVER_RACE`) para
ganar 15 caracteres haría ilegible justo el código que se lee contra el paper. De
863 avisos a 0. Lo arreglado fue mecánico: orden de imports, `noqa` inservibles,
anotaciones entrecomilladas, `zip(strict=False)` explícito y `contextlib.suppress`.

**Lo que ruff encontró y NO se tocó** queda listado fichero por fichero en
`per-file-ignores`, como deuda con nombre y no como excepción permanente:

- **65 firmas de `app/` sin tipo de retorno**, casi todas manejadores de router.
  No es mecánico: el tipo correcto de un handler con `response_model` —o de un
  `Select` de SQLAlchemy— es una decisión, no un `-> None`
- ~465 firmas de `tests/`
- `SIM108` en `km_distribution`: ruff pide un ternario de 90 caracteres donde hay
  un `if/else` con su comentario propio explicando el caso especial
- `RUF001/2/3` (63 avisos): la tipografía española (— · «») marcada como «ambigua»
- `tools/generate_manual.py`: argumentos con tipos de reportlab, y `**kw` que solo
  se puede anotar con el `Any` que ANN401 prohíbe

### Riesgo

**Ninguno.** Solo añade. No toca código de producción.

### Prompt (ejecutado el 2026-08-14)

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee primero CLAUDE.md de esa carpeta para las reglas del proyecto.

CONTEXTO
Voy a reestructurar el motor científico más adelante y necesito una red de
seguridad antes. Hoy el motor tiene 307 tests en verde, pero de los 165 asserts
que hay en tests/test_engine.py, tests/test_domain_engine.py y
tests/test_send_off.py, solo unos 75 comparan valores numéricos concretos. El
resto son estructurales. Eso detecta un motor roto pero NO detecta un motor que
devuelve otro número plausible, que es exactamente el riesgo de la fusión que
viene después.

TAREA 1 — Snapshot de referencia del motor
Crea tests/test_motor_snapshot.py con un test de regresión por comparación
contra fichero de referencia:

- Define una batería de casos representativos que cubra los ejes del dominio:
  los 5 niveles (beginner..elite), las 6 distancias (50/100/200/400/800/1500),
  los 5 estilos válidos por distancia, piscina 25 y 50, n_mac 1 y 3, con y sin
  edad de menor, metas factibles y metas agresivas (que disparen extensión).
  Apunta a 40-60 casos, no a miles.
- Para cada caso, ejecuta AMBOS motores por separado:
  app.engine.progression.generate_plan  y  app.domain.ScienceEngine.generate_plan
- Serializa la salida completa (todas las semanas, todos los campos, todas las
  zonas con su ritmo/salida/descanso) a JSON con redondeo estable.
- Guarda en tests/snapshots/motor_progression.json y motor_science.json
- El test compara la salida actual contra el fichero y falla con un diff legible
  que diga QUÉ caso y QUÉ campo cambió.
- Añade una forma explícita de regenerar los snapshots a propósito
  (variable de entorno o flag), documentada en el docstring del archivo.

TAREA 2 — Linter de Python
Configura ruff en backend/pyproject.toml alineado con las reglas de CLAUDE.md
(type hints en todo, líneas de ~100). Corre `ruff check .`, y deja el repo en
verde: arregla lo que sea trivial y seguro; lo que exija criterio, lístamelo
en vez de tocarlo.

RESTRICCIONES
- No cambies NADA del comportamiento del motor. Este bloque solo añade tests
  y configuración.
- Los 307 tests existentes deben seguir en verde.

AL TERMINAR
Dime cuántos casos cubre el snapshot, qué ejes del dominio quedaron sin cubrir
y qué encontró ruff que no tocaste.
```

---

## A1 · Las reglas que dicen dos cosas distintas — ✅ HECHO (2026-08-13)

### Qué pasaba

Hay dos motores en el código (ese es el problema de fondo, y se arregla en C4).
Mientras tanto, **ya habían divergido en dos reglas concretas**:

**1. Los estilos válidos en 50 metros.**

```
domain/engine.py::allowed_strokes(50)  → libre, espalda, mariposa, pecho, COMBINADO
engine/events.py::allowed_strokes(50)  → libre, espalda, pecho, mariposa
```

No existe el 50 combinado. La versión del dominio estaba mal — pero además **no la
usaba nadie**: no estaba exportada en `domain/__init__.py`. Código muerto que
contradecía la regla correcta, esperando a que alguien lo importara por error.

**2. El tope de semanas de extensión.**

```
domain/engine.py    ScienceEngine.MAX_EXTENSION_WEEKS = 30
engine/feasibility.py  MAX_EXTENSION_WEEKS = 26
```

Y el comentario de `feasibility.py:24` afirmaba que *"coincide con el motor de
dominio"*. No coincidía. Un comentario que miente es peor que no tener comentario,
porque el siguiente que lo lea no va a comprobarlo.

### Cómo quedó

**Divergencia 1 — cerrada borrando la copia mala.** Se verificó primero que nadie
consumía la del dominio: los tres llamadores reales (`simulator/schemas.py` ×2,
`plans/schemas.py`) importan de `app.engine.events`, y el frontend
(`lib/constants.ts:38-44`) implementa la misma regla que `events.py`. El dominio
era el único de tres que daba el 50 combinado por válido. Se retiró de
`domain/engine.py` dejando un comentario que dice dónde vive la regla.

**Divergencia 2 — fijada en 30**, tras comparar lo que ve el entrenador con cada
valor. Dato que decidió la conversación: **el 26 era el único visible**. El 30 no
gobernaba nada, porque `ScienceEngine.generate_plan` solo se alcanza en
producción desde `project_season`, que lee únicamente `plan.realistic_final` — un
número que no depende del tope. `MAX_EXTENSION_WEEKS = 30` es ahora constante de
módulo en `domain/engine.py`, exportada en `domain/__init__.py` e importada por
`feasibility.py`, que ya no la redeclara. El comentario que mentía está reescrito
y explica qué pasaba (el simulador sugería 41 semanas mientras el motor extendía
hasta 45). **Efecto visible:** con meta muy agresiva el simulador pasa a sugerir
hasta 45 semanas y a dibujar 30 filas de extensión, no 26.

**Tests: 442 en verde** (433 de base − 3 movidos + 12 nuevos). Los snapshots no
hicieron falta regenerar: un solo caso de `motor_science.json`
(`50-elite-libre-p50-m1-adulto-agresiva-science-w15`) toca el tope, y al elegir 30
no se movió. Con 26 habría pasado de 45 a 41 semanas.

**Regresión: `tests/test_reglas_unicas.py`** (nuevo). No comprueba solo el valor
de cada regla: comprueba que sigue habiendo **una sola copia**. El test del tope
parsea el AST de `feasibility.py` en vez de comparar valores, porque una copia
nueva con el mismo número pasaría una comparación de valores y volvería a
divergir. `TestAllowedStrokes` se movió aquí desde `test_domain_engine.py`.

`sandbox/engine.py` conserva su copia de `allowed_strokes`: está fuera de `app/` y
es el original del port.

### Por qué importa (sigue en pie)

Esto era el síntoma de que la misma regla vive en dos sitios. Corregir los
valores sin corregir la forma garantiza que vuelva a pasar — por eso la solución
de verdad sigue siendo C1 (`Prueba` como objeto con la validez dentro) y C4 (un
solo motor). Lo que A1 compró es que no haya reglas contradictorias vivas
mientras tanto, y una red que avisa si vuelven.

### Lo que la auditoría de cierre encontró de más

Al terminar se barrieron las demás reglas duplicadas entre `app/domain/` y
`app/engine/`. **No se tocó ninguna** — quedan para C4. Estado medido:

| Regla | Copias | ¿Coinciden hoy? |
|---|---|---|
| **Clasificación de nivel** | `ScienceEngine.generate_plan`, `project_season`, `envelope.level_for` — tres copias de la misma derivación | **No.** El dominio toma el perfil del *evento más cercano*, `envelope` de la *distancia cruda*. 600 m en 7:00 → dominio `competitive`, engine `elite`. La API acepta `distance` de 25 a 10000, así que es alcanzable |
| **Techo I_max** | `ScienceEngine._effective_i_max` vs `envelope.science_envelope` | **Solo con 15 semanas exactas.** El dominio fija 15; `envelope` usa las del plan. 400 m a 20 sem: 0.0270 vs 0.0360 |
| **Factibilidad** | `ScienceEngine._check_feasibility` vs `feasibility.analyze_feasibility` | **Umbrales sí** (0.85 / 1.15 idénticos), **veredictos no.** 400 m 5:00→4:51 en 12 sem: dominio `warning`, engine `aggressive`. Hereda el problema del techo. Hoy invisible: el `feas_status` del dominio no llega a ninguna respuesta |
| **Distribución de fases** | `MACRO_15_PHASES` (5 fases: 3/4/4/2/2) vs `progression.DEFAULT_PHASES` (4 fases: 30/40/20/10 %) | **No.** A 15 semanas: `base_general 1-3` vs `Base 1-4`; `umbral_css 8-11` vs `Construcción 5-10` |
| **Volumen semanal** | `WEEKLY_VOLUME_KM` + `MAX_VOLUME_BY_STROKE` vs `km_distribution.distribute_km` | **No son copias, son dos modelos.** El dominio *deriva* los km de nivel+fase; `engine` *reparte* un `total_km` que teclea el entrenador. Lo que sí está duplicado es la onda 3:1: `[0.77, 0.875, 0.975, 0.55]` vs `[0.78, 0.90, 1.00, 0.58]` |
| `nearest_event` | `ScienceEngine._nearest_event` vs `envelope.nearest_event` | **Sí**, copia literal |
| **Cálculo de zonas** | `ScienceEngine._zones_from_race` vs `zones.calc_zones` | **Sí** en el número central; `zones.py` añade min/mid/max y `send_off` |
| `ZONE_LABELS` | `domain.engine` vs `engine.zones` | **No** — mismo nombre, contenidos distintos (`{"R1": "R1"}` vs `{"R1": "Base aeróbica"}`). El del dominio es identidad y no lo usa nadie |
| **Ritmo /100 m del sprint** | `domain.race_pace_100` (fatiga ×1.100 en 50 m) vs `progression`, que divide en crudo | **No.** 50 m en 25.0 → dominio 55.00, plan persistido 50.00. Es una omisión, no una contradicción: las zonas usan el crudo en ambos |

Dos observaciones para C4: **el nivel, el techo I_max y la factibilidad son la
misma raíz** — `envelope.py` reimplementó la aritmética del dominio en vez de
llamarla, y las tres divergen por lo mismo (qué distancia y cuántas semanas
entran). Y **media clase `ScienceEngine` no la consume producción**
(`WEEKLY_VOLUME_KM`, `MAX_VOLUME_BY_STROKE`, `_check_feasibility`): mismo perfil
de "código muerto que contradice a la regla viva" que tenía el 50 combinado.

### Riesgo

**Bajo**, y confirmado a posteriori. El 50 combinado era código muerto. El tope de
extensión sí afecta a un cálculo visible (las "semanas necesarias" del
simulador), y por eso el valor se eligió en conversación, no por defecto.

### Prompt (ejecutado el 2026-08-13)

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee primero CLAUDE.md de esa carpeta.

CONTEXTO
Una auditoría encontró que la misma regla está implementada dos veces en el
backend y que las dos copias ya dicen cosas distintas. Hoy no voy a unificar los
motores (eso es un trabajo aparte); quiero cerrar las divergencias concretas.

DIVERGENCIA 1 — Estilos válidos en 50 m
  app/domain/engine.py::allowed_strokes(50) devuelve combinado como válido
  app/engine/events.py::allowed_strokes(50) NO lo devuelve
El 50 combinado no existe en natación: la versión correcta es la de events.py.
La de domain/engine.py además no está exportada en domain/__init__.py, así que
hoy no la usa nadie: es código muerto que contradice la regla buena.
Verifícalo antes de tocar nada (busca todos los usos de allowed_strokes en
app/ y tests/) y luego elimina la duplicación dejando UNA sola fuente.

DIVERGENCIA 2 — Tope de semanas de extensión
  app/domain/engine.py    ScienceEngine.MAX_EXTENSION_WEEKS = 30
  app/engine/feasibility.py  MAX_EXTENSION_WEEKS = 26
El comentario de feasibility.py:24 afirma que coinciden. No coinciden.
Antes de elegir un valor, explícame qué consecuencia visible tiene cada uno:
qué ve el entrenador en el simulador con 26 y qué con 30 para una meta muy
agresiva. Espera mi respuesta antes de fijar el valor.
Cuando lo fijemos, que quede en UN solo sitio, importado por el otro, y corrige
el comentario que miente.

RESTRICCIONES
- No unifiques los dos motores. Eso es otro trabajo.
- Los 307 tests deben seguir en verde. Si un test fija el valor viejo del tope,
  dímelo antes de cambiarlo.
- Añade un test de regresión por cada divergencia cerrada.

AL TERMINAR
Busca si hay MÁS reglas duplicadas entre app/domain/ y app/engine/ que yo no haya
detectado (clasificación de nivel, techo I_max, factibilidad, distribución de
fases, volumen semanal) y lístamelas con su estado: ¿coinciden hoy o no?
No las toques, solo repórtalas.
```

---

## A2 · Duplicados y archivos que crecieron de más — ✅ HECHO (backend 2026-08-14, frontend 2026-08-16)

> **Ojo al leer esta sección.** El backend ya estaba partido cuando se escribió
> este plan: el commit `24e3a3f` es *anterior* al commit que creó este archivo,
> así que las cifras de aquí abajo son las de antes del corte y el prompt se
> lanzó una segunda vez en vacío el 2026-08-16. Se conservan como estaban, para
> que el plan siga siendo el registro de qué se encontró y por qué.
>
> **Lo que hay hoy:** la edad vive en `core/dates.py::age_at(birth_date, ref=None)`
> — `plans.service.age_at` y `swimmers.service._age` ya no existen. Los cuatro
> archivos del backend están partidos (`dependencies.py` 386→138 + `principal.py`
> / `dev_identity.py` / `guards.py`; `link_codes/service.py` 411→275 + `codes.py`
> / `queries.py`; `plans/service.py` 333→147 + `roster.py` / `weeks.py`;
> `auth/router.py` 305→120 + `sessions.py` / `members.py`), con los 478 tests en
> verde. El 2026-08-16 se cerró la parte que faltaba, que este plan no listaba:
> `frontend/src/lib/types.ts` (446) → directorio `lib/types/` de siete archivos
> más barril, sin tocar ninguno de los 32 importadores. Ningún archivo del
> proyecto pasa de 300 líneas salvo `domain/engine.py`, que sale en C4.
> El detalle de los dos cortes está en TODO-16 de `TODOS.md`.

### Qué pasa

**Una función de dominio, dos implementaciones con firmas distintas:**

```
modules/plans/service.py:32     age_at(birth_date, ref) -> int | None
modules/swimmers/service.py:28  _age(birth_date) -> int | None
```

Las dos calculan la edad de un atleta. Una acepta fecha de referencia (la usa el
motor, para la edad al inicio del macrociclo), la otra siempre usa hoy.

**Cinco archivos pasan de 300 líneas**, contra la regla del propio `CLAUDE.md`
(*"ningún archivo supera ~300 líneas; si crece, extraer submódulo"*). `TODOS.md`
tiene esto abierto como TODO-16 y decía cuatro; ya son cinco:

```
domain/engine.py           714
modules/link_codes/service.py  411
core/dependencies.py       386
modules/plans/service.py   333
modules/auth/router.py     305
```

### Riesgo

**Bajo**, con un matiz: `core/dependencies.py` es el corazón del aislamiento entre
equipos. Partirlo es seguro pero hay que hacerlo con los tests de guards delante,
no a ojo.

`domain/engine.py` (714) **no se toca aquí** — se disuelve entero en C4.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee primero CLAUDE.md y TODOS.md de esa carpeta (busca TODO-16).

CONTEXTO
Limpieza estructural del backend, sin cambiar comportamiento. Dos cosas.

TAREA 1 — Edad duplicada
app/modules/plans/service.py:32 tiene age_at(birth_date, ref) y
app/modules/swimmers/service.py:28 tiene _age(birth_date). Calculan lo mismo con
firmas distintas. Unifica en una sola función (la de plans/, que acepta fecha de
referencia, es la general: la otra es ese caso con ref=hoy) y déjala donde
corresponda según las reglas de módulos de CLAUDE.md. Antes de moverla, dime
dónde propones ponerla y por qué.

TAREA 2 — Archivos por encima de ~300 líneas
CLAUDE.md dice que ningún archivo pasa de ~300 líneas. Hoy pasan cinco:
  app/domain/engine.py             714   ← NO TOCAR, se rediseña aparte
  app/modules/link_codes/service.py 411
  app/core/dependencies.py          386
  app/modules/plans/service.py      333
  app/modules/auth/router.py        305

Para los cuatro que sí hay que partir: proponme primero el corte de cada uno
(qué submódulo sale, con qué nombre, qué se lleva) y ESPERA mi visto bueno antes
de mover código. Quiero revisar los cortes, no el resultado.

Cuidado especial con core/dependencies.py: es donde vive Principal y todo el
aislamiento entre equipos. Pártelo con tests/test_role_guards.py,
tests/test_athlete_scoping.py y tests/test_scope_helper.py delante.

RESTRICCIONES
- Cero cambios de comportamiento. Esto es mover código, no reescribirlo.
- Los 478 tests en verde después de cada corte, no solo al final.
- No toques app/domain/engine.py.

AL TERMINAR
Actualiza TODO-16 en TODOS.md con lo que quedó cerrado y lo que sigue abierto.
```

---

## A3 · Lo que se detectó y **no** se corrige ahora

Esto no lleva prompt a propósito. Está aquí para que sepas que existe y por qué
lo dejamos.

### La fase que se guarda como etiqueta

`WeeklyPlan.phase` guarda `"Construcción"`, `"Pico"` — nombres para enseñar en
pantalla. Pero `F_FASE`, el multiplicador que gobierna toda la curva científica,
se indexa por `base_general`, `base_especifica`, `umbral_css`, `pre_competitivo`,
`taper`. **La ciencia no puede leer lo que la aplicación guarda.**

Hay tres vocabularios de fase vivos a la vez: los 5 científicos, los 4 de
`DEFAULT_PHASES` y los 4 de `PlanPhase.type` (`base|build|peak|taper`).

**Por qué no se arregla ahora:** la corrección buena es que `Fase` sea un tipo con
su `F_FASE` dentro (bloque **C1**) y que la base de datos guarde la clave, no la
etiqueta (bloque **C2**). Parchearlo antes significa inventar una tabla de
traducción entre tres vocabularios, que es trabajo que se tira después. Y tocar
lo que se guarda en esa columna afecta a filas existentes **y** a lo que se pinta
en la tabla del plan semanal.

### Que haya dos motores

Es el hallazgo más grave (`ScienceEngine.generate_plan()` solo se llama en tests;
los planes reales salen de `engine/progression.py`) y **es el bloque C4 entero**.
No tiene versión corta.

---

# PARTE B — CONSOLIDACIÓN DE LA UI

---

## B1 · Fusionar Plan semanal + Comparación — ✅ HECHO (2026-08-16)

> Commit `2082015`. `/plan-semanal` es un módulo con tres vistas —Plan
> (la tabla editable de siempre), Progresión (lo que era `/comparacion`) y Zonas
> (el `ZonePanel` fuera del cajón de 290 px)—, con el selector y la query
> `['weeks', event.id]` en el shell, por encima del conmutador: dentro de una
> vista, cambiar de pestaña las desmontaría y perdería la selección.
>
> **La vista va en query param (`?vista=progresion`), nunca en subruta.**
> `navConfig` compara la ruta exacta en tres sitios y `SECTION_ACCENT` indexa por
> `pathname`, así que el pathname es la identidad de la sección y no se mueve.
> `/comparacion` queda como redirect. El menú pasa de 8 secciones a 7; el atleta,
> de 4 a 3. Catálogo de vistas en `features/weekly/vistas.ts`, aparte del de
> secciones (`navConfig.ts`), porque no son la misma lista: una es lo que el menú
> enseña y la guarda protege, la otra lo que hay dentro de una sección.
>
> Cero cambios en el backend, como se preveía. **R9 aplicada**: la sección
> conserva su rosa `#f472b6` y el violeta queda libre.
>
> Un matiz sobre la tabla de coste de aquí abajo: `DeviationTable` (103) **no
> desapareció** — se mudó a `features/weekly/` y la dibuja la vista Progresión.
> Lo que se fue es la cáscara de `ComparisonPage`.

### Qué pasa

La app tiene **tres ejes de información**, y uno está dibujado dos veces:

| Eje | Secciones |
|---|---|
| **Un atleta × muchas semanas** | Plan semanal · **Comparación** · (Base aeróbica) |
| **Muchos atletas × una semana** | Tabla del equipo |
| **Muchos atletas × muchas semanas** | Dashboard |

Plan semanal y Comparación usan el **mismo selector**, la **misma query** y el
**mismo gráfico**:

```
weekly/WeeklyPlanPage.tsx:68      queryKey: ['weeks', selection?.event.id]
comparison/ComparisonPage.tsx:21  queryKey: ['weeks', selection?.event.id]
```

`ProgressionChart` y `EventPicker` los usan **exactamente esas dos páginas**, y
nadie más. Comparación es un subconjunto: cuatro KPIs, el mismo gráfico otra vez,
y una tabla que son las mismas semanas filtradas a las que tienen tiempo real.

TanStack Query ya las deduplica en red. Lo único duplicado es la cáscara: dos
rutas, dos páginas, dos entradas de menú, dos colores del sistema de diseño.

### Lo que NO hay que fusionar

**Dashboard y Tabla del equipo parecen fusionables y no lo son.** Comparten la
query `['dashboard', selectedId]` —`TeamPage.tsx:32` lo dice en un comentario—
pero responden a preguntas distintas: *"cómo va el macrociclo"* contra *"qué le
mando a cada uno hoy"*. Compartir una consulta no es ser la misma pantalla.
Fusionarlas sería mezclar.

### La forma

Un módulo, un selector, una query, tres vistas que conservan su trabajo:

```
Atleta
   EventPicker + query ['weeks', event.id]   ← UNA vez
   ├── Plan         tabla editable, parones, recálculo    (lo de hoy)
   ├── Progresión   gráfico grande + desviaciones         (la Comparación de hoy)
   └── Zonas        el ZonePanel a pantalla completa
```

Ganancia colateral: `ZonePanel` sale del cajón de 290 px donde hoy vive apretado.

### Coste y riesgo

**Bajo. No toca el backend en absoluto**: mismos endpoints, mismos datos.

| | |
|---|---|
| Desaparece | `ComparisonPage` (120) + `DeviationTable` (103) ≈ 220 líneas de cáscara |
| Se escribe | el conmutador de vistas, ~60 líneas |
| Ya compartido | `EventPicker`, `ProgressionChart`, `primitives`, `StatusBadge` |
| Tráfico de red | **cero cambio** |

**Hazlo antes de la parte C.** Menos páginas consumiendo `lib/types/` son menos
sitios donde puede fallar la promesa clave del rediseño ("el contrato del API no
cambia"). Y consolidar la UI con el backend en movimiento es bastante más
incómodo.

### R9 · El color de la sección fusionada — ✅ CERRADA (2026-08-16)

**Rosa `#f472b6`.** Plan semanal conserva el suyo y se libera el violeta
`#a78bfa`, que era de Comparación.

Son en realidad dos decisiones y solo la segunda estaba en duda:

1. **Un color por RUTA, no por vista** — las tres pestañas comparten acento.
   El riel, la barra de móvil y la cabecera lo leen del mismo `pathname`
   (`App.tsx:36`), así que un color por pestaña haría que el riel y la página
   dijeran sitios distintos a la vez. **Correcta y ya aplicada.**
2. **Qué color se queda.** Se construyó al revés: la sección se quedó con el
   violeta de Comparación y liberó su propio rosa.

**Por qué rosa.** Desde el lado del entrenador, `/plan-semanal` no se convirtió
en otra cosa: **absorbió** algo. Misma ruta, mismo nombre, y la pestaña "Plan" es
la página de siempre sin tocar. Si la identidad persiste, el color debe
persistir. El efecto de segundo orden es el que decide: **liberar rosa crea una
trampa futura** —rosa reaparece en otra sección y contradice la memoria muscular
de quien lo tenía fichado como Plan semanal—, mientras que liberar violeta no
crea ninguna, porque violeta ya no señala nada que se pueda volver a encontrar.

No hay colisión técnica en ninguna dirección: `#a78bfa` solo existe como token
`--color-violet` y ya no lo usa ninguna zona (MVO2 pasó a `#60a5fa`), y
`#f472b6` solo lo consume la curva sigmoide del simulador (`constants.ts:88`),
que no se dibuja en Plan semanal.

> **✅ APLICADA el 2026-08-16.** `frontend/src/lib/constants.ts` ya lleva
> `'/plan-semanal': '#f472b6'` y el comentario corregido. Verificado con el
> servidor levantado: `--page-accent` resuelve a `#f472b6` en `/plan-semanal` y
> **se mantiene igual en las tres vistas** (`?vista=progresion`, `?vista=zonas`),
> que es la mitad 1 de la decisión funcionando. El riel pinta el enlace activo en
> `rgb(244, 114, 182)` y ningún otro. `tsc --noEmit` limpio, consola sin errores.
>
> **Lo que NO se puede deshacer:** el intercambio de colores Tabla del equipo ↔
> Simulador. El coral `#fb7185` y este rosa son casi indistinguibles en tema
> oscuro, y ese intercambio es lo que mantiene el coral lejos de Plan semanal en
> el riel. Está avisado en el propio `constants.ts`.

### Decisión pendiente

**¿Base aeróbica entra como cuarta pestaña o se queda como sección propia?** Es
el mismo eje (un atleta a lo largo del tiempo), pero arrastra un flujo de alta
pesado (`TestForm`, 289 líneas) que como pestaña podría quedar apretado. Sin
resolver. **No es R9** — R9 era solo el color.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee primero CLAUDE.md de esa carpeta (sobre todo la sección "Roles en el frontend").

CONTEXTO
El frontend tiene 8 secciones y dos de ellas dibujan lo mismo. Comprobado:
  frontend/src/features/weekly/WeeklyPlanPage.tsx:68
  frontend/src/features/comparison/ComparisonPage.tsx:21
usan la MISMA queryKey ['weeks', event.id], el mismo EventPicker y el mismo
ProgressionChart. Y esas dos páginas son las ÚNICAS que usan esos dos
componentes. Comparación es un subconjunto de Plan semanal: 4 KPIs, el mismo
gráfico, y una tabla de desviaciones que son las mismas semanas filtradas a
real_time != null.

TAREA
Fusionar las dos en un solo módulo con tres vistas, compartiendo selector y
query, SIN mezclar sus trabajos (no quiero una página larga con todo apilado):

  Vista "Plan"       la tabla editable de hoy (tiempo real inline, parones)
  Vista "Progresión" el gráfico a tamaño grande + la tabla de desviaciones
                     (lo que hoy es ComparisonPage + DeviationTable)
  Vista "Zonas"      el ZonePanel a pantalla completa, no en el cajón de 290px
                     donde vive hoy dentro de WeeklyPlanPage

Antes de escribir código, enséñame la estructura de archivos que propones y cómo
se conserva el estado al cambiar de vista. Espera mi visto bueno.

PUNTOS QUE HAY QUE ATENDER
1. navConfig.ts es el catálogo ÚNICO de secciones: lo consumen el rail, el drawer
   móvil, la barra superior y la guarda de ruta. Todo el cambio de navegación
   pasa por ahí, no por dos listas.
2. /comparacion desaparece: deja un redirect a la vista de progresión para no
   romper marcadores.
3. SECTION_ACCENT en lib/constants.ts da un color por ruta. Al fusionar queda
   libre el violeta #a78bfa (Comparación). Propóneme qué hacer —¿la sección se
   queda con el rosa de Plan semanal? ¿las pestañas heredan color?— y espera mi
   respuesta. Es una decisión de diseño, no técnica.
4. El rol atleta ve hoy 4 secciones, dos de ellas con el mismo gráfico.
   Comprueba que después de la fusión sigue viendo lo que le corresponde.

RESTRICCIONES
- CERO cambios en el backend. Mismos endpoints, mismos datos, mismas queries.
- `npx tsc -b` y `npx eslint .` en limpio al terminar (hoy los dos lo están).
- No toques Dashboard ni Tabla del equipo: comparten una query pero responden a
  preguntas distintas, y fusionarlas sería mezclar.

AL TERMINAR
Enséñame una captura de cada vista y dime cuántas líneas netas se fueron.
```

---

# PARTE C — REDISEÑO POO

El modelo completo está en `docs/REDISENO.md`. Aquí va el orden de ejecución y el
prompt de cada paso.

**Los pasos C1, C2 y C3 son aditivos: añaden comportamiento sin quitar el que
hay.** Puedes parar después de cualquiera y el programa queda mejor que antes.

---

## C0 · Cerrar las decisiones abiertas — ✅ HECHO (2026-08-16)

**R1–R8 están cerradas.** La sesión de decisión se ejecutó con el prompt de abajo,
con el código delante y corriendo los dos motores sobre casos reales para R6 y R7.
**La fuente de verdad de cada cierre, con su razón, es la §10 de `docs/REDISENO.md`.**
Aquí solo va el resumen operativo: qué cambia en los bloques de este plan.

| # | Cerrada como | Afecta a |
|---|---|---|
| R1 | **Partida en tres**: el modelo las contempla; `Sesion`+`CargaDiaria` **después** de C1–C6; **`Serie` sale del rediseño** | C7, C8 |
| R2 | **Reemplaza**, con `real_time` viva una versión. **Enmendada: la semana NO lleva FK** — deriva sus resultados por fecha y **promedia** | C6 |
| R3 | **Solo el hueco, y más estrecho**: nada en `Principal`, nada en `usuarios` | C3 |
| R4 | **No hay rol nuevo**, pero borrar el macro y cambiar la meta pasan a `require_owner` | C3 |
| R5 | **No** — más dos arreglos (`redeem` mira `is_active` antes que `team_id`; `_principal_for` falla con >1 pertenencia) | C3 |
| R6 | **Fases y forma de la ciencia, total del entrenador**; bandas solo como aviso en la tabla del plan | C4 |
| R7 | **Elegible en el simulador, fija en el plan**; `progression_curve` **sale de la tabla `plans`** | C4 |
| R8 | **SQLite**; se cambia por razón de despliegue y **después** de C6 | D2, D3 |
| R9 | **Rosa `#f472b6`.** La sección superviviente conserva su color; se libera el violeta de la que desapareció. **Un color por RUTA, no por vista** | B1 — ✅ aplicada y verificada en el navegador |

> **R6 destapó tres defectos que entran en el alcance de C4** y que no estaban en
> ningún documento:
> 1. **`classify_level` es un acantilado.** Está calibrada para CSS y se la
>    alimenta con el ritmo de un 200: `2:10.40 → elite → 50,1 km` en la semana 1;
>    `2:10.50 → competitive → 34,6 km`. Una décima cambia el volumen un **45 %**.
>    El nivel debe salir del **test aeróbico** cuando exista.
> 2. **`ScienceEngine` sube el volumen la semana de la competencia** (S14 26,2 →
>    S15 29,2). `distribute_km` tiene una línea explícita que lo evita: se conserva.
> 3. **La onda 3:1 se indexa por `week % 4` absoluta**, así que la descarga cae en
>    la primera semana de cada bloque nuevo, no en la última del microciclo.

**Cinco preguntas NUEVAS quedaron abiertas** (N1–N5 en la §10.3 de `REDISENO.md`):
el promedio semanal, el tiempo de competencia, `sesiones_por_semana`, el PDF y si
la sesión es texto libre. **Ninguna bloquea C1–C8**; todas bloquean el módulo de
entrenamiento diario, cuyo alcance está en la nota 22 del vault.

### Prompt (sesión de decisión, no de código)

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md entero y CLAUDE.md.

NO ESCRIBAS CÓDIGO EN ESTA SESIÓN. Es una sesión de decisión.

Al final de docs/REDISENO.md hay 8 decisiones abiertas (R1-R8). Quiero cerrarlas
contigo, una por una, en orden de impacto: R2, R6, R1, R5, y luego el resto.

Para cada una:
1. Enséñame el código concreto que la decisión afecta (archivo:línea).
2. Dime qué cambia para el ENTRENADOR en cada opción, no solo para el código.
3. Dame tu recomendación con su razón.
4. Espera mi respuesta antes de pasar a la siguiente.

En R6 concretamente quiero ver los números: coge un caso real (un atleta de
200 libre, macro de 15 semanas, 450 km totales) y enséñame el reparto semanal de
kilómetros que da cada uno de los dos motores, lado a lado. Quiero decidir viendo
las dos tablas, no leyendo una descripción.

AL TERMINAR
Actualiza la sección 10 de docs/REDISENO.md con las decisiones cerradas, su fecha
y la razón de cada una. Las que queden abiertas, que queden marcadas como tales.
```

---

## C1 · Objetos de valor

### Qué pasa

El dominio pasa primitivos sueltos por todas partes:

- `(distancia, estilo, piscina)` viajan como tres variables independientes por el
  motor, los schemas y tres tablas.
- Ocho columnas `float` mezclan **dos unidades distintas**: `current_time`,
  `goal_time`, `expected_time`, `recalc_time`, `real_time` son segundos
  absolutos; `avg_per100`, `css_ms`, `pace_100m` son segundos por 100 metros.
  Nada impide restarlos entre sí.
- Las zonas son strings dentro de diccionarios, con la lista de orden en un sitio
  y las etiquetas en dos.
- Nivel, perfil, estilo, especialidad, tipo de test: strings mágicos. De todo el
  esquema, **solo `role` tiene `CheckConstraint`**.

### Por qué es el primer paso

Esta es la causa de las divergencias de A1. Si la validez de una prueba es una
invariante del constructor, **no puede haber dos respuestas al 50 combinado**.
Arreglas la clase de error, no el error.

Y es barato: son unas 300 líneas de tipos, sin tocar nada existente.

### Riesgo

**Ninguno.** Es puramente aditivo: se crean los tipos y se empiezan a usar donde
convenga, sin quitar nada.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (sección 3 completa) y CLAUDE.md.

CONTEXTO
Primer paso del rediseño POO. Es puramente aditivo: creo los objetos de valor,
no quito nada. El objetivo es que reglas que hoy son funciones sueltas pasen a ser
invariantes de un tipo.

TAREA
Crea backend/app/dominio/valores/ con los objetos de la sección 3 de REDISENO.md.
Todos frozen=True, slots=True (es lo que ya usa Principal en core/dependencies.py
y por lo que el coste en rendimiento es despreciable: medí 0,24 µs por objeto).

  tiempo.py    Tiempo (segundos) · Ritmo (s/100m) · Mejora
  prueba.py    Estilo · Piscina · Prueba(distancia, estilo)
  zona.py      Zona (enum ORDENADO R1>R2>MVO2>RL>V) · Prescripcion · JuegoDeZonas
  escalas.py   Nivel · Perfil · Fase · Especialidad · Genero · TipoDeTest ·
               ModoDeIngreso · Tendencia · EstadoDeMacro · Veredicto

LO QUE MÁS IMPORTA DE CADA UNO
- Tiempo y Ritmo son tipos DISTINTOS. Hoy los dos son float y nada impide
  restarlos. Que el error deje de compilar es el punto.
- Prueba RECHAZA en el constructor los combos imposibles (no hay 400 mariposa,
  no hay 50 combinado). Esa validez hoy vive duplicada en app/engine/events.py y
  app/domain/engine.py, y las dos copias YA DICEN COSAS DISTINTAS en 50 m.
  La regla buena es la de events.py.
- Zona es un enum ORDENADO. Hoy la jerarquía vive en una lista suelta
  (ZONE_ORDER en engine/send_off.py) que engine/zones.py reexporta con un
  comentario avisando de que si se separan, una zona nueva es un 500 en la tabla
  del equipo. Con un enum no hay dos listas que separar.
- Fase lleva su F_FASE y su banda de volumen DENTRO. Hoy hay tres vocabularios
  de fase vivos: las 5 claves científicas de F_FASE, las 4 de DEFAULT_PHASES
  (Base/Construcción/Pico/Descenso) y las 4 de PlanPhase.type. Este tipo es la
  única fuente.
- Nivel se DERIVA siempre (Nivel.desde_umbral(ritmo)). Nunca se escribe a mano
  ni se guarda.

RESTRICCIONES
- app/dominio/ no importa NADA: ni SQLAlchemy, ni FastAPI, ni Pydantic, ni de
  app/modules/, ni de app/core/.
- No cambies todavía el código que existe para que los use. Este paso solo crea
  los tipos y sus tests.
- Los 478 tests existentes en verde.

TESTS
Un test por invariante, y en particular uno que fije que Prueba(50, combinado)
es imposible de construir. Ese es el que evita que la divergencia vuelva.

AL TERMINAR
Dime qué código existente sería el primer candidato a migrar a estos tipos y
cuál sería el más doloroso, para planificar el siguiente paso.
```

---

## C2 · Entidades ricas

### Qué pasa

De 14 modelos persistentes, **uno solo tiene comportamiento** (`AerobicSplit.arrival_time`).
Todo lo demás son contenedores de datos, y las reglas viven en funciones sueltas
que reciben `(db, entidad, ...)`.

Hay reglas que son **puras** —no tocan la base de datos— y están huérfanas fuera
de su objeto:

```
plans/service.py:32   age_at(birth_date, ref)        → es Atleta.edad_en(fecha)
plans/service.py:42   current_week_of(plan, today)   → es Macrociclo.semana_actual()
plans/service.py:51   effective_status(plan, today)  → es Macrociclo.estado()
```

Y el análisis del test aeróbico vive entero en `engine/aerobic.py` en vez de en el
test.

### El caso que mejor lo explica

Hoy *"en la base de datos siempre se guarda el tiempo nadado, nunca la llegada"*
es una regla que hay que **acordarse** de aplicar en `create_test`. Si la
conversión ocurre al construir el objeto, **deja de poder violarse**.

Ese es el fallo que inflaba la base aeróbica un 114 %. Pasa de regla documentada
a invariante del tipo.

### Riesgo

**Bajo.** Aditivo: el comportamiento se mueve al objeto y las funciones viejas
delegan mientras dure la transición.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (sección 5) y CLAUDE.md.
Requiere que C1 (objetos de valor en app/dominio/valores/) esté hecho.

CONTEXTO
Segundo paso del rediseño. Hoy el modelo es anémico: de 14 modelos persistentes
solo uno tiene comportamiento. Las reglas puras viven en funciones sueltas de
service.py que reciben (db, entidad, ...). Este paso las devuelve a su objeto.

TAREA
Crea app/dominio/entidades/ con Atleta, Macrociclo y TestAerobico según la
sección 5 de REDISENO.md. Son entidades de DOMINIO: no son modelos SQLAlchemy.

Comportamiento que hay que recuperar de donde está hoy:
  Atleta.edad_en(fecha)          ← plans/service.py:32 age_at()
                                   (y swimmers/service.py:28 _age(), que es la
                                   misma función con otra firma)
  Macrociclo.semana_actual()     ← plans/service.py:42 current_week_of()
  Macrociclo.estado_efectivo()   ← plans/service.py:51 effective_status()
  Macrociclo.fase_de(semana)
  TestAerobico.base_aerobica()   ← engine/aerobic.py analyze_splits()
  TestAerobico.tendencia() / .consistencia() / .densidad()

LO MÁS IMPORTANTE DE ESTE PASO
TestAerobico tiene que hacer la conversión clock→rep EN EL CONSTRUCTOR. Hoy la
regla "en la base de datos siempre se guarda el tiempo nadado, nunca la llegada"
está documentada en CLAUDE.md y hay que acordarse de aplicarla en create_test.
Ese olvido es lo que infló una base aeróbica un 114%. Como invariante del
constructor deja de poder ocurrir. Lee la nota del vault
"19 - El Intervalo de Salida" o la sección correspondiente de CLAUDE.md antes de
implementarlo.

ESTRATEGIA DE TRANSICIÓN
No rompas los llamadores existentes de golpe. Las funciones de service.py se
quedan como envoltorio delegando en la entidad, y se van vaciando después.
Antes de escribir, dime cómo propones mapear el modelo SQLAlchemy a la entidad de
dominio (¿la entidad envuelve al modelo? ¿se construye desde él?) y espera mi
visto bueno: es la decisión que condiciona el paso C5 (repositorios).

RESTRICCIONES
- app/dominio/ no importa NADA de infraestructura.
- Los 478 tests en verde.
- No toques todavía los motores. Eso es C4.

AL TERMINAR
Dime qué queda en plans/service.py después de vaciarlo y si sigue pasando de
300 líneas.
```

---

## C3 · Los roles

### Qué pasa

Hoy el rol es un string y las decisiones que dependen de él son `if` repartidos.
`Principal` (`core/dependencies.py:63`) ya es el 70 % del diseño bueno —
`is_coach`, `is_athlete`, `sees_every_plan`, `scope_to_own_swimmer` son métodos
de rol metidos a mano en una sola clase.

### La decisión que no hay que reabrir

**`Usuario` NO hereda a `Entrenador` ni a `Nadador`.**

El caso que lo descarta: un entrenador que además nada máster en su propio club, o
alguien que es atleta en un club y entrenador en otro. Con herencia, cambiar de
rol significa cambiar de clase — y una fila de `users` no cambia de clase. Habría
que borrar la cuenta y recrearla, perdiendo el histórico.

**El rol cuelga de la pertenencia**, y la jerarquía hereda de `Rol`:

```
Rol (abstracto)
 ├── Administrador      plataforma; cruza equipos → NO cabe en pertenencias
 ├── EntrenadorEnJefe   = dueño; hereda de Entrenador y solo AMPLÍA el alcance
 ├── Entrenador         ve los macrociclos en los que está
 └── AtletaRol          ve lo suyo y solo lo suyo
```

**El jefe sigue siendo una columna** (`teams.owner_id`), no un valor de `rol`.
Hoy esa columna hace **imposible** que un equipo tenga dos jefes, y una FK
compuesta garantiza que sea miembro de ese equipo. Como fila de `team_members`
haría falta un índice único parcial —que SQLite y PostgreSQL no tratan igual— y
transferir la propiedad dejaría de ser un `UPDATE` atómico.

Regla que sale de aquí y vale para todo: **jerarquía de clases en el dominio,
almacenamiento plano en la base de datos.**

### Riesgo

**Bajo en el código, alto si se hace mal.** Es la capa de seguridad: aquí vive el
aislamiento entre equipos y entre atletas. Los tests de guards son el contrato.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (sección 4 COMPLETA) y CLAUDE.md (secciones "Identidad y
roles", "Roles en el frontend" y "Equipos, roles y aislamiento").

CONTEXTO
Tercer paso del rediseño. Hoy el rol es un string y las decisiones que dependen
de él son `if` dentro de Principal (core/dependencies.py:63) y repartidos por los
services. Este paso los convierte en polimorfismo.

DECISIÓN YA TOMADA — NO LA REABRAS
Usuario NO hereda a Entrenador ni a Nadador. El rol cuelga de la pertenencia
(TeamMember), no de la cuenta. La razón está en la sección 4.1 de REDISENO.md.
Y el dueño del equipo sigue siendo la columna teams.owner_id, NO un tercer valor
de team_members.role: esa columna es lo que hace imposible que haya dos jefes, y
como fila haría falta un índice único parcial que SQLite y PostgreSQL no tratan
igual. Jerarquía en el dominio, almacenamiento plano.

TAREA
Crea app/dominio/roles/ con Rol (abstracto) y sus subclases: Administrador,
EntrenadorEnJefe (hereda de Entrenador), Entrenador, AtletaRol.
Interfaz según la sección 4.2 de REDISENO.md:
  puede_ver(recurso) · puede_escribir(recurso)
  alcance_de_atletas() · alcance_de_macrociclos() · secciones_visibles()

Luego haz que Principal COMPONGA un Rol en vez de tener is_coach / is_athlete /
sees_every_plan, y sustituye los `if principal.is_athlete` de los services por
preguntas al rol.

CUIDADO — esto es la capa de seguridad
- Los 403 y los 404 tienen que seguir saliendo exactamente donde salen hoy:
  recurso ajeno → 404 SIEMPRE, nunca 403. El 403 es solo para "tu rol no alcanza".
- scope_to_own_swimmer falla CERRADO a propósito: un atleta sin ficha ligada no
  ve nada, no lo ve todo. Ese comportamiento no se toca.
- El conmutador de desarrollo (is_developer) es un eje ORTOGONAL al rol, no un
  rol más, y no se puede persistir en la base de datos. Que siga siendo imposible.
- Administrador solo se DEJA CONTEMPLADO en la jerarquía; no lo implementes
  (decisión R3). Y cuando se implemente NO va en team_members: cruza equipos y
  el equipo es la frontera de todo.

RESTRICCIONES
- Ningún cambio de esquema en este paso.
- Los 478 tests en verde, y con atención especial a: test_role_guards.py,
  test_athlete_scoping.py, test_scope_helper.py, test_dev_bypass.py,
  test_dev_identity.py, test_cuenta_sin_equipo.py.
- Si algún test de guards necesita cambiar, PARA y explícame por qué antes de
  tocarlo. Un test de seguridad que se ajusta para que pase es una alarma.

AL TERMINAR
Enséñame el diff de core/dependencies.py y confirma que ningún endpoint cambió
el código de estado que devuelve.
```

---

## C4 · Fusionar los dos motores

> **Este es el bloque peligroso. Rama propia. Requiere A0 hecho.**

### Qué pasa

`CLAUDE.md` dice que `domain/engine.py` es la fuente de verdad y que `engine/` lo
adapta. **No es cierto:**

```
ScienceEngine.generate_plan()      → se llama SOLO en tests (28 veces)
engine/progression.generate_plan() → es lo que genera los planes que se guardan
```

`ScienceEngine` entra en la aplicación por una sola puerta: `simulator/router.py:97`
(`project_season`). El plan real del atleta sale de un algoritmo distinto, que
comparte las *tablas* científicas pero no el *cálculo*. Están duplicados:
distribución de fases, techo I_max, factibilidad, volumen semanal, extensión.

Por eso las reglas de A1 divergieron. No fue descuido: fue inevitable.

### La fusión no es quedarse con uno

Los dos aciertan en cosas distintas y el motor bueno necesita las dos mitades:

| De `ScienceEngine` | De `engine/progression.py` |
|---|---|
| distribución F_FASE por fase científica | `clamp_weekly_rate()`: acota el ritmo semanal y **difiere** el excedente |
| ajuste automático del nº de semanas a la meta | curva elegible por el entrenador |
| extensión al ritmo seguro | `distribute_km()` normalizado al total que fijó el entrenador |
| `project_season()` | fases definidas por el usuario, no fijas a 15 semanas |

**La ciencia de uno, la parametrización del otro.** `ScienceEngine` asume macro
fijo de 15 semanas; `progression` respeta las semanas y los km que puso el
entrenador.

> **R6 — CERRADA el 2026-08-16.** El kilometraje lo manda el entrenador: **fases y
> forma de la ciencia, total normalizado al que él puso**, y las bandas de
> `WEEKLY_VOLUME_KM` como **aviso** —nunca valor por defecto ni límite— visible
> **solo en la tabla del plan**. Medido: para un 200 libre de 15 semanas y 450 km,
> `distribute_km` reparte 450,1 y `ScienceEngine` prescribe **777,7**; su
> `generate_plan` ni siquiera recibe `total_km`.
>
> **Tres arreglos entran en este bloque** (ver C0): el acantilado de
> `classify_level`, el taper invertido y la onda 3:1 desfasada.
>
> **R7 — CERRADA:** `progression_curve` **deja de ser columna de `plans`**. Las
> cinco curvas cierran en el mismo punto, pero difieren hasta 1,30 s a mitad de
> plan contra una tolerancia de ±0,4 %: el mismo nado sale `AHEAD` con la
> científica y `BEHIND` con la exponencial. El parámetro se queda en la firma del
> motor, que es de donde lo usa el simulador.

### El riesgo real

**No es que reviente: es que los números cambien sin que nadie lo note.** Los dos
motores reparten los kilómetros distinto, así que regenerar un plan existente
puede dar objetivos semanales distintos a los que el atleta ya está siguiendo.

Por eso **A0 es obligatorio antes**.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (sección 6.1 COMPLETA) y CLAUDE.md.

REQUISITOS PREVIOS — comprueba los dos antes de empezar y PARA si falta alguno:
  1. Existe tests/test_motor_snapshot.py con snapshots de referencia (bloque A0).
  2. La decisión R6 está cerrada en la sección 10 de docs/REDISENO.md.
Sin las dos, esta fusión es a ciegas.

Trabaja en una rama propia.

CONTEXTO
Hay DOS motores. CLAUDE.md dice que app/domain/engine.py es la fuente de verdad,
pero ScienceEngine.generate_plan() solo se llama en tests: los planes que se
guardan en la base de datos salen de app/engine/progression.py. ScienceEngine
entra en la aplicación por una sola puerta, simulator/router.py:97
(project_season). Comparten las tablas científicas (vía envelope.py) pero no el
algoritmo, y por eso ya han divergido en varias reglas.

TAREA
Fusionar en un solo MotorCientifico en app/dominio/servicios/motor.py, que
absorbe y elimina: domain/engine.py::ScienceEngine, engine/progression.py,
engine/envelope.py, engine/feasibility.py, engine/km_distribution.py,
engine/zones.py, engine/send_off.py.

Las constantes científicas van todas a app/dominio/servicios/tablas.py, cada una
con su § de referencia, y MAX_SEMANAS_EXTENSION deja de tener dos valores.

LA FUSIÓN NO ES QUEDARSE CON UNO
Cada motor acierta en cosas distintas y el resultado necesita las dos mitades:
  De ScienceEngine: distribución F_FASE por fase científica, ajuste automático
    del número de semanas a la meta, extensión al ritmo seguro, project_season.
  De progression: clamp_weekly_rate() (acota el ritmo semanal y DIFIERE el
    excedente a las siguientes: modelo causal, no recorte), curva elegible,
    distribute_km() normalizado al total que fijó el entrenador, y fases
    definidas por el usuario en vez de fijas a 15 semanas.
La ciencia de uno, la parametrización del otro.

MÉTODO — no negociable
Trabaja en pasos pequeños, y después de CADA paso corre el test de snapshot.
Cuando un número cambie:
  1. PARA.
  2. Enséñame QUÉ caso y QUÉ campo cambió, con el valor viejo y el nuevo.
  3. Explícame POR QUÉ cambió.
  4. Espera a que yo diga si esa diferencia es intencionada.
No regeneres el snapshot por tu cuenta. Nunca.

RESTRICCIONES
- El contrato del API NO cambia: mismos endpoints, mismos campos, mismas formas
  de respuesta. El frontend no se debe enterar de nada.
- Los 478 tests en verde.
- Si un test del motor hay que cambiarlo, explícame por qué antes.

AL TERMINAR
1. Lista de TODAS las diferencias numéricas que aparecieron y qué decidimos.
2. Actualiza CLAUDE.md: la sección que describe domain/ y engine/ como
   "dominio + adaptador" deja de ser verdad.
3. Dime cuántas líneas y cuántos archivos desaparecieron.
```

---

## C5 · Repositorios

### Qué pasa

La regla del proyecto dice que los módulos no se importan entre sí. **Ya está
rota**, y no por descuido sino por presión del dominio real:

```
aerobic_tests/intervals.py  → plans.access.visible_to, plans.service.current_week_of
dashboard/service.py        → plans.access, plans.service, plans.models, swimmers.models
link_codes/service.py       → auth.models, auth.service, swimmers.models,
                              swimmers.schemas, teams.models   (411 líneas)
```

`Plan`, `Swimmer` y `AerobicTest` **son un mismo agregado** y el código los separó.
El corte fue por endpoint HTTP, no por concepto de dominio. `dashboard` no es un
módulo de dominio: es una vista.

### La solución

Cada agregado expone un repositorio (SQL) y el servicio se queda con las reglas.
`dashboard` deja de importar `plans.service.current_week_of` porque pregunta al
repositorio y le llega un `Macrociclo` que **ya sabe** su semana actual.

### Riesgo

**Medio.** Mueve mucho código, pero sin cambiar comportamiento.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (secciones 2 y 5) y CLAUDE.md.
Requiere C2 (entidades) hecho.

CONTEXTO
CLAUDE.md dice que los módulos no se importan entre sí salvo lecturas explícitas
de modelos. Está roto, y no por descuido: Plan, Swimmer y AerobicTest son un mismo
agregado y el código los separó por endpoint HTTP en vez de por concepto.
Comprobado:
  modules/aerobic_tests/intervals.py → plans.access.visible_to,
                                       plans.service.current_week_of, 4 modelos
  modules/dashboard/service.py       → plans.access, plans.service, plans.models,
                                       swimmers.models
  modules/link_codes/service.py      → auth.models, auth.service, swimmers.models,
                                       swimmers.schemas, teams.models (411 líneas)

TAREA
Introduce app/persistencia/repositorios/ (uno por agregado) y reorganiza según la
sección 2 de REDISENO.md, con esta dirección de dependencias y sin excepciones:
    api → persistencia → dominio
    dominio → nada

Efecto que busco: dashboard deja de importar plans.service.current_week_of porque
pregunta al repositorio y recibe un Macrociclo que YA SABE su semana actual.

Y dashboard deja de ser un módulo de dominio: es una VISTA, y va a api/v1/vistas/
junto con la tabla del equipo y la comparación.

MÉTODO
Empieza por UN agregado (propónme cuál y por qué) y enséñamelo terminado antes de
seguir con los demás. No quiero ver siete repositorios de golpe.

RESTRICCIONES
- El contrato del API no cambia.
- Los 478 tests en verde después de cada agregado migrado, no solo al final.
- Ojo con las consultas: hoy hay tests que convierten el aviso de producto
  cartesiano de SQLAlchemy en un fallo (está en pyproject.toml y es a propósito,
  ver test_scope_helper.py). No lo desactives.

AL TERMINAR
Enséñame el grafo de imports entre módulos y confirma que ya no hay lógica
cruzada, solo lecturas a través de repositorios.
```

---

## C6 · `Resultado` y la migración de los tiempos

### Qué pasa

Los tiempos reales viven en `WeeklyPlan.real_time`, colgando de
`Plan → AthletePlan → AthleteEvent → WeeklyPlan`.

**Consecuencia ya observada:** `remove_athlete` **tuvo que** convertirse en baja
lógica porque borrar la inscripción cascadeaba y se llevaba todos los tiempos
reales del atleta. Está documentado en su propio docstring (**`plans/roster.py:57`**
— el archivo se partió en cinco después de escribirse esta nota): reproducido con
el harness, `weekly_plans` pasaba de 36 filas a 24, incluido un tiempo puesto un
segundo antes.

Se parcheó el síntoma. **La causa —un hecho del atleta modelado como propiedad de
un plan— sigue ahí.**

**Y hay un segundo agujero por la misma causa, este SIN parchear.** `delete_plan`
(`plans/service.py:139`) solo bloquea el borrado si el macrociclo tiene tests
aeróbicos asociados. Un macro sin tests se borra limpio y la cascada se lleva
**todos los tiempos registrados de todos sus atletas**. Lo único que hoy protege
el activo más valioso de la aplicación es que haya un test de por medio.

`AerobicTest` ya cuelga del atleta con macrociclo opcional. Es el patrón correcto
que el resto del esquema no siguió.

### Qué se gana

- Sacar a alguien de un macrociclo no puede tocar su histórico. La baja lógica
  pasa a ser una elección, no un parche.
- El mismo tiempo se puede comparar contra dos macrociclos.
- El histórico de un atleta se lee sin recorrer planes.

### Riesgo

**Medio: toca datos reales.** Mitigación: `INSERT ... SELECT`, conservando
`real_time` durante una versión de transición. Mientras las dos convivan, es
reversible.

> **R2 — CERRADA el 2026-08-16, y ENMENDADA el mismo día.** Reemplaza. Pero la
> semana **no lleva FK al resultado**: el entrenador quiere que **varios tiempos
> de la misma semana se promedien**, y una FK única no admite varios. `Resultado`
> ya lleva `(atleta, prueba, fecha)`, así que la semana **deriva** su conjunto por
> rango de fechas y promedia. Uno, varios y ninguno pasan a ser el mismo caso en
> vez de tres ramas. **No hay `UPDATE` de vuelta en la migración.**
>
> **Regla que hay que implementar con ella:** solo reancla la curva el resultado
> que cae dentro de una semana del plan. Un tiempo del histórico que no cae en
> ninguna —una competencia en fecha suelta, una prueba que no es objetivo de este
> macro— entra en el histórico y **no toca la predicción**. Sin esa regla, sacar
> el tiempo del plan haría que cualquier dato perturbara la curva, que es peor que
> el problema que R2 arregla.
>
> **Criterio de retirada de `real_time`:** cuando ningún lector la use directamente
> (`dashboard/service.py`, `plans/weeks.py`, `plans/roster.py`) y el conteo
> `resultados == real_time no nulos` cuadre en dos despliegues seguidos.
>
> **N1 y N2 siguen abiertas** (§10.3 de `REDISENO.md`): si el promedio es de todos
> los tiempos o el entrenador marca cuál cuenta, y qué hace un tiempo de
> competencia. No bloquean este bloque: bloquean la UI que lo explota.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (secciones 5.10, 7.2, 7.4 y 10) y CLAUDE.md (secciones
"Integridad y borrado" y "Esquema de base de datos").
R2 esta CERRADA (2026-08-16) y ENMENDADA: lee la seccion 10.2 antes de nada.

CONTEXTO
Hoy los tiempos reales viven en WeeklyPlan.real_time, colgando de
Plan → AthletePlan → AthleteEvent → WeeklyPlan. Por eso remove_athlete TUVO QUE
volverse baja lógica: borrar la inscripción cascadeaba y se llevaba los tiempos
reales del atleta (está documentado en plans/service.py:196; con el harness,
weekly_plans pasaba de 36 filas a 24). Se parcheó el síntoma, no la causa.

Un tiempo nadado es un hecho sobre una PERSONA, no una propiedad de un plan.
AerobicTest ya está modelado así —cuelga del atleta, con plan opcional— y es el
patrón que el resto del esquema no siguió.

TAREA
1. Entidad y tabla Resultado según la sección 5.10 de REDISENO.md:
   atleta · prueba · tiempo · fecha · piscina · contexto · competencia_id?
2. La semana NO gana ninguna columna. NO pongas semanas.resultado_id ni ninguna
   otra FK: deriva sus resultados por (atleta, prueba, rango de fechas de esa
   semana) y PROMEDIA cuando hay mas de uno. Uno, varios y ninguno tienen que ser
   el mismo caso, no tres ramas. Esto es la enmienda de R2 y es deliberado: el
   entrenador quiere varios tiempos por semana promediados.
3. Migración Alembic que mueva los real_time existentes a resultados. La prueba y
   el atleta se derivan de athlete_events e athlete_plans; la fecha, de
   weekly_plans.week_date; la piscina, de plans.pool. NO hay UPDATE de vuelta.
4. Solo reancla la curva el resultado que cae dentro de una semana del plan. Un
   resultado del historico que no cae en ninguna NO debe tocar la prediccion.

SEGURIDAD DE LA MIGRACIÓN — esto es lo que más me importa
- Conserva la columna real_time durante esta versión. No la borres. Mientras las
  dos convivan la migración es reversible.
- Escribe el downgrade de la migración y PRUÉBALO, no solo el upgrade.
- Antes de correr nada contra datos, enséñame el conteo esperado: cuántos
  real_time hay hoy y cuántas filas de resultados deberían salir. Y el mismo
  conteo después.
- Recuerda las reglas del proyecto: Alembic es la única fuente del esquema,
  render_as_batch=True para SQLite, y todo modelo nuevo va en
  app/core/model_registry.py Y en alembic/env.py (si no está en el registry, el
  seed deja la tabla viva y `alembic upgrade` revienta con "table already exists").

RESTRICCIONES
- El contrato del API no cambia: el frontend sigue leyendo real_time donde lo lee.
- Los 478 tests en verde, con atención a test_borrado_y_baja.py.
- Añade un test que fije lo que este cambio hace posible: sacar a un atleta de un
  macrociclo y comprobar que sus tiempos siguen existiendo.

AL TERMINAR
Dime qué queda por hacer para poder retirar real_time en la siguiente versión.
```

---

## C7 · `Sesion` (y `Serie`, **fuera del rediseño**)

> **R1 — CERRADA el 2026-08-16.** `Sesion` entra, pero **después de que C1–C6
> estén verdes y desplegados**: C1–C6 mueven comportamiento de sitio y este bloque
> construye algo nuevo; mezclarlos hace que, si C4 sale mal, no se sepa si fue el
> refactor o la funcionalidad.
>
> **`Serie` sale del rediseño.** No por complejidad técnica sino por **coste de
> captura**: es la única pieza que obliga al entrenador a cambiar su rutina diaria
> (del orden de 150–200 filas por atleta y macro), y eso no está decidido. Banister
> **no la necesita**: para el sTSS diario basta fecha + carga. Su alcance futuro
> vive en la nota 22 del vault, junto con el módulo de entrenamiento diario.

### Qué pasa

**La unidad mínima de planificación es la semana.** No existe la sesión ni la
serie.

`engine/send_off.py` calcula prescripciones completas
(`10 × 100 a 1:18 salida 1:30`) que **no se guardan en ninguna parte**: se
computan para pintar una tabla y se tiran. Y de lo ejecutado solo existe un tiempo
por semana.

De este hueco cuelga todo lo que hoy no se puede construir. Sin `Sesion` no hay de
dónde sacar el sTSS diario, y sin sTSS no hay Banister (la nota 05 del vault).

### Riesgo

**Medio.** Es superficie nueva, no modificación. Pero es la pieza más grande del
rediseño y arrastra UI.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (secciones 5.11 y 10) y CLAUDE.md.
Requiere C1-C6 hechos, verdes y desplegados.

ALCANCE: SOLO `Sesion`. `Serie` quedó FUERA del rediseño (decision R1, 2026-08-16).
No la construyas ni dejes su tabla preparada. Lo que Sesion necesita para que
Banister funcione es: atleta, fecha, km, duracion y RPE. Nada mas.

CONTEXTO
Hoy la unidad mínima de planificación es la SEMANA. No existe la sesión ni la
serie. engine/send_off.py calcula prescripciones completas
("10 × 100 a 1:18 salida 1:30") que no se guardan en ningún sitio: se computan
para pintar una tabla y se tiran. Y de lo ejecutado solo hay un tiempo por semana.
Sin sesiones no hay sTSS diario, y sin sTSS no hay Banister.

TAREA
Sesion y Serie según la sección 5.11 de REDISENO.md, con su tabla, su migración
y sus endpoints.

LA DISTINCIÓN QUE HAY QUE RESPETAR
Las zonas y las prescripciones NO se persisten: son derivados deterministas del
ritmo, y guardarlas crearía dato que queda mintiendo en cuanto el entrenador
ajusta la meta. La EXCEPCIÓN es Serie.prescripcion: ahí sí se guarda, como
FOTOGRAFÍA de lo que se mandó nadar ese día. Ya no es un cálculo, es un hecho
histórico. Que quede claro en el código y en los docstrings cuál es cuál.

ANTES DE EMPEZAR
Enséñame el modelo que propones y CÓMO se rellena en la práctica: ¿el entrenador
escribe la sesión a mano? ¿se genera desde el plan semanal y se ajusta? ¿el
atleta registra lo que nadó? Eso condiciona toda la UI y no está decidido.
Espera mi respuesta.

RESTRICCIONES
- Todo modelo nuevo va en app/core/model_registry.py y en alembic/env.py.
- Los 478 tests en verde.
- Frontera de equipo: sesiones y series llevan equipo_id y FK compuesta contra
  (id, equipo_id), como todo lo demás.

AL TERMINAR
Dime qué hace falta en el frontend para que esto sea usable, sin construirlo.
```

---

## C8 · Carga de entrenamiento (Banister)

> **R1 — CERRADA: entra, después de C7.** Y C7 después de C1–C6. Banister depende
> de `Sesion`, **no de `Serie`**: el sTSS diario sale de fecha + carga.

### Qué pasa

CTL / ATL / TSB está documentado en la nota 05 del vault desde el principio y
nunca se pudo construir porque no había de dónde sacar la carga diaria. Con
`Sesion`, ya la hay.

Es también lo que alimenta las alertas de sobreentrenamiento de la nota 14.

### Riesgo

**Bajo.** Es derivado: se recalcula, no se edita.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee docs/REDISENO.md (secciones 5.12 y 6.3), CLAUDE.md, y la nota del vault
E:\Obsidian\Inbox\Peakstroke\05 - Modelo Banister CTL-ATL-TSB.md
Requiere C7 (Sesion/Serie) hecho.

CONTEXTO
El modelo Banister está documentado desde el principio y nunca se pudo construir
porque no había de dónde sacar la carga diaria. Con Sesion ya la hay.

TAREA
1. CargaAcumulada en app/dominio/servicios/banister.py:
   CTL = media exponencial 42 días · ATL = 7 días · TSB = CTL - ATL
2. Tabla carga_diaria (atleta, fecha, stss, ctl, atl, tsb) — DERIVADA: se
   recalcula desde las sesiones, no se edita a mano.
3. Alertas de sobreentrenamiento según la nota 14 del vault
   ("14 - Errores Críticos del Sistema").

REGLA DE ORO DEL PROYECTO
Todo cálculo va con su fórmula y su fuente científica en el docstring. Nada de
constantes sin justificar: si un número no tiene referencia, pregúntame antes de
ponerlo. Las tablas científicas de este proyecto llevan su § de referencia y esto
no es la excepción.

ANTES DE EMPEZAR
El sTSS por sesión es la entrada de todo el modelo y hay que definirlo: ¿de dónde
sale? ¿volumen × intensidad de zona? ¿RPE? Enséñame las opciones con su respaldo
en la literatura y espera mi decisión.

RESTRICCIONES
- Los 478 tests en verde.
- Que el recálculo sea idempotente y reproducible: correrlo dos veces da lo mismo.

AL TERMINAR
Un ejemplo con datos del seed: la curva CTL/ATL/TSB de un atleta a lo largo de un
macrociclo, y si dispara alguna alerta.
```

---

# PARTE D — PSADMIN

> Aplicación de administración **separada de verdad** del programa: no una UI
> aparte, una frontera aparte. Para 1–2 personas (tú y quien te dé soporte).

---

## D · El principio: seis capas independientes

"App aparte" no significa "menos superficie". Hay dos cosas que suenan igual y no
lo son:

| | Qué es | Superficie de ataque |
|---|---|---|
| Frontend aparte, mismo backend | otra SPA llamando a `/api/v1/admin/*` | **sube** — los endpoints viven en el proceso expuesto |
| **Proceso aparte** | otro FastAPI, otro puerto, no publicado | **baja** — ese código **no está cargado** en el proceso público |

Si la razón fuese *"nadie va a encontrar `/admin`"*, eso no es seguridad, es
esconder la llave bajo la maceta. La propiedad que vale es **"el endpoint no
existe en el proceso expuesto"**, y solo la da el proceso aparte.

El diseño apila **seis barreras independientes**. Si una falla, las otras
aguantan:

| # | Barrera | Qué impide |
|---|---|---|
| 1 | **Proceso separado** | El API público no tiene rutas de admin. `main.py` registra 8 routers; PSAdmin registra los suyos y ninguno de esos |
| 2 | **Red separada** | PSAdmin escucha en `127.0.0.1` o en red privada (Tailscale/WireGuard). No es alcanzable desde internet |
| 3 | **Sesión separada** | Secreto JWT propio, cookie propia, cuentas propias, 2FA obligatorio. Un token de PeakStroke no abre PSAdmin ni al revés |
| 4 | **Usuario de base de datos separado** | Solo `SELECT` sobre vistas + `INSERT` sobre su propia auditoría. **Ni un `UPDATE` ni un `DELETE` en todo el esquema** |
| 5 | **Vistas en vez de tablas** | Los datos deportivos **no están en ninguna vista**. PSAdmin no puede leerlos: no es una convención, es el motor de la base de datos |
| 6 | **Auditoría append-only** | PSAdmin lee el registro y no puede alterarlo. Un administrador no puede borrar su rastro |

La 5 es la que hace todo el trabajo pesado y merece detalle: PeakStroke define
vistas (`v_admin_accesos`, `v_admin_cuentas`, `v_admin_equipos`) y PSAdmin
consulta **solo** eso. La vista es el contrato: cambiar el esquema por detrás no
rompe PSAdmin, y PSAdmin no puede ver una columna que no esté en la vista.

### Lo que PSAdmin NUNCA debe poder hacer

**Ver datos deportivos.** Todo tu aislamiento es *"el equipo es la frontera de
todo"*, impuesto por FKs compuestas contra `(id, team_id)`. Un admin que ve a
través de esa frontera es, por construcción, lo único del sistema que la rompe.
La línea: **metadatos sí** (cuántos, quién entró, qué falló), **tiempos, tests y
planes de un atleta, no**. Un administrador de plataforma no necesita saber
cuánto nada nadie.

**Suplantar.** Tu código ya tomó esta decisión con muy buen criterio:
`dev_identity_enabled` exige que fallen **dos** condiciones a la vez, e
`is_developer` no se puede persistir en ninguna columna. Un PSAdmin con "entrar
como este usuario" es el conmutador de desarrollo, en producción, con mejor cara.

**Escribir.** Las operaciones peligrosas van al CLI (bloque D1), no a la web.
Leer no destruye; por eso mirar puede ser cómodo y tocar no necesita serlo.

---

## D0 · La auditoría (va en PeakStroke, no en PSAdmin)

**Prioridad: PRIMERO de la parte D, y útil por sí sola.**

### Qué pasa

**"Ver accesos" hoy es imposible: ese dato no existe.** Todo el rastro que hay:

```
users.last_login_at    un timestamp por usuario, SOBRESCRITO en cada login
logger.warning(...)    4 llamadas, a stdout, sin persistir
```

`last_login_at` te dice la última vez y borra la anterior. Hoy no puedes
responder *"¿quién revocó a este atleta?"* ni *"¿alguien intentó entrar y falló?"*.

**Consecuencia de diseño:** PSAdmin no observa nada, **lee lo que PeakStroke
grabó**. El único que ve las peticiones es el proceso que las atiende, así que la
instrumentación va dentro de PeakStroke por necesidad, no por comodidad.

### Riesgo

**Bajo**, con una trampa que hay que evitar: si el fallo al escribir la auditoría
tumba la petición, has convertido una tabla de registro en punto único de fallo de
toda la aplicación. Se registra y se sigue.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee CLAUDE.md (secciones "Identidad y roles", "Equipos, roles y aislamiento",
"Integridad y borrado" y "Esquema de base de datos") y docs/PLAN-DE-TRABAJO.md
(la parte D).

CONTEXTO
Voy a construir una app de administración separada (PSAdmin) que enseñe accesos y
actividad. Ese dato hoy NO EXISTE: el único rastro es users.last_login_at, que se
sobrescribe en cada login, y cuatro logger.warning que van a stdout. PSAdmin no
observará nada: leerá lo que PeakStroke grabe. Este bloque construye ESE registro.
PSAdmin todavía no existe y no se toca en esta sesión.

TAREA 1 — Tabla de auditoría, append-only
Un evento por fila. Nunca UPDATE, nunca DELETE.
Campos mínimos: momento (timezone-aware), tipo de evento, resultado (ok/fallo),
actor (user_id + email DENORMALIZADO en el momento del hecho), equipo si aplica,
objetivo (qué recurso), ip, user_agent, y un detalle corto legible.

Por qué el email va denormalizado: la auditoría registra lo que era verdad EN ESE
MOMENTO. Si mañana cambia el correo o la cuenta se archiva, el registro no debe
cambiar de significado. Por la misma razón, ninguna FK hacia esta tabla lleva
CASCADE: el rastro sobrevive a lo que describe.

TAREA 2 — Qué se registra
Todo lo que ya es un evento de seguridad en el código de hoy:
  - login correcto y login fallido (y el motivo del fallo)
  - logout y revocación de sesiones (token_version)
  - refresh reusado -> el código YA lo trata como robo (auth/router.py::refresh);
    ese es el evento más importante de todos
  - cambio de contraseña
  - cambio de rol en team_members, revocación y restauración de pertenencia
  - transferencia de propiedad de equipo
  - códigos de vinculación: emitidos, canjeados, revocados
  - bajas y restauraciones de nadador, test aeróbico e inscripción
  - uso del bypass de desarrollo (hoy solo hay un logger.warning en
    core/dependencies.py::exigir_o_bypass)

TAREA 3 — Vistas de solo lectura para PSAdmin
Crea vistas SQL que serán el ÚNICO contrato de lectura de PSAdmin:
  v_admin_accesos    eventos de acceso y sesión
  v_admin_cuentas    cuentas y su estado, SIN datos deportivos
  v_admin_equipos    equipos con conteos agregados, SIN datos deportivos
Regla dura: ninguna vista expone tiempos, tests, planes, zonas ni nada del
rendimiento de un atleta. La vista es la frontera, no una convención.

RESTRICCIONES CRÍTICAS
- Si escribir la auditoría falla, la petición del usuario SIGUE ADELANTE. Se
  registra el fallo y se continúa. Una tabla de log no puede tumbar la app.
  Pero DEJA un aviso claro en el log del servidor cuando eso pase.
- El coste por petición tiene que ser despreciable. Mídelo y dímelo.
- Alembic es la única fuente del esquema; el modelo nuevo va en
  app/core/model_registry.py Y en alembic/env.py.
- Los 478 tests en verde.

PRIVACIDAD — habla conmigo antes de decidir
La auditoría guarda IPs, y en este sistema hay cuentas de MENORES de edad (el
motor tiene una corrección por juventud para sub-18). Una IP es dato personal.
Proponme una política de retención y de anonimización con sus opciones y espera
mi decisión antes de implementarla. No la des por supuesta.

AL TERMINAR
Enséñame el coste medido por petición y una consulta de ejemplo sobre cada vista.
```

---

## D1 · CLI de operaciones

### Qué pasa

Las operaciones peligrosas —crear un equipo, provisionar una cuenta, revocar
acceso, resetear una contraseña— **no necesitan una web**. Las haces tres veces al
año.

Un CLI ejecutado por SSH en el servidor tiene **superficie de red cero**: no hay
puerto, no hay endpoint, no hay sesión que robar. Es la opción más segura del
documento entero, y ya la tienes a medias en `tools/create_user.py`.

### Riesgo

**Bajo.** Amplía un patrón que ya existe.

### Prompt

```text
Trabajo en PeakStroke, en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
Lee CLAUDE.md y backend/tools/create_user.py (el patrón ya existe ahí).
Requiere D0 (auditoría) hecho.

CONTEXTO
Las operaciones de administración peligrosas no van a tener interfaz web: van por
CLI, ejecutado en el servidor. Superficie de red cero: no hay puerto ni endpoint
ni sesión que robar. tools/create_user.py ya es esto para un caso.

TAREA
Amplía backend/tools/ a un CLI de administración coherente que cubra:
  - crear equipo y su dueño (ya existe, unifícalo bajo el mismo CLI)
  - provisionar y despachar cuentas de PSAdmin (ver bloque D2)
  - revocar y restaurar la pertenencia de una cuenta
  - forzar la revocación de todas las sesiones de un usuario (token_version)
  - resetear una contraseña (emitiendo una temporal, mostrada UNA sola vez)
  - transferir la propiedad de un equipo
  - un informe de salud: versión, estado de las migraciones, conteos

REQUISITOS
- TODA operación escribe en la auditoría de D0, con quién la ejecutó (el usuario
  del sistema operativo) y desde dónde.
- Las destructivas piden confirmación explícita escribiendo el nombre del recurso,
  no un "s/n". Y tienen --dry-run que enseña lo que haría sin hacerlo.
- Nada de contraseñas por argumento de línea de comandos: quedan en el historial
  del shell. Léelas por stdin.
- Respeta las reglas del proyecto: nada se borra, se da de baja; el dueño no puede
  quedarse sin acceso; los emails se normalizan a minúsculas.

AL TERMINAR
Un README corto en tools/ con cada comando y cuándo usarlo.
```

---

## D2 · PSAdmin — proceso, sesión y frontera

### Qué pasa

Aquí se construyen las barreras 1 a 4. **Con 1–2 operadores te puedes permitir
controles que no escalan**, y eso es una ventaja: 2FA obligatorio, sin registro,
sin recuperación de contraseña por web, sesiones cortas. Cuentas provisionadas
solo por CLI desde el servidor.

### La tentación que hay que resistir

Compartir código con PeakStroke. Si PSAdmin importa `app.core.security`, están
acopladas y una vulnerabilidad viaja entre las dos. **Aquí la duplicación
deliberada es lo correcto** — es de los pocos sitios donde repetir 40 líneas
compra más de lo que cuesta.

### Riesgo

**Medio.** Es infraestructura nueva y es la pieza de seguridad. Se hace despacio.

### Prompt

```text
Voy a crear PSAdmin, una aplicación de administración SEPARADA de PeakStroke.
PeakStroke está en C:\Users\diego\OneDrive\Desktop\PeakStroke\PeakStroke\peakstroke.
PSAdmin va en una carpeta HERMANA, no dentro de peakstroke/.

Lee antes: peakstroke/docs/PLAN-DE-TRABAJO.md (parte D completa) y
peakstroke/CLAUDE.md (para las convenciones, no para copiar código).
Requiere D0 (auditoría y vistas) hecho.

CONTEXTO
PSAdmin lo usamos 1 o 2 personas. La separación no es de interfaz, es de
frontera real. El objetivo es que el proceso público de PeakStroke NO TENGA
NINGUNA ruta de administración: que ese código ni siquiera esté cargado ahí.

TAREA — construye las barreras 1 a 4 del documento

BARRERA 1 · Proceso separado
FastAPI propio, main.py propio, puerto propio. Registra sus routers y NINGUNO de
los 8 de PeakStroke. No añadas ni una ruta de admin al peakstroke/backend.

BARRERA 2 · Red
Por defecto escucha en 127.0.0.1, nunca 0.0.0.0. Documenta las dos formas de
llegar para 2 personas —túnel SSH y red privada tipo Tailscale— con sus
diferencias. Recomiéndame una y explícame por qué.

BARRERA 3 · Sesión propia
Secreto JWT distinto del de PeakStroke, cookie con otro nombre, cuentas propias
en su propia tabla. Con 1-2 usuarios puedo permitirme controles que no escalan, y
los quiero todos:
  - 2FA con TOTP, OBLIGATORIO, sin excepción
  - sin registro y sin invitación: las cuentas se provisionan por CLI (bloque D1)
  - sin recuperación de contraseña por web: si se pierde, se reprovisiona desde
    el servidor
  - sesión corta y sin "recuérdame"
  - bloqueo por intentos fallidos
Un token de PeakStroke no debe abrir PSAdmin ni al revés. Escribe un test que lo
fije.

BARRERA 4 · Usuario de base de datos propio
PSAdmin conecta con credenciales que SOLO tienen:
  - SELECT sobre las vistas v_admin_* de D0 (no sobre las tablas base)
  - INSERT sobre su propia tabla de auditoría
Ni un UPDATE ni un DELETE en todo el esquema. Documenta el SQL de provisión de
ese rol.
IMPORTANTE: esto lo da PostgreSQL de forma nativa y SQLite no. Dime qué se puede
garantizar hoy en SQLite y qué queda pendiente del salto a PostgreSQL, sin
fingir que está protegido si no lo está.

LA TENTACIÓN QUE HAY QUE RESISTIR
No compartas código con PeakStroke. Si PSAdmin importa app.core.security, están
acopladas y una vulnerabilidad viaja entre las dos. Duplica las 40 líneas que
haga falta. Es de los pocos sitios donde repetir sale más barato que compartir.

RESTRICCIONES
- CERO cambios en peakstroke/backend en esta sesión. Si algo hace falta allí,
  PARA y dímelo: es trabajo de otro bloque.
- PSAdmin no lee tablas base, solo vistas.
- Tests desde el primer día, y en particular los de la frontera: que un token
  cruzado no funcione, que el usuario de DB no pueda escribir, que las vistas no
  expongan datos deportivos.

AL TERMINAR
Enséñame, ejecutándolo, que el proceso público de PeakStroke devuelve 404 en
cualquier ruta de administración que se te ocurra probar.
```

---

## D3 · PSAdmin — lo que se ve

### Qué pasa

La interfaz. Metadatos, nunca datos deportivos:

| Panel | Qué enseña |
|---|---|
| **Accesos** | Logins correctos y fallidos por cuenta, con IP y agente, en el tiempo |
| **Sesiones** | Revocaciones, y **refresh reusado** — que el código ya trata como robo |
| **Cuentas** | Altas, bajas, cambios de rol, transferencias de propiedad |
| **Equipos** | Cuántos, cuántos miembros, actividad. Sin entrar en el deporte |
| **Salud** | Errores 5xx, versión desplegada, estado de las migraciones |

El panel que más valor da es el de **refresh reusado**: el código ya detecta ese
caso y corta todas las sesiones, pero hoy **nadie se entera de que pasó**.

### Riesgo

**Bajo.** Es lectura sobre vistas.

### Prompt

```text
Trabajo en PSAdmin (carpeta hermana de peakstroke/).
Lee peakstroke/docs/PLAN-DE-TRABAJO.md (parte D).
Requiere D2 hecho.

CONTEXTO
La interfaz de PSAdmin. Solo lectura, solo metadatos, solo sobre las vistas
v_admin_* que definió el bloque D0.

TAREA — cinco paneles
1. ACCESOS — logins correctos y fallidos por cuenta, con IP y agente, en línea de
   tiempo. Filtros por cuenta, por rango de fechas y por resultado.
2. SESIONES — revocaciones y, sobre todo, REFRESH REUSADO. El código de PeakStroke
   ya detecta ese caso y corta todas las sesiones porque lo trata como robo de
   token, pero hoy nadie se entera de que ocurrió. Que sea el panel más visible de
   los cinco, con aviso destacado.
3. CUENTAS — altas, bajas, cambios de rol, transferencias de propiedad.
4. EQUIPOS — cuántos, cuántos miembros, cuándo hubo actividad. Agregados.
5. SALUD — errores 5xx, versión desplegada, estado de las migraciones.

REGLA DURA
Ni un tiempo, ni un test, ni un plan, ni una zona de ningún atleta. Si un panel
necesita un dato que no está en las vistas, NO amplíes la vista por tu cuenta:
para y pregúntame. Esa frontera es el punto entero de PSAdmin.

TAMBIÉN
PSAdmin registra en SU PROPIA auditoría quién entró y qué consultó. Somos dos
personas: "quién miró esto" tiene que tener nombre.

RESTRICCIONES
- Solo lectura. Ni un formulario que escriba nada en PeakStroke.
- CERO cambios en peakstroke/.
- Interfaz sobria: esto se mira cuando algo va mal, no se contempla.

AL TERMINAR
Dime qué preguntas de seguridad puedo responder ahora que antes no podía, y
cuáles siguen sin respuesta.
```

---

## D · Decisiones abiertas

| # | Decisión | Recomendación |
|---|---|---|
| **R10** | ¿Túnel SSH o red privada (Tailscale/WireGuard)? | **Tailscale** para dos personas: casi tan fuerte y mucho más cómodo. SSH si el segundo perfil es esporádico |
| **R11** | Política de retención de la auditoría | **Pendiente.** Hay IPs y hay cuentas de menores. Hay que decidirlo, no heredarlo |
| **R12** | ¿PSAdmin espera a PostgreSQL? | La barrera 4 (usuario de solo lectura) **solo es real en PostgreSQL**. D0 y D1 no dependen de eso; D2 y D3 sí. **R8 se cerró el 2026-08-16 como "SQLite, y el cambio va después de C6"**, así que D2 y D3 esperan a esa migración — que ahora tiene un disparador de despliegue, no de rediseño |

> **Nota (2026-08-16).** R1–R8 están cerradas; ver C0 y la §10 de `docs/REDISENO.md`.
> **R9** también se cerró ese día (rosa `#f472b6`; ver B1) y **ya está aplicada**
> en `frontend/src/lib/constants.ts`. Siguen abiertas **R10**,
> **R11** y **R12** de aquí arriba, la cuarta pestaña de B1 (Base aeróbica), y las
> **cinco preguntas nuevas N1–N5** de la §10.3 de `REDISENO.md`, que bloquean el
> módulo de entrenamiento diario y no este plan.

---

# Orden y dependencias

```
A0  red de seguridad ✅ ─────────┐
                                 │ (obligatorio antes de C4)
A1  reglas divergidas ✅         │
A2  duplicados y archivos ✅     │
                                 │
B1  fusión de la UI ✅ ──────────┤ (mejor antes de C, no obligatorio)
                                 │
C0  cerrar decisiones ✅ R1-R9 (2026-08-16) · abiertas: R10, R11, R12
     │                           │
     ├─ C1 valores ──┬─ C2 entidades ──┬─ C5 repositorios
     │               │                 │
     │               └─ C3 roles       └─ C6 Resultado ─┐
     │                                                  │ (verde + desplegado)
     │                                                  ▼
     │                                        C7 Sesion ── C8 Banister
     │                                    (`Serie` FUERA — R1)
     └────────────────────────── C4 motores ◄──────────── A0

D0  auditoría ──┬── D1 CLI            (independientes de A/B/C: se pueden
                │                      hacer en cualquier momento)
                └── D2 frontera ── D3 paneles
                         ▲
                    PostgreSQL (R8/R12) para que la barrera 4 sea real
```

**La parte D es independiente de A, B y C.** No comparte código ni depende del
rediseño. `D0` es la única que toca PeakStroke y es útil por sí sola: hoy no
puedes responder *"¿quién revocó a este atleta?"*.

**Ruta mínima si quieres el mayor retorno con el menor riesgo:**
`A0 → A1 → B1 → C0 → C1 → C2`. Todo aditivo, nada irreversible, y cierra cuatro
de los seis hallazgos.

> **Al 2026-08-16 esa ruta va por `C1`.** `A0`, `A1`, `A2`, `B1` y `C0` están
> hechos; de la parte C **no hay nada construido todavía** —medido, no supuesto:
> `app/domain/` sigue siendo solo `engine.py`, los dos motores siguen en pie, no
> hay objetos de valor ni repositorios, y la última migración es la del
> 2026-08-10—, así que `C1` … `C8` quedan enteros. `D0`–`D3` tampoco están
> empezados: no hay módulo de auditoría ni CLI de operaciones (`tools/` solo
> tiene `create_user.py` y `sim_cli.py`). Siguen abiertas **R10**, **R11** y
> **R12**, pero ninguna bloquea `C1`.

**Ruta de seguridad, si PSAdmin es lo que más te urge:** `D0 → D1`. Te da el
registro de accesos y las operaciones peligrosas fuera de la web, sin construir
todavía ninguna aplicación nueva. `D2` y `D3` pueden esperar a PostgreSQL.

**Ruta completa:** todo, con `C4` en rama propia y `C6` con el downgrade probado.

---

# Anexo · Los seis hallazgos, en una tabla

Para releer rápido de qué iba todo esto.

| # | Hallazgo | Evidencia | Se cierra en |
|---|---|---|---|
| P1 | Hay dos motores y el "oficial" solo corre en tests | `ScienceEngine` solo se llama en tests; los planes salen de `progression.py` | **C4** |
| P2 | Ya divergieron, y son **más de tres**: quedan **6 abiertas** | ✅ cerradas en A1 (2026-08-13): ~~50 m combinado~~ · ~~`MAX_EXTENSION_WEEKS` 30/26~~. **Abiertas:** fases (5/4/4) · clasificación de nivel · techo I_max · factibilidad · ritmo /100 del sprint · `ZONE_LABELS`. De las seis, **dos están medidas** (ver C0): el nivel salta de banda por una décima (`2:10.40` → elite, `2:10.50` → competitive: **45 % más volumen**), y `ScienceEngine` sube el volumen la semana de competencia mientras `distribute_km` lo baja | **A1** ✅ las dos primeras · **C1 + C4** las seis restantes |
| P3 | `WeeklyPlan.phase` guarda etiqueta, no clave de dominio | la DB tiene `"Construcción"`; `F_FASE` indexa `base_especifica` | **C1 + C2** |
| P4 | Modelo anémico: 14 modelos, 1 con comportamiento | `age_at`, `current_week_of`, `effective_status` huérfanas | **C2** |
| P5 | El corte es por endpoint, no por concepto | `dashboard`, `aerobic_tests`, `link_codes` importan lógica ajena | **C5** |
| P6 | Obsesión por primitivos | 8 columnas `float` con dos unidades; solo `role` tiene `CheckConstraint` | **C1** |

---

# Anexo · Lo que NO hay que tocar

Estas piezas están bien y el rediseño las conserva enteras. Si un prompt propone
cambiarlas, di que no.

- **El aislamiento por equipo impuesto por la base de datos**: FKs compuestas
  contra `(id, team_id)` en toda tabla de relación. Mezclar equipos es imposible
  aunque el código tenga un bug.
- **`PRAGMA foreign_keys=ON`** en cada conexión SQLite.
- **Recurso ajeno → 404, nunca 403.** El 403 es solo "tu rol no alcanza".
- **`team_id` sale siempre de la sesión**, nunca del cuerpo de la petición.
- **Nada se borra: se da de baja.**
- **`scope_to_own_swimmer` falla cerrado**: un atleta sin ficha ligada no ve nada,
  no lo ve todo.
- **El conmutador de desarrollo** con sus dos ejes ortogonales, y que
  `is_developer` no se pueda persistir.
- **Ficha ≠ cuenta**, unidas solo por un código canjeado que caduca, se gasta y
  tiene dos lados.
- **Revocada ≠ sin equipo.** Confundirlos deja entrar a quien acabas de echar.
- **Alembic como única fuente del esquema.**
- **Las tablas científicas y su trazabilidad al § de la fuente.**
- **Los 478 tests.** Son el contrato que hace posible todo lo demás.
