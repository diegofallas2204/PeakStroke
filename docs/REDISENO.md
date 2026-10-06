# PeakStroke — Modelo del rediseño

> **Estado al 2026-10-05: los ocho pasos del §9 son código** (el 7 y el 8 el
> 2026-09-23; sus pantallas el 2026-10-01). **Lo que falta, en el orden de este
> documento:**
>
> | # | Dónde | Qué falta | Tipo | Estado |
> |---|---|---|---|---|
> | 1 | §5.3 `Atleta` | `dar_de_baja()` / `restaurar()` | código | ✅ **hecho 2026-10-05**: idempotentes; crear, editar, baja y alta pasan por `Atleta` y `RepositorioDeAtletas.guardar`. **Excepción**: ligar la cuenta (`user_id`) sigue en el canje del código (`codigos`), que es el punto 5 |
> | 2 | §5.4 `Macrociclo` + §5.6 `Inscripcion` | la entidad `Inscripcion` (con `dar_de_baja()` / `restaurar()`) y `Macrociclo.inscribir()` | código | ✅ **hecho 2026-10-05**: idempotentes; `inscribir()` exige ficha del club y activa (y devolver también: es inscribir otra vez); `RepositorioDeInscripciones` (compone al de macrociclos) con `por_id` acotado. Las pruebas y semanas siguen como filas (puntos 3-4) |
> | 3 | §5.7 `PruebaObjetivo` | la entidad, con `mejora_pedida()` y `factibilidad()` | código | ⬜ pendiente |
> | 4 | §5.8 `Semana` | la entidad, con `zonas()`, `real()` y `desviacion()` derivados | código | ⬜ pendiente |
> | 5 | §10.2 punto 3 | **R5.3**: el orden de las comprobaciones en `redeem` | decisión + código | ⬜ pendiente, pide decisión |
> | 6 | §10.3 | **N1** y **N2**: qué entra en el promedio semanal | decisión | ⬜ abiertas |
> | 7 | §10.3 | **N3** y **N5**: sesiones por semana y sesión estructurada | decisión | ⬜ abiertas, del módulo diario (fuera del rediseño) |
>
> Los puntos 1-4 son un solo frente: hasta que `Inscripcion`, `PruebaObjetivo`
> y `Semana` sean entidades, **las escrituras arman filas del ORM desde
> `api/v1/`** (CLAUDE.md) y los mutadores no tienen a quién devolver un agregado
> que el repositorio guarde. **N4 está cerrada**: el PDF se arma en el cliente
> (construido el 2026-08-25).
>
> Lo que sigue debajo es la historia del documento, en orden de fecha.
>
> **Estado original (2026-08-12): MODELO CERRADO, sin construir.** La beta actual
> sigue intacta y funcionando. Este documento es el modelo objetivo para la
> versión limpia.
>
> Fecha: 2026-08-12 · Línea base medida: 307 tests en verde, `tsc` limpio,
> `eslint` limpio.
>
> **Actualización 2026-08-13:** el bloque A1 del plan de trabajo (cerrar las dos
> divergencias concretas) sí se ejecutó — no toca el rediseño, borra reglas
> duplicadas y añade `tests/test_reglas_unicas.py`. Línea base entonces: **442
> tests en verde**. El modelo de este documento sigue sin construirse.
>
> **Línea base vigente: 478 tests en verde** (suite completa ejecutada el
> 2026-08-16: `478 passed in 130.54s`, sin fallos ni omitidos, con `PEAKSTROKE_`
> por defecto). La progresión es 307 → 442 → 478; las dos primeras
> cifras se conservan arriba porque fechan lo que se midió entonces. **Donde este
> documento diga "los N tests" sin fecha, se refiere a los 478 de hoy.**
>
> **Actualización 2026-08-16 — las ocho decisiones (R1–R8) están cerradas.**
> Ver **§10**, que guarda cada una con su fecha y su razón. Cerrarlas cambió
> cinco cosas del cuerpo del documento (§10.2) y abrió cinco preguntas nuevas
> (§10.3), ninguna de las cuales bloquea la construcción. Los sitios afectados
> llevan una nota `> **Rn — CERRADA**` al lado del texto original: se conserva
> lo que se pensaba antes, porque la razón del cambio se lee mejor con las dos
> versiones delante.
>
> **Actualización 2026-08-16 — el paso 1 está construido.** `app/dominio/valores/`
> existe con los objetos del §3 y sus tests; `app/engine/events.py` se borró al
> migrar su regla a `Prueba`. **Línea base ahora: 729 tests en verde** (478 + 251).
> Es el primer trozo de este documento que deja de ser modelo y pasa a ser código.
> Detalle y decisiones en el bloque C1 de `docs/PLAN-DE-TRABAJO.md`.
>
> **Construirlo enmendó el §3 en dos puntos, y las dos enmiendas están aplicadas**
> (código y modelo, mismo día): se añadió **`Duracion`** —`Tiempo` hacía de nado y
> de instante a la vez y solo el nado es siempre positivo— y **`Mejora.base` pasó
> de `float` a `Tiempo | Ritmo`**, porque sin unidad una mejora de ritmo salía
> convertida en un tiempo absoluto: P6 reentrando por el único tipo que une las
> dos unidades. El porqué de cada una, con su evidencia, en la enmienda del §3.1.
>
> Que el modelo estuviera "cerrado" no lo hacía correcto: las dos se vieron **al
> escribir el código**, no al revisarlo, y la señal de la primera estaba dentro
> del propio código nuevo (`zona.py` se salía del tipo para sumar dos tiempos).
>
> Una decisión de construcción que este documento no fijaba: *«el dominio no
> importa nada»* se tomó **literal**, así que `app/dominio/` tampoco importa
> `app/domain/`. Por eso las tablas científicas que un valor necesita viven dentro
> del tipo, con una red (`tests/test_valores_vs_motor.py`) que las compara contra
> la fuente viva hasta que el paso 4 retire la copia vieja.
>
> **Actualización 2026-08-25 — el paso 5 está construido, y con él el §2 entero.**
> `app/modules/` **ya no existe**. Seis agregados, cada uno con su tabla en
> `persistencia/tablas/`, su repositorio en `persistencia/repositorios/` y su
> rebanada en `api/v1/`: `atletas` · `codigos` · `equipos` · `macrociclos` ·
> `tests_aerobicos` · `usuarios`; más `api/v1/simulador/` (sin tabla) y
> `api/v1/vistas/` (el tablero y la tabla del equipo, que **no son agregados**).
> Línea base ahora: **834 tests en verde** (822 + 12 de
> `tests/test_dependencias_de_capas.py`). Detalle y decisiones en el bloque C5
> de `docs/PLAN-DE-TRABAJO.md`.
>
> **La dirección de dependencias dejó de ser una convención.** El §2 la enuncia;
> desde hoy hay un test que falla cuando se viola, y el grafo
> (`tools/grafo_de_imports.py`) no tiene ninguna flecha que suba. P5 del §0 está
> **cerrado**: las tres violaciones que la auditoría contó ya no se pueden
> escribir.
>
> **Construirlo enmendó el §5.5 en un punto.** `FaseDelMacro` necesitaba
> **`tipo`** —el `base|build|peak|taper` que la base guarda— porque sin él, quien
> quisiera pintar la franja de fases volvía a necesitar el modelo del ORM, que es
> justo el import que este paso viene a quitar. **No decide el reparto 4↔5**:
> `fase` sigue viajando en `None` y P3 sigue siendo el único hallazgo del §0 sin
> bloque asignado.
>
> Una decisión de construcción que este documento no fijaba: **tres repositorios
> no llevan `Principal`** (equipos, usuarios y códigos). El equipo *es* la
> frontera que los demás aplican y `Principal` se construye a partir de lo que
> devuelve; y la mitad de las lecturas de códigos las hace quien todavía no
> pertenece a ningún club. Acotarlos por lo que ellos mismos resuelven sería
> circular. Lo que sostiene la frontera ahí sigue siendo que **el `team_id` sale
> de la sesión, nunca del cuerpo de la petición**.
>
> **Actualización 2026-09-22 — P3 cerrado.** El reparto 4↔5 que tres pasos
> seguidos dejaron abierto se decidió **quitando el vocabulario de cuatro**, no
> traduciéndolo: las fases de un macrociclo **son** las cinco de `Fase`. Las
> fases por defecto (`servicios/plan.fases_por_defecto`) salen de
> `MACRO_15_FASES` con cada frontera en la semana más cercana a donde cambia la
> curva científica, así que la franja que ve el entrenador y la curva que sigue
> el atleta cambian de fase en las mismas semanas. `plan_phases.type` y
> `weekly_plans.phase` guardan la **clave**, con un `CHECK` que lo impone; el
> nombre del tramo es texto libre del entrenador y es lo que se enseña.
> `FaseDelMacro.tipo` —el tercer vocabulario que añadió el paso 5— se fue, y
> `FaseDelMacro.fase` pasó a ser obligatoria. La migración `a3f1c2d4e5b6`
> convirtió las filas que había (cada tramo a la fase con la que más se solapa
> en la forma de 15 semanas: base→base_general, build→umbral_css,
> peak→pre_competitivo, taper→taper) y su downgrade las devuelve. **Ningún
> número del motor se movió**: los snapshots se regeneraron solo por la etiqueta
> de fase y su diff son solo líneas de `phase`. Línea base: **938 tests**.
>
> **Lo que sigue sin decidirse** no son decisiones de modelo sino de producto, y
> viven en §10.3.

