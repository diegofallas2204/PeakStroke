# PeakStroke — Sistema de Planificación y Predicción de Rendimiento para Natación

## Descripción General

PeakStroke es una aplicación de escritorio profesional orientada a entrenadores y nadadores de natación competitiva. Su propósito central es permitir la planificación estructurada de macrociclos de entrenamiento, calcular progresiones de mejora realistas y proyectar tiempos objetivo semana a semana, con base en la carga de trabajo y la capacidad aeróbica del atleta.

La aplicación busca responder preguntas concretas como: *¿Cuánto debe mejorar mi parcial aeróbico cada semana para alcanzar mi tiempo meta en 12 semanas?* o *¿Es realista bajar de 1:05 a 1:02 en un macrociclo de 18 semanas con esta carga de kilómetros?*

---

## Objetivo General

Desarrollar una aplicación de escritorio profesional que permita:

- Registrar y gestionar atletas con su historial deportivo.
- Crear y administrar macrociclos de entrenamiento (12 o 18 semanas), divididos en microciclos de 4–5 semanas.
- Calcular automáticamente el porcentaje de mejora requerido por semana según prueba, carga y tiempo objetivo.
- Proyectar el parcial aeróbico semanal esperado para alcanzar el tiempo meta.
- Comparar el rendimiento real del atleta contra el rendimiento planificado.
- Visualizar curvas de progresión (lineal, exponencial, logarítmica, sigmoidal).
- Simular escenarios modificando semanas, kilómetros y objetivos.

---

## Stack Tecnológico

| Capa | Tecnología | Razón |
|---|---|---|
| Lenguaje | Python 3.12+ | Ecosistema científico, rapidez de desarrollo |
| UI | PySide6 (Qt) | Interfaz moderna, alto rendimiento, soporte gráfico |
| Base de datos | SQLite | Sin servidor, portable, fácil distribución |
| ORM | SQLAlchemy | Abstracción de datos, escalable |
| Gráficos | Matplotlib integrado en PySide6 | Visualización científica nativa |

---

## Arquitectura

Arquitectura en capas con principios SOLID. La interfaz nunca realiza cálculos directamente; todo pasa por servicios especializados.

```
UI
│
├── Services
│
├── Business Logic
│
├── Repositories
│
└── Database (SQLite)
```

---

## Estructura del Proyecto

```
swim-performance-app/
├── main.py
├── app/
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── dashboard_view.py
│   │   ├── athlete_view.py
│   │   ├── macrocycle_view.py
│   │   ├── weekly_plan_view.py
│   │   ├── simulation_view.py
│   │   ├── graphs_view.py
│   │   └── widgets/
│   ├── models/
│   │   ├── athlete.py
│   │   ├── macrocycle.py
│   │   ├── weekly_plan.py
│   │   ├── parcial.py
│   │   └── prediction.py
│   ├── services/
│   │   ├── calculations.py
│   │   ├── progression_engine.py
│   │   ├── aerobic_analysis.py
│   │   ├── prediction_engine.py
│   │   ├── macrocycle_engine.py
│   │   └── curve_generator.py
│   ├── database/
│   │   ├── connection.py
│   │   ├── schema.py
│   │   └── repositories/
│   ├── charts/
│   │   ├── progress_chart.py
│   │   ├── comparison_chart.py
│   │   ├── macrocycle_chart.py
│   │   └── simulation_chart.py
│   ├── utils/
│   │   ├── time_utils.py
│   │   └── validators.py
│   └── config/
│       └── training_zones.py   ← factores de zona por distancia (fuente de verdad única)
├── assets/
│   ├── icons/
│   └── styles/
├── requirements.txt
└── README.md
```

---

## Lecciones del Prototipo (natacion_planner.html)

Se construyó un prototipo HTML que sirvió como prueba de concepto. Estos son sus problemas identificados que la aplicación real debe corregir:

