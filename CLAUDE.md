# OG_PIOS — Master Configuration

This file is read by Claude Code at the start of every session. It defines how work in this
project is organized, using the **WAT Framework**.

## The WAT Framework

WAT stands for **Workflows — Agent — Tools**. It's a simple separation of concerns for how
Claude Code operates in this repo:

- **W — Workflows**: Step-by-step procedures that orchestrate the work. A workflow is a plan
  written in plain language (Markdown) describing what needs to happen, in what order, and
  under what conditions. Workflows don't execute anything themselves — they tell the Agent
  what to do and when to reach for which Tool.
- **A — Agent**: Claude Code itself. The Agent reads workflows, decides how to carry them out,
  and executes steps using Tools. The Agent holds no long-term state of its own beyond this
  file and whatever it's told each session — the workflows and tools are the source of truth.
- **T — Tools**: Scripts and integrations the Agent invokes to actually get things done
  (API calls, data processing, file conversions, external service integrations, etc). Tools
  are concrete and executable; workflows describe *when* and *why* to use them.

In short: **Workflows say what to do, the Agent decides how, Tools do it.**

When starting a task, the Agent should:
1. Check `/workflows/` for an existing procedure that matches the request.
2. If a workflow exists, follow it step by step, using scripts/integrations from `/tools/`.
3. If no workflow exists for a recurring task, consider proposing one (as a new file in
   `/workflows/`) once the task's steps are understood, so it can be reused later.
4. Use `/temp/` for any working files generated along the way — never leave scratch output in
   `/workflows/` or `/tools/`.

## Folder Structure

```
OG_PIOS/
├── CLAUDE.md              # This file — master config, read every session
├── .env                   # API keys and secrets — NEVER commit
├── .gitignore             # Excludes .env and temp/ contents from git
├── workflows/              # Step-by-step procedure files (the "W")
├── tools/                  # Scripts and integrations (the "T")
└── temp/                   # Temporary working files — safe to clear
    ├── output/             # Generated results, exports, reports
    └── resources/          # Downloaded/intermediate files used mid-task
```

### `/workflows/`
Each file is one procedure, written so both a human and the Agent can follow it. Prefer one
workflow per file, named for what it accomplishes (e.g. `workflows/publish-report.md`).
A workflow should specify: trigger/when to use it, required inputs, ordered steps, which tools
each step uses, and expected output.

### `/tools/`
Scripts and integrations the Agent calls to do the actual work — API clients, data
transformers, CLI wrappers, etc. Keep tools single-purpose and composable so workflows can
chain them. Document any required environment variables at the top of each script.

### `/temp/`
Disposable working space. Nothing here should be treated as a permanent source of truth.
- `temp/output/` — finished artifacts a workflow produces (before they're delivered elsewhere).
- `temp/resources/` — intermediate files pulled in or generated mid-workflow (downloads,
  scratch data, partial results).

Contents of `temp/` are excluded from git via `.gitignore`. Clear it freely between tasks.

### `.env`
Holds API keys and secrets referenced by tools/integrations. **Never commit this file** — it
is excluded via `.gitignore`. If you add a new secret, document its name (not its value) in
the relevant tool's script comments so future sessions know it's required.

## Conventions for the Agent

- Prefer editing/extending an existing workflow or tool over creating a near-duplicate.
- Keep workflows declarative (what/when/order) and tools imperative (how).
- Never write secrets into workflow or tool files — reference `.env` variables instead.
- Treat `/temp/` as ephemeral; don't rely on its contents persisting across sessions.

## OG-PIOS Application

Alongside the WAT framework above, this repo also hosts the **OG-PIOS** product codebase: an
oil & gas production intelligence & optimization platform (production analytics, well/equipment
monitoring, predictive maintenance, anomaly detection, forecasting, production-loss and
cost/revenue analysis, alerts, what-if simulation, reporting). Target users span 7 roles:
Administrator, Production Operator, Production Engineer, Maintenance Engineer, Management,
Analyst, Viewer.

**How this coexists with WAT**: `workflows/` / `tools/` / `temp/` drive *automation of Claude
Code sessions* in this repo (e.g. a future `workflows/add-new-module.md` could describe how to
scaffold a new sidebar module using a script in `tools/`). The directories below are the
*product application code* — a separate concern:

```
frontend/     # Next.js app (native, npm)
backend/      # FastAPI app (Docker)
database/     # ERD notes / ops reference — schema itself lives in backend/alembic/
ml/           # stub — future analytics/ML code
docs/         # architecture.md, data-model.md
scripts/seed/ # plan for future synthetic demo-data generation
tests/        # reserved for future cross-stack/e2e tests
docker-compose.yml
```

**Key commands**:
- `docker compose up -d --build` — start backend (FastAPI, :8000) + PostgreSQL.
- `docker compose exec backend alembic upgrade head` — apply migrations.
- `docker compose exec backend python -m app.db.seed` — seed roles + demo admin.
- `docker compose exec backend pytest -q` — backend tests.
- `cd frontend && npm run dev` — frontend dev server (:3000, native, no Docker).
- `cd frontend && npm run test` — frontend tests (Vitest).

Full setup/testing detail lives in the root `README.md` — don't duplicate it here.

### Standing guardrail — AI/analytics output framing
OG-PIOS is a **decision-support platform, not a control system**. It must never autonomously
operate valves, chokes, DCS/SCADA setpoints, pumps, or compressors. Every anomaly/forecast/
recommendation surfaced by AI Insights, Alerts, or the What-If Simulator must be framed as an
estimate requiring engineering review — using language like "possible contributor," "estimated
impact," "requires investigation," never a guaranteed conclusion. This is encoded in the schema
itself (`AIRecommendation.disclaimer_text` in `backend/app/models/ai.py`) and must be honored
by any future session that touches these modules.