---

## 0. Por qué se rediseña

La beta funciona y su modelo de datos es sólido. Lo que está al revés es dónde
vive el comportamiento. Seis hallazgos de la auditoría, en orden de gravedad:

| # | Hallazgo | Evidencia |
|---|---|---|
| P1 | **Hay dos motores.** El que declara ser la fuente de verdad no corre en producción | `ScienceEngine.generate_plan()` solo se llama en tests; los planes reales salen de `engine/progression.py` |
| P2 | **Ya divergieron.** Y son más de tres | ~~50 m combinado~~ y ~~`MAX_EXTENSION_WEEKS` (30/26)~~ cerradas en A1 el 2026-08-13; **siguen abiertas**: ~~fases (5/4/4)~~ (cerrada con P3, 2026-09-22), clasificación de nivel, techo I_max, factibilidad, ritmo /100 del sprint, `ZONE_LABELS` |
| P3 | **`Semana.phase` guarda una etiqueta de interfaz**, no una fase de dominio | la DB tiene `"Construcción"`; `F_FASE` se indexa por `base_especifica`. No se pueden cruzar. **✅ CERRADO el 2026-09-22** en bloque propio (C4 pasó sin tocarlo): la base guarda la clave de `Fase` y las fases del macro son las cinco de la ciencia — ver la actualización de arriba |
| P4 | **Modelo anémico.** 14 modelos, 1 con comportamiento | reglas puras (`edad_at`, `current_week_of`, `effective_status`) huérfanas en `service.py` |
| P5 | **El corte es por endpoint, no por concepto.** La regla "los módulos no se importan" ya está rota | `dashboard`, `aerobic_tests` y `link_codes` importan lógica de otros módulos |
| P6 | **Obsesión por primitivos.** `(distancia, estilo, piscina)` viaja suelto; 8 columnas de tiempos son `float` mezclando dos unidades | de todo el esquema, solo `role` tiene `CheckConstraint` |

**P6 es la causa de P2.** La divergencia del 50 combinado fue posible porque la
validez de una prueba es una función suelta y no una propiedad del objeto. Se
cerró a mano en A1 (2026-08-13) borrando la copia mala, que es tapar el síntoma:
mientras la regla siga siendo una función suelta, la siguiente copia vuelve a
entrar. El cierre dejó una red en `tests/test_reglas_unicas.py` que falla si
reaparece, pero la solución de forma sigue siendo `Prueba` (§C1).

---

## 1. Principios de diseño

1. **Una regla, un sitio.** Si una regla científica o de negocio aparece dos
   veces, es cuestión de tiempo que digan cosas distintas. La auditoría de cierre
   de A1 (2026-08-13) contó **nueve** reglas duplicadas entre `app/domain/` y
   `app/engine/`; **seis ya dicen cosas distintas**.
2. **Invariante antes que convención.** Lo que hoy es "hay que acordarse de
   hacerlo en `create_test`" pasa a ser imposible de violar por construcción.
3. **Jerarquía de clases en el dominio, almacenamiento plano en la base de
   datos.** Sin herencia de tablas, sin discriminadores, sin tabla por subclase.
4. **Los hechos de rendimiento pertenecen al atleta, no al plan.** Un tiempo
   nadado es un hecho sobre una persona; el macrociclo lo referencia.
5. **Lo derivado se calcula, lo ocurrido se guarda.** Las zonas y las
   prescripciones nunca se persisten; lo que efectivamente se nadó, sí.
6. **El dominio no importa nada.** Ni SQLAlchemy, ni FastAPI, ni Pydantic. Se
   puede probar, empaquetar y portar sin la aplicación alrededor.
7. **Un archivo, una responsabilidad, ~300 líneas.** Hoy hay cinco que la rompen.

### Lo que NO se hace, y por qué

| Descartado | Razón |
|---|---|
| DDD completo (aggregate roots formales, unit of work, domain events, repositorios abstractos) | tres capas de indirección para 7.400 líneas y un equipo. Objetos de valor + entidades ricas + repositorios concretos dan el 90 % del beneficio |
| Herencia sobre `Usuario` (`class Entrenador(User)`) | ver §4. Cambiar de rol exigiría cambiar de clase; una fila de `users` no cambia de clase |
| Persistir zonas y prescripciones | dato derivado que queda mintiendo en cuanto el entrenador ajusta la meta |
| Event sourcing / CQRS | no hay volumen ni requisito de auditoría que lo justifique |
| Microservicios | un backend, un despliegue. El motor ya es empaquetable como librería |
| Reescribir el frontend | el rediseño es del backend; el frontend solo cambia sus tipos (`lib/types/`) |

---

## 2. Estructura

```
backend/app/
├── dominio/                     ← POO puro. No importa NADA de infraestructura
│   ├── valores/                 objetos inmutables sin identidad
│   │   ├── tiempo.py            Tiempo · Duracion · Ritmo · Mejora
│   │   ├── prueba.py            Prueba · Estilo · Piscina
│   │   ├── zona.py              Zona · Prescripcion · JuegoDeZonas
│   │   └── escalas.py           Nivel · Perfil · Fase · Especialidad · …
│   ├── entidades/
│   │   ├── usuario.py           Usuario
│   │   ├── equipo.py            Equipo · Pertenencia
│   │   ├── atleta.py            Atleta
│   │   ├── macrociclo.py        Macrociclo · FaseDelMacro · Competencia
│   │   ├── inscripcion.py       Inscripcion · PruebaObjetivo · Semana
│   │   ├── test_aerobico.py     TestAerobico · Parcial
│   │   ├── resultado.py         Resultado                          ← nuevo
│   │   ├── sesion.py            Sesion (R1: tras 1-6) · Serie (R1: fuera)
│   │   └── carga.py             CargaDiaria                  ← nuevo (R1: tras 1-6)
│   ├── roles/
│   │   └── rol.py               Rol · Administrador · EntrenadorEnJefe ·
│   │                            Entrenador · Atleta(rol)
│   └── servicios/
│       ├── motor.py             MotorCientifico  ← el único
│       ├── tablas.py            todas las constantes + su fuente §
│       ├── curvas.py            Curva (Strategy) + 5 implementaciones
│       ├── intervalos.py        cálculo de salida y descanso
│       └── banister.py          CargaAcumulada (CTL/ATL/TSB) ← nuevo (R1: tras 1-6)
│
├── core/                        config · database · security · principal
│
├── persistencia/                ← el ORM vive aquí, no en el dominio
│   ├── tablas/                  definición SQLAlchemy de cada tabla
│   ├── mapeo/                   tabla ↔ entidad de dominio
│   └── repositorios/            AtletaRepo · MacrocicloRepo · TestRepo · …
│
└── api/                         ← I/O puro
    └── v1/
        ├── atletas/             router + schemas
        ├── macrociclos/
        ├── tests/
        ├── simulador/
        ├── equipos/
        ├── auth/
        └── vistas/              dashboard, tabla de equipo, comparación
                                 (son VISTAS, no módulos de dominio)
```

**Dirección de dependencias, sin excepciones:**

```
api  →  persistencia  →  dominio
 └──────────────────────────↑        (la api puede leer el dominio directo)

dominio  →  nada
```

Esto es lo que mata P5: `vistas/dashboard` deja de importar
`plans.service.current_week_of` porque pregunta al repositorio y le llega un
`Macrociclo` que ya sabe su semana actual.

> **CONSTRUIDO el 2026-08-25** (bloque C5). El árbol de arriba es el que hay,
> con dos ajustes que se decidieron al construirlo: los códigos de vinculación
> van en `api/v1/codigos/` (el §2 no los nombraba) y `api/dependencias.py`
> entrega los repositorios como dependencia de FastAPI. `current_week_of` y
> `effective_status` **se borraron**, no se dejaron delegando: un envoltorio que
> delega sigue siendo un import que cruza. Lo comprueba
> `tests/test_dependencias_de_capas.py`, que además prohíbe declarar una tabla
> fuera de `persistencia/tablas/` — que es la condición que hace innecesaria la
> vieja excepción de «lecturas explícitas de modelos».

---

## 3. Objetos de valor

Inmutables (`frozen=True`), sin identidad, comparables por valor.

### 3.1 Tiempo y ritmo

| Objeto | Contenido | Comportamiento |
|---|---|---|
| `Tiempo` | segundos absolutos, **siempre > 0** | `desde_texto("1:05.32")` · `texto()` · comparación · `- → Mejora` · `diferencia() → Duracion` · `+ Duracion → Tiempo` |
| `Duracion` | segundos **con signo**; admite 0 y negativos | `texto()` · `a_tiempo()` · `es_negativa()` · `+ - neg abs` · comparación |
| `Ritmo` | segundos por 100 m | `desde(tiempo, distancia)` · `a_tiempo(distancia)` · `texto()` |
| `Mejora` | segundos + `base: Tiempo \| Ritmo` | `.segundos` · `.porcentaje` · `.fraccion` · `es_regresion()` · `resultado` (del **mismo tipo** que la base) |

**Por qué importan.** Hoy hay ocho columnas `float` que mezclan dos unidades:
`current_time`, `goal_time`, `expected_time`, `recalc_time`, `real_time` son
segundos absolutos; `avg_per100`, `css_ms`, `pace_100m` son segundos/100 m. Nada
impide restarlos entre sí. Con tipos distintos, el error no compila.

