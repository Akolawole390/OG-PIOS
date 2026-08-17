# Workflow: Build a Sidebar Module (Wells, and future modules)

## Trigger
Use this workflow when building out a full-stack module for one of the placeholder pages
listed in `frontend/src/config/navigation.ts` (Wells, Production, Equipment, Maintenance,
Production Loss, Cost & Revenue, AI Insights, Alerts, What-If Simulator, Reports,
Administration) — i.e. replacing a `ComingSoon` placeholder with real functionality backed
by the existing schema.

## Required inputs
- The module name and its nav entry (`frontend/src/config/navigation.ts`).
- Which existing models (`backend/app/models/`) the module reads/writes. Most modules should
  reuse existing models; only add columns/tables for a genuinely missing concept, and prefer
  additive (nullable) columns over restructuring existing tables.
- Which roles (from the 7 seeded roles) can read vs. write, per the product's role
  descriptions.
- Whether the module needs new demo/seed data beyond what `backend/app/db/seed.py` provides.

## Ordered steps

1. **Audit the existing schema first.** Read `backend/app/models/*.py` and
   `docs/data-model.md`. Identify what's already representable via existing models/FKs before
   proposing new tables or columns. Only add what's missing, and prefer nullable additive
   columns.
2. **Model changes (if any).** Edit the relevant file in `backend/app/models/`, update
   `backend/app/models/__init__.py`'s imports/`__all__` if a new model class was added, then
   generate a migration: `docker compose exec backend alembic revision --autogenerate -m
   "<description>"`, inspect the generated file in `backend/alembic/versions/`, then apply
   with `docker compose exec backend alembic upgrade head`.
3. **Schemas.** Add `backend/app/schemas/<module>.py` — Pydantic v2, read models use
   `model_config = ConfigDict(from_attributes=True)`, following `schemas/user.py`'s pattern.
4. **Router.** Add `backend/app/routers/<module>.py` — `APIRouter(prefix="/<module>",
   tags=["<module>"])`. Use `Depends(get_current_user)` for reads,
   `Depends(require_role(...))` for writes, matching the product's stated role ownership for
   that data domain. Register in `backend/app/main.py` via `app.include_router(<module>.router)`.
5. **Seed data (if the module needs realistic demo data beyond roles/admin).** Add a new,
   additive `backend/app/db/seed_<module>.py` (never edit `backend/app/db/seed.py`, which is
   reserved for roles + demo admin only). Use stdlib `random`/`datetime`; do not add
   `numpy`/`pandas` unless the module genuinely requires heavier synthesis and the team has
   agreed to expand backend dependencies. Run via
   `docker compose exec backend python -m app.db.seed_<module>`.
6. **Backend tests.** Add `backend/tests/test_<module>.py`. Extend
   `backend/tests/conftest.py` only if a new shared fixture is needed (e.g. reuse the
   `auth_headers` fixture added for Wells for any future role-gated endpoint tests — don't
   duplicate it). Run `docker compose exec backend pytest -q`.
7. **Frontend data/auth infra.** Reuse `frontend/src/lib/api.ts` (add new typed helper
   functions for the module's endpoints; don't create a second fetch wrapper) and
   `frontend/src/components/auth/AuthGuard.tsx` (already wraps every `(app)/*` route via
   `frontend/src/app/(app)/layout.tsx` — no per-module change needed).
8. **Frontend pages.** Replace `frontend/src/app/(app)/<module>/page.tsx`'s
   `ComingSoon` with the real list/dashboard view. Add nested routes
   (`[id]/page.tsx`, `new/page.tsx`, `[id]/edit/page.tsx`) as needed. Reuse
   `components/layout/PageHeader.tsx` and `components/dashboard/KpiCard.tsx`. Put
   module-specific shared components under `frontend/src/components/<module>/`.
9. **Charts.** If the module renders any chart/graph/stat-tile styling beyond the plain
   `KpiCard`, invoke Claude Code's `dataviz` skill before writing that code — every time,
   not just the first module.
10. **Frontend tests.** Add focused Vitest + RTL tests under
    `frontend/src/app/(app)/<module>/__tests__/` or
    `frontend/src/components/<module>/__tests__/`, mocking `@/lib/api` and (where relevant)
    `next/navigation` per `frontend/src/components/navigation/__tests__/sidebar.test.tsx`'s
    pattern. Run `cd frontend && npm run test`.
11. **Verify end-to-end.** Run the full verification sequence (migrations → seed → backend
    tests → `npm run build` → `npm run test` → manual curl + browser check) documented in
    each module's implementation notes / PR description.

## Tools used
- `docker compose exec backend alembic ...` / `pytest -q` / `python -m app.db.seed_<module>`
- `npm run dev` / `npm run build` / `npm run test` (from `frontend/`)
- `curl` for manual API verification against `http://localhost:8000`

## Expected output
A module that: has any necessary additive schema changes + migration; a FastAPI router
registered in `main.py` with role-appropriate auth; additive seed data (if needed); backend
tests covering the new endpoints including role-gated 403 cases; a real frontend list/detail
(+ create/edit where applicable) UI using shared `AuthGuard`/`lib/api.ts`/`PageHeader`/
`KpiCard`; frontend tests; a clean `npm run build`; and no modification to
`backend/app/db/seed.py`, `backend/tests/conftest.py`'s existing fixtures, or any other
module's files.

## Applied to: Wells module
First module built via this workflow. See `docs/data-model.md` for the Well completion-field
addition, `backend/app/routers/wells.py` for the endpoint set, and
`backend/app/db/seed_wells.py` for the synthetic data (3 fields, 25 wells, 90 days of
production/pressure history).

## Applied to: Production module
Second module. Notably extended the workflow itself in a few ways worth carrying into future
modules:

- **Composite resources.** When a module's natural unit spans multiple existing tables (here:
  `ProductionRecord` + `PressureRecord` + `TemperatureRecord`, keyed by `(well_id,
  record_date)`), keep the tables separate and compose them in the router layer rather than
  merging schemas — see `docs/data-model.md`'s "composite production record" note.
- **Data-integrity migrations.** Adding a unique constraint to enforce an invariant the module
  assumes (here: one record per well per day) is a legitimate additive migration, not schema
  creep — just verify it applies cleanly against existing data first.
- **App config vs. demo data.** A new admin-configurable setting (`SystemSetting`,
  `boe_gas_factor_scf_per_bbl`) was seeded via the **migration itself**, not
  `seed_wells.py` — config that must exist in every environment doesn't belong in a
  demo-data-only, idempotent-guarded seed script.
- **Shared validation.** One module can have two entry points that need the same business
  rules (manual entry vs. CSV import here). Put the rules in one pure, DB-free service module
  (`backend/app/services/production_validation.py`) and have both routers call it — never
  duplicate a validation tier list.
