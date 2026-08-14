# PeakStroke — Modelo del rediseño

> **Estado: BORRADOR PARA REVISIÓN.** Nada de esto está construido. La beta
> actual sigue intacta y funcionando. Este documento es el modelo objetivo para
> la versión limpia; se revisa, se anota y se conversa antes de escribir código.
>
> Fecha: 2026-08-12 · Línea base medida: 307 tests en verde, `tsc` limpio,
> `eslint` limpio.
>
> **Actualización 2026-08-13:** el bloque A1 del plan de trabajo (cerrar las dos
> divergencias concretas) sí se ejecutó — no toca el rediseño, borra reglas
> duplicadas y añade `tests/test_reglas_unicas.py`. Línea base ahora: **442 tests
> en verde**. El modelo de este documento sigue sin construirse.
>
> **Cómo revisarlo:** las decisiones abiertas están marcadas `❓R1`…`❓R8` al
> final. Responde esas ocho y el modelo queda cerrado. Todo lo demás lleva
> recomendación y razón: si no estás de acuerdo, anótalo donde esté.

---

## 0. Por qué se rediseña

La beta funciona y su modelo de datos es sólido. Lo que está al revés es dónde
vive el comportamiento. Seis hallazgos de la auditoría, en orden de gravedad:

| # | Hallazgo | Evidencia |
|---|---|---|
| P1 | **Hay dos motores.** El que declara ser la fuente de verdad no corre en producción | `ScienceEngine.generate_plan()` solo se llama en tests; los planes reales salen de `engine/progression.py` |
| P2 | **Ya divergieron.** Y son más de tres | ~~50 m combinado~~ y ~~`MAX_EXTENSION_WEEKS` (30/26)~~ cerradas en A1 el 2026-08-13; **siguen abiertas**: fases (5/4/4), clasificación de nivel, techo I_max, factibilidad, ritmo /100 del sprint, `ZONE_LABELS` |
| P3 | **`Semana.phase` guarda una etiqueta de interfaz**, no una fase de dominio | la DB tiene `"Construcción"`; `F_FASE` se indexa por `base_especifica`. No se pueden cruzar |
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
| Reescribir el frontend | el rediseño es del backend; el frontend solo cambia sus tipos (`lib/types.ts`) |

---

## 2. Estructura

