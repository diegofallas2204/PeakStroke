# PeakStroke

Sistema de planificación y predicción de rendimiento para natación competitiva.
Web-first PWA · FastAPI + React + Vite · SaaS por suscripción

## Arrancar en desarrollo

### Backend
```bash
cd backend
cp .env.example .env      # editar con tus credenciales de PostgreSQL
pip install -r requirements.txt
alembic upgrade head      # crear tablas en la DB
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev               # http://localhost:5173
```

### API Docs
Una vez corriendo el backend: http://localhost:8000/docs

## Estructura
```
backend/
  app/
    core/           → config, DB, seguridad, tier_limits, dependencies
    modules/
      auth/         → registro, login, JWT
      training_plans/ → macrociclos, atletas, plan semanal, T-30/T-15
      billing/      → Stripe (próximamente)
  alembic/          → migraciones de base de datos

frontend/
  src/
    features/
      auth/               → login/registro
      training-plans/     → macrociclos, tabla del equipo, gráficos
    shared/
      lib/        → axios configurado
      hooks/      → useAuthStore (Zustand)
```

## Próximas features (v2)
- Módulo billing con Stripe (tiers Free/Coach/Club)
- Exportación PDF del plan
- Gráfico de carga ATL/CTL/TSB
- Dashboard del entrenador
