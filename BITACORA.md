# PeakStroke — Bitácora Técnica

> Registro de cálculos, teorías, reglas empíricas y decisiones de diseño
> del sistema PeakStroke. Este documento está destinado a respaldar las
> decisiones técnicas ante entrenadores certificados y como memoria del
> proyecto.

**Proyecto:** PeakStroke — Sistema de Planificación y Predicción de Rendimiento para Natación  
**Inicio:** 01/06/2025  
**Mantenido por:** Sesiones de desarrollo con Claude

---

## Entrada #001 — Regla empírica base: 1 segundo por microciclo en base aeróbica

**Fecha:** 01/06/2025  
**Categoría:** Regla empírica — validada en práctica  
**Fuente:** Empírica — validada por el entrenador en trabajo real con atletas  
**Relacionado con:** Motor de progresión, Planificación del macrociclo, T-30/T-15

### Contexto

Durante el diseño del motor de progresión del sistema PeakStroke, se planteó
la pregunta: ¿cuánto debe mejorar la base aeróbica por microciclo para que
el plan sea realista y efectivo? El entrenador aportó una regla validada
empíricamente en su trabajo con nadadores de competencia.

### Desarrollo

La regla empírica establecida y validada en práctica es:

> **Por cada microciclo de entrenamiento (4–5 semanas), el atleta debe
> mejorar 1 segundo en su base aeróbica (promedio R1 × 100m) para producir
> una mejora observable en las pruebas de 400m y 800m.**

Esta regla tiene coherencia fisiológica directa: el 400m y el 800m son
eventos dominantemente aeróbicos (85–95% del sistema energético), por lo
que la mejora en la base aeróbica se transfiere casi linealmente al tiempo
de competencia.

La base aeróbica se mide como el **promedio de los parciales** del test
T-30 (30 repeticiones de 100m en R1) o T-15 (15 repeticiones de 100m en R1).

### Valores de referencia

| Evento | Splits de 100m | Mejora teórica por 1s en R1 | % mejora aprox. |
|--------|---------------|----------------------------|-----------------|
| 400m   | 4             | ~4.0 s por microciclo       | ~1.3%           |
| 800m   | 8             | ~8.0 s por microciclo       | ~1.3%           |

El porcentaje de mejora es consistente (~1.3%) porque la relación es
casi lineal para eventos predominantemente aeróbicos.

### Advertencias / Limitaciones

- Esta regla aplica **exclusivamente** a eventos aeróbicos (400m en adelante).
- El escalado no es perfectamente lineal en la práctica; el 400m tiene
  un componente anaeróbico (~10–15%) que introduce cierta variabilidad.
- La mejora de 1s/micro asume un plan de entrenamiento estructurado con
  kilometraje adecuado. Sin carga suficiente, la mejora puede ser menor.

### Notas para validación externa

- ¿Confirmar con entrenadores certificados si el rango de 1s/micro es
  consistente con literatura de entrenamiento para nadadores juveniles vs.
  adultos?
- ¿Varía este factor según el nivel de base del atleta (principiante vs.
  competidor nacional)?

---

## Entrada #002 — Modelo de dos tiers para el motor de progresión

**Fecha:** 01/06/2025  
**Categoría:** Cálculo matemático — Decisión de diseño  
**Fuente:** Teórica (fisiología deportiva) + Empírica (regla de 1s/micro como base)  
**Relacionado con:** Motor de progresión, `services/progression_engine.py`, `config/training_zones.py`

### Contexto

La regla empírica de 1s/micro funciona para 400m y 800m, pero falla para
eventos de velocidad (50m, 100m) y para estilos que no son crawl (mariposa,
pecho, espalda). Se diseñó un modelo unificado que divide los eventos en
dos categorías según el sistema energético dominante.

### Desarrollo

El motor de progresión opera en **dos modos** según el tipo de evento:

#### Tier 1 — Eventos aeróbicos (400m y más)

La mejora se calcula directamente desde la base aeróbica (R1):

```
mejora_semanal = (1s × factor_distancia × factor_estilo × ratio_aerobico) / semanas_por_micro
```

La mejora de 1s en R1 por microciclo se distribuye a lo largo de las
semanas del microciclo y se escala según la distancia y el estilo.

#### Tier 2 — Eventos de velocidad/mixtos (50m, 100m, 200m)

La mejora NO viene principalmente de la base aeróbica. Proviene de:
técnica, salida, viraje, y capacidad de sprint. Se usa una **ventana de
mejora fraccionada** con techo fisiológico por distancia y estilo:

```
mejora_por_micro = ventana_base × factor_estilo
```