**1. Mejora hardcodeada:** el prototipo asume `1 segundo de mejora por microciclo` sin importar la prueba, la carga semanal ni el nivel del atleta. La aplicación real debe calcular la mejora esperada basada en la distancia del evento, el kilometraje del macrociclo y una curva de progresión seleccionable.

**2. Zonas de entrenamiento invertidas:** el prototipo define RI con factor 1.26–1.30 y RII con factor 1.35 sobre el tiempo meta, lo que produce que R2 sea *más lento* que R1 — ilógico. La jerarquía correcta de zonas en natación es:

| Zona | Descripción | Factor sobre tiempo meta (100m) | Velocidad relativa |
|---|---|---|---|
| R1 | Base aeróbica (recuperación activa) | ~1.35–1.40 | Más lento |
| R2 | Umbral aeróbico | ~1.25–1.30 | Moderado |
| MVO2 | VO₂ máximo / umbral anaeróbico | ~1.15–1.20 | Rápido |
| RL | Resistencia de lactato | ~1.10–1.15 | Muy rápido |
| V | Velocidad pura | ~1.05–1.10 | Máximo |

*Los factores varían según la distancia de la prueba; deben estar en un archivo de configuración separado (`config/training_zones.py`).*

**3. Sin fechas reales en eje X:** la tabla muestra número de semana, no fecha. La UI real debe mostrar `DD/MM` por semana según la fecha de inicio del macrociclo.

**4. Sin comparación real vs. esperado:** el prototipo solo proyecta. La aplicación real debe permitir ingresar el tiempo real y recalcular la curva desde ese punto.

**5. Sin T-30/T-15:** la base aeróbica es un input manual. Debe derivarse del test aeróbico registrado.

---

## Funcionalidades Principales

### 1. Planificación del Macrociclo (funcionalidad principal)

Esta es la funcionalidad central de la aplicación. Todo lo demás (T-30/T-15, comparación, simulador) alimenta o deriva de aquí.

El entrenador define:
- Prueba objetivo (25m, 50m, 100m, 200m, 400m, 800m, etc.)
- Tiempo actual del atleta (obtenido del T-30/T-15 o ingresado manualmente)
- Tiempo meta
- Duración del macrociclo (12 o 18 semanas)
- Semanas por microciclo (4 o 5)
- Kilometraje total del macrociclo
- Curva de progresión (lineal, exponencial, logarítmica, sigmoidal)
- Fecha de inicio

El sistema calcula automáticamente para **cada semana**:
- Fecha real (DD/MM) — usada en el eje X de todos los gráficos
- Tiempo esperado en la prueba objetivo
- Mejora semanal requerida (en segundos y %)
- Parcial aeróbico objetivo (base R1 esperada)
- Kilómetros planificados
- Fase del macrociclo (Base / Construcción / Pico / Descenso)
- Zonas de entrenamiento derivadas del tiempo esperado esa semana

**Motor de progresión:** la mejora NO es lineal por defecto ni fija en 1s/microciclo. Se calcula distribuida a lo largo de las semanas según la curva seleccionada y el porcentaje de mejora total relativo a la prueba y kilometraje. El resultado es un plan semana a semana donde la curva refleja la fisiología real del entrenamiento.

---

### 2. Módulo T-30 / T-15 — Base Aeróbica

El T-30 y T-15 son tests de esfuerzo donde el atleta nada 30 o 15 repeticiones de 100m (R1) y se registra el tiempo de cada parcial. El promedio de esos parciales define la **base aeróbica actual** del atleta, que es el punto de partida para todo el macrociclo.

**Flujo del módulo:**

1. El entrenador selecciona el atleta, la fecha y el tipo de test (T-30 o T-15).
2. Ingresa el tiempo de cada repetición (R1×100m) en formato `mm:ss.cc`.
3. El sistema calcula automáticamente:
   - Promedio de los parciales → **base aeróbica**.
   - Desviación estándar → consistencia del atleta.
   - Tendencia dentro del test (¿se cae o se mantiene?).