- **Shared chart infra moved, not duplicated.** `TrendChart` (built for Wells) turned out to
  be fully generic — it was relocated from `components/wells/` to `components/charts/` rather
  than copied, and a new `BarChart` was added alongside it for nominal-categorical ranking
  charts (production by well/field/facility). Re-invoke the dataviz skill for any genuinely
  new mark type (a bar chart is not a line chart), but reuse the same palette tokens already
  validated in `globals.css` where the encoding job is the same.
- **Extend seed data in place when it's the same dataset, growing.** `seed_wells.py` went from
  90 to 365 days plus new tables (temperature, targets) via edits to the existing file, not a
  parallel `seed_production.py` — it's the same wells/fields/facilities getting richer, not a
  new demo dataset.

See `docs/data-model.md` for the schema additions, `docs/api.md` for the endpoint summary and
CSV import design, and `backend/app/db/seed_wells.py` for the 365-day synthetic dataset.

## Applied to: Equipment module
Third module. Reused `Equipment`/`EquipmentReading`/`MaintenanceRecord`/`DowntimeEvent` (already
existed, unused by Wells/Production) rather than adding new tables. A few new patterns worth
carrying forward:

- **Role gating is a per-module judgment call, not a copy-paste default.** Wells/Production
  both gate writes to `Administrator` + `Production Engineer`. Equipment deliberately uses
  `Administrator` + `Maintenance Engineer` instead, because the product brief names Maintenance
  Engineer as the stated domain owner for equipment health/maintenance data — always re-derive
  the write-role pair from the brief's role descriptions, don't default to the previous
  module's pair.
- **A cached-and-refreshed value is a legitimate exception to "always compute live."**
  Production established computing derived fields (BOE, water-cut) live on every read because
  they're cheap arithmetic on already-loaded columns. Equipment's health score needs 3-4
  sub-queries (readings, maintenance, downtime, alerts) per item, so list/dashboard reads use a
  cached `Equipment.health_score` column (refreshed on defined write triggers: create,
  status/operating-hours update, new health-relevant reading) while `GET /equipment/{id}/health`
  always recomputes fresh and writes the result back to the cache. Default to live computation;
  only cache when the per-row query cost is genuinely prohibitive at list scale, and always
  provide one endpoint that guarantees freshness.
- **Put a scored/banded business rule in its own pure, DB-free service module**, same pattern as
  `production_validation.py` — `backend/app/services/equipment_health.py` takes plain values in
  (`HealthInputs`) and returns a plain result out (`HealthResult`), so the whole scoring formula
  is unit-testable without a database and reusable from both the API router and the seed script
  (the seed script's problem-equipment patterns call the real `compute_health()` on generated
  data rather than faking a low score directly).
- **A new ordinal/status encoding is a new chart component, not a bar-chart variant.** The
  dataviz skill's collision rule (a status color must never impersonate a categorical series)
  means Equipment's 5 fixed health bands got their own `HealthDistributionChart.tsx` and their
  own `--status-*` token set in `globals.css`, kept separate from `--chart-series-*`. Re-run the
  skill's palette validator for any new status step, not just new categorical hues.
- **An "extensible" enum field (per the product brief) is a free-text column with UI
  suggestions, not a closed `Literal`.** `equipment_type` is stored as free text and validated
  nowhere below the UI layer; `EquipmentForm.tsx` offers a `<datalist>` of common values instead
  of a `<select>`, so new equipment types don't require a schema or frontend change.
- **A read schema can deliberately be looser than its write schema.** `EquipmentRead.status` is
  typed as plain `str`, not the strict `Literal` used by `EquipmentCreate`/`EquipmentUpdate` —
  validation belongs at the write boundary; a read must never fail to serialize because of a
  legacy or unexpected stored value.
- **Direct FKs are simpler than indirection when the schema already has them.** Wells reaches
  `MaintenanceRecord`/`DowntimeEvent` history via `Equipment` as an intermediary; Equipment
  itself has `equipment_id` as a direct FK on both tables, so `GET /equipment/{id}/maintenance`
  and `/downtime` query directly with no join — reuse the existing read schemas
  (`MaintenanceRecordRead`, `DowntimeEventRead`, and their `*Summary`/`*ListResponse` wrappers)
  from `schemas/well.py` rather than redefining them.

See `docs/data-model.md` for the Equipment field/relationship additions and the health-score
concept note, `docs/api.md` for the `/equipment` endpoint summary, and
`backend/app/db/seed_wells.py` for the facility-level equipment, reading, and problem-pattern
generation.

## Applied to: Maintenance module
Fourth module. Turns the `MaintenanceRecord`/`DowntimeEvent` data that Wells and Equipment
already read (but never wrote) into a real work-order system. Reused this same workflow file
rather than a separate one — it already named Maintenance in its own trigger list.

- **A "work order" doesn't need its own model.** `MaintenanceRecord` already had everything a
  work order needs (equipment FK, type, status, cost, dates) plus an unused `technician_id`
  FK — this module added `work_order_number`, `priority`, planned-vs-actual date pairs, a
  four-part cost breakdown, `downtime_hours`, `failure_cause`/`corrective_action`/`notes`, and
  wired up the technician relationship, all as additive columns on the existing table. "Don't
  duplicate an existing model" extends to not inventing a parallel `WorkOrder` table when one
  work order *is* one maintenance record.
- **A shared DB-orchestration function gets promoted to a service module on its second
  consumer, not before.** Equipment's health-recompute logic lived as a private helper inside
  `routers/equipment.py` until this module needed the same recompute-on-maintenance-change
  behavior — it moved to `services/equipment_health.py` as `recompute_equipment_health()` at
  that point, imported by both routers. Matches the Production module's
  `production_validation.py` lesson: don't duplicate a rule across routers, but don't
  pre-extract something only one router uses either.
- **A field an API needs but the schema doesn't have yet (`well_id` on a maintenance record,
  `field`/`facility` scope) is resolved through the existing relationship chain, never stored
  redundantly.** Reused Equipment's own `_resolve_scope()` helper via a direct cross-router
  import — the same judgment call as the shared health function: fine for a second consumer,
  a third would be the trigger to promote it into a shared module.
- **A minimal read-only lookup endpoint is sometimes the honest way to satisfy one explicit
  requirement.** "Assign work order" needed a technician picker, which needed a way to list
  users — there was no `/users` endpoint anywhere. Added the smallest possible one (`GET
  /users`, read-only, optional role filter, reusing the existing `UserRead` schema) rather
  than skip the requirement or build a free-text ID field.
