# OG-PIOS Architecture

## Overview
OG-PIOS is a decision-support platform for oil & gas production intelligence: production
analytics, well/equipment monitoring, predictive maintenance, anomaly detection, forecasting,
production-loss and cost/revenue analysis, alerts, what-if scenario simulation, and reporting.

It is explicitly **not** a control system — it never operates valves, chokes, DCS/SCADA
setpoints, or field equipment. All AI/analytics output is framed as an estimate requiring
engineering review, never a guaranteed conclusion. See the guardrail section in the root
`CLAUDE.md`.

## Stack
| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router) + React + TypeScript + Tailwind CSS |
| Backend | Python + FastAPI + Pydantic + SQLAlchemy |
| Database | PostgreSQL + Alembic migrations |
| Analytics (future) | Pandas, NumPy, scikit-learn, XGBoost |
| Charts (future) | Recharts or Plotly |

## Local development topology
- **Frontend** runs natively via Node.js (`npm run dev`, port 3000) — no container, for fast
  iteration.
- **Backend + Database** run via Docker Compose (`docker-compose.yml`): a `backend` service
  (FastAPI, port 8000) and a `db` service (`postgres:16-alpine`, port 5432). Python is not
  required on the host machine.
- The frontend talks to the backend over HTTP at `NEXT_PUBLIC_API_URL` (default
  `http://localhost:8000`).

## Auth flow (current scaffold)
1. User submits email/password to `POST /auth/login` (OAuth2 password flow).
2. Backend verifies the password hash (`pwdlib`, argon2) and issues a JWT (`PyJWT`).
3. Frontend stores the token (currently `localStorage` — a scaffold shortcut; httpOnly cookie
   handling is planned follow-up work, not yet implemented).
4. Protected backend routes depend on `get_current_user` / `require_role(*roles)`
   (`backend/app/deps.py`) to authorize by JWT and role.

## Roles
Administrator, Production Operator, Production Engineer, Maintenance Engineer, Management,
Analyst, Viewer — see `backend/app/db/seed.py` for the seeded role list. Role-based
authorization is scaffolded (`require_role`) but not yet applied across every module route.

## Application modules (sidebar)
Dashboard, Wells, Production, Equipment, Maintenance, Production Loss, Cost & Revenue,
AI Insights, Alerts, What-If Simulator, Reports, Administration — each currently a placeholder
page (`frontend/src/app/(app)/*/page.tsx`) driven by a single nav config
(`frontend/src/config/navigation.ts`).

## Data model
See [`data-model.md`](./data-model.md) for the table/relationship summary.