`Mejora` existe porque los dos motores actuales expresan lo mismo de dos formas:
`progression` maneja segundos, `ScienceEngine` maneja fracciones decimales. Un
tipo que lleva las dos elimina la conversión manual repetida.

> **Enmienda 2026-08-16, al construir el paso 1.** Dos cosas de esta sección
> estaban mal y se corrigieron con el código delante:
>
> 1. **Faltaba `Duracion`.** `Tiempo` hacía de dos cosas —un nado y un instante o
>    hueco del reloj— y solo la primera es siempre positiva. La salida de la
>    primera repetición de una serie **es 0**, y el descanso perdido de un parcial
>    es **negativo** (`missed_intervals`). Con un solo tipo, ni `Parcial.inicio`
>    (§5.9) se podía construir ni se podía escribir la conversión reloj→nadado,
>    que es la invariante que más protege la base aeróbica. La señal estaba en el
>    propio código nuevo: `zona.py` se salía del tipo para sumar dos tiempos.
>    Restar dos instantes sigue **sin** ser una `Mejora`: para eso está
>    `Tiempo.diferencia()`, porque `90 − 30` entre dos llegadas de reloj es un
>    hueco de 60 s, no una mejora del 66 %.
> 2. **`Mejora.base` no podía ser un `float`.** Sin unidad, `Ritmo(80) − Ritmo(78)`
>    devolvía un resultado de tipo `Tiempo`: una mejora de ritmo salía convertida
>    en un tiempo absoluto de 1:18. Es **P6 reentrando por el único tipo que une
>    las dos unidades**, que es justo lo que esta sección existe para impedir.
>    Con `base: Tiempo | Ritmo`, `resultado` devuelve el mismo tipo que la base y
>    el error deja de poder escribirse.

### 3.2 La prueba

```
Estilo    enum   libre · espalda · pecho · mariposa · combinado
Piscina   enum   50 · 25            + factor(perfil)
Prueba    (distancia: int, estilo: Estilo)
```

`Prueba` **rechaza en el constructor** los combos imposibles:

| Distancia | Estilos válidos |
|---|---|
| ≥ 600 m | solo libre |
| 300–599 m | libre, combinado |
| 100–299 m | los cinco |
| < 100 m | libre, espalda, pecho, mariposa (**no** combinado) |

Comportamiento: `perfil_sugerido()` · `tier()` (1 = ≥400 aeróbica, 2 = velocidad)
· `evento_mas_cercano()` (para indexar las tablas científicas).

**Esto es lo que cierra P2 estructuralmente.** Hoy la validez vive en
`engine/events.py` y una copia contradictoria en `domain/engine.py`. Con una sola
clase que no deja construir un 50 combinado, la divergencia deja de ser posible.

### 3.3 Zonas y prescripciones

```
Zona          enum ORDENADO      R1 > R2 > MVO2 > RL > V   (lento → rápido)
                                 + ratio_descanso() + tope en segundos

Prescripcion  Zona · Ritmo · salida: Tiempo · descanso: Duracion · distancia_rep
              texto() → "10 × 100 a 1:18 salida 1:30"

JuegoDeZonas  Mapping[Zona, Prescripcion]
              JuegoDeZonas.de(ritmo_carrera, prueba, piscina)
```

**Decisión: no se persisten.** Son derivados deterministas. Hoy `send_off.py`
calcula prescripciones completas que se pintan en una tabla y se tiran; eso está
bien y se conserva. Guardarlas crearía dato derivado que queda desfasado en
cuanto cambia la meta.

La excepción es `Serie` (§5.9): lo que efectivamente se mandó nadar un día sí se
guarda, como fotografía histórica. Ahí ya no es un cálculo, es un hecho.

Que `Zona` sea un enum **ordenado** importa: la jerarquía R1>R2>MVO2>RL>V vive
hoy en una lista suelta (`ZONE_ORDER` en `send_off.py`, reexportada por
`zones.py` con un comentario explicando que si se separan, una zona nueva se
convierte en un 500). Con un enum ordenado no hay dos listas que separar.

### 3.4 Escalas

| Objeto | Valores | Nota |
|---|---|---|
| `Nivel` | beginner · recreational · advanced · competitive · elite | **siempre derivado** vía `Nivel.desde_umbral(ritmo)`. Nunca se escribe a mano ni se guarda |
| `Perfil` | velocidad · medio_fondo · fondo | sugerido por la prueba, el entrenador puede sobrescribir |
| `Fase` | base_general · base_especifica · umbral_css · pre_competitivo · taper · extension | **lleva su `F_FASE` y su banda de volumen dentro** |
| `Especialidad` | velocidad · medio_fondo · fondo · aguas_abiertas | del atleta, no de la prueba |
| `Genero` | — | |
| `TipoDeTest` | T30 · T15 · CUSTOM · CSS · DIRECT | |
| `ModoDeIngreso` | rep · clock | tiempo nadado vs llegada de reloj |
| `Tendencia` | improving · stable · declining | derivada del test |
| `EstadoDeMacro` | activo · borrador · terminado · suspendido | |
| `Veredicto` | ok · warning · aggressive | factibilidad |

**`Fase` es la que cierra P3.** Hoy hay tres vocabularios vivos: las 5 claves
científicas de `F_FASE`, las 4 de `DEFAULT_PHASES` (`Base/Construcción/Pico/
Descenso`) y las 4 de `PlanPhase.type` (`base|build|peak|taper`). La base de
datos guarda la etiqueta humana, así que la ciencia no puede leer lo que la
aplicación persiste. Con un solo enum: se guarda la clave, y `FaseDelMacro.nombre`
queda como texto libre solo para la interfaz.

> **Construido el 2026-09-22.** Tal cual, con una precisión: el entrenador no
> elige entre cuatro tramos sino entre las cinco fases, y las que nacen por
> defecto son la forma de 15 semanas escalada a su macro. `Fase.del_macro()`
> rechaza la extensión, que no es un tramo sino lo que viene después.

---

## 4. Los roles

### 4.1 La decisión

`Usuario` es identidad y nada más: correo, hash, nombre, versiones de sesión.
**No hereda a `Entrenador` ni a `Nadador`.**

El caso concreto que lo descarta: **un atleta que asciende a entrenador en su
club.** Ocurre, y hoy es un `UPDATE team_members.role`. Con herencia sería
cambiar de clase una fila de `users`, que no cambia de clase: habría que borrar
la cuenta y recrearla, perdiendo el histórico y la identidad.