- **A second write-boundary schema for the same underlying table is fine when the two callers
  need genuinely different shapes.** `schemas/well.py`'s `MaintenanceRecordRead` (lightweight,
  denormalized `equipment_tag`/`equipment_type`, no `id`-heavy detail) stayed untouched for
  Wells'/Equipment's read-only sub-resource endpoints; this module's own `MaintenanceEntry` in
  the new `schemas/maintenance.py` is the full work-order shape. Named with an `Entry` suffix
  to avoid colliding with the existing lightweight type name on the frontend — same precedent
  as Production's `ProductionEntry` vs. Wells' `ProductionRecord`.
- **"Prepare the foundation" means a small, honestly-caveated calculator, not a dashboard.**
  `services/reliability_metrics.py` (MTBF/MTTR/availability/failure-frequency) mirrors
  `equipment_health.py`'s pure/DB-free, directly-unit-tested shape, and every metric declares
  whether its own minimum sample size was met rather than returning a misleading number from
  thin data. Surfaced as one small card on the existing Equipment detail page, not a new
  route — matching the spec's actual ask.
- **A closed vocabulary gets a strict `Literal`; an "allow more in the future" vocabulary
  stays a free string with frontend suggestions.** `status` and `priority` are `Literal`s;
  `maintenance_type` is a plain `str` with a `<datalist>`, exactly mirroring Equipment's
  `equipment_type` split — re-derive this per field from the spec's own wording, don't
  default one way for a whole module.

See `docs/data-model.md` for the new fields and the documented Well → Equipment → Maintenance →
Failure/Downtime relationship chain, `docs/api.md` for the `/maintenance`, `/users`, and
`/equipment/{id}/reliability` endpoint summaries, and `backend/app/db/seed_wells.py` for the
technician/work-order synthetic data generation.

## Applied to: Production Loss module
Fifth module. Closes the chain explicitly requested end-to-end: `Well → Production →
Equipment → Maintenance → Failure/Downtime → Production Loss → Estimated Financial Impact`.

- **An already-modeled-but-unused table is extended in place, not replaced.**
  `ProductionLoss`/`CommodityPrice` existed in `models/economics.py` since the initial schema
  migration but had zero references anywhere (no router, schema, or seed data) — confirmed via
  a full-repo grep before touching anything. Extending it (new columns, new relationships) was
  the right move for the exact same reason Equipment's `field_id`-resolution pattern and
  Maintenance's `technician_id` FK were reused rather than duplicated: an unused-but-correctly-
  shaped piece of schema is an asset to build on, not a reason to start over.
- **An existing cross-router resolution helper gets reused directly, not duplicated a 3rd
  time.** `production.py` already had two internal variants of "resolve the most recent
  `ProductionTarget` for a well/date" (`/kpis`'s `_resolve_target`, `/actual-vs-target`'s
  inline closure). Rather than write a 3rd copy in the new `production_loss.py`, it imports
  `_resolve_target` directly — the same "2nd consumer reuses, 3rd triggers extraction"
  judgment call already applied to `_resolve_scope` (Equipment → Maintenance). `production.py`
  itself needed zero changes.
- **"Auto-computed by default, manual override allowed" is a third point on the computed-vs-
  stored spectrum**, alongside Production's "always live" (water-cut/GOR/BOE) and Equipment's
  "cached, explicitly refreshed" (health score). Here, a value is normally derived from real
  `ProductionTarget`/`ProductionRecord`/`CommodityPrice` rows and cached on write, but a caller
  can supply it directly for cases (historical backfill) the automatic path can't reach —
  never fabricated when neither path applies; the field simply stays `None`.
- **The synthetic-data rule stayed strict**: every seeded `ProductionLoss` row is tied to a
  *real* previously-generated incident (a `failure_event` equipment's downtime + emergency
  work order, an anomaly well's guaranteed downtime event, or a sampled general downtime
  event) — never an independently invented one — and its lost-volume/revenue numbers are
  produced by importing and calling the actual `_compute_derived_fields()` the API itself
  uses, not a re-implementation. Same principle as Equipment health/Maintenance's seeded
  problem patterns, now applied a third time.
- **A missing shared utility (currency formatting) was filled for new code only.** No
  `formatCurrency()` existed anywhere in the frontend despite 7+ pages hand-rolling
  `` `$${value.toLocaleString()}` ``. One was added to `lib/format.ts` and used by this
  module's new pages; the existing pages were deliberately left untouched — filling a real gap
  is in scope, retrofitting working code that wasn't asked for is not.
- **Role gating is re-derived per module, not copied from the nearest neighbor.** Despite
  Production Loss being reachable from Equipment/Maintenance data, it's gated
  `Administrator`/`Production Engineer` (matching Wells/Production's ownership) rather than
  `Maintenance Engineer`, because the domain — production-analysis/financial reporting — is
  Production's, not Maintenance's. Re-confirms the lesson first written down for the
  Maintenance module: always re-derive the write-role pair from the brief, never default to
  whichever module was built most recently.

See `docs/data-model.md` for the `ProductionLoss`/`CommodityPrice` field additions and the
completed relationship chain, `docs/api.md` for the `/production-loss` endpoint summary, and
`backend/app/db/seed_wells.py` for the commodity-price and incident-linked loss generation.

## Applied to: Cost & Revenue module
Sixth module. The most integrative one yet — it introduces almost no new domain data (only
`OperatingCost` gains detail fields), and instead connects five existing modules into a
management/analyst-facing economics view: `Production → Revenue → Operating Cost →
Maintenance Cost → Production Loss → Estimated Financial Impact`.

- **Currency safety is the module's central, deliberately-tested guardrail.** The brief
  supports both USD and NGN but explicitly forbids inventing an exchange rate. Every financial
  aggregate is returned as `list[{currency, amount}]`, never a single blended number, and any
  revenue-minus-cost or per-unit calculation is only computed when both sides resolve to the
  *same* currency for that scope — otherwise the API returns an empty list plus a
  `currency_mismatch: bool` flag rather than a fabricated figure. `test_cost_revenue.py`'s
  `test_dashboard_currency_mismatch_never_blended_into_a_fabricated_margin` seeds USD revenue
  against NGN cost on the same well specifically to prove this path is exercised, not just
  theoretically correct.
- **A second, real reason to keep an existing model "extend in place."** `OperatingCost`
  (`models/economics.py`) existed since the initial schema with only
  `cost_date`/`category`/`amount`/`currency`/`field_id`/`facility_id`/`well_id` and zero
  references anywhere — the same "unused but correctly-shaped" situation Production Loss's
  `ProductionLoss`/`CommodityPrice` were in. Extended with `equipment_id`, `description`,
  `cost_period`, `source`, `notes` rather than replaced.
- **Two existing modules' aggregate endpoints are reused wholesale from the frontend, not
  duplicated.** Maintenance cost sections call `/maintenance/by-scope` and
  `/maintenance/cost-trend` directly; Production Loss sections call
  `/production-loss/dashboard`, `/by-scope`, and `/trend` directly. This module never
  recomputes `estimated_revenue_impact` a second way — the "do not double-count production
  loss" requirement is satisfied by construction (one source of truth, read in multiple
  places), not by a reconciliation check.