4. La base aeróbica queda asociada al macrociclo y sirve como tiempo de partida para el motor de progresión.

**Visualización:**

- Gráfico de línea con los parciales del test en el eje Y y el número de repetición en el eje X.
- Línea horizontal de promedio superpuesta.
- Si existe un test anterior, se muestra la curva comparativa (test actual vs. test anterior) para visualizar la mejora de la base aeróbica.
- El eje X del gráfico de progresión semanal del macrociclo muestra la **fecha de cada semana** (no solo el número).

**Recálculo dinámico:**

- El entrenador puede ingresar el tiempo aeróbico actual del atleta y compararlo contra el tiempo esperado según el plan.
- El sistema indica si el atleta va **adelantado, dentro del plan o atrasado**.
- Si el tiempo actual difiere del proyectado, el motor recalcula la curva de progresión restante y ajusta los parciales esperados semana a semana.

**Separación de responsabilidades (modularización):**

- `services/t30_t15_service.py` — lógica de cálculo del test (promedio, desviación, tendencia).
- `charts/t30_chart.py` — gráfico de parciales del test.
- `charts/aerobic_comparison_chart.py` — gráfico comparativo entre tests.
- `database/repositories/aerobic_test_repository.py` — acceso a datos del test.
- `ui/aerobic_test_view.py` — vista de ingreso y visualización del test.

Ningún archivo debe superar las ~300 líneas. Si una clase crece, se extrae a un módulo aparte.

**Tabla de base de datos:**

```sql
CREATE TABLE aerobic_tests (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER NOT NULL,
    macrocycle_id INTEGER,
    test_type TEXT NOT NULL,       -- 'T30' o 'T15'
    test_date DATE NOT NULL,
    repetitions INTEGER NOT NULL,  -- 30 o 15
    avg_time REAL,                 -- promedio en segundos
    std_dev REAL,                  -- desviación estándar
    notes TEXT,
    created_at DATETIME
);

CREATE TABLE aerobic_test_splits (
    id INTEGER PRIMARY KEY,
    aerobic_test_id INTEGER NOT NULL,
    rep_number INTEGER NOT NULL,   -- 1..30 o 1..15
    split_time REAL NOT NULL       -- tiempo en segundos
);
```

---

### 3. Gestión de Atletas
- Crear, editar, eliminar y consultar atletas.
- Datos: nombre, edad, sexo, peso, estatura, especialidad.

### 4. Gestión de Macrociclos (CRUD)
- Crear, editar, duplicar y finalizar macrociclos.
- Duración: 12 o 18 semanas, divididas en microciclos de 4–5 semanas.
- Datos: nombre, fechas, semanas, kilometraje total, evento objetivo, tiempo objetivo.

### 5. Planificación Semanal Automática
Dado un macrociclo, el sistema genera automáticamente para cada semana:
- Kilómetros planificados.
- Mejora esperada (%).
- Tiempo esperado en prueba objetivo.
- Parcial aeróbico objetivo.
- Nivel de intensidad y carga.

### 6. Registro de Resultados Reales
- Fecha, distancia, estilo, tiempo real, fatiga percibida, observaciones.

### 7. Comparación de Rendimiento
- Tiempo esperado vs. tiempo real.
- Diferencia absoluta y porcentual.
- Estado: **Adelantado / Dentro del plan / Atrasado**.

### 8. Simulador de Escenarios
- El entrenador puede modificar semanas, kilómetros, tiempo meta y curva de mejora.
- La app recalcula en tiempo real tiempos semanales, curva y predicción final.

---

## Módulo Matemático

Motor de cálculo independiente que incluye:

- **Conversión de tiempos**: `1:05.32` ↔ `65.32 seg`.
- **Mejora total**: diferencia entre tiempo actual y tiempo meta, en segundos y porcentaje.
- **Mejora semanal requerida**: distribución de la mejora total en N semanas.
- **Curvas de progresión** (seleccionables):
  - *Lineal*: mejora constante por semana.
  - *Exponencial*: mejoras rápidas al inicio.
  - *Logarítmica*: mejoras decrecientes.
  - *Sigmoidal*: lentas → rápidas → lentas.
