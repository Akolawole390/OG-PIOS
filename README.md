# OG-PIOS — Oil & Gas Production Intelligence & Optimization System

A decision-support platform for oil & gas production: analytics, well/equipment monitoring,
predictive maintenance, anomaly detection, forecasting, production-loss and cost/revenue
analysis, alerts, what-if scenario simulation, and reporting.

**This is a decision-support tool, not a control system.** It never operates valves, chokes,
DCS/SCADA setpoints, or field equipment, and all AI/analytics output must be presented as an
estimate requiring engineering review — never a guaranteed conclusion. See `CLAUDE.md` for the
full standing guardrail.

> **Status**: first-session scaffold. Structure, auth foundation, navigation shell, and
> placeholder pages are in place; the actual analytics/AI features are not yet implemented.

## Stack
| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router) + React + TypeScript + Tailwind CSS |
| Backend | Python + FastAPI + Pydantic + SQLAlchemy |
| Database | PostgreSQL + Alembic |
| Analytics (planned) | Pandas, NumPy, scikit-learn, XGBoost |

## Prerequisites
- **Node.js** (frontend runs natively)
- **Docker Desktop** (backend + PostgreSQL run in containers)
- **Python is *not* required locally** — the backend runs entirely inside Docker.

## Setup

### 1. Backend + database
```
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.seed
```
This starts PostgreSQL and the FastAPI backend at `http://localhost:8000`
(interactive docs at `/docs`), applies migrations, and seeds the 7 roles plus one demo admin
user (`admin@ogpios.dev` / `ChangeMe123!` — change this before any real deployment).

### 2. Frontend
```
cd frontend
npm install
npm run dev
```
Visit `http://localhost:3000` — redirects to `/dashboard` inside the app shell.

## Project structure
```
OG_PIOS/
├── frontend/        # Next.js app (native, npm)
├── backend/         # FastAPI app (Docker)
├── database/        # ERD notes / ops reference (schema itself lives in backend/alembic/)
├── ml/              # stub — future analytics/ML code
├── docs/            # architecture.md, data-model.md
├── scripts/seed/    # plan for future synthetic demo-data generation
├── tests/           # reserved for future cross-stack/e2e tests
├── docker-compose.yml
├── workflows/       # WAT framework: step-by-step procedure files
├── tools/           # WAT framework: scripts/integrations
└── temp/            # WAT framework: disposable working files
```
The `workflows/` / `tools/` / `temp/` folders are a separate, general-purpose "WAT Framework"
for orchestrating Claude Code sessions in this repo — see `CLAUDE.md`. They coexist with, but
are independent of, the OG-PIOS application code above.

## Testing
```
# Backend
docker compose exec backend pytest -q

# Frontend
cd frontend && npm run test
```

## Environment variables
- `backend/.env.example` → copy to `backend/.env` for local overrides (optional — sane
  defaults are baked into `docker-compose.yml`).
- `frontend/.env.example` → copy to `frontend/.env.local` (`NEXT_PUBLIC_API_URL`).
- Never commit real `.env` files — only `.env.example` templates are tracked.

## Known limitations (this session's scaffold)
- No real production/equipment/AI data — only 7 roles + 1 demo admin user are seeded.
- Auth token is stored in `localStorage`; httpOnly cookie handling is follow-up work.
- `require_role` authorization is demonstrated but not yet applied across every module route.
- All 12 sidebar modules besides the dashboard shell are placeholder pages.
- No AI/ML models, SCADA/DCS integration, or synthetic 365-day data generation yet.