- **One additive extension to a working endpoint**, not a new one: Maintenance's
  `/maintenance/by-scope?group_by=` gained a `well` option (alongside the existing
  `type`/`equipment`/`field`) using the same `_resolve_scope` helper it already had access to
  — existing `type`/`equipment`/`field` behavior is untouched.
- **Role gating re-derived a fourth time, and for the first time lands outside the two
  engineering pairs.** Writes to `/operating-costs` require `Administrator`/`Management`
  (not Production or Maintenance Engineer), because the brief frames this module explicitly as
  a management/analyst decision-support tool. Reconfirms: never default the write-role pair to
  whichever module was built most recently — always re-derive it from the brief.
- **An unresolvable-currency assumption is documented, not silently guessed.**
  `MaintenanceRecord.cost` has no currency column (never added in the Maintenance module).
  Rather than retrofit one — which would touch a working, already-verified module for a need
  this module alone has — Cost & Revenue treats it as USD via a single named constant
  (`MAINTENANCE_COST_CURRENCY` in `cost_revenue.py`) with an inline comment explaining why.
- **Synthetic operating costs are split by field currency, not decoration.** Niger Delta Field
  costs seed in NGN, Permian Basin/North Sea Field costs seed in USD — chosen independently
  per currency, never derived from a coded conversion rate — specifically so the
  currency-mismatch guardrail has a real, demonstrable case in the seeded demo data, not just
  in a hand-crafted test fixture.

See `docs/data-model.md` for the `OperatingCost` field additions and the "Economic Calculation
Methodology" section, `docs/api.md` for the `/operating-costs` and `/cost-revenue` endpoint
summaries, and `backend/app/db/seed_wells.py` for the field-currency-split cost generation.

## Applied to: Alerts module
Seventh module, and the first that is cross-cutting rather than domain-owning: it centralizes
22 rule-based conditions already detectable across Production/Equipment/Maintenance/Production
Loss/Cost & Revenue into one auditable Alert & Event Intelligence system.

- **A dormant model became live, and it wasn't dead code.** `models.ai.Alert` existed since the
  initial schema with zero rows ever written — but `equipment_health.py`'s
  `recompute_equipment_health()` already *read* `Alert.equipment_id`/`triggered_at` for its
  `alarm_frequency` scoring factor. Extending `Alert` in place (per "don't duplicate existing
  models") and finally populating it activates that factor for the first time — a deliberate,
  self-limiting reuse: `triggered_at` never moves after creation, so an alert ages out of the
  factor's 30-day window regardless of how long it stays open, and dedup caps it at one row per
  (type, equipment) while open. Worth remembering for any future module: a model with zero
  writes can still have a live reader elsewhere — grep for the class name, not just for
  `.query()`/`.add()` calls, before assuming it's inert.
- **A services → routers import direction, deliberately, for a stated reason.**
  `services/alert_rules.py` imports private helpers from `routers/production.py`,
  `routers/equipment.py`, `routers/maintenance.py`, and `routers/cost_revenue.py` — the reverse
  of the usual layering. This is the same "2nd/3rd consumer reuses a private helper directly"
  pattern used throughout this project (e.g. `cost_revenue.py` importing `_resolve_scope` from
  `equipment.py`), just crossing the services/routers boundary once. Kept in `services/` rather
  than folded into `routers/alerts.py` specifically so `seed_wells.py` can call
  `run_alert_rules()` directly without pulling in FastAPI — the same reason
  `equipment_health.py`'s `compute_health()` lives in services, not in `routers/equipment.py`.
- **Partial reuse is more honest than a full reuse claim.** The brief's 6 named economics alert
  types don't map 1:1 onto `cost_revenue.py`'s existing 6 ad hoc cost alerts (different
  concepts — an absolute-threshold check isn't a rate-of-change check). Two rules
  (`declining_operating_margin`, `high_maintenance_cost`) reuse the *exact* existing detection
  logic, now with a configurable threshold replacing the hard-coded multiplier; the other four
  are genuinely new comparisons built from the same currency-safe helpers
  (`_compute_scope_totals`, `_per_unit_by_currency`, `_load_price_series`) rather than a fresh,
  uncoordinated re-aggregation. Don't claim full reuse when only the *supporting* helpers are
  shared and the comparison itself is new — document the split honestly.
- **A found bug in a live rule engine, not just a fixed schema.** Verification by actually
  running `POST /alerts/run` twice against the reseeded dataset (not just reading the code)
  surfaced two real gaps the design missed on paper: (1) `_generate_production_alerts` gated
  down-well outage detection behind a resolvable `reference_date`, when `production.py`'s own
  `/issues` endpoint — the precedent this rule explicitly reuses — never gates that check on
  production-record data existing at all (fixed by only gating the reference-date-*dependent*
  per-well loop, not the whole function). (2) Two test fixtures assumed severity math that
  doesn't hold for small equal-weighted samples (2 equipment items can never mathematically
  exceed 2× their own pairwise average — needed 3+ low-cost items to pull the average down).
  Both were caught by actually exercising the rule engine end-to-end against real data, the same
  lesson Cost & Revenue's currency-mismatch bug taught: run the thing, don't just read it.
- **Deduplication as a stated, testable lifecycle contract, not an implementation detail.**
  `dedup_key = f"{alert_type}:{scope_type}:{scope_id}"`, matched only against *open* states
  (`new`/`acknowledged`/`investigating`). A still-true condition updates the existing open row
  in place (bumping `occurrence_count`); a resolved/dismissed alert does **not** suppress
  reopening if the condition recurs, since the lookup only matches open states. Verified live:
  running the engine twice showed `created=0, updated=N` on the second pass, then resolving one
  alert and running a third time showed a fresh row open again for the same `dedup_key`.
- **Auto-resolution is asymmetric by severity, and manual alerts are exempt from it entirely.**
  Non-critical open alerts whose condition clears on a later run auto-resolve (system-generated
  history note); critical alerts never do — the literal reading of "do not automatically mark
  critical alerts as resolved." Manually created alerts (`source_module="manual"`,
  `dedup_key="manual:{uuid}"`) are excluded from the auto-resolve sweep entirely, not just from
  the critical branch — without that exclusion a manual alert would auto-resolve on the very
  next rule run regardless of severity, since its dedup_key can never match a rule-generated one.