Donde la ventana base es un rango empírico-fisiológico basado en lo
observado en competencia y literatura.

### Fórmulas / Tablas

#### Factor distancia (Tier 1)

| Evento | Factor distancia | Razón |
|--------|-----------------|-------|
| 800m   | 8.0             | 8 splits de 100m |
| 400m   | 4.0             | 4 splits de 100m |
| 200m   | 1.8             | No lineal — speed toma control (~35–45% anaeróbico) |
| 100m   | 0.45            | Modelo Tier 2 (speed) |
| 50m    | 0.15            | Modelo Tier 2 (speed puro) |

#### Ratio aeróbico por distancia

| Evento | % Aeróbico | % Anaeróbico/Speed |
|--------|-----------|-------------------|
| 800m   | 90–95%    | 5–10%             |
| 400m   | 85–90%    | 10–15%            |
| 200m   | 55–70%    | 30–45%            |
| 100m   | 25–40%    | 60–75%            |
| 50m    | 10–20%    | 80–90%            |

#### Factor estilo (relativo a crawl = 1.0)

| Estilo      | Factor   | Razón |
|-------------|---------|-------|
| Crawl/Libre | 1.00    | Referencia — más eficiente mecánicamente |
| Espalda     | 0.88–0.92 | Técnica similar al crawl, algo menos eficiente |
| Mariposa    | 0.72–0.80 | Alta demanda técnica y energética |
| Pecho       | 0.65–0.72 | El más ineficiente mecánicamente |
| Combinado   | 0.80    | Promedio ponderado de estilos |

#### Ventana de mejora por microciclo — Tier 2 (velocidad)

| Evento        | Rango realista/micro |
|---------------|---------------------|
| 100m crawl    | 0.40–0.60 s         |
| 100m mariposa | 0.30–0.50 s         |
| 100m espalda  | 0.35–0.50 s         |
| 100m pecho    | 0.25–0.45 s         |
| 50m crawl     | 0.10–0.25 s         |
| 50m mariposa  | 0.08–0.20 s         |

Si el plan proyecta más que el techo de la ventana, el sistema debe
marcar el objetivo como **"agresivo"** y recomendar ajuste de semanas o meta.

### Valores de referencia — Ejemplo de alerta

**Caso: Sofía Ramírez — 100m Mariposa**

```
Tiempo actual:           1:07.80  (67.80 s)
Tiempo meta:             1:02.00  (62.00 s)
Mejora total requerida:  5.80 s
Macrociclo:              12 semanas / 3 microciclos de 4 semanas
Mejora requerida/micro:  5.80 / 3 = 1.93 s/micro  ← SUPERA techo
Ventana realista:        0.30–0.50 s/micro
Estado:                  ⚠ OBJETIVO AGRESIVO
Recomendación:           Extender a 18 semanas, o ajustar meta a ~1:04.xx
```

### Advertencias / Limitaciones

- Los factores de estilo son estimaciones basadas en biomecánica general.
  Pueden variar significativamente según el nivel técnico individual del atleta.
- La ventana de mejora de velocidad aplica a atletas juveniles/amateur
  competitivos. En élite, las ventanas son aún más pequeñas.
- El 200m es el caso más complejo — es un evento "bisagra" que puede operar
  en Tier 1 o Tier 2 según el estilo (200m libre es más aeróbico que 200m
  mariposa o pecho).

### Notas para validación externa

- ¿Los factores de estilo (mariposa=0.72–0.80, pecho=0.65–0.72) son
  consistentes con lo que manejan entrenadores certificados?
- ¿La ventana de 0.30–0.50s/micro para 100m mariposa corresponde a lo
  observado en temporadas de 12–18 semanas con atletas juveniles de nivel
  nacional?
- ¿Cómo ajusta el factor de estilo cuando el atleta tiene técnica
  excepcionalmente buena o mala?

---

## Entrada #003 — Decisiones de diseño del sistema: flujo y vistas principales (mockup v2)

**Fecha:** 01/06/2025  
**Categoría:** Decisión de diseño  
**Fuente:** Decisión del equipo de desarrollo + retroalimentación del entrenador  
**Relacionado con:** `ui/`, todas las vistas principales

### Contexto

Durante el desarrollo del mockup HTML interactivo (v2), el entrenador
evaluó el flujo propuesto y sugirió cambios fundamentales basados en cómo
trabaja realmente con sus atletas.

### Desarrollo

#### Flujo principal: Macrociclo → Atletas (no al revés)

El flujo original era: registrar atleta → crear macrociclo para el atleta.
El flujo correcto según la práctica real es:

> **El entrenador primero diseña el macrociclo general del equipo, y luego
> agrega los atletas a ese macro.**

Razón: en natación competitiva, el equipo entrena bajo un mismo macrociclo
(misma competencia objetivo, mismas fechas, similar carga). Los atletas
se diferencian por sus pruebas individuales y tiempos, pero el marco
temporal es compartido.

#### Atletas con hasta 3 pruebas principales

Cada atleta puede tener hasta 3 pruebas principales activas en un macrociclo:
- **Prueba #1**: prueba principal (la que define el macro del atleta)
- **Prueba #2**: prueba secundaria (seguimiento)
- **Prueba #3**: opcional

Cada prueba tiene su propio tiempo actual y tiempo meta. El motor de
progresión genera un plan independiente para cada prueba.

#### T-30/T-15: modo de ingreso directo

Además del ingreso de 30 o 15 parciales individuales, el sistema debe
permitir ingresar directamente el tiempo promedio (base aeróbica) si
ya se tiene calculado. Esto facilita migrar datos históricos o usar
tests calculados con otras herramientas.

#### Fases del macrociclo: configurables por el entrenador

Las fases (Base, Construcción, Pico, Descenso) NO son fijas. El entrenador
puede:
- Cambiar el nombre de cada fase
- Ajustar qué semanas cubre cada fase
- Agregar o eliminar fases
- El sistema valida que las fases cubran todas las semanas del macro

#### Tabla del equipo: vista central

Una vista específica "Tabla del Equipo" que funciona como herramienta
de control operativo semanal:
- Muestra todos los atletas del macrociclo en una sola tabla
- Filtros por: semana, prueba, atleta
- Columnas: atleta, prueba, base aeróbica, tiempo esperado, parcial R1
  objetivo, km semana, tiempo real, diferencia, estado
- Atletas con múltiples pruebas aparecen con filas agrupadas
- Vista alternativa "por atleta": plan completo de un atleta específico
- Exportable a CSV

### Advertencias / Limitaciones

- La vista de tabla del equipo puede volverse muy ancha cuando hay muchos
  atletas con 3 pruebas cada uno. Evaluar paginación o scroll horizontal
  en la implementación real.
- El límite de 3 pruebas por atleta puede ser insuficiente para
  pruebas combinadas (200m IM, 400m IM). Pendiente definir si el IM
  se trata como prueba separada o si tiene su propio módulo.

### Notas para validación externa

- ¿Con cuántas pruebas simultáneas trabaja normalmente un entrenador
  por atleta en un macrociclo? ¿Es 3 suficiente?
- ¿La tabla del equipo como se diseñó refleja el formato de control
  que usan los entrenadores certificados en sus planillas actuales?

---

## Entrada #004 — Parcial /100m como referencia central para zonas de entrenamiento

**Fecha:** 01/06/2025  
**Categoría:** Decisión de diseño — Cálculo matemático  
**Fuente:** Corrección del entrenador sobre uso práctico del sistema  
**Relacionado con:** Motor de progresión, zonas de entrenamiento, UI de plan semanal

### Contexto

Durante la revisión del mockup v2 y el motor de progresión, el entrenador
clarificó cómo se usan realmente las zonas en la planificación del entrenamiento:
el número operativo no es el tiempo total de la prueba sino el **parcial por
cada 100m**, porque es la unidad con la que se calculan tiempos de cualquier
tipo de serie.

### Desarrollo

El entrenador planifica series usando el `/100m` como bloque base:

```
Serie de 100m en R1 → tiempo objetivo = R1 /100m
Serie de 200m en R1 → tiempo objetivo = R1 /100m × 2
Serie de 300m en R1 → tiempo objetivo = R1 /100m × 3
Serie de 400m en R1 → tiempo objetivo = R1 /100m × 4
```

Por eso **todas las zonas deben expresarse siempre en segundos por 100m**,
y `pace_100m` debe aparecer de forma prominente en todas las tablas del sistema.

### Fórmulas

```
pace_100m = expected_race_time / (distance_m / 100)

Ejemplos:
  400m en 4:55.00 (295s) → pace_100m = 295 / 4 = 73.75s  = 1:13.75 /100m
  100m en 1:05.00 (65s)  → pace_100m = 65  / 1 = 65.00s  = 1:05.00 /100m
  800m en 9:48.00 (588s) → pace_100m = 588 / 8 = 73.50s  = 1:13.50 /100m

Zonas a partir del pace_100m:
  R1   = pace_100m × 1.375   (base aeróbica)
  R2   = pace_100m × 1.275   (umbral aeróbico)
  MVO2 = pace_100m × 1.175   (VO₂ máximo)
  RL   = pace_100m × 1.125   (resistencia lactato)
  V    = pace_100m × 1.075   (velocidad pura)
```

