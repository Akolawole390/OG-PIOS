# OG-PIOS Deployment Guide

## Architecture: frontend and backend deploy separately

OG-PIOS is two independently-deployable services, not one:

- **Frontend** (`frontend/`) — a Next.js 16 App Router application. This is what Vercel deploys.
- **Backend** (`backend/`) — a FastAPI application that requires a persistent PostgreSQL
  connection and a long-running process. It is **not included in the Vercel deployment** and
  cannot run as Vercel serverless functions without a substantial rework (the app depends on a
  standard long-lived DB connection pool, background rule-engine runs, and Docker Compose for
  local orchestration — none of which map onto Vercel's stateless function model as-is). There is
  no `api/` directory in this repo and none should be added to force this.

**Do not point the deployed frontend at a local backend.** The backend must be hosted somewhere
that can run a persistent Python process and reach a PostgreSQL database — e.g. Railway, Render,
Fly.io, a VM, or a container platform. Deploy it there first, then point the frontend at its
public URL via `NEXT_PUBLIC_API_URL` (see below). Running `docker compose up` locally is for
development only, never for production traffic.

## Vercel deployment (frontend only)

### Root cause of a "Ready" deployment that 404s on every route

The repository root has no `package.json` — the only one is `frontend/package.json`. If Vercel's
project **Root Directory** is left at its default (the repo root), Vercel has nothing to
framework-detect or build at that path, so the deploy reports "Ready" (the no-op build itself
doesn't error) but serves nothing at any route, including `/`.

Two equally valid fixes — pick **one**, not both:

1. **Recommended: set Root Directory in the Vercel dashboard.** Project → Settings → General →
   Root Directory → `frontend`. Save, then trigger a redeploy. Vercel's zero-config Next.js
   detection then works exactly as it would for a single-app repo; no `vercel.json` is required.
2. **Alternative: keep Root Directory at the repo root** and let the checked-in root
   `vercel.json` (already added to this repo) redirect the build into `frontend/`:
   ```json
   {
     "framework": "nextjs",
     "installCommand": "cd frontend && npm install",
     "buildCommand": "cd frontend && npm run build",
     "outputDirectory": "frontend/.next"
   }
   ```
   Use this if you'd rather not touch the dashboard setting, or if other tooling in this repo
   expects Vercel's working directory to stay at the root.

If Root Directory is set to `frontend` in the dashboard, Vercel will look for `vercel.json`
*inside* `frontend/` (which doesn't exist) and ignore the root one — the two approaches don't
conflict, but only whichever one actually matches your dashboard setting takes effect.

### Routing

This is a Next.js App Router application (server-rendered/hybrid), not a client-only SPA — it
does **not** need a catch-all rewrite for client-side routing. `/` itself is a real route
(`frontend/src/app/page.tsx`) that redirects to `/dashboard`; no rewrites or redirects section is
needed in `vercel.json` for this app to serve every page correctly once the Root Directory issue
above is resolved.

## Backend deployment (Railway)

The backend is a plain FastAPI app with no background workers, no scheduler, and no static file
serving — it's a stateless request/response API, well-suited to Railway's standard web-service
model. `backend/Dockerfile` already exists and is what Railway should build from directly (no
new Dockerfile needed).

### Root Directory

Same class of issue as the Vercel fix: the repository root has no top-level app, so when creating
the Railway service, **set its Root Directory to `backend`** (Railway service → Settings → Root
Directory). Railway then auto-detects `backend/Dockerfile` with no path ambiguity, and
`backend/railway.json` (already added) travels with it to set the correct health-check path.

### Why a health-check path must be configured explicitly

There is no root `/` route in this API-only backend (confirmed — `backend/app/main.py` has no
`@app.get("/")` handler), only `GET /health` → `{"status": "ok"}` (`backend/app/routers/health.py`,
already present, unchanged). Railway's default health-check target is `/`, which would 404 and
could make Railway consider a perfectly healthy deploy unhealthy. `backend/railway.json` sets
`deploy.healthcheckPath` to `/health` to fix this — no application code changes were needed.

### Port

Railway injects a `PORT` environment variable and expects the container to bind to it.
`backend/Dockerfile`'s `CMD` now reads `${PORT:-8000}` (falls back to 8000 only if `$PORT` isn't
set, e.g. for a manual `docker run` outside Railway) — verified locally by running the built image
with `PORT=8080` and confirming it bound to 8080. The previous hardcoded `--port 8000 --reload`
was dev-only; local Docker Compose now sets its own explicit `command:` on the `backend` service
to reproduce that exact dev behavior (hot-reload included), so nothing changed for local dev.

## Database (Railway PostgreSQL plugin)

Add Railway's PostgreSQL plugin to the project. It provisions a Postgres instance and exposes
connection details (host/port/user/password and a combined `DATABASE_URL`) as service variables
you can reference from the backend service.

**Important — dialect prefix mismatch**: Railway's Postgres plugin exposes `DATABASE_URL` as
plain `postgresql://...`. This app's SQLAlchemy engine (`backend/app/core/database.py`) requires
`postgresql+psycopg://...` — only `psycopg` (v3) is installed (`psycopg[binary]` in
`requirements.txt`), not the older `psycopg2` that a bare `postgresql://` scheme defaults to. When
setting the backend service's `DATABASE_URL` variable in Railway, **insert `+psycopg` manually**:
```
postgresql+psycopg://<user>:<password>@<host>:<port>/<database>
```
This is a one-time manual step, not a code change, so it stays visible and intentional rather than
silently rewritten.

### Migration sequence

Alembic (`backend/alembic/env.py`) reads `DATABASE_URL` directly from the environment — it only
needs that variable set and the `app` package importable; it does not require the FastAPI server
to already be running, so it can be run as a one-off Railway command against a fresh database:

1. Create the Postgres service (above) and note its connection details.
2. Set the backend service's environment variables (table below), **including a real
   `SECRET_KEY`** — `Settings`' production validator runs eagerly at import time
   (`backend/app/core/config.py`), so even running Alembic with `ENVIRONMENT=production` and the
   placeholder `SECRET_KEY` still in place will fail immediately with a clear error, before it
   ever touches the database.
3. Run `alembic upgrade head` against that `DATABASE_URL` (via `railway run alembic upgrade head`,
   or a one-off Railway shell/release command).
4. **Optional pilot seed** — only if you explicitly want the synthetic pilot dataset from
   `docs/OGPIOS_PILOT_GUIDE.md` in this environment: `railway run python -m app.db.seed_wells`
   (idempotent). Never run this automatically or by default against what's meant to be a real
   deployment.
5. Deploy/start the FastAPI service (Railway does this from the same Dockerfile once the above
   is in place).

## Environment variables

### Frontend (configure in Vercel → Project → Settings → Environment Variables)

| Variable | Purpose | Required | Where |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL the browser calls for the backend API. Falls back to `http://localhost:8000` if unset — which will silently break every API call in production, since that address only exists on each visitor's own machine, not your backend. | **Required** for a working production deploy (the app will still load without it, but no data will ever appear) | Vercel dashboard, Production (and Preview, if you want preview deployments to hit a real backend) |

No other frontend environment variables exist — confirmed by searching `frontend/src` for every
`process.env.*` reference; `NEXT_PUBLIC_API_URL` is the only one.

### Backend (configure in Railway → backend service → Variables)

| Variable | Purpose | Required | Where |
|---|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string. Must use the `postgresql+psycopg://` scheme (see Database section above) — Railway's raw plugin value uses plain `postgresql://` and needs `+psycopg` inserted manually | Required | Railway backend service variables — reference the Postgres plugin's values, with `+psycopg` added |
| `SECRET_KEY` | JWT signing key. The app refuses to start with the placeholder default when `ENVIRONMENT=production` (see `backend/app/core/config.py`) | Required in production | Railway backend service variables — generate with `openssl rand -hex 32`, never reuse the `.env.example` placeholder |
| `ALGORITHM` | JWT signing algorithm | Optional (defaults to `HS256`) | Railway backend service variables |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime | Optional | Railway backend service variables |
| `CORS_ORIGINS` | Origins allowed to call the API — must include your deployed Vercel frontend URL | Required | Railway backend service variables |
| `ENVIRONMENT` | `development` or `production` — gates debug-only response fields and the secret-key check | Required | Railway backend service variables |
| `AI_PROVIDER` | `none` (default, deterministic rule-based only) or one of `openai\|anthropic\|google\|local` | Optional | Railway backend service variables |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | Matching key for the selected AI provider | Required only if that provider is selected | Railway backend service variables |
| `LOCAL_AI_BASE_URL` / `LOCAL_AI_MODEL` | Config for a self-hosted/local AI provider | Required only if `AI_PROVIDER=local` | Railway backend service variables |
| `RESET_TOKEN_EXPIRE_MINUTES` / `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES` | Password reset / email verification token lifetimes | Optional | Railway backend service variables |
| `FRONTEND_URL` | Used to build links inside password-reset/verification emails — should be the deployed Vercel URL in production | Required if using the mail flow in production | Railway backend service variables |
| `MAIL_PROVIDER` | `console` (default) only logs emails — **must not be used in a real deployment**; no real mail provider is implemented yet | Required to change before real users rely on password reset | Railway backend service variables |

Railway also injects `PORT` automatically (see Port section above) — do not set this yourself.

Never commit real values for any of the above — `backend/.env.example` documents names only, and
`.env` is git-ignored. Set actual secrets directly in each platform's environment-variable UI.

## Full deployment sequence

1. Create the PostgreSQL service on Railway.
2. Configure the backend service's environment variables (table above), including `DATABASE_URL`
   with `+psycopg` inserted and a real `SECRET_KEY`.
3. Run migrations (`alembic upgrade head`) against that database — see Migration sequence above.
4. Deploy the FastAPI backend service on Railway (Root Directory = `backend`, per above).
5. Verify `GET /health` on the backend's Railway URL returns `{"status": "ok"}`.
6. Note the backend's Railway-assigned public URL.
7. In Vercel: set `NEXT_PUBLIC_API_URL` to that backend URL, and set Root Directory to `frontend`
   **or** rely on the root `vercel.json` (pick one, see above).
8. Redeploy the frontend on Vercel.
9. Test frontend → backend communication: visit the deployed root URL, confirm it loads and
   redirects to `/login`/`/dashboard`, and confirm a real API-backed page (e.g. Wells) shows data
   instead of an empty/error state. Also set `CORS_ORIGINS` on the backend to include the exact
   Vercel frontend URL, or these calls will be rejected by the browser.