- **Filling an existing placeholder is the whole "dashboard integration" ask.** The main
  `/dashboard` page already had a `KpiCard label="Active Alerts" value="—" hint="Not yet
  connected"` tile from an earlier module. Wiring it to `GET /alerts/summary`'s open-alert count
  was the entire "add a visible alert summary to the main management dashboard" requirement —
  no new dashboard section, no Sidebar badge (deliberately skipped: a live-fetch on a
  component every page renders is a bigger footprint than this ask needs).

See `docs/data-model.md` for the `Alert`/`AlertStatusHistory` field additions, the full 22-rule
table with default thresholds and the severity rubric, `docs/api.md` for the `/alerts` endpoint
summary, and `backend/app/db/seed_wells.py` for the real rule-engine run against seeded data.

## Applied to: AI Insights module
Eighth module, and the first that sits **on top of** the whole stack rather than beside it —
`Well → Production → Equipment → Maintenance → Failure/Downtime → Production Loss →
Cost & Revenue → Alerts → AI Insights`. Explicitly not a chatbot: an evidence-based analysis
engine generating 24 structured, source-cited insight types, plus an optional AI-interpretation
layer that only ever phrases already-computed figures.

- **A second "modeled but never populated" model, extended the same way as the first.**
  `AIRecommendation` existed since the initial schema (`observation`/`evidence`/
  `possible_contributors`/`recommended_investigation`/`potential_impact`/`confidence`, zero rows
  ever written) — the same situation `Alert` was in before the prior module. Extended in place,
  called "Insight" in API/docs while the table stays `ai_recommendations` (same "keep the DB
  name, rename in the API" precedent `Alert`'s `state` column set). `AIPrediction` (genuine
  forecasting/ML) stays untouched and dormant a second time — its docstring now says so
  explicitly, and the inherited `ai_prediction_id` FK was dropped rather than kept as
  permanently-null dead scaffolding, since nothing in this module (or any planned one) writes an
  `AIPrediction` row.
- **Fact-vs-hypothesis separation is a data guarantee, not a prose convention.** The brief
  requires the UI to visibly distinguish OBSERVED FACT / CALCULATED METRIC / CORRELATION /
  POSSIBLE CONTRIBUTOR. A free-text `evidence` column can't guarantee that distinction survives
  into the UI — so it was replaced with a child table, `AIInsightEvidence`, one row per fact with
  a typed `evidence_type`. This is deliberately a different, citation-oriented shape from
  `AuditLog.entity_type`/`entity_id` (an audit row records *who did what*; this records *what
  fact backs this claim, and where to verify it*) — worth noting explicitly so a future reader
  doesn't mistake the difference for a missed reuse.
- **Confidence is derived, never fabricated.** `confidence_level` (high/medium/low) is computed
  from the count of distinct evidence *categories* present (3+/2/1), replacing the inherited
  numeric `confidence: float` outright rather than keeping both — the brief explicitly warns
  against implying a statistical model that doesn't exist. This rule caught a real design bug
  during testing: the cross-domain generator's two evidence items (a production-decline fact and
  an equipment-health fact) were both typed `observed_fact`, so 2 independent *sources* only
  counted as 1 *category* → `low` confidence instead of the intended `medium`. Fixed by
  recognizing that a health score is itself a *computed* value (`equipment_health.py`'s
  `compute_health()`), not a raw recorded reading — retyping it `calculated_metric` fixed both
  the semantics and the confidence math in one change, not a special case bolted on.
- **`insight_engine.py` calls `alert_rules.py`'s private `_generate_*_alerts` functions
  directly, never `run_alert_rules()`.** ~14 of the 24 insight types are semantically identical
  to an existing alert type — reusing those candidates directly (as an insight's primary
  evidence) avoids a third reimplementation of the same condition. Calling the private
  generators rather than the public orchestrator is deliberate: it means running the insight
  engine can never have the side effect of writing `Alert` rows, so the two engines stay
  independently runnable and testable. Severity-tiered alert families collapse into one insight
  type each (`equipment_low_health`/`equipment_critical_health` → one
  `equipment_health_deterioration`), same principle as the tiered-severity rubric elsewhere: the
  tier is still visible via `current_value`/`threshold_value`/severity, so collapsing loses no
  information.
- **The cross-domain generator is one function with two tiered outputs, not two generators.**
  The flagship "production decline + equipment health decline + recent maintenance + downtime"
  correlation and its simpler "just the first two signals" cousin
  (`equipment_linked_to_production_decline`) come from the *same* generator, not a bespoke extra
  equipment detector — a real duplication a design review caught before it was built. The
  generator also can't be built from `AlertCandidate` lists alone: alert generators only emit
  candidates for alert-worthy conditions, so "recent maintenance happened, nothing alert-worthy
  about it" has to come from a direct supplementary query, scoped to the well/equipment ids
  pulled off the two co-occurring candidates — worth remembering for any future generator that
  wants to correlate an alert-worthy signal against a merely-contextual one.
