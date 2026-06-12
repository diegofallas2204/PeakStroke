# PeakStroke — Claude Code Context

## Proyecto
Sistema de planificación y predicción de rendimiento para natación competitiva.
Hoy: aplicación web local-first para un entrenador. Mañana: SaaS multi-tenant (PWA).

## Stack
- **Backend:** FastAPI (Python 3.12+) + SQLAlchemy 2 async + SQLite (aiosqlite) + Pydantic v2
- **Frontend:** React 19 + Vite + TypeScript strict + Tailwind CSS v4
- **Estado cliente:** TanStack Query
- **Gráficos:** Recharts (tema custom) · **Animación:** GSAP · **WebGL:** Three.js
- **Iconos:** lucide-react (nunca emojis)
- **Arquitectura:** Vertical slice (feature-based) en ambos lados

## Comandos
```
# Backend (puerto 8000)
cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --port 8000

# Frontend (puerto 5173, proxy /api -> 8000)
cd frontend && npm run dev

# Tests del motor
cd backend && .venv\Scripts\python -m pytest tests/ -v

# Re-sembrar datos demo
cd backend && .venv\Scripts\python seed.py
```

## Reglas de código (NO negociables)
- Toda feature backend nueva: `backend/app/modules/<feature>/` con models.py / schemas.py / service.py / router.py
- `router.py` nunca tiene lógica de negocio — recibe, delega al service, retorna
- El motor (`backend/app/engine/`) son funciones puras: jamás importan DB ni modelos
- Módulos no se importan entre sí salvo lecturas explícitas de modelos; nunca lógica cruzada
- Ningún archivo supera ~300 líneas; si crece, extraer submódulo
- Type hints en todo Python; TypeScript strict en el frontend
- Frontend: cada página vive en `frontend/src/features/<feature>/`

## Reglas de dominio (natación)
- `pace_100m` es la unidad central de todos los cálculos de zonas
- Zonas con factores POR DISTANCIA de prueba (rangos min/max del Excel de
  pronósticos): fuente de verdad única `backend/app/engine/zones.py`
- Jerarquía de zonas (lento -> rápido): R1 > R2 > MVO2 > RL > V
- Pruebas >= 400m = Tier 1 (regla aeróbica); < 400m = Tier 2 (ventanas de velocidad)
- Eje X de TODOS los gráficos: fechas reales DD/MM, nunca números de semana
- La curva ideal (`expected_time`) nunca se modifica; los recálculos van en `recalc_time`

## Camino al SaaS (no implementado aún, diseño preparado)
- DB: cambiar `PEAKSTROKE_DATABASE_URL` a PostgreSQL (asyncpg) — el código no cambia
- Agregar módulos `auth/` (JWT + refresh rotation) y `billing/` (Stripe) según
  `../oficial/PLAN_IMPLEMENTACION.md`
- Tier guards: `core/tier_limits.py` + dependencia `require_feature()`
- Alembic para migraciones al salir de SQLite

## Archivos de referencia
- README.md — bitácora completa del proyecto
- ../oficial/PLAN_IMPLEMENTACION.md — plan de fases SaaS
- ../mockup.html — prototipo visual original (referencia, no copiar)
