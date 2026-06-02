# PeakStroke — Claude Code Context

## Proyecto

Sistema de planificación y predicción de rendimiento para natación competitiva.
Aplicación de escritorio (Python + PySide6) para entrenadores y nadadores.

Ver [ENUNCIADO_PEAKSTROKE.md](ENUNCIADO_PEAKSTROKE.md) para la especificación completa.
Ver [BITACORA.md](BITACORA.md) para decisiones técnicas y reglas empíricas validadas.
Ver [MAPA_SISTEMA.md](MAPA_SISTEMA.md) para el glosario de archivos — qué hace cada uno, cuándo tocarlo y cómo fluyen los datos.

## Stack

- **Lenguaje:** Python 3.12+
- **UI:** PySide6 (Qt6)
- **Base de datos:** SQLite + SQLAlchemy ORM
- **Gráficos:** Matplotlib integrado en PySide6
- **Arquitectura:** MVC/MVVM en capas, principios SOLID

## Comandos

```bash
python main.py              # arrancar la aplicación
python test_engine.py       # correr pruebas del motor de progresión
pip install -r requirements.txt  # instalar dependencias
```

## Reglas del proyecto

- Ningún archivo supera ~300 líneas. Si una clase crece, se extrae.
- Un archivo = una responsabilidad.
- Type hints en todo el código.
- La UI nunca hace cálculos directamente — todo pasa por servicios.
- `pace_100m` es la unidad central de referencia en todos los cálculos de zonas.
- Zonas de entrenamiento: R1 (×1.375), R2 (×1.275), MVO2 (×1.175), RL (×1.125), V (×1.075).
- Eje X de todos los gráficos: fechas reales `DD/MM`, no números de semana.
- Fuente de verdad de zonas: `app/config/training_zones.py`.

## Stack (actualizado v1.0.0)

- **Backend:** FastAPI + PostgreSQL + SQLAlchemy async + Alembic
- **Frontend:** React + Vite + TypeScript + Tailwind CSS + PWA
- **Estado cliente:** TanStack Query + Zustand
- **Gráficos:** Recharts
- **Arquitectura:** Vertical slice (feature-based, no layer-based)

## Comandos

```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Migración de DB (después de cambiar modelos)
cd backend && alembic revision --autogenerate -m "descripcion" && alembic upgrade head
```

## Reglas del proyecto

- Ningún archivo supera ~300 líneas. Si una clase crece, se extrae.
- Un archivo = una responsabilidad.
- Type hints en todo el código Python. TypeScript strict en el frontend.
- La UI nunca hace cálculos directamente — todo pasa por el backend.
- `pace_100m` es la unidad central de referencia en todos los cálculos de zonas.
- Zonas de entrenamiento: R1 (×1.375), R2 (×1.275), MVO2 (×1.175), RL (×1.125), V (×1.075).
- Eje X de todos los gráficos: fechas reales `DD/MM`, no números de semana.
- Fuente de verdad de zonas: `backend/app/modules/training_plans/progression_engine.py` → `ZONE_FACTORS`.
- Fuente de verdad de tiers: `backend/app/core/tier_limits.py` → `TIER_LIMITS`.
- Los módulos NO se importan entre sí — solo importan de `core/`.
- `router.py` nunca tiene lógica de negocio — solo delega al service.

## Flujo de trabajo con gstack

El flujo de desarrollo para este proyecto sigue el ciclo gstack:

```
/office-hours → /plan-eng-review → implementar → /review → /cso → /ship
```

Para diseño de UI:
```
/design-consultation → /design-shotgun → /design-html
```

**Al terminar cualquier sesión importante:** ejecutar `/context-save` para actualizar `MAPA_SISTEMA.md` y guardar el estado del proyecto.

## gstack skills disponibles

<!-- gstack:start -->
| Skill | Propósito |
|-------|-----------|
| `/office-hours` | Validar suposiciones antes de codear |
| `/autoplan` | Generar plan de implementación completo |
| `/plan-ceo-review` | Validación estratégica de alcance |
| `/plan-eng-review` | Arquitectura, diagramas, casos edge |
| `/design-consultation` | Definir sistema de diseño |
| `/design-shotgun` | Generar 4-6 variantes de mockup |
| `/design-html` | Convertir mockup a HTML de producción |
| `/review` | Code review automático — bugs de producción |
| `/cso` | Auditoría de seguridad OWASP + STRIDE |
| `/investigate` | Análisis de causa raíz en bugs |
| `/spec` | Escribir especificación técnica detallada |
| `/health` | Dashboard de salud del proyecto |
| `/retro` | Retrospectiva de sprint |
<!-- gstack:end -->

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec

## Estructura actual del proyecto

```
PeakStroke/
├── main.py                          # (pendiente)
├── app/
│   ├── config/
│   │   └── training_zones.py        # factores de zona (fuente de verdad)
│   ├── services/
│   │   └── progression_engine.py    # motor de progresión
│   └── utils/
│       └── time_utils.py            # conversión de tiempos
├── test_engine.py                   # pruebas del motor
├── mockup.html                      # prototipo HTML de referencia
├── ENUNCIADO_PEAKSTROKE.md
└── BITACORA.md
```