- **Insight generation is always 100% deterministic — the AI provider layer is never in that
  path, even if one is configured.** `run_insight_engine()` is called from `seed_wells.py` with
  no network dependency; coupling bulk generation to an AI call would make every seed/test run
  depend on provider mocking. AI is invoked only by three explicit, opt-in paths (per-insight
  `/interpret`, the assistant's fallback, an off-by-default narrative flag on the brief/summary)
  — never the bulk `/run` endpoint, which also isn't rate-limited, unlike those three.
- **No auto-dismiss, by design — a genuinely different lifecycle than Alerts', not a smaller
  version of it.** An insight whose condition stops being reaffirmed stays exactly as it was;
  `dismissed` is always a 100% manual action. An alert says "this needs attention now"; an
  insight says "here's what the data showed," which doesn't stop being true once the condition
  passes. Staleness is surfaced instead as a **derived** `is_stale`/`days_since_confirmed` pair
  (computed at read time from `last_confirmed_at`), not a 4th status value blurring the
  intentionally simple `new`/`reviewed`/`dismissed` model.
- **The AI provider layer is synchronous, on purpose, in an otherwise fully synchronous
  codebase.** A grep before writing any adapter confirmed zero `async def` anywhere in any
  router or service. `AIProvider.interpret()` uses `httpx.Client`, not `AsyncClient` — avoids
  making the AI layer the one inconsistent code path, and avoids event-loop juggling inside
  otherwise-sync FastAPI handlers. `NullProvider` (used when no key is configured) is a
  genuinely functional deterministic template responder, not a bare stub — the app is meant to
  be actually useful with zero AI configured, not just non-crashing.
- **The Assistant reuses existing query logic per matched question; it doesn't reimplement
  aggregation a fourth way.** Verification caught a real currency-safety bug the same class as
  Cost & Revenue's: the "highest cost per barrel" template originally picked one "best" field by
  comparing NGN and USD values as raw numbers — the exact cross-currency blending mistake this
  project has fixed twice before. Fixed to track the highest field independently per currency,
  same rule every other money aggregate in this project already follows.

See `docs/data-model.md` for the `AIRecommendation`/`AIInsightEvidence`/`AIInsightFeedback`
field additions, the full 24-insight-type table, the confidence rubric, and the staleness
mechanic; `docs/api.md` for the `/ai-insights` endpoint summary; `docs/ai-architecture.md` for
the provider abstraction and the hybrid-intelligence boundary; and `backend/app/db/seed_wells.py`
for the real insight-engine run against seeded data.

## Applied to: What-If Simulator module
Ninth module, and the first that is explicitly **counterfactual, not operational** — every prior
module modeled something that actually happened (a well produced, a cost was incurred, an alert
fired); this one models something that *might* happen, without ever touching the records that
say what did. Deterministic calculation always runs first (`services/whatif_calculations.py`,
pure, no AI import anywhere in it); an optional `/interpret` endpoint only ever phrases numbers
that calculation already produced — the same hybrid-intelligence boundary AI Insights
established, applied to a genuinely new surface.

- **The first genuinely greenfield model since the original schema.** Every module from
  Production Loss through AI Insights extended a table that already existed but had zero rows
  ("modeled but never populated"). A grep before writing any code confirmed no
  `Scenario`/`WhatIf`/`Simulation` model, table, router, or schema existed anywhere — `Scenario`
  (`backend/app/models/simulation.py`) is a genuinely new table, not a fourth or fifth instance of
  that reuse pattern. `assumptions`/`results` are the first real use of `sqlalchemy.JSON` in this
  codebase, for exactly the structured-but-non-relational data `docs/data-model.md`'s own stated
  portability principle already sanctions it for.
- **A saved scenario's `results` is a frozen snapshot, not a live view — a genuinely different
  storage shape than every prior dashboard.** Every other module's dashboard/detail endpoint
  recomputes from current data on every `GET`. A saved `Scenario` does the opposite on purpose:
  `results` + `calculation_version` are written once at `POST`/`PUT`/`rerun` time and a plain
  `GET` never touches them again. This is what makes "store the assumptions and calculation
  version used — important for reproducibility" (the brief's own wording) literally true rather
  than aspirational: a saved scenario shows exactly what was seen when it was saved, not a number
  that silently drifts as production/cost data changes underneath it. `POST
  /what-if/scenarios/{id}/rerun` is the one explicit, deliberate way to refresh it.
- **Two-tier guardrails, not a single pass/fail gate.** The brief explicitly warns against
  silently rejecting a merely unusual scenario, but also requires rejecting a mathematically
  impossible one (negative production/cost/downtime, a loss reduction over 100%, a non-positive
  price). `validate_assumptions()` returns typed flags with `severity="error"` (the router turns
  these into a 422, listing exactly which field and why) or `severity="warning"` (still computed
  and returned, carrying "Scenario is outside configured operating assumptions," never dropped).
  The warning bound is a configurable `SystemSetting`
  (`whatif_reasonable_change_pct_bound`, default 50), same `_KEY`/`DEFAULT_`/typed-getter pattern
  every prior threshold has used.
- **One downtime lever, not the two the brief's variable list implies.** The brief lists both a
  general "downtime increase/decrease %" and a "maintenance downtime reduction %" as separate
  scenario variables, but the only baseline downtime figure available
  (`ProductionLoss.downtime_hours`) is already aggregated across causes and doesn't cleanly split
  "maintenance-caused" from "general" without inventing a ratio nothing in the data supports. This
  is documented here as a deliberate scope simplification — one `downtime_change_pct` lever — not
  a silently dropped requirement, applying the project's standing "never invent missing baseline
  data" rule to a new case.
- **Two "potential recovery" figures are computed and reported, but deliberately never folded
  into the headline production number.** `Estimated Potential Production Recovery` from a
  downtime reduction (`recovered_downtime_hours × (baseline_oil_bbl / (period_days × 24))`) and
  from a production-loss reduction (`baseline_lost_oil_bbl − scenario_lost_oil_bbl`) are each kept
  as their own labeled fields on `ScenarioMetrics`, separate from `oil_bbl` (which only ever
  reflects `production_change_pct`). Merging either into `oil_bbl` would double-count the same
  barrels under two different levers — the brief's own "do not apply a scenario adjustment twice"
  instruction, made concrete for the two places in this module where double-counting was a real
  risk.
- **The energy-cost lever scales only the energy slice of operating cost, reusing
  `_split_operating_costs`'s existing energy/other split rather than re-deriving it.** If
  `energy_cost_change_pct` is supplied, energy and the rest of operating cost are each scaled
  independently; if it's absent, the whole baseline operating cost is scaled once by
  `operating_cost_change_pct`. Either path touches each dollar exactly once — the module's other
  concrete instance of the "never apply an adjustment twice" rule.
- **`cost_revenue.py`'s scope-aggregation helpers gained `facility_id`/`equipment_id` as
  additive, default-`None` kwargs — the fourth consumer of the private-helper-reuse convention
  `alert_rules.py`/`insight_engine.py`/`ai_assistant.py` already established.**
  `_production_query`/`_operating_cost_query` already supported `facility_id`;
  `_maintenance_cost_query`/`_production_loss_query`/`_compute_scope_totals` didn't, so they were
  extended the same "one more optional kwarg" way `group_by=well` was added to
  `/maintenance/by-scope` — every existing caller's behavior is provably unchanged since none of
  them pass the new kwargs.
- **No seed data for saved scenarios.** Every prior module's synthetic dataset represents
  operational history — things that would exist regardless of who uses the app. A saved
  `Scenario` is a specific user's hypothesis-testing artifact; seeding fake ones would misrepresent
  the feature as something nobody actually ran, the same reasoning already applied to not seeding
  fake `AIInsightFeedback` rows. The feature is exercised through the API/UI and the test suite's
  own fixtures instead.

See `docs/data-model.md` for the `Scenario` field list, the full formula set verbatim, and the
guardrail rubric; `docs/api.md` for the `/what-if` endpoint summary; `docs/ai-architecture.md` for
the `/interpret` endpoint's place in the hybrid-intelligence boundary.

## Applied to: Reports module
Tenth and final planned module — converts data every other module already computes into Daily
Operations, Weekly Production, Monthly Management, and What-If Scenario reports. No new
operational data, no new business-logic formulas: purely an aggregation, presentation, and export
layer over the other nine modules.

- **Extends `Report`, not a new model — the return to the dominant pattern after What-If
  Simulator's one greenfield exception.** `Report` (`report_type`/`period_start`/`period_end`/
  `file_path`/`generated_by_id`) existed since the initial scaffold with zero rows ever written —
  the same "modeled but never populated" situation `Alert`/`AIRecommendation`/`OperatingCost`/
  `ProductionLoss` were in before their modules extended them in place. What-If Simulator's
  `Scenario` was greenfield only because no candidate table existed; here one already did, so
  Reports returns to the dominant reuse pattern rather than repeating the exception. New fields
  mirror `Scenario`'s already-proven shape almost 1:1: `name`/`description`, `filters` (JSON),
  `sections` (JSON list), `results` (JSON, frozen snapshot), `calculation_version`, `status`,
  `last_generated_at` — a second module independently arriving at the same "saved artifact with a
  frozen JSON snapshot" shape one module later, not a coincidence but the natural continuation of
  Decision 4/13's reproducibility requirement.