### Caso especial: pruebas de 50m

```
pace_100m = 50m_time × 2   (aproximación)
```

**Limitación:** la segunda mitad de una serie sin bloque de salida es más
lenta que con bloque. El factor ×2 es una referencia base; el ajuste fino
lo realiza el entrenador según el tipo de serie.

### Implementación

- `pace_100m` es campo explícito en `WeeklyEntry` (Python y JS)
- En la tabla del plan semanal aparece como columna destacada con la aclaración
  de que es la referencia para escalar series
- El tiempo total de la prueba se muestra atenuado — no es el número operativo
- Todas las zonas en el sistema se expresan /100m

### Notas para validación externa

- ¿Los factores de zona (R1=×1.375, R2=×1.275, etc.) corresponden con los
  rangos que manejan los entrenadores certificados?
- ¿Los factores varían según la distancia o el estilo, o son fijos?
  (El sistema los tiene en `config/training_zones.py` y son ajustables)
- ¿El ajuste de salida para 50m es operativamente relevante o se maneja
  siempre a criterio del entrenador?

---

## Entrada #005 — Pivote arquitectónico: de app de escritorio a SaaS web-first

**Fecha:** 2026-06-02
**Categoría:** Decisión de arquitectura — Cambio de stack
**Fuente:** Prompt maestro del proyecto v2.0
**Relacionado con:** Toda la arquitectura del sistema

### Contexto

El proyecto comenzó como una aplicación de escritorio (Python + PySide6 + SQLite).
Durante la fase de planificación, se tomó la decisión estratégica de reestructurar
hacia un modelo SaaS web-first para maximizar alcance, reducir fricción de instalación
y habilitar un modelo de negocio por suscripción.

### Decisión

**Stack anterior:** Python + PySide6 + SQLite + SQLAlchemy (desktop)

**Stack nuevo:**
- **Backend:** FastAPI (Python) + PostgreSQL + SQLAlchemy async + Alembic
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + PWA
- **Estado cliente:** TanStack Query (server state) + Zustand (auth/UI state)
- **Gráficos:** Recharts
- **Pagos:** Stripe (implementación futura v2)
- **Deploy:** Railway/Render (backend) + Vercel/Netlify (frontend)

### Justificación

1. **PWA = app nativa sin tienda:** Se instala en Windows/Mac/Linux igual que una
   app nativa. El usuario siempre tiene la última versión sin actualizaciones manuales.
2. **Un código para todos los clientes:** El mismo frontend sirve a browser, PWA
   desktop y (en el futuro) React Native móvil.
3. **Modelo SaaS habilita ingresos recurrentes:** Licencia única tiene techo de
   ingresos; suscripción permite crecer con el uso.
4. **Multi-entrenador desde el diseño:** La arquitectura web permite que un club
   tenga múltiples entrenadores accediendo al mismo dato.

### Motor de progresión

El motor de progresión Python (`progression_engine.py`) se portó íntegramente al
backend FastAPI en `backend/app/modules/training_plans/progression_engine.py`.
Los factores, ventanas y reglas empíricas se conservaron exactamente — no se
perdió ninguna lógica del prototipo de escritorio.

---

## Entrada #006 — Arquitectura vertical slice (feature-based)

**Fecha:** 2026-06-02
**Categoría:** Decisión de arquitectura — Organización del código
**Fuente:** Prompt maestro v2.0
**Relacionado con:** Estructura de carpetas `backend/app/modules/` y `frontend/src/features/`

### Regla fundamental

El código se organiza **por feature/módulo**, NO por tipo de archivo.

```
✅ CORRECTO                        ❌ INCORRECTO
backend/app/modules/               backend/app/
  training_plans/                    models/      ← todos mezclados
    models.py                        routers/     ← todos mezclados
    schemas.py                       services/    ← todos mezclados
    service.py
    router.py
```

### Protocolo para agregar una nueva feature

**Backend:** Crear `app/modules/nueva_feature/` con 4 archivos
(`models.py`, `schemas.py`, `service.py`, `router.py`) y registrar en `main.py`:
```python
app.include_router(nueva_router, prefix="/api/v1/nueva-feature", tags=["Nueva"])
```

**Frontend:** Crear `src/features/nueva-feature/` con carpetas
(`components/`, `hooks/`, `api.ts`) y agregar la ruta en `App.tsx`.

**Ningún módulo existente se toca.**

### Reglas de convivencia entre módulos