- **Predicción de tiempo final**: basada en tiempo actual, semanas, kilómetros y curva seleccionada.

---

## Base de Datos

### `athletes`
```sql
CREATE TABLE athletes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER,
    gender TEXT,
    weight REAL,
    height REAL,
    specialty TEXT,
    created_at DATETIME
);
```

### `macrocycles`
```sql
CREATE TABLE macrocycles (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER,
    name TEXT,
    start_date DATE,
    end_date DATE,
    weeks INTEGER,
    goal_event TEXT,
    goal_time REAL,
    total_km REAL,
    objective TEXT
);
```

### `weekly_plan`
```sql
CREATE TABLE weekly_plan (
    id INTEGER PRIMARY KEY,
    macrocycle_id INTEGER,
    week_number INTEGER,
    planned_km REAL,
    planned_improvement_percent REAL,
    expected_time REAL,
    aerobic_target REAL,
    intensity TEXT,
    load_level TEXT
);
```

### `parcial_times`
```sql
CREATE TABLE parcial_times (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER,
    date DATE,
    distance INTEGER,
    stroke TEXT,
    real_time REAL,
    expected_time REAL,
    difference_percent REAL,
    fatigue_level INTEGER,
    notes TEXT
);
```

### `performance_predictions`
```sql
CREATE TABLE performance_predictions (
    id INTEGER PRIMARY KEY,
    athlete_id INTEGER,
    macrocycle_id INTEGER,
    week_number INTEGER,
    predicted_time REAL,
    predicted_improvement REAL,
    confidence_level REAL
);
```

---

## Interfaz y UX

- **Tema oscuro**, diseño limpio, navegación lateral.
- Gráficos interactivos, tablas filtrables.
- Inspiración visual: TrainingPeaks, Garmin Connect, Golden Cheetah (sin copiar diseños).

### Dashboard principal
Muestra: atleta seleccionado, macrociclo activo, tiempo actual vs. objetivo, progreso acumulado, porcentaje de cumplimiento, próximo parcial esperado.

### Gráficos
- **Progresión**: tiempo esperado + tiempo real + predicción.
- **Curva ideal vs. curva real**.
- **Cumplimiento semanal**: avance y porcentaje.

---

## Requisitos Técnicos

- Python 3.12+, PySide6, SQLite, SQLAlchemy, Matplotlib.
- Arquitectura MVC/MVVM.
- Type hints en todo el código.
- POO, código escalable y preparado para IA.
- **Límite de longitud por archivo**: ningún módulo debe superar ~300 líneas. Si una clase o servicio crece, se extrae a un submódulo. Esto aplica a UI, servicios, repositorios y gráficos por igual.
- **Un archivo, una responsabilidad**: cada archivo hace una sola cosa (ej. `t30_t15_service.py` solo calcula el test; `t30_chart.py` solo dibuja el gráfico del test).
- **Eje X con fechas reales**: todos los gráficos de progresión semanal deben mostrar la fecha de inicio de cada semana en el eje X (formato `DD/MM`), no solo el número de semana.

---

## Hoja de Ruta — Funcionalidades Futuras

| Fase | Funcionalidad |
|---|---|
| v2 | Exportación PDF y Excel |
| v2 | Múltiples entrenadores |
| v3 | Sincronización en nube |
| v3 | Machine Learning para predicción automática |
| v3 | Detección de sobreentrenamiento |
| v3 | Recomendación automática de cargas |
| v4 | Aplicación móvil (iOS / Android) |

---

## Fase Actual

**Planeación.** Antes de escribir código, se define la arquitectura, el modelo de datos y el motor matemático. El objetivo es construir una base sólida para una aplicación real de uso deportivo, no un prototipo académico.
