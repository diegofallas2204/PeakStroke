# PeakStroke — Performance Planner para Natación Competitiva

Sistema de planificación de macrociclos y predicción de rendimiento para
entrenadores de natación de alto rendimiento. Local-first hoy, diseñado para
convertirse en SaaS sin reescrituras.

![Stack](https://img.shields.io/badge/FastAPI-Python_3.12+-009688) ![Frontend](https://img.shields.io/badge/React_19-TypeScript_strict-3178c6) ![UI](https://img.shields.io/badge/Tailwind_v4-GSAP_·_Three.js-8b5cf6)

---

## 1. Qué hace el sistema

PeakStroke responde las preguntas centrales de un entrenador:

- *¿Es realista bajar de 1:07.8 a 1:04.5 en 12 semanas?* → **Motor de factibilidad**
- *¿Qué tiempo debo exigir cada semana y en cada zona?* → **Plan semanal automático**
- *¿El atleta va adelantado o atrasado respecto al plan?* → **Comparación real vs. esperado**
- *¿Cuál es la base aeróbica real del atleta?* → **Módulo T-30 / T-15 / CSS**
- *¿Qué pasa si cambio semanas, kilómetros o la meta?* → **Simulador de escenarios**

### Módulos funcionales

| Módulo | Qué hace |
|---|---|
| **Dashboard** | Pulso del macrociclo activo: semana actual, fases, estados del equipo, cumplimiento de registro, desviación media, próxima competencia, progresión planificada vs. real. |
| **Macrociclos** | Asistente de 3 pasos: configuración (12–18 semanas, micros 3:1 o 4:1, km, curva) → fases configurables con colores → resumen. Competencias marcadas por semana. Relación 1:N con atletas. |
| **Atletas** | CRUD con perfil deportivo: especialidad (velocidad / medio fondo / fondo / aguas abiertas), estilo principal, antropometría. |
| **Base aeróbica** | 5 modos de ingreso: T-30, T-15, test personalizado N×D (ej. 12×400 → el sistema normaliza cada parcial a /100m), CSS 400/50 (Wakayoshi) e ingreso directo. Calcula promedio, desviación estándar y tendencia; gráfico de parciales con comparativa contra el test anterior. |
| **Plan semanal** | La tabla central: fecha real (DD/MM), fase, km, tiempo esperado, pace/100, proyección recalculada, tiempo real editable inline, diferencia y estado. Panel de zonas por semana con km sugeridos por especialidad. Soporta **parones** (lesión/vacaciones): la semana se congela y la mejora restante se redistribuye. |
| **Tabla del equipo** | Todos los atletas en una semana dada con sus tiempos objetivo por zona (R1–V) y km sugeridos. Gráfico de progreso colapsable. Navegación entre semanas. |
| **Comparación** | Curva ideal vs. proyección ajustada vs. puntos reales, desviación semanal en barras, resumen de estados. |
| **Simulador** | Stateless: modifica parámetros y el motor recalcula en vivo. Banner de factibilidad con tier fisiológico, ventanas realistas, semanas sugeridas si el objetivo es agresivo, comparación de las 4 curvas y plan completo. |

---

## 2. El motor de predicción (valor de negocio)

Vive en `backend/app/engine/` como **funciones puras** (sin DB, sin HTTP):
testeable, portable y ajustable de forma aislada. 33 tests unitarios lo cubren.

### 2.1 Zonas de entrenamiento — `zones.py`
Factores **por banda de distancia** derivados de la calculadora real de
entrenadores (`pronosticos PABLO belen.xlsx`) y validados contra la teoría
(Maglischo, Fernandes et al.). Cada zona tiene rango min–max sobre el
`pace_100m` del tiempo esperado:

| Prueba | R1 | R2 | MVO2 | RL | V |
|---|---|---|---|---|---|
| ≤50m | 1.26–1.35 | 1.20–1.25 | 1.15–1.20 | 1.06–1.12 | 1.02–1.05 |
| 75–100m | 1.21–1.30 | 1.15–1.20 | 1.15–1.20 | 1.06–1.12 | 1.02–1.05 |
| 150–200m | 1.20–1.30 | 1.12–1.18 | 1.10–1.15 | 1.05–1.10 | 1.02–1.05 |
| 300–500m | 1.15–1.20 | 1.10–1.12 | 1.08–1.10 | — | — |
| 600–1000m | 1.11–1.15 | 1.05–1.10 | 1.05–1.10 | — | — |
| ≥1500m | 1.10–1.12 | 1.05–1.10 | — | — | — |

A mayor distancia los factores se comprimen (el ritmo de competencia ya es casi
aeróbico) y las zonas de velocidad dejan de prescribirse. Además define la
**distribución de km por zona según especialidad** (Seiler 80/20, Issurin):
un fondista acumula ~70% en R1; un velocista reparte hacia RL/V.

### 2.2 Curvas de progresión — `curves.py`
Cuatro curvas normalizadas (f(0)=0, f(1)=1) que distribuyen la mejora total:
**sigmoidal** (adaptación → aceleración → meseta, la recomendada), lineal,
exponencial y logarítmica.

### 2.3 Distribución de kilometraje — `km_distribution.py`
Combina la envolvente del macrociclo (rampa hasta ~70% del ciclo + taper de
40–60%) con la **onda de supercompensación 3:1 / 4:1** (Bompa): tres o cuatro
semanas de carga progresiva y una de descarga. Normalizado al total exacto.

### 2.4 Factibilidad — `feasibility.py`
Dos regímenes fisiológicos:

- **Tier 1 (≥400m)**: mejora gobernada por la base aeróbica. Regla:
  `1 s/micro × factor_distancia × factor_estilo × ratio_aeróbico`.
- **Tier 2 (<400m)**: ventanas de mejora realista en s/microciclo por
  combinación distancia+estilo (ej. 100 mariposa: 0.30–0.50 s/micro).

Veredictos: `ok` / `warning` (hasta 1.5× el techo) / `aggressive` — en cuyo
caso calcula **cuántas semanas necesitaría** el objetivo.

### 2.5 Progresión y recálculo — `progression.py`
- `generate_plan()`: semana a semana con **fecha real (lunes, DD/MM)**, tiempo
  esperado, pace/100, zonas, km y fase.
- `recalculate_remaining()`: ancla la curva al último tiempo real y reproyecta
  las semanas restantes hacia la meta. Las semanas con parón no progresan y la
  mejora se redistribuye entre las activas.
- La curva ideal (`expected_time`) **nunca se modifica**; el recálculo vive en
  `recalc_time`. Así el gráfico muestra ambas: plan original y proyección viva.
- Estados con tolerancia ±0.4%: adelantado / en plan / atrasado.

### 2.6 Base aeróbica — `aerobic.py`
- `analyze_splits()`: normaliza cualquier test N×D a parciales /100m; promedio
  (= base aeróbica), desviación estándar (consistencia) y tendencia por
  regresión lineal (mejora / estable / se cae).
- `css_from_400_50()`: Critical Swim Speed de Wakayoshi: `350/(T400−T50)`.

---

## 3. Arquitectura

```
peakstroke/
├── backend/                      FastAPI · SQLAlchemy async · SQLite
│   ├── app/
│   │   ├── main.py               registra routers, CORS, lifespan (init DB)
│   │   ├── core/
│   │   │   ├── config.py         settings (env PEAKSTROKE_*, URL de DB)
│   │   │   └── database.py       engine async, get_db, Base
│   │   ├── engine/               ★ MOTOR PURO (sin DB) — 7 módulos
│   │   │   ├── time_utils.py     'm:ss.cc' <-> segundos
│   │   │   ├── zones.py          factores por distancia + mix por especialidad
│   │   │   ├── curves.py         4 curvas de progresión
│   │   │   ├── km_distribution.py envolvente + onda 3:1
│   │   │   ├── feasibility.py    tiers, ventanas, semanas sugeridas
│   │   │   ├── progression.py    generate_plan / recalculate / status
│   │   │   └── aerobic.py        splits, tendencia, CSS
│   │   └── modules/              ★ VERTICAL SLICES
│   │       ├── swimmers/         models · schemas · service · router
│   │       ├── plans/            macrociclos, fases, competencias,
│   │       │                     athlete_plans, athlete_events, weekly_plans
│   │       ├── aerobic_tests/    tests + splits
│   │       ├── dashboard/        agregaciones (summary, team-week)
│   │       └── simulator/        stateless, solo invoca el motor
│   ├── tests/test_engine.py      33 tests del motor
│   ├── seed.py                   datos demo realistas
│   └── requirements.txt
│
└── frontend/                     React 19 · Vite · TS strict · Tailwind v4
    └── src/
        ├── lib/                  api.ts (cliente tipado) · types.ts · format.ts · constants.ts
        ├── hooks/                usePageEnter (GSAP stagger) · useCountUp
        ├── components/
        │   ├── layout/           Sidebar (nav animada + chip de macro) · PageHeader
        │   ├── ui/               Card, StatCard (count-up), RingGauge (SVG+GSAP),
        │   │                     Modal, Badge, EventPicker, ZoneTag, EmptyState
        │   ├── charts/           tema Recharts + ProgressionChart (Y invertido)
        │   └── three/            WaveBackground (shader GLSL de ondas)
        └── features/             ★ espejo del backend
            ├── dashboard/  ├── plans/  ├── swimmers/  ├── aerobic/
            ├── weekly/     ├── team/   ├── comparison/ └── simulator/
```

### Principios aplicados
- **Vertical slice**: cada feature es autocontenida (modelos→API→UI). Agregar
  una feature nueva = una carpeta nueva en cada lado, sin tocar las demás.
- **Motor puro**: la lógica de negocio de mayor valor no conoce la
  infraestructura. Se puede ajustar, versionar y testear sin levantar nada.
- **Router sin lógica**: los endpoints reciben, delegan al service y retornan.
- **Una responsabilidad por archivo**, ningún archivo >300 líneas.
- **Fuente de verdad única**: zonas en `engine/zones.py`, catálogos UI en
  `lib/constants.ts`.

### API (REST, versionada `/api/v1`)
```
GET/POST/PUT/DELETE  /swimmers
GET/POST/PATCH/DELETE /plans            (+ fases y competencias embebidas)
POST/DELETE          /plans/{id}/athletes          genera el plan semanal
GET                  /plans/events/{id}/weeks       semanas + zonas + estado
PATCH                /plans/weeks/{id}              tiempo real / parón → recalcula
GET/POST/DELETE      /aerobic-tests   + POST /analyze (preview sin persistir)
GET                  /dashboard/summary · /dashboard/team-week
POST                 /simulator/run                 motor en vivo, sin persistencia
GET                  /health
```
Documentación interactiva: `http://localhost:8000/docs` (Swagger automático).

---

## 4. Experiencia de usuario

Diseño basado en las referencias visuales del proyecto (`dashboard.jpg`,
`analisis ui.jpg`, `estética de gráficos.jpg`):

- **Tema oscuro profundo** (#06070b) con tarjetas glaseadas, bordes sutiles y
  acentos violeta / cian / magenta / ámbar / menta.
- **Tipografía**: Space Grotesk (display y números), Inter (texto),
  JetBrains Mono (tiempos — tabular).
- **Cero emojis**: iconografía SVG profesional (lucide) en toda la app.
- **Three.js**: fondo WebGL con shader GLSL propio — un campo de puntos
  ondulante (la superficie de la piscina) con gradiente violeta→cian, máscara
  radial y pausa automática cuando la pestaña no es visible.
- **GSAP**: entrada de páginas con stagger fade-up, count-up en métricas,
  gauge circular animado con glow, transiciones de hover con elevación.
- **Gráficos custom** (Recharts tematizado): eje Y invertido para tiempos
  (menor = más arriba), fechas reales DD/MM en X, gradientes, líneas punteadas
  para proyección, puntos reales con glow, tooltips con estética del sistema.
- **Interacciones de entrenador**: tiempo real editable inline (Enter guarda,
  Esc cancela), factibilidad en vivo mientras se escribe la meta, navegación
  de semanas, panel de zonas al hacer click en una fila.

---

## 5. Cómo correr el proyecto

### Requisitos
- Python 3.12+ · Node.js 20+

### Backend (terminal 1)
```powershell
cd peakstroke\backend
python -m venv .venv          # solo la primera vez
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python seed.py  # datos demo (opcional, recomendado)
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

### Frontend (terminal 2)
```powershell
cd peakstroke\frontend
npm install                   # solo la primera vez
npm run dev
```

Abrir **http://localhost:5173**. El proxy de Vite enruta `/api` → `:8000`.

### Tests
```powershell
cd peakstroke\backend
.venv\Scripts\python -m pytest tests/ -v
```

---

## 6. Datos demo (seed)

`python seed.py` repuebla la base con un escenario realista:
8 atletas (4 especialidades, 5 estilos), macrociclo activo de 12 semanas
cursando la **semana 7** (fase Construcción), 11 pruebas objetivo, tiempos
reales de las semanas 1–6 con sesgos por atleta (adelantados/atrasados),
2 competencias (una principal en semana 12) y 12 tests aeróbicos:
T-30 iniciales, T-15 de control, un 12×400 y un CSS.

---

## 7. Fundamentos teóricos aplicados

Del documento `macrociclos_natacion_investigacion.pdf`:

| Concepto | Fuente | Dónde se aplica |
|---|---|---|
| CSS = 350/(T400−T50) | Wakayoshi et al. (1992) | `engine/aerobic.py`, modo CSS del módulo de tests |
| Periodización y fases | Matveyev (1964), Bompa & Haff (2009) | Fases por defecto Base/Construcción/Pico/Descenso |
| Supercompensación 3:1 | Bompa & Haff (2009) | Onda de microciclo en `km_distribution.py` |
| Taper 40–60% de volumen | Mujika | Envolvente final del kilometraje |
| Distribución por especialidad | Seiler (2010), Issurin (2008) | `SPECIALTY_ZONE_MIX` en `engine/zones.py` |
| Dominio aeróbico por prueba | Gastin (2001), Maglischo (2011) | `AEROBIC_RATIO` del análisis de factibilidad |
| Factores de zona por distancia | Calculadora de entrenadores (Excel) | `engine/zones.py` (tabla §2.1) |

---

## 8. Decisiones técnicas (bitácora)

| Decisión | Razón |
|---|---|
| **SQLite en lugar de PostgreSQL** (por ahora) | Local-first sin fricción de instalación. SQLAlchemy async hace que migrar a Postgres sea cambiar una URL de entorno. Alembic se incorporará en ese momento. |
| **Sin auth/billing todavía** | El usuario es un solo entrenador local. La arquitectura vertical-slice deja los slots `auth/` y `billing/` listos según `oficial/PLAN_IMPLEMENTACION.md` (JWT + refresh rotation + Stripe + tier guards). |
| **Motor como funciones puras** | El valor de negocio es la precisión de los cálculos: debe poder ajustarse y testearse sin tocar API ni UI. |
| **`expected_time` inmutable + `recalc_time`** | El entrenador necesita ver el plan original y la proyección viva a la vez; sobrescribir destruiría la trazabilidad. |
| **Factores de zona por distancia (no globales)** | El mockup usaba un factor único por zona; el Excel real de entrenadores demuestra que varían fuertemente con la distancia. Se modeló como bandas con rango min–max. |
| **Recharts sobre canvas custom** | Declarativo, tematizable al nivel de las referencias, y mantiene los gráficos como componentes React testables. |
| **Three.js solo decorativo** | Un shader de ondas sutil (puntos, no geometría pesada), con `pixelRatio` limitado y pausa en `visibilitychange`: estética sin costo de batería. |
| **TanStack Query** | Caché e invalidación automática: registrar un tiempo real refresca semanas y dashboard sin estado manual. |
| **Tailwind v4 con `@theme`** | Design tokens centralizados en CSS nativo; los componentes usan utilidades + clases semánticas (.card, .btn, .field). |

---

## 9. Roadmap sugerido

| Fase | Feature |
|---|---|
| v0.2 | Carga interna **TRIMP Edwards** + ATL/CTL/TSB (detección de sobreentrenamiento) — la investigación ya lo recomienda |
| v0.2 | Exportación PDF/Excel del plan semanal para imprimir en la piscina |
| v0.2 | Registro de tiempos por zona entrenada (no solo prueba objetivo) |
| v0.3 | Auth multi-entrenador (JWT) + PostgreSQL + Alembic |
| v0.3 | Billing Stripe con tiers Free/Coach/Club (plan ya documentado) |
| v0.3 | PWA instalable (vite-plugin-pwa) para uso en la piscina |
| v0.4 | Sugerencias automáticas de ajuste de carga cuando el atleta se desvía |
| v0.4 | ML sobre el histórico de tests para afinar las ventanas de mejora |
| v1.0 | App móvil (React Native, reutiliza el cliente API tipado) |

---

*Construido con Claude Code (Fable 5) · Junio 2026*