```
backend/app/
├── dominio/                     ← POO puro. No importa NADA de infraestructura
│   ├── valores/                 objetos inmutables sin identidad
│   │   ├── tiempo.py            Tiempo · Ritmo · Mejora
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
│   │   ├── sesion.py            Sesion · Serie                     ← nuevo ❓R1
│   │   └── carga.py             CargaDiaria                        ← nuevo ❓R1
│   ├── roles/
│   │   └── rol.py               Rol · Administrador · EntrenadorEnJefe ·
│   │                            Entrenador · Atleta(rol)
│   └── servicios/
│       ├── motor.py             MotorCientifico  ← el único
│       ├── tablas.py            todas las constantes + su fuente §
│       ├── curvas.py            Curva (Strategy) + 5 implementaciones
│       ├── intervalos.py        cálculo de salida y descanso
│       └── banister.py          CargaAcumulada (CTL/ATL/TSB)       ← nuevo ❓R1
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

---

## 3. Objetos de valor

Inmutables (`frozen=True`), sin identidad, comparables por valor.

### 3.1 Tiempo y ritmo

| Objeto | Contenido | Comportamiento |
|---|---|---|
| `Tiempo` | segundos absolutos | `desde_texto("1:05.32")` · `texto()` · comparación · `- → Mejora` |
| `Ritmo` | segundos por 100 m | `desde(tiempo, distancia)` · `a_tiempo(distancia)` · `texto()` |
| `Mejora` | segundos + base | `.segundos` · `.porcentaje` · `es_regresion()` |

**Por qué importan.** Hoy hay ocho columnas `float` que mezclan dos unidades:
`current_time`, `goal_time`, `expected_time`, `recalc_time`, `real_time` son
segundos absolutos; `avg_per100`, `css_ms`, `pace_100m` son segundos/100 m. Nada
impide restarlos entre sí. Con tipos distintos, el error no compila.

`Mejora` existe porque los dos motores actuales expresan lo mismo de dos formas:
`progression` maneja segundos, `ScienceEngine` maneja fracciones decimales. Un
tipo que lleva las dos elimina la conversión manual repetida.

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

Prescripcion  Zona · Ritmo · salida: Tiempo · descanso: Tiempo · distancia_rep
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

---

## 4. Los roles

### 4.1 La decisión

`Usuario` es identidad y nada más: correo, hash, nombre, versiones de sesión.
**No hereda a `Entrenador` ni a `Nadador`.**

El caso concreto que lo descarta: un entrenador que además nada máster en su
propio club, o alguien que es atleta en un club y entrenador en otro. Con
herencia, cambiar de rol significa cambiar de clase — y una fila de `users` no
cambia de clase. Habría que borrar la cuenta y recrearla, perdiendo el histórico
y la identidad.

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
  ├── Administrador       plataforma; cruza equipos      ❓R3
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
`es_desarrollador`, que ya es ese mismo patrón funcionando. ❓R3

### 4.5 Entrenador asistente

**No necesita rol propio.** Hoy un entrenador solo ve los macrociclos en los que
está (`plan_coaches`) y el jefe los ve todos: eso *es* la distinción
jefe/asistente, y ya está impuesta en la capa de acceso.

Haría falta un rol nuevo solo si el asistente debe tener **menos** permisos
dentro de un macrociclo que sí lleva (ejemplo: registrar tiempos sí, cambiar la
meta no). ❓R4

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

### 5.5 `FaseDelMacro` (PlanPhase) y `Competencia` (Competition)

```
FaseDelMacro:  nombre (texto libre, UI) · fase: Fase (clave de dominio) ·
               semana_inicio · semana_fin · color · orden

Competencia:   nombre · semana · dias · es_principal
```

El desdoble `nombre` / `fase` es lo que cierra P3: el entrenador puede llamarle
"Construcción" a lo que el motor conoce como `base_especifica`.

### 5.6 `Inscripcion` (AthletePlan)

```
atleta · macrociclo · base_aerobica: Ritmo? · fuente_de_base · activa

dar_de_baja() / restaurar()      baja lógica; el histórico no se toca
```

### 5.7 `PruebaObjetivo` (AthleteEvent)

```
prueba: Prueba · actual: Tiempo · meta: Tiempo · prioridad

mejora_pedida() -> Mejora
factibilidad(nivel, semanas, n_mac, edad) -> Veredicto
```

`distance` + `stroke` sueltos pasan a ser un `Prueba`. Aquí es donde la
validación deja de depender de que alguien llame a `is_valid_event`.

### 5.8 `Semana` (WeeklyPlan)

```
numero · fecha · km_planificados
esperado: Tiempo          curva ideal original — NUNCA se modifica
recalculado: Tiempo?      curva recalculada tras un tiempo real
fase: Fase                ← clave de dominio, no etiqueta
deshabilitada + razon
resultado_id?             ← FK a Resultado. YA NO guarda el tiempo

zonas() -> JuegoDeZonas   derivado, no persistido
desviacion() -> Mejora?
```

**Cambio de fondo:** `real_time` sale de aquí. Ver §5.10.

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
documentado en su propio docstring (`plans/service.py:196`). El bug se parcheó;
la causa —un hecho del atleta modelado como propiedad de un plan— sigue ahí.

Con `Resultado` colgando del atleta:
- sacar a alguien de un macrociclo no puede tocar su histórico (la baja lógica
  pasa a ser una elección, no un parche);
- el mismo tiempo se puede comparar contra dos macrociclos;
- el histórico de un atleta se lee sin recorrer planes;
- `Semana.resultado_id` es una referencia opcional: la semana *apunta* al tiempo,
  no lo posee.

`AerobicTest` ya está modelado así (cuelga del atleta, con macrociclo opcional).
Es el patrón correcto que el resto del esquema no siguió. ❓R2

### 5.11 `Sesion` y `Serie` — nuevo ❓R1

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

### 5.12 `CargaDiaria` — nuevo ❓R1

```
atleta · fecha · stss · ctl · atl · tsb

               derivada de Sesion; se recalcula, no se edita
               alerta_de_sobreentrenamiento() -> bool