- Los módulos NO se importan entre sí directamente
- Si dos módulos comparten lógica → va en `core/`
- `router.py` nunca tiene lógica de negocio — solo recibe, delega y retorna
- `service.py` recibe la sesión de DB como parámetro — nunca la importa globalmente
- Schemas: siempre `XCreate` (entrada) / `XUpdate` (parcial) / `XResponse` (salida)

---

## Entrada #007 — Modelo de datos: macrociclo centrado en el equipo

**Fecha:** 2026-06-02
**Categoría:** Decisión de diseño — Modelo de datos
**Fuente:** Office Hours session — respuestas del entrenador
**Relacionado con:** `backend/app/modules/training_plans/models.py`

### Flujo correcto según el entrenador

> El entrenador primero diseña el macrociclo del equipo, luego agrega atletas.
> NO al revés (atleta → macrociclo).

Esto se refleja en el modelo:
```
Macrocycle (el equipo)
  └── AthleteMacrocycle (liga atleta al macro)
        ├── aerobic_base (pace_100m base aeróbica, editable)
        └── AthleteEvent (hasta 3 pruebas por atleta)
              └── WeeklyPlan (plan semana × prueba)
```

### Decisiones clave de UI (Office Hours)

**Parón por lesión/vacaciones:** Modo dual
- La semana inhabilitada muestra en la tabla como vacía
- El gráfico muestra DOS curvas: ideal (gris) + recalculada (azul)
- El entrenador decide cuál seguir — el sistema no fuerza

**Vista tabla del equipo:** Una fila por atleta con selector inline de prueba
- Por defecto muestra la prueba #1 (prioritaria)
- Cada fila tiene un dropdown para cambiar entre las 3 pruebas
- Los tiempos se actualizan en tiempo real al cambiar la prueba

**Zonas en tabla:** Las 5 zonas visibles y colapsables
- Columnas `R1 | R2 | MVO2 | RL | V` con `pace_100m` en formato `mm:ss.cc`
- Toggle para colapsar/expandir — estado persiste por sesión

### `pace_100m` como campo explícito

Por decisión del entrenador (Entrada #004), `pace_100m` es el número operativo central.
Aparece como columna destacada en la tabla del equipo. El tiempo total de la prueba
se muestra atenuado — no es el número que usa el entrenador en el día a día.

---

## Entrada #008 — Tiers de suscripción y guardas de acceso

**Fecha:** 2026-06-02
**Categoría:** Decisión de negocio — Control de acceso
**Fuente:** Prompt maestro v2.0
**Relacionado con:** `backend/app/core/tier_limits.py` y `backend/app/core/dependencies.py`

### Estructura de tiers

| Tier | Nadadores | Historial | Exportación | Multi-entrenador | Macrociclos |
|------|-----------|-----------|-------------|-----------------|-------------|
| free | 5 | 3 meses | No | No | 1 |
| coach | 20 | Completo | Sí | No | Ilimitado |
| club | Ilimitado | Completo | Sí | Sí | Ilimitado |

### Trial automático

Al registrarse, el usuario recibe tier `coach` con `trial_ends_at = now + 30 días`.
Al hacer login, si el trial venció y no hay `stripe_customer_id`, el sistema
degrada automáticamente a `free`. Esto ocurre en `auth/service.py:authenticate_user`.

### Guard pattern

```python
# Uso en cualquier endpoint:
@router.get("/export")
async def export(user = Depends(require_feature("export"))):
    ...
```

`require_feature` lanza HTTP 403 con mensaje amigable si el tier no tiene el feature.
La fuente de verdad es el dict `TIER_LIMITS` en `core/tier_limits.py` — un solo lugar
para cambiar todos los límites.

---

## Entrada #009 — Eje X de gráficos: fechas reales DD/MM

**Fecha:** 2026-06-02
**Categoría:** Regla de implementación — UI
**Fuente:** Enunciado del proyecto + decisión del equipo
**Relacionado con:** `frontend/src/features/training-plans/components/ProgressionChart.tsx`
y `backend/app/modules/training_plans/models.py:WeeklyPlan.week_date`

### Regla

**TODOS los gráficos de progresión semanal muestran la fecha de inicio de cada
semana en el eje X (formato `DD/MM`), NO el número de semana.**

Implementación:
- `WeeklyPlan.week_date` almacena la fecha del lunes de cada semana en la DB
- El frontend formatea con `date-fns: format(parseISO(week_date), 'dd/MM', { locale: es })`
- Recharts recibe `label` como string `DD/MM` directamente
- Esta regla aplica a `ProgressionChart.tsx` y a cualquier gráfico futuro de progresión

---