- **A two-tier filter-support discovery shaped the whole calculation layer.** Every module's
  `*_dashboard`/`*_summary`/`*_issues` endpoint (equipment, maintenance, alerts, insights) turned
  out to be permanently unfiltered — fleet-wide only, `db.query(X).all()`, confirmed by direct
  reads of `get_equipment_dashboard`, `get_equipment_issues`, `get_maintenance_dashboard`,
  `get_alert_summary`, `get_insight_summary`. Only the paginated `list_*` endpoints accept the
  field/facility/well/equipment(+date/category/severity/type) filters a report needs. Rather than
  duplicate a sixth copy of every module's WHERE-clause logic, `report_calculations.py` calls the
  `list_*` functions directly (generous `page_size`, aggregates `.items` in Python) — the same
  "call the router function as a plain Python function" precedent `ai_insights.py`'s existing
  `get_daily_brief`/`get_management_summary` already established, just applied to five more
  modules at once.
- **A real, working bug class from calling FastAPI route functions directly, caught and fixed
  during integration testing, not left for a user to find.** Every one of those `list_*`
  functions declares parameters like `status_filter: str | None = Query(None, alias="status")`
  and `page: int = Query(1, ge=1)` — fine when FastAPI's dependency injection resolves the
  `Query(...)` sentinel from the request, but calling the function directly as plain Python uses
  the *literal* `Query(...)` object as the default value, not `None`/`1`. This surfaced
  immediately as a `psycopg.ProgrammingError: cannot adapt type 'Query'` the first time a real
  smoke test ran `list_equipment(field_id=..., ...)` without explicitly passing `status_filter`
  and `page` too. Fixed by explicitly passing every `Query(...)`-defaulted parameter at every
  direct call site — worth remembering for any future module that calls an existing FastAPI
  route function directly rather than through HTTP: a function's own declared defaults are not
  safe to rely on outside of FastAPI's request cycle.
- **`results` is a plain JSON dict on the API response, not ~30 new fully-typed schema classes —
  a deliberate departure from What-If Simulator's fully-typed `ScenarioResultsRead`.** What-If's
  single result shape (baseline/scenario/comparison) justified full typing because every scenario
  produces an identical structure. Reports' 4 types have structurally different section sets
  (Daily ≠ Weekly ≠ Monthly ≠ What-If), and each section already embeds an upstream-typed
  schema's own `model_dump(mode="json")` — retyping that a second time for marginal benefit would
  contradict the brief's own "keep the first version simple and reliable." The frontend still
  gets full clarity via hand-written TypeScript interfaces in `lib/api.ts` that describe exactly
  what `report_calculations.py` actually produces per section — documented, just not backend-
  pydantic-enforced.
- **The first new backend dependency added in this entire build.** No PDF or Excel library
  existed anywhere in `requirements.txt` before this module (confirmed by direct read) — every
  prior module added zero new dependencies. `fpdf2` was chosen specifically for having zero
  system/apt dependencies (unlike `weasyprint`, which needs Pango/Cairo) and a simple enough API
  to draw the 1-2 native bar charts PDF export needed without pulling in `matplotlib`. CSV export
  reuses `production.py`'s existing `io.StringIO`/`csv.writer`/`StreamingResponse` pattern
  unchanged — this codebase's only prior export endpoint.
- **fpdf2's core "Helvetica" font is latin-1-only, but this codebase's prose (disclaimers,
  section docstrings, methodology strings) freely uses em-dashes and curly quotes.** Rather than
  hunting down every string literal across every module that might end up embedded in a report,
  `report_export.py` overrides `FPDF.cell`/`multi_cell` once to normalize text to ASCII at the
  one boundary where the mismatch actually matters — the correct place to fix an encoding
  constraint that didn't exist when those strings were originally written, not a source-wide
  find-and-replace.
- **The What-If Scenario Report is a near passthrough, not a new calculation.** `Scenario.results`
  (What-If Simulator) was already the exact frozen snapshot a report needs
  (`baseline`/`scenario`/`comparison`/`guardrail_flags`) — `build_what_if_scenario_report()`
  embeds it directly via `_results_json_to_schema`, reusing What-If's own JSON round-trip
  function rather than re-deriving anything, and labels every scenario figure "Scenario Estimate"
  per the brief's explicit instruction, never a forecast.
- **No seed data for saved reports**, same reasoning as What-If's saved scenarios: a saved
  `Report` is a specific user's artifact, not operational history that would exist regardless of
  who uses the app.

See `docs/data-model.md` for the `Report` field list, the 4 report types and their sections, and
the calculation-reuse map back to each source module; `docs/api.md` for the `/reports` endpoint
summary; `docs/ai-architecture.md` for the Monthly report's optional narrative and the What-If
report's passthrough interpretation in the hybrid-intelligence table.

## Applied to: Administration module
Eleventh and final module in the original module list — replaces the last `ComingSoon`
placeholder with user management, permissions/roles visibility, system settings, operational
thresholds, AI configuration status, audit logging, and system health. Unlike every prior module,
it is **Administrator-only end to end, including reads**, since it exposes user PII, system
configuration, and the full audit trail rather than operational data any role should see.

- **"Do not duplicate permission logic" resolved by building a read-only mirror of what already
  enforces access, not a second authorization system.** A grep of every `current_user.role`
  reference confirmed exactly one authorization primitive exists anywhere (`deps.py`'s
  `require_role(...)`) — no permissions table, no decorators, no middleware. Building a
  database-editable permission-granting UI would have meant rewriting authorization across every
  router to consult it, and would risk permanent drift between "what the matrix says" and "what
  actually gets enforced." `services/permissions.py`'s `PERMISSION_MATRIX` is instead
  hand-transcribed from the real `require_role(...)` calls in all 15 routers, including honestly
  recording real gaps the brief's requested grid doesn't have an endpoint for (e.g. Wells has no
  delete endpoint) via a `note` field rather than inventing one. Role management follows the same
  logic and stays read-only for the same reason — a role name is a hard-coded string literal, so
  a UI-created role would enforce nothing.