```

La nota 05 del vault, por fin construible.

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
`progression`.** ❓R6

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
ediciones en tres archivos. Con Strategy es un archivo. ❓R7

### 6.3 `CargaAcumulada` — Banister ❓R1

```
CargaAcumulada
  calcular(sesiones, desde, hasta) -> list[CargaDiaria]
  CTL = media exponencial 42 d · ATL = 7 d · TSB = CTL − ATL
```

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
                    ├──< sesiones ──< series           ← NUEVO ❓R1
                    ├──< carga_diaria                  ← NUEVO ❓R1
                    ├──< entrenadores_de_atleta >── pertenencias
                    └──< inscripciones

macrociclos ──< fases_del_macro
            ──< competencias ──< resultados            (agrupa, no posee)
            ──< entrenadores_del_macro >── pertenencias
            ──< inscripciones ──< pruebas_objetivo ──< semanas
                                                          └─ resultado_id? (FK)

codigos_de_vinculacion ── atletas · pertenencias · usuarios
```

### 7.2 Cambios respecto a la beta

| # | Cambio | Motivo |
|---|---|---|
| 1 | `semanas.real_time` → `semanas.resultado_id` (FK a `resultados`) | §5.10 — el tiempo es del atleta |
| 2 | `resultados` (tabla nueva) | idem |
| 3 | `sesiones` + `series` (nuevas) ❓R1 | la unidad mínima deja de ser la semana |
| 4 | `carga_diaria` (nueva) ❓R1 | CTL/ATL/TSB |
| 5 | `semanas.fase` y `fases_del_macro.tipo` guardan la **clave** de `Fase`, no la etiqueta | cierra P3 |
| 6 | `CheckConstraint` en zona, nivel, perfil, estilo, especialidad, tipo_de_test, piscina, estado, modo_de_ingreso, rol | hoy solo `rol` lo tiene; el resto acepta cualquier string |
| 7 | `usuarios.es_staff` (o `roles_de_plataforma`) ❓R3 | admin no cabe en `pertenencias` |
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
semanas.real_time  ──►  resultados(atleta, prueba, tiempo, fecha, contexto='control')
                        + semanas.resultado_id = nuevo.id
