# OG-PIOS — Oil & Gas Production Intelligence & Optimization System

A decision-support platform for oil & gas production: analytics, well/equipment monitoring,
predictive maintenance, anomaly detection, forecasting, production-loss and cost/revenue
analysis, alerts, what-if scenario simulation, and reporting.

**This is a decision-support tool, not a control system.** It never operates valves, chokes,
DCS/SCADA setpoints, or field equipment, and all AI/analytics output must be presented as an
estimate requiring engineering review — never a guaranteed conclusion. See `CLAUDE.md` for the
full standing guardrail.

> **Status**: scaffold + all eleven planned modules working. Structure, auth foundation, navigation shell,
> and placeholder pages are in place. **Wells** (list/search/filter/sort, add/edit, detail
> dashboard with production/pressure/water-cut trends, downtime and maintenance summaries),
> **Production** (records CRUD with search/filter/date-range, CSV import with preview/confirm,
> analytics charts, KPIs, per-well targets, admin-configurable BOE factor, a fleet-wide
> dashboard), **Equipment** (inventory CRUD across well/facility/standalone equipment,
> transparent rule-based health scoring with a factor-by-factor breakdown, sensor-reading
> ingestion, maintenance/downtime history, a fleet-wide dashboard with health-band distribution),
> **Maintenance** (work orders with priority/scheduling/cost breakdown/technician assignment, a
> dashboard with cost/downtime/status charts, a rule-based overdue/due-today/upcoming schedule
> view, and a foundational MTBF/MTTR/availability reliability calculator on the Equipment detail
> page), **Production Loss** (auto-computed lost-volume and estimated-financial-impact
> records linking Well → Production → Equipment → Maintenance → Failure/Downtime, a dashboard
> with category/well/equipment/field/time-trend charts, and commodity-price-driven revenue
> impact), **Cost & Revenue** (operating cost CRUD scoped to field/facility/well/equipment,
> a management/analyst economics dashboard connecting live commodity-price-driven revenue,
> operating cost, maintenance cost, and Production Loss's financial impact into an estimated
> operating margin, unit economics per bbl/BOE, field/well economics ranking, trend charts, and
> rule-based cost alerts — all money grouped strictly by currency (USD/NGN), never blended
> across an invented exchange rate), **Alerts** (a centralized, rule-based Alert & Event
> Intelligence system covering 22 alert types across Production/Equipment/Maintenance/
> Production Loss/Economics, with configurable thresholds, a documented severity rubric,
> deduplication with an update-in-place lifecycle, an audit trail of every status change, and
> an Alert Center dashboard/list/detail UI with Acknowledge/Investigate/Resolve/Dismiss actions),
> and **AI Insights** (an evidence-based analysis engine — not a chatbot — generating 24
> structured, source-cited insight types across Production/Equipment/Maintenance/Production
> Loss/Economics/Cross-Domain, with fact-vs-hypothesis separation encoded in the data model
> itself, a transparent evidence-count-based confidence rubric, an AI-provider abstraction
> — OpenAI/Anthropic/Google/local, all optional — that never touches bulk insight generation,
> an AI Operations Assistant answering real questions from OG-PIOS data with source citations,
> and a Daily Operations Brief/Management Summary), and **What-If Simulator** (a deterministic
> baseline-vs-scenario comparison tool — production/downtime/production-loss/cost/commodity-price
> levers, a scenario builder with live preview, saved scenarios with a frozen results snapshot
> for reproducibility, multi-scenario comparison, a basic sensitivity-sweep analysis, and an
> optional AI-interpretation layer over already-computed results — no demo scenarios are
> seeded, since a saved scenario is a specific user's hypothesis-testing artifact, not
> operational history), and **Reports** (Daily Operations, Weekly Production, Monthly
> Management, and What-If Scenario reports — a report builder with filter/section selection and
> live preview, saved reports with a frozen results snapshot for reproducibility, CSV and PDF
> export with a traceability footer on every figure, and an optional AI-narrated executive
> summary on the Monthly report — every figure is aggregated from the other nine modules'
> existing calculations, never a new formula), and **Administration** (full user management —
> create/edit/activate/deactivate/role-assign — with deactivation taking effect immediately on
> an already-issued token, not just on next login; a read-only permission matrix and role list
> generated directly from the authorization checks that actually enforce access, never a
> separately-editable system; company/display and 30 operational-threshold system settings
> grouped into a usable UI; AI provider/model configuration status with zero API-key exposure by
> construction; a searchable/filterable audit log covering user, settings, and generation events
> across Reports/What-If/AI Insights; and a live system-health view) are fully implemented
> end-to-end. All eleven sidebar modules are now complete.

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
docker compose exec backend python -m app.db.seed_wells
```
This starts PostgreSQL and the FastAPI backend at `http://localhost:8000`
(interactive docs at `/docs`, summarized in `docs/api.md`), applies migrations, seeds the 7
roles plus one demo admin user (`admin@ogpios.dev` / `ChangeMe123!` — change this before any
real deployment), and seeds 25 demo wells with 365 days of production/pressure/temperature
history, per-well production targets, a fleet of well-linked and facility-linked equipment with
~90 days of sensor readings, five deliberately unhealthy equipment items for testing health
scoring, 3 demo maintenance technicians, a realistic mix of maintenance work orders
(preventive/corrective/emergency/inspection/calibration/routine/predictive types; scheduled/
waiting-for-parts/cancelled/completed statuses; cost breakdowns; a few intentionally overdue
equipment), monthly synthetic oil/gas commodity prices, production-loss records each tied
to a real downtime/failure/maintenance incident with its lost-volume and revenue-impact
estimate computed by the same calculation service the API uses, operating cost records at
field/facility/well/equipment level split by field currency (Niger Delta Field in NGN, Permian
Basin/North Sea Field in USD) so the currency-mismatch safeguard has a real demonstrable case,
and finally a real run of both the Alerts module's rule engine and the AI Insights module's
evidence-based insight engine against all of the above (never a disconnected, independently
invented alert or insight) (`seed_wells`, idempotent — safe to re-run; only actually re-seeds
against an empty database).

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
├── docs/            # architecture.md, data-model.md, api.md, ai-architecture.md, security.md
├── scripts/seed/    # plan for the future full-scale synthetic demo-data generator
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
- AI Insights' provider integration is entirely optional — `AI_PROVIDER` (`none`/`openai`/
  `anthropic`/`google`/`local`) plus the matching `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/
  `GOOGLE_API_KEY`/`LOCAL_AI_BASE_URL`. Leave `AI_PROVIDER=none` (the default) to run entirely on
  the deterministic rule-based engine — see `docs/ai-architecture.md`.
- Password reset / email verification — `MAIL_PROVIDER=console` (the default, and the only
  implementation today) never sends a real email; it logs the message, and the API response
  echoes the reset/verification token when `ENVIRONMENT=development`. `RESET_TOKEN_EXPIRE_MINUTES`,
  `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`, and `FRONTEND_URL` (used to build the emailed links)
  are also configurable — see `docs/security.md`.

## Known limitations
- Auth token is stored in `localStorage`; httpOnly cookie handling is follow-up work.
- `require_role` authorization is applied to every module's write endpoints, and to every
  Administration endpoint (including reads) — there is exactly one authorization primitive in
  the codebase (`deps.py`'s `require_role`), documented in full in `docs/security.md`.
- All eleven sidebar modules (Dashboard, Wells, Production, Equipment, Maintenance,
  Production Loss, Cost & Revenue, Alerts, AI Insights, What-If Simulator, Reports, and
  Administration) are fully implemented — no placeholder pages remain.
- No machine learning, forecasting, SCADA/DCS integration, or predictive maintenance yet.
  "Active Production Issues" on the Production dashboard, equipment health scoring, the
  Maintenance schedule/overdue view, the reliability (MTBF/MTTR/availability) calculator,
  Production Loss's lost-volume/revenue-impact estimates, every Cost & Revenue figure (estimated
  revenue, operating margin, unit economics, cost alerts), all 22 Alerts module rule types, and
  all 24 AI Insights types are explicit rule-based/statistical calculations with configurable
  thresholds — not anomaly detection, failure prediction, or genuine AI root-cause analysis.
  AI Insights' optional provider-authored text (`/interpret`, the Assistant's fallback, brief/
  summary narratives) only ever *phrases* these same deterministic figures — it never
  calculates, invents, or overrides them (see `docs/ai-architecture.md`'s hybrid-intelligence
  table). Equipment health score, the reliability metrics, and every Production Loss/Cost &
  Revenue/Alerts/AI Insights figure are **decision-support indicators/estimates, not certified
  safety/engineering/audited financial assessments**; nothing in these modules triggers
  automatic equipment control, status changes, operating-parameter changes, or autonomous
  financial decisions. The Alerts rule engine only ever opens, updates, or (for non-critical
  severities) auto-resolves an alert; the AI Insights engine only ever opens or updates an
  insight (never auto-dismisses) — neither mutates any other module's data.
- The Alerts and AI Insights rule engines have no scheduler/cron yet — both run on-demand
  (`POST /alerts/run`, `POST /ai-insights/run`, Administrator-only) or once during `seed_wells`.
  Two Alerts rule types (`high_estimated_lost_revenue`, `high_estimated_financial_impact`) and
  two AI Insights types (`high_lost_revenue`, `high_downtime_financial_impact`) are USD-only,
  following Production Loss's own USD-only `estimated_revenue_impact`. External notification
  channels (email/SMS/WhatsApp) are not implemented — `GET /alerts/summary`'s `new` count is the
  in-app-notification foundation a future dispatcher would consume. AI Insights' rate limiter
  (`/interpret`, `/assistant`) is in-memory, single-process, and resets on restart — documented
  as a first-pass limiter, not production-grade.
- `EquipmentReading` is real, general-purpose infrastructure for future SCADA/DCS/historian/IoT
  ingestion (not a mock integration), but no such integration exists yet — readings are only
  populated by the seed script and the manual `POST /equipment/{id}/readings` endpoint today.
- CSV import supports CSV only; the parsing layer is structured so an Excel importer could be
  added later without touching validation/classification logic (see `docs/api.md`).
- `GET /users` remains the minimal, unpaginated read-only lookup added for the Maintenance
  module's technician-assignment dropdown — unchanged, so that caller is unaffected. Full user
  management (create/edit/activate/deactivate/role-assign) is a separate, Administrator-only
  surface at `/administration/users` and `POST`/`PUT /users/{id}`.
- Password change/forgot/reset and email verification are implemented (`POST /auth/change-
  password`, `/forgot-password`, `/reset-password`, `/send-verification`, `/verify-email` — see
  `docs/security.md`), but with two accepted limitations: (1) **no real email is ever sent** —
  the only mail provider implemented is a console/dev one that logs the message
  (`MAIL_PROVIDER=console`, the only supported value today), so this must never be selected in a
  real deployment; (2) **an access token issued before a password change/reset stays valid until
  it naturally expires** (up to `ACCESS_TOKEN_EXPIRE_MINUTES`, 60 min by default) — `deps.py`'s
  `get_current_user` checks `is_active` but not the password hash, and closing this fully was
  deliberately scoped out to avoid touching this codebase's highest-blast-radius file (see
  `docs/security.md`'s "Password management & email verification" section for the full reasoning).
- Role and permission management in the Administration module are deliberately **read-only** —
  the 7 roles and their permissions are generated from the `require_role(...)` calls that
  actually enforce access, not a separately editable system (see `docs/security.md`). There is no
  create/delete-role UI.
- `CommodityPrice` (and therefore Production Loss's `estimated_revenue_impact`) is seeded in
  USD only, so Production Loss dashboard/by-scope/trend totals sum it directly without a
  currency dimension. Cost & Revenue's `OperatingCost` genuinely supports USD and NGN — its
  aggregates group strictly by currency and never blend the two — but it never converts between
  them or between an `OperatingCost` currency and Production Loss's USD-only revenue impact; a
  genuinely multi-currency commodity-price feed would need that added.
- Synthetic data covers Wells + Production (365 days), Equipment (~90 days of readings),
  Maintenance (work orders across the full type/status/priority vocabulary), Production Loss
  (commodity prices + incident-linked loss records), Cost & Revenue (`OperatingCost` records at
  field/facility/well/equipment level, split USD/NGN by field), Alerts, and AI Insights (real
  runs of both rule engines against all of the above, in that order — every seeded alert and
  insight references a real well/equipment/maintenance-record/production-loss-event, never an
  independently invented one) — see `scripts/seed/README.md`. **What-If Simulator has no seeded
  scenarios by design**: a saved `Scenario` is a specific user's hypothesis-testing artifact, not
  operational history, so seeding fake ones would misrepresent the feature as something nobody
  actually ran (the same reasoning already applied to not seeding fake `AIInsightFeedback` rows).
  The module is exercised through its own API/UI and its automated test suite instead. **Reports
  has no seeded reports either**, for the identical reason — a saved `Report` is a specific
  user's artifact. Every generated report always carries a synthetic-data disclaimer, since this
  environment has never run against verified production data.
- **`fpdf2` is the first new backend dependency added in this entire build** (every prior module
  added zero) — needed for PDF export in the Reports module. It's pure-Python with no system/apt
  dependencies, unlike `weasyprint`. Excel/`.xlsx` export is not implemented; CSV covers the
  "Excel/CSV where appropriate" requirement instead, matching this codebase's minimal-dependency
  convention and its one prior export precedent (`GET /production/export`).