> **R5 — CERRADA el 2026-08-16.** Este párrafo argumentaba antes desde
> *"un entrenador que además nada máster en su propio club, o alguien que es
> atleta en un club y entrenador en otro"*. Las dos mitades son hoy imposibles y
> el diseño las mantiene imposibles: la segunda por `UNIQUE(user_id)` en
> `team_members`, la primera por `link_codes/service.py:260` (*"Una cuenta de
> entrenador no puede ligarse a una ficha"*) y porque una pertenencia lleva **un**
> `role`. Argumentar desde un caso que el propio modelo prohíbe debilitaba una
> decisión que es correcta por otra razón.

**El rol cuelga de la pertenencia**, que es donde ya vive hoy:

```
Usuario ──< Pertenencia >── Equipo
                │
                └── Rol   ← el polimorfismo vive aquí
```

### 4.2 La jerarquía

```
Rol (abstracto)
  · puede_ver(recurso) -> bool
  · alcance_de_atletas() -> Alcance      todos | los_mios | solo_yo | ninguno
  · alcance_de_macrociclos() -> Alcance
  · secciones_visibles() -> set[Seccion]
  · puede_escribir(recurso) -> bool
  │
  ├── Administrador       plataforma; cruza equipos   (R3: solo el hueco)
  ├── EntrenadorEnJefe    = dueño del equipo; ve TODOS los macrociclos del club
  │     └── hereda de Entrenador y solo amplía el alcance
  ├── Entrenador          ve los macrociclos en los que está (`entrenadores_del_macro`)
  └── AtletaRol           ve lo suyo y solo lo suyo
```

`EntrenadorEnJefe` hereda de `Entrenador` y **solo sobrescribe
`alcance_de_macrociclos()`**. Eso captura la regla real de hoy: el dueño llega a
todos los macrociclos porque, si no, los planes de un entrenador que se va
quedarían huérfanos. Es una ampliación de alcance, no un rol distinto.

`Principal` (que ya existe y funciona) se convierte en la composición:

```
Principal { usuario, pertenencia, rol: Rol, atleta_id?, es_desarrollador }
```

Los `if principal.is_athlete` repartidos por los services desaparecen: preguntan
al `Rol`. `Principal` hoy ya es el 70 % de esto — `is_coach`, `is_athlete`,
`sees_every_plan`, `scope_to_own_swimmer` son métodos de rol metidos a mano en
una sola clase. Convertirlos en subclases es un refactor pequeño y ya cubierto
por los tests de guards.

### 4.3 Almacenamiento

**Plano. El dueño sigue siendo una columna, no un tercer valor de `rol`.**

```
usuarios(id, correo, ...)                     identidad
pertenencias(usuario_id, equipo_id, rol, activa)   rol ∈ {entrenador, atleta}
equipos(id, nombre, dueño_id)                 ← el jefe es esta columna
```

Razón de no meter `entrenador_en_jefe` como valor de `rol`: hoy `dueño_id` siendo
una columna única hace **imposible** que un equipo tenga dos jefes, y una FK
compuesta garantiza que el jefe sea miembro de ese mismo equipo. Como fila de
`pertenencias` haría falta un índice único parcial, que SQLite y PostgreSQL no
tratan igual — lo descubrirías al migrar. Y transferir la propiedad dejaría de
ser un `UPDATE` atómico.

Tienes la jerarquía de clases que pediste; el almacenamiento no la necesita.

### 4.4 Administrador

Es el único rol que **no cabe en `pertenencias`**, y no por convención: un
administrador de plataforma cruza equipos por definición, y el equipo es la
frontera de todo el aislamiento del sistema. Meterlo ahí obligaría a que cada
consulta llevara una excepción "salvo si es admin", que es exactamente como se
rompen las fronteras.

Va como bandera en `usuarios` (`es_staff`) o tabla `roles_de_plataforma` aparte,
y `Principal` lo resuelve como **eje ortogonal** — igual que hoy resuelve
`es_desarrollador`, que ya es ese mismo patrón funcionando.

> **R3 — CERRADA el 2026-08-16: solo el hueco, y más estrecho.** Que la
> jerarquía de `Rol` no cierre la puerta (que `alcance_de_atletas()` pueda
> devolver `todos`) y nada más. **Ni `es_staff` en `usuarios`, ni campo en
> `Principal`, ni tabla `roles_de_plataforma`.** Un hueco en una jerarquía de
> clases es gratis y reversible; un campo en el objeto del que cuelga el
> aislamiento, no.

### 4.5 Entrenador asistente

**No necesita rol propio.** Hoy un entrenador solo ve los macrociclos en los que
está (`plan_coaches`) y el jefe los ve todos: eso *es* la distinción
jefe/asistente, y ya está impuesta en la capa de acceso.

Haría falta un rol nuevo solo si el asistente debe tener **menos** permisos
dentro de un macrociclo que sí lleva (ejemplo: registrar tiempos sí, cambiar la
meta no).

> **R4 — CERRADA el 2026-08-16: no hay rol nuevo, pero dos guards se mueven.**
> El argumento de arriba vale para **ver**, no para **escribir**: dentro de un
> macro que lleva, el asistente puede hoy borrarlo y cambiar la meta, porque
> `plans/router.py` los protege con `require_coach` y no con `require_owner`.
> **Esas dos operaciones pasan a `require_owner`.** No es un rol nuevo: es
> reconocer que ya eran de dueño y estaban mal guardadas. Un rol más añadiría
> una tercera pregunta a cada escritura, que es como se abrió el agujero del
> scoping del atleta.
>
> **Aplicada el 2026-09-24.** «Cambiar la meta» es cambiar `main_event` en
> `PATCH /plans/{id}`: el `goal_time` de una prueba no se edita por ninguna ruta.

---

## 5. Entidades

Identidad + ciclo de vida. El nombre nuevo va primero; entre paréntesis, cómo se
llama hoy.

### 5.1 `Usuario` (User)

```
correo · nombre · hash · activo · version_de_token · rotacion_de_refresh
created_at · ultimo_login

revocar_sesiones()          sube version_de_token → invalida todo lo emitido
rotar_refresh()             sube rotacion_de_refresh → el refresh sirve una vez
cambiar_password(nueva)     rehash + revocar_sesiones()
```

Sin cambios de modelo. Solo recupera el comportamiento que hoy está en
`auth/service.py`.

### 5.2 `Equipo` (Team) y `Pertenencia` (TeamMember)

```
Equipo:       nombre · dueño_id · activo
              transferir_propiedad(nuevo_jefe)   exige que sea entrenador y miembro
              es_jefe(usuario) -> bool

Pertenencia:  usuario · equipo · rol · activa · desde
              rol_de_dominio(es_dueño) -> Rol    ← la fábrica de la §4.2
              revocar() / restaurar()
```

**`revocada ≠ sin equipo`** se conserva como está: son dos estados distintos y
confundirlos deja entrar a quien acabas de echar. Sigue exigiendo
`incluir_inactivas=True` explícito para separarlos.

### 5.3 `Atleta` (Swimmer)

```
equipo · nombre · usuario_id? · nacimiento · genero
especialidad · estilo_principal · peso · altura · notas · activo

edad_en(fecha) -> int?           ← hoy duplicada: age_at() y _age(), dos firmas
tiene_cuenta() -> bool
perfil_para(prueba) -> Perfil
dar_de_baja() / restaurar()
```

Ficha y cuenta siguen siendo la misma persona vista desde dos sitios, unidas solo
por un `CodigoDeVinculacion` canjeado.

> **Enmienda del 2026-08-16 (paso 2), aplica a todas las entidades.** Los
> mutadores —`dar_de_baja()`, `restaurar()`, `inscribir()`— **no se construyeron
> todavía**: hasta que exista el repositorio del paso 5 no hay nada que persista
> lo que cambian, y un `atleta.dar_de_baja()` que no escribe es peor que no
> tenerlo, porque parece que funciona. Entran con su repositorio. El paso 2
> construyó solo el comportamiento de consulta.
>
> **Al 2026-10-05** (cabecera, puntos 1-2): el repositorio ya existe desde el
> paso 5, así que la razón de esperar se fue; no entraron en C5, C6, C7 ni C8
> porque ninguno los necesitaba. **`Atleta` ✅ hecho ese día**: `dar_de_baja()` y
> `restaurar()` son idempotentes y devuelven si cambiaron (se audita solo el
> cambio), `Atleta.nueva(...)` construye la ficha desde los textos del API con
> los alias canonizados, y `RepositorioDeAtletas.guardar(atleta)` es la única
> escritura —no toca `usuario_id`, que es del canje—. **⬜ `inscribir()` sigue
> pendiente** con `Inscripcion` (punto 2). **✅ Hecho ese mismo día**:
> `Macrociclo.inscribir(atleta, base, fuente)` comprueba que la ficha es de su
> club y está activa (`InscripcionImposible`, el 409); «un atleta, un macrociclo
> vivo» se quedó en `api/v1/macrociclos/inscripcion.py`, decisión del usuario.

### 5.4 `Macrociclo` (Plan)

```
equipo · nombre · inicio · semanas · semanas_por_micro · km_totales
curva · piscina · n_mac · prueba_principal · estado · notas

semana_actual() -> int?          ← hoy plans/service.py:42
estado_efectivo() -> EstadoDeMacro   ← hoy plans/service.py:51
fase_de(semana) -> Fase
inscribir(atleta, base_aerobica) -> Inscripcion
duracion_en_semanas()
```

Raíz del agregado de planificación. Absorbe las funciones sueltas de
`plans/service.py`, que son puras y no tocan la base de datos.

> **Enmienda del 2026-08-16 (paso 2): `fase_de(semana) -> FaseDelMacro`, no
> `Fase`.** La base guarda cuatro tramos (`base|build|peak|taper`) y `Fase` tiene
> cinco claves científicas; ese reparto lo decide el paso 4 y `escalas.Fase`
> se niega expresamente a adivinarlo (§5.5). Devolver la `Fase` aquí habría
> exigido inventar la traducción — la sexta versión de la regla que este tipo
> existe para cerrar. `FaseDelMacro.fase` viaja en `None` hasta el paso 4; el
> desdoble nombre (UI) / clave de dominio ya está construido y esperándola.
>
> **Resuelto el 2026-09-22 (P3):** `FaseDelMacro.fase` es obligatoria y viene de
> la base; `fase_de()` sigue devolviendo el tramo porque quien pregunta casi
> siempre quiere las dos mitades — el nombre para enseñarlo y la `Fase` para
> calcular.

### 5.5 `FaseDelMacro` (PlanPhase) y `Competencia` (Competition)

```
FaseDelMacro:  nombre (texto libre, UI) · fase: Fase (clave de dominio) ·
               semana_inicio · semana_fin · color · orden

Competencia:   nombre · semana · dias · es_principal
```

El desdoble `nombre` / `fase` es lo que cierra P3: el entrenador puede llamarle
"Construcción" a lo que el motor conoce como `base_especifica`.

### 5.6 `Inscripcion` (AthletePlan) — ✅ construida 2026-10-05 (cabecera, punto 2)

```
atleta · macrociclo · base_aerobica: Ritmo? · fuente_de_base · activa

dar_de_baja() / restaurar()      baja lógica; el histórico no se toca
```

### 5.7 `PruebaObjetivo` (AthleteEvent) — ⬜ sin construir (cabecera, punto 3)

```
prueba: Prueba · actual: Tiempo · meta: Tiempo · prioridad

mejora_pedida() -> Mejora
factibilidad(nivel, semanas, n_mac, edad) -> Veredicto
```

`distance` + `stroke` sueltos pasan a ser un `Prueba`. Aquí es donde la
validación deja de depender de que alguien llame a `is_valid_event`.

### 5.8 `Semana` (WeeklyPlan) — ⬜ sin construir (cabecera, punto 4)

```
numero · fecha · km_planificados
esperado: Tiempo          curva ideal original — NUNCA se modifica
recalculado: Tiempo?      curva recalculada tras un tiempo real
fase: Fase                ← clave de dominio, no etiqueta
deshabilitada + razon
                          ← NINGUNA columna de tiempo real. Ver abajo.

zonas() -> JuegoDeZonas   derivado, no persistido
resultados() -> [Resultado]   los que caen en esta semana (derivado)
real() -> Tiempo?         promedio de resultados(); None si no hay ninguno
desviacion() -> Mejora?
```

**Cambio de fondo:** `real_time` sale de aquí. Ver §5.10.

**La semana no tiene FK al resultado** (decisión R2 enmendada, §10.2). El
entrenador quiere que **varios tiempos de la misma semana se promedien**, y una
FK única no admite varios. `Resultado` ya lleva `(atleta, prueba, fecha)`, así
que la semana deriva su conjunto por rango de fechas. Uno, varios y ninguno son
el mismo caso.

**Solo reancla la curva lo que `real()` devuelve.** Un resultado del histórico
del atleta que no cae en ninguna semana del plan —una competencia en fecha
suelta, una prueba que no es objetivo de este macro— entra en su histórico y
**no toca la predicción**.

**Un tiempo en otra piscina sí entra, convertido** (2026-09-22, al construir
C6): a la piscina del macro, con el factor corta/larga de `Piscina.factor`
—el mismo que usan las zonas—. La fila guarda lo que marcó el reloj; se
convierte al leer (`Resultado.tiempo_en`).

### 5.9 `TestAerobico` (AerobicTest) y `Parcial` (AerobicSplit)

```
TestAerobico:  atleta · macrociclo? · tipo · fecha · repeticiones · distancia_rep
               salida: Tiempo? · modo_de_ingreso · notas · activo

               base_aerobica() -> Ritmo        ← engine/aerobic.py analyze_splits
               tendencia() -> Tendencia
               consistencia() -> float
               densidad() -> float             trabajo / (trabajo + descanso)

Parcial:       numero · tiempo_nadado: Tiempo · inicio: Tiempo?
               llegada() -> Tiempo?            inicio + nadado
               descanso_hasta(siguiente) -> Tiempo?
```

**El valor real está en el constructor.** Hoy *"en la base de datos siempre se
guarda el tiempo nadado"* es una regla que hay que acordarse de aplicar en
`create_test`. Si la conversión `clock → rep` ocurre al construir el objeto,
**deja de poder violarse**. Ese es el fallo que infló la base aeróbica un 114 %:
pasa de regla documentada a invariante del tipo.

### 5.10 `Resultado` — nuevo

```
atleta · prueba: Prueba · tiempo: Tiempo · fecha · piscina
contexto: competencia | control | serie
competencia_id?                   si se nadó en una competencia del macro
```

**Este es el cambio estructural del modelo de datos.** Hoy los tiempos reales
viven en `Semana.real_time`, colgando de
`Macrociclo → Inscripcion → PruebaObjetivo → Semana`. Consecuencia ya observada:
`remove_athlete` **tuvo que** convertirse en baja lógica porque borrar la
inscripción cascadeaba y se llevaba los tiempos reales del atleta — está
documentado en su propio docstring (`plans/roster.py:57`; el archivo se partió en
cinco después de que se escribiera esta nota). El bug se parcheó; la causa —un
hecho del atleta modelado como propiedad de un plan— sigue ahí.

**Y hay un segundo agujero por la misma causa, este sin parchear:**
`delete_plan` (`plans/service.py:139`) solo bloquea el borrado si el macrociclo
tiene tests aeróbicos asociados. Un macro sin tests se borra limpio, y la cascada
`Plan → AthletePlan → AthleteEvent → WeeklyPlan` se lleva **todos los tiempos
registrados de todos sus atletas**. Lo único que hoy protege el activo más
valioso de la aplicación es que haya un test de por medio.

Con `Resultado` colgando del atleta:
- sacar a alguien de un macrociclo no puede tocar su histórico (la baja lógica
  pasa a ser una elección, no un parche);
- borrar un macrociclo tampoco;
- el mismo tiempo se puede comparar contra dos macrociclos;
- el histórico de un atleta se lee sin recorrer planes;
- el tiempo lleva **su propia piscina**. Hoy `real_time` es un `float` sin unidad
  de piscina y la piscina es del *plan*, así que un tiempo nadado en corta dentro
  de un macro de larga se compara contra una curva de larga sin que nada avise.

`AerobicTest` ya está modelado así (cuelga del atleta, con macrociclo opcional).
Es el patrón correcto que el resto del esquema no siguió.

> **R2 — CERRADA el 2026-08-16: reemplaza.** `real_time` se conserva durante una
> versión de transición, y se retira cuando ningún lector la use directamente
> (`dashboard/service.py`, `plans/weeks.py`, `plans/roster.py`) y el conteo
> `resultados == real_time no nulos` cuadre en dos despliegues seguidos.
> **Enmendada el mismo día:** la semana no lleva FK. Ver §5.8 y §10.2.
>
> **Construido el 2026-09-22 (C6).** `real_time` queda como sombra que se
> escribe y nadie lee, y el criterio de los «dos despliegues» se cambió por uno
> que una aplicación local puede cumplir: **se retira al empezar C7**. Detalle
> en el bloque C6 de `docs/PLAN-DE-TRABAJO.md`.

### 5.11 `Sesion` y `Serie` — nuevo (R1: `Sesion` tras 1-6; `Serie` fuera)

```
Sesion:  atleta · fecha · macrociclo? · semana? · km_totales · notas · rpe?
         carga() -> float                 sTSS de la sesión
         zonas_nadadas() -> Mapping[Zona, float]   km por zona

Serie:   sesion · orden · repeticiones · distancia
         prescripcion: Prescripcion       FOTOGRAFÍA de lo mandado
         tiempos: list[Tiempo]            lo efectivamente nadado
         cumplimiento() -> float
```

Hoy la unidad mínima de planificación es la **semana**. No existe la sesión ni la
serie. `engine/send_off.py` calcula prescripciones completas
(`10 × 100 a 1:18 salida 1:30`) que no se guardan en ninguna parte: se computan
para pintar una tabla y se tiran. Y de lo ejecutado solo existe un tiempo por
semana.

De este hueco cuelga todo lo que hoy no se puede construir. Sin `Sesion` no hay
de dónde sacar el sTSS diario, y sin sTSS no hay Banister.

> **`Sesion` construida el 2026-09-23 (C7)**, con tres enmiendas a lo de arriba:
>
> ```
> Sesion:  atleta · fecha · distancia_m · duracion: Tiempo · rpe? (CR-10) · notas
>          ritmo_medio() -> Ritmo         duración total / distancia; derivado
>          carga(css: Ritmo) -> float     sTSS; derivado; `css` el vigente ESE día
> ```
>
> 1. **Sin `macrociclo?` ni `semana?`.** `weekly_plans` va por prueba objetivo:
>    con dos pruebas hay dos filas para la misma semana y `semana_id` no tiene a
>    cuál apuntar. Misma razón que la enmienda de R2: se encuentran por fecha.
> 2. **Sin `zonas_nadadas()`.** Sin series no se sabe qué se nadó en cada zona, y
>    el reparto *planificado* presentado como nadado es el dato que miente.
> 3. **Cómo se rellena: después de nadar** (opción A). La apunta el atleta o su
>    entrenador; planificarla antes es el módulo de la nota 22 y depende de N5.
>
> Se **borra de verdad** (es un registro que su dueño corrige), y el RPE se
> guarda sin decidir aún qué carga sale de él: eso es de C8.

### 5.12 `CargaDiaria` — nuevo (R1: tras 1-6)

```
atleta · fecha · stss · ctl · atl · tsb

               derivada de Sesion; se recalcula, no se edita
               alerta_de_sobreentrenamiento() -> bool
```

La nota 05 del vault, por fin construible.

> **Construida el 2026-09-23 (C8)** como tabla `carga_diaria`, con dos enmiendas:
> **sin columna `tsb`** (es CTL − ATL; una tercera columna podría discrepar), y
> **sin `alerta_de_sobreentrenamiento()` en la fila**: las alertas miran rachas y
> rampas de varios días, así que son de la serie (`banister.alertas`), no de un
> día. Es un **derivado materializado**: lo escribe solo
> `persistencia/repositorios/carga.recalcular`, en la misma transacción que la
> sesión o el test que lo cambia, y un test comprueba que coincide con el cálculo
> desde cero tras cualquier secuencia de escrituras. Se guarda por escala —muchas
> lecturas, una escritura al día por atleta—, no porque sea un hecho.

### 5.13 Relaciones auxiliares

```
CodigoDeVinculacion (LinkCode)     ficha ↔ cuenta; caduca, se gasta, dos lados
EntrenadorDeAtleta  (CoachAthlete) M:N, quién lleva a quién
EntrenadorDelMacro  (PlanCoach)    M:N, decide VISIBILIDAD del macrociclo
```

Sin cambios de modelo. `CodigoDeVinculacion` gana el ciclo de vida como
comportamiento (`es_servible()`, `canjear(usuario)`, `revocar()`) en vez de
tres columnas que hay que comprobar a mano.

---

## 6. Servicios de dominio

### 6.1 `MotorCientifico` — uno solo

Absorbe y **elimina**: `domain/engine.py::ScienceEngine`,
`engine/progression.py`, `engine/envelope.py`, `engine/feasibility.py`,
`engine/km_distribution.py`, `engine/zones.py`, `engine/send_off.py`.

```
MotorCientifico
  generar_plan(prueba, actual, meta, semanas, km, curva, piscina, n_mac, edad)
      -> PlanGenerado
  recalcular_desde(plan, semana_ancla, tiempo_real) -> PlanGenerado
  factibilidad(prueba, actual, meta, nivel, semanas, n_mac, edad) -> Factibilidad
  envolvente(prueba, actual, semanas, n_mac, edad) -> Envolvente
  proyectar_temporada(prueba, actual, n_macros, edad) -> ProyeccionAnual
  zonas(ritmo_carrera, prueba, piscina, distancia_rep) -> JuegoDeZonas
```

**Qué se conserva de cada motor.** Los dos actuales aciertan en cosas distintas,
y la fusión no es "quedarse con uno":

| De `ScienceEngine` | De `engine/progression.py` |
|---|---|
| distribución F_FASE por fase científica | `clamp_weekly_rate()`: acota el ritmo semanal y **difiere** el excedente (modelo causal) |
| ajuste automático de nº de semanas a la meta | curva elegible por el entrenador |
| extensión con ritmo seguro | `distribute_km()` normalizado al `km_totales` que fijó el entrenador |
| `proyectar_temporada()` | fases definidas por el usuario, no fijas a 15 semanas |

El motor fusionado necesita las dos mitades. `ScienceEngine` asume macro fijo de
15 semanas; `progression` respeta las semanas y los km que puso el entrenador.
La fusión es: **la ciencia de `ScienceEngine`, la parametrización de
`progression`.**

> **R6 — CERRADA el 2026-08-16: el kilometraje lo manda el entrenador.**
> Fases y forma de la ciencia; **total normalizado al que puso el entrenador**;
> las bandas de `WEEKLY_VOLUME_KM` como **aviso**, nunca como valor por defecto
> ni como límite, y visible **solo en la tabla del plan**. Medido con un caso
> real, `ScienceEngine` prescribe 777,7 km donde el entrenador puso 450 —
> `generate_plan` ni siquiera recibe `total_km`. Los números y los tres
> defectos que destaparon (el acantilado de `classify_level`, el taper
> invertido y la onda 3:1 desfasada) están en §10.4, y los tres entran en el
> alcance del paso 4.

`tablas.py` guarda todas las constantes con su § de referencia:
`ZONE_OVER_RACE`, `I_MAX_TABLE`, `F_FASE`, `WEEKLY_VOLUME_KM`,
`MAX_VOLUME_BY_STROKE`, `POOL_FACTOR_25`, `STROKE_TPACE_CORRECTION_S`,
`MESO_LOAD_PATTERN`, `ANNUAL_IMPROVEMENT_RANGE`, `MACROCYCLE_DEGRADATION`,
`RATIO_DESCANSO`. Un solo sitio, y `MAX_SEMANAS_EXTENSION` deja de tener dos
valores.

### 6.2 `Curva` — patrón Strategy

```
Curva (abstracta)
  progreso(x: float) -> float       f(0)=0, f(1)=1
  etiqueta: str
  ├── Cientifica       F_FASE, back-loaded, pico en taper   ← por defecto
  ├── Sigmoide · Lineal · Exponencial · Logaritmica          solo comparar
```

Hoy `curve_progress(x, curve)` es una cadena de `if` por string, con `CURVES`,
`CURVE_LABELS` y los parámetros de forma (`EXP_K`, `LOG_SCALE`,
`SIGMOID_STEEPNESS`) en constantes paralelas: añadir una curva son cuatro
ediciones en tres archivos. Con Strategy es un archivo.

> **R7 — CERRADA el 2026-08-16: elegible en el simulador, fija en el plan.**
> Y `progression_curve` **deja de ser columna de `plans`**; el parámetro se
> queda en la firma del motor, que es de donde lo usa el simulador. La razón
> no es que las otras curvas "solo comparen escenarios": **cambian el veredicto
> que ve el atleta**. Mismo tiempo nadado, la semana 8 sale `AHEAD` con la
> científica y `BEHIND` con la exponencial (§10.4). Dejar la columna y esconder
> el desplegable sería teatro, que CLAUDE.md ya prohíbe.

### 6.3 `CargaAcumulada` — Banister (R1: tras 1-6)

```
CargaAcumulada
  calcular(sesiones, desde, hasta) -> list[CargaDiaria]
  CTL = media exponencial 42 d · ATL = 7 d · TSB = CTL − ATL
```

> **Construida el 2026-09-23 (C8)** en `dominio/servicios/banister.py`. Lo que
> decidió el usuario, con los números delante:
>
> - **La carga es el sTSS** (`Sesion.carga(css)`, nota 05). El CSS es el del
>   último test ≤ la fecha de la sesión; un T15 o un test libre solo a falta de
>   otro (`TipoDeTest.mide_el_umbral`). Sin test previo, la sesión no entra y se
>   cuenta aparte. Un día sin sesión es carga 0.
> - **Arranque en equilibrio**: CTL₀ = ATL₀ = carga media de los primeros 14
>   días. Con CTL₀ = 0, medido con el seed, un atleta que cumple su plan daba
>   «fatiga sostenida» cada semana hasta el taper (la CTL tarda ~3τ en olvidar el
>   cero). Es un supuesto —ya entrenaba a una carga parecida—, escrito como tal.
> - **Alertas** (convención de la práctica, no ciencia revisada; umbrales de la
>   nota 05 unificados): TSB < −25 advertencia, < −40 peligro, TSB < 0 más de 14
>   días seguidos, y **rampa**: CTL +7 o más en una semana. Ninguna en los 14
>   días del arranque.

---

## 7. Modelo de datos

### 7.1 Esquema objetivo

```
usuarios ──< pertenencias >── equipos
   │                              │
   └──(1:1 opc)── atletas ────────┘
                    │
                    ├──< tests_aerobicos ──< parciales
                    ├──< resultados                    ← NUEVO
                    ├──< sesiones (R1: tras 1-6) ──< series (R1: fuera)
                    ├──< carga_diaria                  ← NUEVO (R1: tras 1-6)
                    ├──< entrenadores_de_atleta >── pertenencias
                    └──< inscripciones

macrociclos ──< fases_del_macro
            ──< competencias ──< resultados            (agrupa, no posee)
            ──< entrenadores_del_macro >── pertenencias
            ──< inscripciones ──< pruebas_objetivo ──< semanas
        (la semana NO tiene FK: deriva sus resultados por fecha — R2, §10.2)

codigos_de_vinculacion ── atletas · pertenencias · usuarios
```

### 7.2 Cambios respecto a la beta

| # | Cambio | Motivo |
|---|---|---|
| 1 | `semanas.real_time` **se retira**; la semana no gana ninguna columna — deriva sus resultados por `(atleta, prueba, rango de fechas)` y **promedia** | §5.10 y §10.2 — el tiempo es del atleta, y el entrenador quiere varios por semana |
| 2 | `resultados` (tabla nueva) | idem |
| 3 | `sesiones` (tras 1-6); `series` **fuera del rediseño** — R1 | la unidad mínima deja de ser la semana |
| 4 | `carga_diaria` (nueva, tras 1-6) — R1 | CTL/ATL/TSB |
| 5 | `semanas.fase` y `fases_del_macro.tipo` guardan la **clave** de `Fase`, no la etiqueta | cierra P3 |
| 6 | `CheckConstraint` en zona, nivel, perfil, estilo, especialidad, tipo_de_test, piscina, estado, modo_de_ingreso, rol | hoy solo `rol` lo tiene; el resto acepta cualquier string |
| 7 | ~~`usuarios.es_staff`~~ — **R3: no se añade nada.** Solo el hueco en la jerarquía de `Rol` | admin no cabe en `pertenencias`, pero tampoco se construye |
| 8 | Un solo registro de modelos | hoy hay que acordarse en `model_registry.py`, `alembic/env.py` y `seed.py`; olvidarlo revienta al primer INSERT |
| 9 | Nombres de tabla en español, coherentes con el dominio | hoy mezcla `swimmers`/`plans` con conceptos en español |

### 7.3 Lo que NO cambia

Es lo mejor que tiene la beta y se conserva entero:

- **FKs compuestas contra `(id, equipo_id)`** en toda tabla de relación: la base
  de datos hace imposible mezclar equipos aunque el código tenga un bug.
- **`PRAGMA foreign_keys=ON`** en cada conexión SQLite.
- **Nada se borra: se da de baja** (`activo` en atletas, pertenencias, usuarios,
  tests, inscripciones).
- **`ondelete=CASCADE` solo donde hay composición real** (macro → fases,
  test → parciales).
- **Alembic como única fuente del esquema**; `init_db()` no hace `create_all()`.
- **Portabilidad SQLite → PostgreSQL**: sin `JSONB`, sin `citext`, sin enums
  nativos, correos normalizados en el servicio, `DateTime(timezone=True)` siempre.
- **`equipo_id` sale siempre de la sesión**, nunca del cuerpo de la petición.
- **Recurso ajeno → 404, nunca 403.**

### 7.4 Migración de datos

Todo el esquema actual es migrable sin pérdida. El único paso con trabajo real:

```
semanas.real_time  ──►  resultados(atleta, prueba, tiempo, fecha, piscina,
                                   contexto='control')

(NO hay UPDATE de vuelta: la semana no guarda referencia. El vínculo se deriva
 de la fecha, que es lo que permite varios resultados por semana — R2, §10.2.)
```

La prueba y el atleta se derivan de `pruebas_objetivo` e `inscripciones`; la
fecha, de `semanas.fecha`. Es un `INSERT ... SELECT` **sin** `UPDATE` de vuelta
(la frase decía «con», de antes de la enmienda de R2).
El resto son renombres de columna y `CheckConstraint` añadidos.

---

## 8. Mapa de traducción

| Hoy | Rediseño | Qué cambia |
|---|---|---|
| `User` | `Usuario` | + comportamiento de sesión |
| `Team` / `TeamMember` | `Equipo` / `Pertenencia` | + `Rol` polimórfico |
| — | `Rol` y sus 4 subclases | **nuevo** (el polimorfismo que hoy son `if` en `Principal`) |
| `Swimmer` | `Atleta` | + `edad_en()` (hoy duplicada en dos sitios) |
| `Plan` | `Macrociclo` | + `semana_actual()`, `estado_efectivo()`, `fase_de()` |
| `PlanPhase` | `FaseDelMacro` | desdobla nombre (UI) y `Fase` (dominio) |
| `Competition` | `Competencia` | — |
| `AthletePlan` | `Inscripcion` | — |
| `AthleteEvent` | `PruebaObjetivo` | `(distance, stroke)` → `Prueba` |
| `WeeklyPlan` | `Semana` | `real_time` sale; `resultados()` y `real()` se derivan |
| `AerobicTest` / `AerobicSplit` | `TestAerobico` / `Parcial` | análisis dentro del objeto; conversión clock→rep como invariante |
| `LinkCode` | `CodigoDeVinculacion` | + ciclo de vida como métodos |
| `CoachAthlete` / `PlanCoach` | `EntrenadorDeAtleta` / `EntrenadorDelMacro` | — |
| `Principal` | `Principal` | compone `Rol` en vez de tener `is_coach`/`is_athlete` |
| `ScienceEngine` + `engine/progression` + `envelope` + `feasibility` + `km_distribution` | `MotorCientifico` | **7 archivos → 1 servicio** |
| `curve_progress()` + `CURVES` + `CURVE_LABELS` | `Curva` (Strategy) | 3 constantes paralelas → 5 clases |
| `engine/zones.py` + `send_off.py` | `Zona` · `Prescripcion` · `JuegoDeZonas` | dicts de strings → tipos |
| `engine/time_utils.py` | `Tiempo` · `Ritmo` | funciones sueltas → tipos con unidad |
| ~~`engine/events.py`~~ — **HECHO 2026-08-16**, módulo borrado | `Prueba` | **función suelta → invariante del objeto** |
| `engine/aerobic.py` | `TestAerobico` (métodos) | — |
| `modules/dashboard` | `api/v1/vistas/` | deja de ser módulo de dominio; es una vista |
| `modules/simulator` | `api/v1/simulador/` | llama al motor, no persiste |
| — | `Resultado` | **nuevo** |
| — | `Sesion` / `CargaDiaria` | **nuevo**, tras los pasos 1-6 (R1). `Serie` queda fuera |
| — | `persistencia/repositorios/` | **nuevo** (cierra P5) |

---

## 9. Orden de construcción

| # | Paso | Riesgo | Cierra | Se puede parar aquí |
|---|---|---|---|---|
| 1 | `dominio/valores/` completo — **✅ HECHO 2026-08-16** | bajo | P6, P2 | sí |
| 2 | Entidades ricas (`Atleta`, `Macrociclo`, `TestAerobico`) — **✅ HECHO 2026-08-16** | bajo | P4 | sí |
| 3 | `Rol` + subclases; `Principal` compone — **✅ HECHO 2026-08-17** | bajo | — | sí |
| 4 | **Fusión de los dos motores** — **✅ HECHO 2026-08-17** (rama `refactor/motor-unico`) | **medio-alto** | P1 (P3 no: se cerró aparte el 2026-09-22) | rama propia |
| 5 | `persistencia/repositorios/` + recorte de imports cruzados — **✅ HECHO 2026-08-25** | medio | P5 | sí |
| 6 | `Resultado` + migración de `real_time` — **✅ HECHO 2026-09-22** | medio | §5.10 | sí |
| 7 | `Sesion` (R1: **`Serie` fuera**) — **✅ HECHO 2026-09-23** (pantallas 2026-10-01) | medio | el hueco de fondo | sí |
| 8 | `CargaDiaria` + Banister (R1) — **✅ HECHO 2026-09-23** (pantallas y tabla del equipo 2026-10-01) | bajo | nota 05 | — |

> **2026-10-05:** los ocho pasos son código. Lo que este orden no recogía —los
> mutadores y las tres entidades de escritura del §5— está en la tabla de la
> cabecera, puntos 1-4.

El paso 4 es el único con riesgo real. Se hace en rama propia y con los 478 tests
delante (2026-08-13): `test_domain_engine.py` y `test_engine.py` ya fijan el
comportamiento esperado de los dos motores por separado, así que la fusión tiene
contrato explícito de entrada. `test_reglas_unicas.py` añade la comprobación de
que una regla cerrada no vuelve a duplicarse — al fusionar hay que **mover** sus
asserts al motor único, no borrarlos.

Ojo con el paso 4: la auditoría de A1 midió que **el nivel, el techo I_max y la
factibilidad ya divergen** entre los dos motores, y las tres por la misma causa
(`envelope.py` reimplementó la aritmética del dominio en vez de llamarla, y
difieren en qué distancia y cuántas semanas entran). No es una fusión de dos
implementaciones que coinciden: hay que decidir cuál gana en cada una. Ver la
tabla del bloque A1 en `docs/PLAN-DE-TRABAJO.md` para los números concretos.

Los pasos 1–3 no rompen nada: son adición. Se puede parar después de cualquiera.

---

## 10. Decisiones — CERRADAS el 2026-08-16

Las ocho se cerraron en una sesión de decisión, en orden de impacto (R2, R6, R1,
R5 y luego el resto), con el código delante y —en R6 y R7— corriendo los motores
sobre casos reales. **El modelo queda cerrado.** Lo que sigue abierto es la lista
del §10.3, que son preguntas nuevas que salieron de estas respuestas, no restos
de las viejas.

> **R9 se cerró el mismo día y no está aquí a propósito.** Es el color de la
> sección fusionada de B1 — una decisión de frontend, y este documento es el
> modelo del backend. Vive en el bloque B1 de `docs/PLAN-DE-TRABAJO.md`, con su
> razón. Se cerró como **rosa `#f472b6`** —la sección superviviente conserva su
> color— y **ya está aplicada** en `frontend/src/lib/constants.ts`.

### 10.1 Las ocho

| # | Decisión | Cerrada como | Razón |
|---|---|---|---|
| **R1** | ¿`Sesion`/`Serie`/`CargaDiaria` entran o quedan para v2? | **Partida en tres.** El modelo las contempla. `Sesion`+`CargaDiaria` se construyen **después** de que los pasos 1–6 estén verdes y desplegados. `Serie` **sale** del rediseño | Los pasos 1–6 mueven comportamiento de sitio; el 7 y el 8 construyen algo nuevo. Mezclarlos hace que, si el paso 4 sale mal, no se sepa si fue el refactor o la funcionalidad. Y **Banister depende de `Sesion`, no de `Serie`**: para el sTSS diario basta fecha + carga. `Serie` es la única pieza que obliga al entrenador a cambiar su rutina, y eso todavía no está decidido. Alcance futuro completo en la nota 22 del vault |
| **R2** | ¿`Resultado` reemplaza a `Semana.real_time` o conviven? | **Reemplaza**, con `real_time` viva durante **una** versión de transición y criterio de retirada escrito. **Enmendada el mismo día: la semana NO lleva FK** (ver §10.2) | Hoy `DELETE /plans/{id}` cascadea hasta `weekly_plans` y lo único que lo frena es que haya un test aeróbico asociado (`plans/service.py:139`). Un macro sin tests se borra con el histórico dentro. Es el tercer parche sobre la misma causa: un hecho de una persona modelado como propiedad de un plan. `AerobicTest` ya cuelga del atleta y no ha necesitado ninguno |
| **R3** | ¿`Administrador` se construye o se deja el hueco? | **Solo el hueco, y más estrecho de lo propuesto**: que la jerarquía de `Rol` no cierre la puerta (que `alcance_de_atletas()` pueda devolver `todos`). **Cero campos en `Principal`, cero columnas en `usuarios`** | Un hueco en una jerarquía de clases es gratis y reversible. Un campo en el objeto del que cuelga todo el aislamiento no lo es: existe, se serializa, y alguien acaba resolviéndolo desde la base sin la spec que la revisión de CEO del 2026-08-06 pidió |
| **R4** | ¿El asistente necesita menos permisos dentro de un macro que sí lleva? | **No hay rol nuevo.** Pero **dos operaciones pasan de `require_coach` a `require_owner`**: borrar el macrociclo y cambiar la meta de una prueba objetivo | El argumento del documento (`entrenadores_del_macro` ya distingue) vale para **ver**, no para **escribir**: hoy el asistente puede borrar el macro que lleva. Un rol nuevo mete una tercera pregunta en cada escritura, que es como se abrió el agujero del scoping del atleta. Mover dos guards reconoce que esas acciones ya eran de dueño y estaban mal guardadas |
| **R5** | ¿Una persona en más de un equipo? | **No** — más dos arreglos que entran en el rediseño (§10.2) | `Principal` vale porque `team_id` **no es una elección**. Con dos clubes pasa a ser estado de sesión: algo que se elige, se guarda, caduca y se desincroniza. Eso convierte la frontera de aislamiento de invariante en convención, justo lo que este rediseño está deshaciendo en todas partes. No se paga por un caso que todavía no existe |
| **R6** | Al fusionar, ¿quién manda el kilometraje? | **Fases y forma de la ciencia, total del entrenador.** Las bandas de `WEEKLY_VOLUME_KM` quedan como **aviso**, nunca como valor por defecto ni como límite — y el aviso se enseña **solo en la tabla del plan**, no en el formulario de creación | Medido (§10.4). `ScienceEngine` no es más científico en volumen: es **peor**. Sube la carga la semana de la competencia y hace depender 15 km/semana de una décima de segundo. La normalización de `progression` no es una concesión al entrenador, es lo único que hoy protege el plan de esa inestabilidad. Lo valioso de `ScienceEngine` son **las cinco fases**, que son las que `F_FASE` sabe indexar y las que cierran P3 |
| **R7** | ¿Curva elegible o fija en `Cientifica`? | **Elegible en el simulador; en el plan real, fija.** Y `progression_curve` **deja de ser columna de `plans`** — el parámetro se queda en la firma del motor | No es que las otras "solo comparen escenarios": **cambian el veredicto que ve el atleta** (§10.4). Dejar la columna y esconder el desplegable sería teatro, que CLAUDE.md ya prohíbe explícitamente. **Construida el 2026-09-23**: `Macrociclo.curva` es una propiedad fija y la columna se borró (migración `82135c6cb2d8`) |
| **R8** | ¿PostgreSQL desde el rediseño? | **SQLite.** Se cambia cuando haya una razón de **despliegue**, no de rediseño, y **después** del paso 6 | Los pasos 4 y 6 van a producir números y filas distintas. Cambiar de motor a la vez le da dos sospechosos a cada diferencia, y la red de 153 casos solo sirve con una variable en juego. La migración de `real_time` es la única cirugía sobre datos reales: hacerla una vez y luego mover la base entera duele menos que hacerla dos veces sobre dos motores |

### 10.2 Lo que estas decisiones cambian en el resto del documento

Cinco correcciones al modelo que salieron de cerrarlas. Están aplicadas en el
cuerpo; se listan aquí para que se vean juntas.

1. **La semana no lleva FK al resultado** (enmienda a R2, misma fecha). El
   entrenador quiere que **varios tiempos de la misma semana se promedien**, y
   una FK única no admite varios. `Resultado` ya lleva `(atleta, prueba, fecha)`,
   así que la semana **deriva** su conjunto por rango de fechas y promedia. Uno,
   varios y ninguno pasan a ser el mismo caso en vez de tres ramas. Afecta a
   §5.8, §7.1, §7.2, §7.4 y §8.
2. **Solo reancla la curva el resultado que cae dentro de una semana del plan.**
   Sin esta regla, sacar el tiempo del plan haría que cualquier dato del
   histórico del atleta perturbara la predicción — peor que el problema que R2
   arregla. Con promedio semanal, reancla el promedio.
3. **`redeem` tiene que mirar `is_active` antes que `team_id`** (de R5). Hoy
   `link_codes/service.py:258` responde *"Tu cuenta ya pertenece a otro equipo"*
   a alguien cuya pertenencia está **revocada**, así que un atleta que deja un
   club no puede entrar en otro sin tocar la base de datos. Invertir esos dos
   `elif` es el arreglo entero.
4. **`_principal_for` debe fallar con más de una pertenencia activa** (de R5).
   Hoy hace `.first()` sin `ORDER BY` (`core/dependencies.py:78`). La `UNIQUE` lo
   hace inofensivo *ahora*; el día que se quite —"un cambio de una línea"— esa
   consulta atiende al club equivocado **sin fallar**. `one_or_none()` cuesta lo
   mismo y convierte una fuga silenciosa en un error inmediato. `plans/access.py:73`
   ya tuvo que codificarse a la defensiva anticipando ese cambio.
   **Aplicado el 2026-09-24.** El 3 (`redeem`) sigue sin aplicar: choca con
   «revocado ≠ sin equipo» (CLAUDE.md) y se decide aparte. **⬜ Pendiente al
   2026-10-05** (cabecera, punto 5).
5. **El ejemplo de §4.1 se cambió** por el del atleta que asciende a entrenador.
   El anterior argumentaba desde dos casos que el propio modelo prohíbe.

### 10.3 Preguntas nuevas, abiertas

Salieron de cerrar las ocho. Ninguna bloquea el rediseño; todas bloquean el
módulo de entrenamiento diario (nota 22 del vault).

| # | Pregunta | Por qué importa |
|---|---|---|
| **N1** | ¿El promedio semanal es de **todos** los tiempos de la prueba esa semana, o el entrenador marca cuál cuenta? | Un control mal nadado arrastra el promedio, y con él la curva reanclada de las semanas siguientes |
| **N2** | ¿Un tiempo de competencia entra en el promedio o manda sobre él? | `Resultado.contexto` ya distingue competencia · control · serie; falta decidir qué hace con esa distinción |
| **N3** | ¿`sesiones_por_semana` del equipo admite excepción por atleta o por macro? | Hoy `teams` no tiene dónde guardarlo siquiera |
| ~~**N4**~~ | ~~El PDF de las tablas: ¿backend (fiel, pesado) o cliente (barato, se desincroniza)?~~ | ✅ **Cerrada: cliente.** Construido el 2026-08-25 en Simulador y Tabla del equipo |
| **N5** | ¿La sesión que sube el entrenador es texto libre o series estructuradas? | Es la misma pregunta que dejó `Serie` fuera: el coste no es técnico, es de captura |

### 10.4 Los números que cerraron R6 y R7

Se corrieron los dos motores sobre casos reales. Las tablas completas están en la
nota 20 del vault; aquí, lo que decidió cada una.

**R6 — Emiliano, 200 libre 1:56.48 → 1:53.00, 15 semanas, 450 km:**

- `distribute_km` reparte **450.1 km**, el total que puso el entrenador.
- `ScienceEngine` prescribe **777.7 km** en esas mismas 15 semanas (2422.7 con su
  extensión de 30). **`generate_plan` ni siquiera recibe `total_km`**: no
  discrepa, nunca preguntó.
- Normalizadas al mismo total, las dos formas se parecen mucho más de lo que
  sugieren las columnas crudas. La diferencia real es dónde cae el pico (S11 vs S7).

> **Tres defectos que la comparación destapó, y que entran en el alcance del paso 4:**
>
> 1. **El nivel es un acantilado.** `classify_level` está calibrada para CSS (un
>    umbral de test de 400/1500) y se la alimenta con el ritmo de un 200. Medido:
>    `2:10.40 → elite → 50.1 km` en la semana 1; `2:10.50 → competitive → 34.6 km`.
>    Una décima de segundo cambia el volumen prescrito un **45 %**. Mientras siga
>    así, todo lo que depende del nivel —volumen, I_max, factibilidad— hereda el
>    salto. **El nivel debe salir del test aeróbico cuando exista** (un CSS medido)
>    y caer al ritmo derivado solo si no hay test.
> 2. **`ScienceEngine` sube el volumen la semana de la competencia**: S14 = 26.2 →
>    S15 = 29.2 km. `distribute_km` tiene una línea explícita para evitarlo
>    (última semana siempre descarga: 10.6 km). En taper, el motor "científico" es
>    el que se equivoca. **Se conserva la línea de `distribute_km`.**
> 3. **La onda 3:1 y las fases están desfasadas.** `MESO_LOAD_PATTERN[week % 4]`
>    usa la semana **absoluta**, así que la descarga cae en la *primera* semana de
>    cada bloque nuevo (S4 abre `base_especifica` descargando; S8, `umbral_css`).
>    **La onda debe contarse dentro del microciclo.**

**R7 — atleta de club, 200 libre 2:40 → 2:37, meta factible (sin recorte del techo):**

Las cinco curvas cierran **exactamente** en la meta — `clamp_weekly_rate` ya se
encarga. Pero el camino no es cosmético: en la semana 8 el rango entre curvas es
de **1.30 s**, contra una tolerancia de estado de ±0.4 %. Con el mismo tiempo
nadado (158.00):

```
S8, curva science      esperado 158.66   dif −0.416 %  →  AHEAD
S8, curva sigmoid      esperado 158.55   dif −0.347 %  →  ON_TRACK
S8, curva linear       esperado 158.40   dif −0.253 %  →  ON_TRACK
S8, curva logarithmic  esperado 157.71   dif +0.184 %  →  ON_TRACK
S8, curva exponential  esperado 157.36   dif +0.407 %  →  BEHIND
```

El mismo nado es *"va adelantado"* o *"va atrasado"* según una casilla que el
entrenador rellenó quince semanas antes. Por eso la curva sale de `plans`.

---

## 11. Qué queda igual de bueno

Para que la revisión no sugiera que hay que rehacerlo todo. Estas piezas son
correctas y el rediseño las conserva sin tocar:

- El aislamiento por equipo impuesto por **la base de datos**, no por el código.
- `Principal` como identidad efectiva resuelta una sola vez por petición.
- La separación **ficha ≠ cuenta** y el código de vinculación con sus tres
  propiedades (caduca, se gasta, tiene dos lados).
- **Revocada ≠ sin equipo**, y el pool global como estado legítimo.
- Nada se borra; se da de baja.
- El conmutador de desarrollo con sus dos ejes ortogonales (quién eres / si te
  saltas los guards) y la imposibilidad de persistir `es_desarrollador`.
- Las tablas científicas y su trazabilidad a la fuente (§ del documento de
  referencia).
- 478 tests. Son el contrato que hace este rediseño posible.