```

La prueba y el atleta se derivan de `pruebas_objetivo` e `inscripciones`; la
fecha, de `semanas.fecha`. Es un `INSERT ... SELECT` con un `UPDATE` de vuelta.
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
| `WeeklyPlan` | `Semana` | `real_time` → `resultado_id` |
| `AerobicTest` / `AerobicSplit` | `TestAerobico` / `Parcial` | análisis dentro del objeto; conversión clock→rep como invariante |
| `LinkCode` | `CodigoDeVinculacion` | + ciclo de vida como métodos |
| `CoachAthlete` / `PlanCoach` | `EntrenadorDeAtleta` / `EntrenadorDelMacro` | — |
| `Principal` | `Principal` | compone `Rol` en vez de tener `is_coach`/`is_athlete` |
| `ScienceEngine` + `engine/progression` + `envelope` + `feasibility` + `km_distribution` | `MotorCientifico` | **7 archivos → 1 servicio** |
| `curve_progress()` + `CURVES` + `CURVE_LABELS` | `Curva` (Strategy) | 3 constantes paralelas → 5 clases |
| `engine/zones.py` + `send_off.py` | `Zona` · `Prescripcion` · `JuegoDeZonas` | dicts de strings → tipos |
| `engine/time_utils.py` | `Tiempo` · `Ritmo` | funciones sueltas → tipos con unidad |
| `engine/events.py` (`domain.allowed_strokes` ya borrada en A1) | `Prueba` | **función suelta → invariante del objeto** |
| `engine/aerobic.py` | `TestAerobico` (métodos) | — |
| `modules/dashboard` | `api/v1/vistas/` | deja de ser módulo de dominio; es una vista |
| `modules/simulator` | `api/v1/simulador/` | llama al motor, no persiste |
| — | `Resultado` | **nuevo** |
| — | `Sesion` / `Serie` / `CargaDiaria` | **nuevo** ❓R1 |
| — | `persistencia/repositorios/` | **nuevo** (cierra P5) |

---

## 9. Orden de construcción

| # | Paso | Riesgo | Cierra | Se puede parar aquí |
|---|---|---|---|---|
| 1 | `dominio/valores/` completo | bajo | P6, P2 | sí |
| 2 | Entidades ricas (`Atleta`, `Macrociclo`, `TestAerobico`) | bajo | P4 | sí |
| 3 | `Rol` + subclases; `Principal` compone | bajo | — | sí |
| 4 | **Fusión de los dos motores** | **medio-alto** | P1, P3 | rama propia |
| 5 | `persistencia/repositorios/` + recorte de imports cruzados | medio | P5 | sí |
| 6 | `Resultado` + migración de `real_time` | medio | §5.10 | sí |
| 7 | `Sesion` / `Serie` ❓R1 | medio | el hueco de fondo | sí |
| 8 | `CargaDiaria` + Banister ❓R1 | bajo | nota 05 | — |

El paso 4 es el único con riesgo real. Se hace en rama propia y con los 442 tests
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

## 10. Decisiones abiertas — para tu revisión

| # | Decisión | Recomendación | Impacto si cambia |
|---|---|---|---|
| **❓R1** | ¿`Sesion`/`Serie`/`CargaDiaria` entran en este rediseño o quedan para v2? | **Entran.** Es el hueco de fondo: sin ellas no hay Banister, y las prescripciones que el motor calcula siguen sin tener dónde guardarse | si quedan fuera, el modelo es válido igual; solo se pospone el paso 7–8 |
| **❓R2** | ¿`Resultado` reemplaza a `Semana.real_time` o conviven? | **Reemplaza.** Convivir significa dos sitios donde vive el mismo hecho, que es P1 otra vez | alto: es el cambio estructural del esquema |
| **❓R3** | ¿`Administrador` se construye ahora o se deja el hueco? | **Solo el hueco** (`Rol` lo contempla, no se implementa). La revisión de CEO del 2026-08-06 lo dejó fuera hasta tener spec propia | bajo: es aditivo |
| **❓R4** | ¿El entrenador asistente necesita menos permisos dentro de un macrociclo que sí lleva? | **No.** `entrenadores_del_macro` ya da la distinción. Solo si quieres "registra tiempos pero no cambia la meta" | medio: un rol más en la jerarquía |
| **❓R5** | ¿Una persona puede pertenecer a más de un equipo? | **No por ahora.** Hoy `UNIQUE(usuario_id)` lo impide y el diseño lo respeta. Quitar esa restricción es un cambio de una línea, pero `Principal` pasaría a tener que elegir equipo activo | alto: toca toda la frontera de aislamiento |
| **❓R6** | Al fusionar los motores, ¿mando la ciencia de `ScienceEngine` o la parametrización de `progression`? | **Las dos** (§6.1): ciencia de uno, parametrización del otro. Pero hay un conflicto real: `ScienceEngine` reparte km por nivel/fase, `progression` los normaliza al total que puso el entrenador | alto: define qué ve el entrenador |
| **❓R7** | ¿Se mantiene la curva elegible por el entrenador o se fija `Cientifica`? | **Se mantiene**, pero como herramienta del simulador. En el plan real, `Cientifica` por defecto (ya lo es) | bajo |
| **❓R8** | ¿PostgreSQL desde el rediseño o seguimos con SQLite? | **SQLite.** El `docker-compose.yml` ya trae PostgreSQL 17 listo; el salto es `pip install asyncpg` + una variable. No lo mezcles con el rediseño del dominio | medio si se hacen a la vez |

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
- 307 tests. Son el contrato que hace este rediseño posible.
