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
| Analytics (future) | Pandas, NumPy, scikit-learn, XGBoost — no ML yet, see `README.md`'s Known Limitations |
| Charts | Recharts — in use since the Wells module (`TrendChart`/`BarChart`/`HealthDistributionChart`) |

## Local development topology
- **Frontend** runs natively via Node.js (`npm run dev`, port 3000) — no container, for fast
  iteration.
- **Backend + Database** run via Docker Compose (`docker-compose.yml`): a `backend` service
  (FastAPI, port 8000) and a `db` service (`postgres:16-alpine`, port 5432). Python is not
  required on the host machine.
- The frontend talks to the backend over HTTP at `NEXT_PUBLIC_API_URL` (default
  `http://localhost:8000`).

## Auth flow
1. User submits email/password to `POST /auth/login` (OAuth2 password flow, rate-limited).
2. Backend verifies the password hash (`pwdlib`, argon2), confirms `is_active`, and issues a JWT
   (`PyJWT`).
3. Frontend stores the token (currently `localStorage` — a known limitation; httpOnly cookie
   handling is planned follow-up work, not yet implemented — see `README.md`).
4. Protected backend routes depend on `get_current_user` / `require_role(*roles)`
   (`backend/app/deps.py`) to authorize by JWT and role — this is the *only* authorization
   primitive anywhere in the codebase, applied to every module's write endpoints and to every
   Administration endpoint (including reads). See `docs/security.md`.
5. Self-service password change, forgot/reset password, and email verification are implemented
   (`POST /auth/change-password|forgot-password|reset-password|send-verification|verify-email`)
   using stateless, single-use purpose-scoped JWTs — no separate token-storage table. See
   `docs/security.md`'s "Password management & email verification" section for the full design.

## Roles
Administrator, Production Operator, Production Engineer, Maintenance Engineer, Management,
Analyst, Viewer — see `backend/app/db/seed.py` for the seeded role list. `require_role(...)` is
applied across every module's write endpoints and, uniquely, across all of Administration
(including reads) — see `docs/security.md` for the full role/permission matrix.

## Application modules (sidebar)
Dashboard, Wells, Production, Equipment, Maintenance, Production Loss, Cost & Revenue,
AI Insights, Alerts, What-If Simulator, Reports, and Administration are all fully implemented
end-to-end (frontend, backend, database, tests) — no placeholder pages remain, driven by a
single nav config (`frontend/src/config/navigation.ts`). See `README.md`'s status summary for
what each module does and `workflows/wells-module.md` for the build history of each.

## Data model
See [`data-model.md`](./data-model.md) for the table/relationship summary.