- **A real security gap, found by reading the code rather than assumed away, and fixed as part of
  functionality the brief explicitly asked for.** "Activate/deactivate users" is meaningless if a
  deactivated user's existing JWT keeps working — and it did, before this module: neither
  `deps.py`'s `get_current_user` nor `routers/auth.py`'s `login` checked `User.is_active`. Fixed
  as a 2-call-site, additive change, verified end-to-end (not just unit-tested in isolation): a
  token issued before deactivation is rejected on its very next request after the deactivation
  happens, confirmed via both a backend test and a live curl-based smoke test.
- **A sixth "modeled but never populated" table, extended the same way as the prior five.**
  `AuditLog` existed since the initial scaffold with zero rows ever written anywhere (grepped to
  confirm) — the same situation `Alert`/`AIRecommendation`/`OperatingCost`/`ProductionLoss`/
  `Report` were all in before their modules populated them. Extended with `status` and
  `metadata_json` (named `_json` since SQLAlchemy's declarative `Base` reserves the plain
  `metadata` attribute name) and written for the first time via one wrapped, never-raising write
  path (`services/audit.py::record_audit_event()`).
- **Audit hooks scoped to exactly what the brief names, the same "don't touch every router for a
  nice-to-have" judgment call Alerts' engine-vs-router reuse and Reports' narrow calculation-reuse
  map already established.** Wired into user management, `PUT /settings/{key}`, `POST /reports`,
  `POST /what-if/scenarios`, and `POST /ai-insights/run` — not the other 7 routers' CRUD, which
  the brief never named and which would have meaningfully raised regression risk on an otherwise-
  stable, already-tested codebase for marginal value.
- **AI key protection achieved by construction, not by redacting a response after the fact.**
  `GET /administration/ai-config` and `/system-health` only ever call
  `get_ai_provider(settings).provider_name`/`.model`/`.is_configured` — properties that were
  already safe by design in the AI Insights module's own provider abstraction. No Administration
  code path ever reads `settings.openai_api_key` or the other 3 provider key/URL fields, so there
  is no key-shaped value anywhere in this module's code for a future bug to accidentally expose.
- **A new paginated admin user-list endpoint, kept fully separate from the existing one, rather
  than extending it.** `GET /users` (added by the Maintenance module for the technician-assignment
  dropdown) is unpaginated, active-only, and takes only a `role=` filter — extending its response
  shape or default filtering to serve Administration's fuller needs would have risked that
  existing caller. `GET /administration/users` is a new, separate, Administrator-only endpoint
  with real pagination/search/role/active filters; `GET /users` is untouched, byte-for-byte, and
  covered by a regression test asserting its existing shape and access level still hold.
- **8 new settings via the by-now-established pattern** (`_KEY`/`DEFAULT_`/typed-getter in
  `system_settings.py`, seeded via the migration itself, validated via a new `ALLOWED_VALUES`/
  `FREE_TEXT_SETTING_KEYS` branch in `routers/settings.py`) — company name, default currency,
  unit system, date format, timezone, and 3 default unit labels. The Administration settings page
  groups all 38 settings (8 new + 30 existing thresholds) by category for a usable UI; the
  underlying `GET`/`PUT /settings` endpoints themselves are unchanged.

See `docs/data-model.md` for the `AuditLog` field additions and the 8 new `SystemSetting` keys;
`docs/api.md` for the `/administration` and extended `/users` endpoint summary; `docs/security.md`
for the full authorization architecture, default roles/permissions, audit logging, and data-
protection control documentation this module introduces.

## Applied to: Password management & email verification
A cross-cutting auth feature, not a new sidebar module — added after Administration exposed a
real gap: there was no way to change a password at all (`UserUpdate` deliberately never touches
`hashed_password`, and no self-service endpoint existed either).

- **Stateless, single-use tokens via a password-hash fingerprint claim, no new token-storage
  table.** `core/security.py`'s `create_purpose_token`/`decode_purpose_token` reuse the existing
  JWT machinery with a `purpose` claim; a reset token embeds an HMAC fingerprint of the password
  hash at issue time, so consuming it (or any intervening password change) auto-invalidates it —
  the same trick Django's `PasswordResetTokenGenerator` uses, adapted to a codebase with no
  Redis/session table.
- **A `mail_providers/` package mirrors `services/ai_providers/` exactly** — only a console/dev
  provider is implemented (logs the message instead of sending it), selected the same way
  `ai_provider` selects among AI providers, ready for a real SMTP/API provider to be added later
  behind the same interface without touching any caller.
- **A deliberately accepted, documented limitation, not silently shipped as fixed**: an access
  token issued before a password reset/change stays valid until it naturally expires, since
  `deps.py`'s `get_current_user` checks `is_active` but not the password hash — closing this
  fully would mean touching this codebase's highest-blast-radius file and rippling into every
  test that builds a token directly. See `docs/security.md`.
- **A real security gap found during this session's own master audit, fixed in the same pass**:
  `POST /auth/login` had zero rate limiting (only forgot-password/send-verification did) —
  closed by reusing the same `check_email_rate_limit` helper, keyed by the submitted email.

See `docs/security.md`'s "Password management & email verification" section for the full design,
and `docs/api.md`'s Auth section for the 5 new endpoints.

## Applied to: Dashboard redesign & oil/gas branding
Not a new module — the main `/dashboard` page was the thinnest page in the app (2 of its 7 KPI
cards were hardcoded `"—"` placeholders explicitly marked "not yet connected," despite the data
having been available via `getCostRevenueDashboard()` since the Cost & Revenue module shipped).

- **Every new section reuses an already-shipped component and an already-shipped endpoint** —
  zero new backend work, zero new chart types. The 2 fake KPIs were wired to real Cost & Revenue
  figures; new sections (production trend, equipment health distribution, production-loss-by-
  category, and 3 "needs attention" list widgets) all call existing dashboard/summary endpoints
  other modules already had.
- **Branding color (an amber/gold oil & gas accent) was scoped to chrome only** (Sidebar,
  auth pages) **on the user's explicit choice**, not applied to data/charts — the validated
  `--chart-series-*`/`--status-*` tokens stayed untouched, since "distinctive" here means
  deliberate information hierarchy on one page, not a new visual language clashing with the
  other 11 modules. Contrast was computed with the `dataviz` skill's validator, not eyeballed
  (`amber-700`/`amber-400` text, `amber-700`/`amber-500` buttons — both pairs ≥4.5:1).
  A dashboard-only hero banner (`DashboardHero.tsx`) followed the same rule: an original inline-
  SVG illustration, no external image file or network dependency, matching this app's
  "everything local" convention — the user's explicit choice over hotlinking a real photo.

See `docs/data-model.md`/`docs/api.md` — unchanged by this work, since every figure reuses an
existing endpoint; the dashboard page itself and `DashboardHero.tsx` are the only new files.
