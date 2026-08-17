# API

Full interactive request/response schemas: `http://localhost:8000/docs` (FastAPI's auto-served
Swagger UI) once the backend is running. This file only summarizes endpoint groups, auth
requirements, and the two design decisions that aren't self-evident from the OpenAPI schema
alone (below).

## Auth
`POST /auth/login` (OAuth2 password flow, form-urlencoded) → JWT. `GET /auth/me` → current
user, including `role_name` (used by the frontend to gate write UI without a second lookup).

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /auth/change-password` | any authenticated user | body: `current_password`, `new_password` (min 8 chars); 400 if `current_password` doesn't match; audits `password_changed` |
| `POST /auth/forgot-password` | public | body: `email`; **always** returns the same generic message regardless of whether the account exists/is active (anti-enumeration); rate-limited 3/15min per submitted email; only a real, active account gets a token issued/"emailed" — see `docs/security.md` |
| `POST /auth/reset-password` | public | body: `token`, `new_password`; stateless, single-use via a password-hash fingerprint claim (no token table) — see `docs/security.md` for the full design and its one accepted limitation |
| `POST /auth/send-verification` | any authenticated user, rate-limited 3/15min | idempotent no-op if already verified; issues an email-verification token otherwise |
| `POST /auth/verify-email` | public | body: `token`; sets `is_email_verified=true`; idempotent on repeat calls |

`forgot-password`/`send-verification` responses include `debug_token`/`debug_reset_url`/
`debug_verify_url` fields, populated **only** when `ENVIRONMENT=development` — the only mail
provider implemented (`services/mail_providers/`) is a console/dev one that logs the message
instead of sending it, so these fields make the flow testable without any mail infrastructure.

## Wells (`/wells`, `/facilities`)
`GET/POST /wells`, `GET/PUT /wells/{id}`, `GET /wells/{id}/{production,pressure,downtime,
maintenance}`, `GET /facilities`. Reads: any authenticated user. Writes: `Administrator` or
`Production Engineer`.

## Production (`/production`)
Composite-record CRUD, export, KPIs, trends, scope comparisons, targets, and rule-based issue
detection — see `docs/data-model.md` for what "composite record" means.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /production` | any authenticated user | `search`, `well_id`, `field_id`, `facility_id`, `date_from`, `date_to`, `sort`, `order`, `page`, `page_size` |
| `POST /production` | Administrator/Production Engineer | 422 on invalid values (negative production/pressure, extreme temperature); 201 with `warnings` populated on unusual-but-plausible values; 400 on `(well_id, record_date)` duplicate |
| `GET/PUT/DELETE /production/{id}` | read: any user; write: Administrator/Production Engineer | `well_id`/`record_date` are immutable on update (delete + recreate to move a record); delete cascades to sibling pressure/temperature rows only, never `DowntimeEvent` |
| `GET /production/export` | any authenticated user | streams CSV, same filters as the list endpoint (shared query-builder, so they can't drift) |
| `GET /production/kpis` | any authenticated user | see `docs/data-model.md` / router docstring-level comments for exact formulas (volume-weighted water-cut/GOR, `reference_date = MAX(record_date)` in scope, not literal calendar-today) |
| `GET /production/trends?metric=oil_gas_water\|water_cut\|gor\|pressure` | any authenticated user | scoped by well/field/facility/date range |
| `GET /production/by-scope?group_by=well\|field\|facility` | any authenticated user | ranking bars, `order`/`limit` |
| `GET /production/actual-vs-target` | any authenticated user | per-date actual vs. resolved target (see `ProductionTarget` resolution rule in `docs/data-model.md`) |
| `GET /production/issues` | any authenticated user | rule-based only (open downtime events, zero-production active wells) — explicitly not anomaly detection |
| `GET/POST/PUT/DELETE /production/targets` | read: any user; write: Administrator/Production Engineer | |

### CSV import (`/production/import`) — design notes
Both endpoints require `Administrator`/`Production Engineer`.

- **`POST /production/import/preview`** (multipart file upload) parses, validates, and
  classifies every row (`valid | warning | duplicate | invalid`) and **persists nothing**.
- **`POST /production/import/confirm`** takes the client's reviewed rows back, each carrying
  the user's chosen `action` (`create | overwrite | skip`) — there is **no server-side
  staging/import-job table**. The confirm endpoint re-parses and re-validates every row from
  scratch and re-checks for duplicates against the current DB state before writing anything;
  it never trusts whatever `status` the earlier preview response claimed. Still-invalid rows
  are always rejected regardless of the requested action. Rejected rows are always returned in
  the response (`rejected: [...]`) — never silently dropped.
- Row-level writes during confirm use a SQL savepoint (`Session.begin_nested()`) so one row's
  failure doesn't abort rows already written earlier in the same batch.
- CSV parsing (`backend/app/services/csv_import.py`) returns a plain `list[dict[str, str]]` —
  a deliberate seam so a future Excel importer could return the same shape and reuse all the
  validation/classification logic unchanged. No `openpyxl`/Excel dependency is added yet.

## Equipment (`/equipment`)
Reads: any authenticated user. Writes: `Administrator` or `Maintenance Engineer` (the product
brief's stated domain owner for equipment/maintenance data — deliberately not the
Production Engineer pair Wells/Production use). Fixed sub-paths (`/dashboard`, `/by-scope`,
`/issues`) are registered before `/{id}` to avoid Starlette treating them as an id.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /equipment` | any authenticated user | `search`, `equipment_type`, `status`, `field_id`, `facility_id`, `well_id`, `sort`, `order`, `page`, `page_size` |
| `POST /equipment` | Administrator/Maintenance Engineer | `equipment_tag` unique (400 on duplicate); resolves `field`/`facility`/`well` display fields from whichever of `facility_id`/`well_id` is set; computes and stores an initial health score |
| `GET/PUT/DELETE /equipment/{id}` | read: any user; write: Administrator/Maintenance Engineer | `PUT` recomputes and re-caches the health score if status/operating-hours/health-relevant fields change; `DELETE` returns 400 if any maintenance/reading/downtime history exists (no cascade — preserves the audit trail) |
| `GET /equipment/{id}/health` | any authenticated user | always recomputes fresh from current data (never trusts the cache) and writes the result back; returns the full factor-by-factor breakdown plus `disclaimer_text` |
| `GET/POST /equipment/{id}/readings` | read: any user; write: Administrator/Maintenance Engineer | filter by `parameter`/date range; `parameter` is free text (`temperature`, `vibration`, `current`, `flow`, ...) — this is real infrastructure for future SCADA/IoT/historian population, not a mock integration; a POST of a health-relevant parameter triggers a health recompute |
| `GET /equipment/{id}/maintenance` | any authenticated user | direct `equipment_id` FK on `MaintenanceRecord` — reuses `MaintenanceRecordRead`/`MaintenanceSummary` from `schemas/well.py` |
| `GET /equipment/{id}/downtime` | any authenticated user | direct `equipment_id` FK on `DowntimeEvent` — reuses `DowntimeEventRead`/`DowntimeSummary` from `schemas/well.py` |
| `GET /equipment/dashboard` | any authenticated user | status counts (including a rule-based `attention_count`) + health-band distribution |
| `GET /equipment/by-scope?group_by=type\|field\|facility` | any authenticated user | count + average health score per bucket |
| `GET /equipment/issues?limit=` | any authenticated user | failed-status items first, then lowest health score |

Health scoring itself (`backend/app/services/equipment_health.py`) is documented in
`docs/data-model.md`'s "Equipment health score" section — it is explicitly a **decision-support
indicator, not a certified safety or engineering system**, per this project's standing AI/
analytics-output guardrail.

## Maintenance (`/maintenance`)
Reads: any authenticated user. Writes: `Administrator` or `Maintenance Engineer` (same domain
owner as Equipment). One `MaintenanceRecord` row *is* one work order — no separate work-order
resource. Fixed sub-paths registered before `/{id}`.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /maintenance` | any authenticated user | `search`, `equipment_id`, `well_id`, `field_id`, `facility_id`, `status`, `priority`, `maintenance_type`, `date_from`/`date_to` (on actual `start_date`), `sort`, `order`, `page`, `page_size` |
| `POST /maintenance` | Administrator/Maintenance Engineer | requires a valid `equipment_id`; auto-generates `work_order_number`; computes `cost` from the four cost components (never accepted directly); recomputes the linked equipment's health score |
| `GET/PUT/DELETE /maintenance/{id}` | read: any user; write: Administrator/Maintenance Engineer | `PUT` recomputes equipment health if `status`/`maintenance_type`/`start_date`/`equipment_id` change (recomputes for both old and new equipment on reassignment); `DELETE` returns 400 unless status is `scheduled`/`open` with no cost or downtime recorded yet — cancel via `PUT status=cancelled` instead to preserve the audit trail |
| `GET /maintenance/dashboard` | any authenticated user | status counts (incl. `emergency_count` and a rule-based `computed_overdue_count`), total cost, total downtime, equipment requiring maintenance |
| `GET /maintenance/by-scope?group_by=type\|equipment\|field\|well` | any authenticated user | count + total cost + total downtime per bucket; `well` added by the Cost & Revenue module for well-level maintenance cost economics |
| `GET /maintenance/cost-trend` | any authenticated user | monthly cost totals, keyed off actual (falling back to planned) start date |
| `GET /maintenance/schedule` | any authenticated user | `overdue`/`due_today`/`upcoming` buckets, combining open work orders' `planned_completion_date` and each equipment's own `next_maintenance_due` (`maintenance_schedule_lookahead_days` setting controls the upcoming window) — rule-based, never mutates a record's stored status |

Equipment reliability (MTBF/MTTR/availability/failure frequency) is equipment-scoped, so it's
exposed as `GET /equipment/{id}/reliability` (any authenticated user) rather than under
`/maintenance` — see `docs/data-model.md`'s "Reliability metrics" section for the documented
assumptions and disclaimer.

## Production Loss (`/production-loss`)
Reads: any authenticated user. Writes: `Administrator` or `Production Engineer` (matches
Wells/Production's domain ownership — this is a production-analysis/financial-reporting
artifact, not a Maintenance Engineer concern, even though it links to Equipment/Maintenance
data).

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /production-loss` | any authenticated user | `search` (cause), `well_id`, `equipment_id`, `field_id`, `facility_id`, `category`, `date_from`/`date_to`, `sort`, `order`, `page`, `page_size` |
| `POST /production-loss` | Administrator/Production Engineer | auto-resolves `ProductionTarget`/`ProductionRecord`/`CommodityPrice` for the given `well_id`+`loss_date` and computes lost volumes/revenue impact/currency for any field left unset; a caller-supplied value always takes precedence over the auto-computed one |
| `GET/PUT/DELETE /production-loss/{id}` | read: any user; write: Administrator/Production Engineer | `PUT` re-resolves and recomputes any not-manually-overridden field when `well_id`/`loss_date`/`downtime_event_id`/`maintenance_record_id` change; `DELETE` returns 400 if linked to a real `downtime_event_id`/`maintenance_record_id` — edit instead to preserve the audit trail |
| `GET /production-loss/dashboard` | any authenticated user | event count, total oil/gas lost, total revenue impact, avg downtime, counts by category |
| `GET /production-loss/by-scope?group_by=category\|well\|equipment\|field` | any authenticated user | count + total oil/gas lost + total revenue impact per bucket |
| `GET /production-loss/trend` | any authenticated user | monthly oil/gas-lost and revenue-impact totals |

Every response carries a `disclaimer_text` (`PRODUCTION_LOSS_DISCLAIMER`) plus the resolved
`oil_price_per_bbl`/`gas_price_per_mscf` that drove the revenue figure — see
`docs/data-model.md`'s "Production Loss" section for the full computation rule. Explicitly a
**decision-support estimate, not a certified financial figure**, per this project's standing
AI/analytics-output guardrail — no AI root-cause analysis, predictive analytics, or
SCADA/DCS/autonomous control is implemented here.

## Operating Costs (`/operating-costs`)
Reads: any authenticated user. Writes: `Administrator` or `Management` — the first module where
the write-role pair isn't a Production/Maintenance Engineer, re-derived from the brief's framing
as a management/analyst decision-support tool. No delete-block: a plain entered financial record
with no downstream FK dependents, freely correctable by an authorized role.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /operating-costs` | any authenticated user | `search` (description), `field_id`, `facility_id`, `well_id`, `equipment_id`, `category`, `currency`, `date_from`/`date_to`, `sort`, `order`, `page`, `page_size` |
| `POST /operating-costs` | Administrator/Management | validates `amount >= 0`, `currency` is `USD`/`NGN`, and any supplied `field_id`/`facility_id`/`well_id`/`equipment_id` exists (404 otherwise); `field_name`/`facility_name` on read are resolved through a field→facility→well→equipment fallback even when only the most-specific FK is set |
| `GET/PUT/DELETE /operating-costs/{id}` | read: any user; write: Administrator/Management | `field_id`/`facility_id`/`well_id`/`equipment_id` on read are the raw stored values (edit-form fidelity), distinct from the resolved `field_name`/`facility_name` |

## Cost & Revenue (`/cost-revenue`)
Reads: any authenticated user. Connects Production, Operating Cost, Maintenance Cost, and
Production Loss into a management/analyst-facing economics view — see `docs/data-model.md`'s
"Cost & Revenue" section for the four calculation formulas and the currency-safety rule this
whole module is built around.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /cost-revenue/dashboard` | any authenticated user | fixed to the latest calendar month with production data; production/revenue/costs/economics/production-loss sections, all money as `list[{currency, amount}]` |
| `GET /cost-revenue/unit-economics` | any authenticated user | filterable by `field_id`/`facility_id`/`well_id`/`date_from`/`date_to`; cost & revenue per bbl/BOE, margin only where currency-matched |
| `GET /cost-revenue/economics-by-scope?scope=field\|well&rank_by=production\|revenue\|cost_efficiency\|margin` | any authenticated user | one endpoint serves both Field and Well Economics; well rows add nullable `high_production`/`high_cost`/`low_margin`/`high_loss` flags plus a `review_note` — never an automatic "uneconomic" label |
| `GET /cost-revenue/revenue-trend` | any authenticated user | monthly, filterable by field/facility/well/commodity |
| `GET /cost-revenue/cost-trend` | any authenticated user | monthly **operating** cost by currency (distinct from `/maintenance/cost-trend`) |
| `GET /cost-revenue/margin-trend` | any authenticated user | monthly, currency-matched scopes only |
| `GET /cost-revenue/alerts` | any authenticated user | 6 rule-based categories (rapid cost increase, high maintenance cost, high cost/bbl, high production loss, declining margin, unusually high energy cost) — informational only, explicitly not AI-driven |

Every money figure across both routers is grouped `list[{currency, amount}]`, never blended
across currencies; a margin/per-unit figure returns empty with `currency_mismatch: true` rather
than an invented exchange rate. Every dashboard/unit-economics response carries a
`disclaimer_text` (`ECONOMICS_DISCLAIMER`) — **management/analytical estimates, not audited
accounting figures**, per this project's standing guardrail. No AI financial recommendations,
autonomous decisions, or SCADA/DCS control are implemented here.

## Alerts (`/alerts`)
Reads: any authenticated user. Lifecycle actions (acknowledge/investigate/resolve/dismiss/
notes): any authenticated user **except Viewer** — operational actions, not a single domain's
write privilege. Manual create/update: `Administrator`/`Management`. Rule-engine trigger:
`Administrator` only (a system operation, not domain data entry). See `docs/data-model.md`'s
"Alerts" section for the full 22-rule table, severity rubric, and dedup/auto-resolve mechanics.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /alerts` | any authenticated user | `search` (title/description), `severity`, `category`, `status`, `field_id`, `facility_id`, `well_id`, `equipment_id`, `date_from`/`date_to` (on `triggered_at`), `sort`, `order`, `page`, `page_size` |
| `POST /alerts` | Administrator/Management | manual creation; `dedup_key` auto-generated as `manual:{uuid}` so the rule engine's dedup lookup and auto-resolve sweep never touch it |
| `GET/PUT /alerts/{id}` | read: any user; write: Administrator/Management | `PUT` edits title/description/severity/recommended_action/notes directly (not a status transition — see the action endpoints below) |
| `GET /alerts/summary` | any authenticated user | dashboard aggregate: totals, by-severity/status/category/field/equipment counts, recent alerts |
| `POST /alerts/run` | Administrator | triggers `run_alert_rules()`, returns per-category created/updated/auto-resolved counts |
| `GET /alerts/{id}/history` | any authenticated user | `AlertStatusHistory` rows (every transition + note addition), newest first |
| `PUT /alerts/{id}/acknowledge` | any except Viewer | sets status `acknowledged`, records `acknowledged_at`/`acknowledged_by`, optional note |
| `PUT /alerts/{id}/investigate` | any except Viewer | sets status `investigating` |
| `PUT /alerts/{id}/resolve` | any except Viewer | sets status `resolved`, records `resolved_at`/`resolved_by`, optional note |
| `PUT /alerts/{id}/dismiss` | any except Viewer | sets status `dismissed`, optional note |
| `POST /alerts/{id}/notes` | any except Viewer | appends a note-only history row and updates the alert's current `notes` field |

Every response carries `disclaimer_text` (`ALERT_DISCLAIMER`) — a rule-based decision-support
indicator requiring engineering/management review, never a guaranteed conclusion or autonomous
action. No AI, machine learning, predictive maintenance, autonomous equipment/production
control, or external (email/SMS/WhatsApp) notifications are implemented here — see
`docs/data-model.md`'s "Notification foundation" note for what's deliberately deferred.

## AI Insights (`/ai-insights`)
Reads: any authenticated user. Status update (reviewed/dismissed) and feedback submission: any
authenticated user **except Viewer**. `/assistant` and `/interpret`: same role restriction, plus
a hand-rolled in-memory rate limit (10 requests/60s per user per endpoint — resets on process
restart, not multi-worker-safe). `/run`: `Administrator` only, and is **never** rate-limited or
AI-touched (100% deterministic). See `docs/data-model.md`'s "AI Insights" section for the full
24-type table, confidence rubric, and dedup/staleness mechanics, and `docs/ai-architecture.md`
for the provider abstraction and hybrid-intelligence boundary.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /ai-insights` | any authenticated user | `search` (title/summary), `category`, `insight_type`, `severity`, `confidence_level`, `status`, `field_id`, `facility_id`, `well_id`, `equipment_id`, `date_from`/`date_to`, `sort`, `order`, `page`, `page_size` |
| `GET /ai-insights/{id}` | any authenticated user | full detail incl. nested `AIInsightEvidence`/`AIInsightFeedback` |
| `PUT /ai-insights/{id}/status` | any except Viewer | `reviewed`/`dismissed` — dismissal is always manual, the engine never auto-dismisses |
| `POST /ai-insights/{id}/feedback` | any except Viewer | `useful`/`not_useful`/`incorrect`/`needs_review`, storage only, never used to auto-train |
| `POST /ai-insights/{id}/interpret` | any except Viewer, rate-limited | adds an AI-authored interpretive paragraph via the configured provider (or `NullProvider`'s deterministic phrasing) to an already-generated insight |
| `POST /ai-insights/run` | Administrator | triggers `run_insight_engine()`, returns per-category created/updated counts, always deterministic |
| `GET /ai-insights/summary` | any authenticated user | dashboard aggregate: totals, by-severity/category/confidence counts, recent + critical insights |
| `POST /ai-insights/assistant` | any except Viewer, rate-limited | Q&A; matches ~8 known question patterns deterministically against real data with source citations, falls through to the configured AI provider (or a clear "can't answer" message) only for unmatched questions |
| `GET /ai-insights/daily-brief` | any authenticated user | 7-section operations brief; `?narrative=true` adds an optional AI-authored narrative layered on the same computed figures |
| `GET /ai-insights/management-summary` | any authenticated user | 5-question management summary; same optional `?narrative=true` |

Every response carries `disclaimer_text` (`INSIGHT_DISCLAIMER`) — an evidence-cited observation
requiring engineering/management review, never a guaranteed conclusion. No autonomous equipment/
production control, no claimed root causes without explicit evidence, no fabricated data/costs/
production values, and no presenting an estimate as an audited result are implemented or
permitted here.

## What-If Simulator (`/what-if`)
Reads (list/get/preview/compare/sensitivity): any authenticated user, since none of these
persist or change anything. Create/update/delete/rerun/interpret: any authenticated user
**except Viewer** — a planning tool every operational/analytical role should be able to use,
same reasoning as Alerts' lifecycle-action gating. `/interpret` is additionally rate-limited via
the same `rate_limiter()` factory AI Insights uses. See `docs/data-model.md`'s "What-If
Simulator" section for the full formula set, the frozen-snapshot storage design, and the
two-tier guardrail rubric.

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /what-if/scenarios` | any except Viewer | resolves the baseline, computes the scenario, hard-rejects (422) any mathematically impossible assumption, stores `results`+`calculation_version`+`last_run_at` as a frozen snapshot |
| `GET /what-if/scenarios` | any authenticated user | `search` (name), `created_by_id`, `field_id`, `well_id`, `sort`, `order`, `page`, `page_size` |
| `GET /what-if/scenarios/{id}` | any authenticated user | returns the stored snapshot — never recomputes |
| `PUT /what-if/scenarios/{id}` | any except Viewer | updates name/description/baseline/assumptions and recomputes (a fresh "run") |
| `DELETE /what-if/scenarios/{id}` | any except Viewer | |
| `POST /what-if/scenarios/{id}/rerun` | any except Viewer | recomputes against current data, assumptions unchanged — the one way a saved snapshot updates |
| `POST /what-if/preview` | any authenticated user | ad-hoc baseline+assumptions run, nothing persisted — the Scenario Builder's live-preview step |
| `POST /what-if/compare` | any authenticated user | body: `scenario_ids` (2+); compares each scenario's **stored** results, never recomputes; optional `?narrative` AI comparison |
| `POST /what-if/sensitivity` | any authenticated user | body: baseline + base assumptions + a swept `variable` + `values`; returns one point per value, reusing the same deterministic formulas |
| `POST /what-if/scenarios/{id}/interpret` | any except Viewer, rate-limited | mirrors AI Insights' `/interpret` — interprets the scenario's already-stored results, never recalculates |

Every response carries `disclaimer_text` (`WHATIF_DISCLAIMER`) — a planning/decision-support
estimate, never a forecast or guaranteed outcome. No scenario, run, or comparison ever modifies
a production/cost/maintenance record, changes an equipment setting, or sends a SCADA/DCS
command.

## Reports (`/reports`)
Reads (`types`/`preview`/list/get/export): any authenticated user. Create/update/delete/
regenerate: any authenticated user **except Viewer** — same role philosophy as What-If Simulator
and Alerts (a planning/reporting tool every operational/analytical role should be able to use,
write actions restricted). See `docs/data-model.md`'s "Reports" section for the 4 report types,
the per-section calculation-reuse map, and the frozen-snapshot storage design.

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /reports/types` | any authenticated user | static metadata: the 4 report types, each with its available sections |
| `POST /reports/preview` | any authenticated user | computes and returns a report, persists nothing — the Report Builder's live-preview step |
| `POST /reports` | any except Viewer | computes + saves a frozen `results` snapshot |
| `GET /reports` | any authenticated user | `search` (name), `report_type`, `created_by_id`, `sort`, `order`, `page`, `page_size` |
| `GET /reports/{id}` | any authenticated user | returns the stored snapshot — never recomputes |
| `PUT /reports/{id}` | any except Viewer | renames/updates description/filters/sections only — never silently recomputes `results` |
| `DELETE /reports/{id}` | any except Viewer | |
| `POST /reports/{id}/regenerate` | any except Viewer | recomputes against current data, updates `last_generated_at` — the one way a saved snapshot changes |
| `GET /reports/{id}/export?format=csv\|pdf` | any authenticated user | streams from the stored `results` only, never recomputes |

Filters (`ReportFilters`): `date_from`/`date_to`, `field_id`/`facility_id`/`well_id`/
`equipment_id`, `commodity`, `maintenance_type`, `alert_severity`, `production_loss_category`,
and `scenario_id` (What-If Scenario Report only) — the same filter set applies consistently
across every section of a report. `POST /reports`/`/preview` validate that any referenced field/
facility/well/equipment/scenario actually exists (404 otherwise) and that `date_from <= date_to`
(422 otherwise).

Every response carries `disclaimer_text` (`REPORT_DISCLAIMER`) and — unconditionally, since no
verified-production-data mode exists anywhere in this codebase — `synthetic_data_disclaimer`. No
report generation, export, or regeneration ever modifies a production/cost/maintenance/equipment
record.

## Users (`/users`)
`GET /users?role=<name>` — any authenticated user. Deliberately left unpaginated/active-only,
unchanged since the Maintenance module added it to populate the technician-assignment dropdown —
**this exact shape must not change**, since that caller depends on it. Full user management
(create/edit/role-assign/activate/deactivate) is a separate, Administrator-only surface added by
the Administration module:

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /users` | any authenticated user | unpaginated, active-only, optional `role=` exact-name filter — unchanged, see above |
| `GET /users/{id}` | Administrator | full detail incl. `created_at`/`updated_at`; never returns `hashed_password` |
| `POST /users` | Administrator | hashes the password via the existing `hash_password`; 400 on duplicate email, 404 on unknown `role_id`; audits `user_created` |
| `PUT /users/{id}` | Administrator | updates `full_name`/`role_id`/`is_active` only — **never accepts or returns a password field**; audits `role_changed` and/or `user_activated`/`user_deactivated` and/or `user_updated`, whichever actually changed |

Deactivating a user (`is_active=false`) takes effect immediately, not just on next login — both
`get_current_user` and `login` reject inactive users, so an already-issued JWT stops working on
its very next request. See `docs/data-model.md`'s Administration section for why this was a real,
pre-existing gap fixed by this module.

## Settings (`/settings`)
`GET /settings` — any authenticated user. `PUT /settings/{key}` — **Administrator only**
(narrower than the usual Administrator/Production Engineer write pattern, since a bad
conversion factor silently corrupts every BOE figure company-wide). Now also validates the 8
Administration-added string settings: `default_currency`/`unit_system` against a fixed allowed-
value set, the remaining 6 (`company_name`, `timezone`, `date_format`, `default_production_unit`,
`default_gas_unit`, `default_volume_unit`) as non-blank free text. Every successful update is
audited (`system_setting_changed`, with the old/new value in `metadata_json`).

## Administration (`/administration`)
Every endpoint requires `Administrator` — the only module gated Administrator-only on reads as
well as writes. See `docs/data-model.md`'s Administration section for why (permission/role
management are read-only views, not editable systems) and `docs/security.md` for the full
security/data-protection control list.

| Endpoint | Notes |
|---|---|
| `GET /administration/dashboard` | total/active/inactive users, per-role user counts, 5 most recent audit events, system/config status summary, `ai_provider_configured` |
| `GET /administration/roles` | the 7 fixed roles with a live user count each — no create/delete (roles are hard-coded string literals inside `require_role(...)` calls, not database-editable) |
| `GET /administration/permissions` | the static, code-derived matrix from `services/permissions.py` — mirrors the real `require_role(...)` calls in every router, including honestly-recorded gaps (e.g. Wells has no delete endpoint) |
| `GET /administration/users` | paginated, fully-filterable (`search`, `role_id`, `is_active`, `page`, `page_size`) — the Administration module's own list, separate from the unpaginated `GET /users` above |
| `GET /administration/audit-log` | `search` (action/details), `user_id`, `action`, `resource` (matches `entity_type`), `date_from`/`date_to`, `page`, `page_size` |
| `GET /administration/audit-log/{id}` | single event detail |
| `GET /administration/system-health` | backend/database/API status (computed live, `SELECT 1` for the DB check), AI provider status, app version, environment — never a connection string, port, or other infrastructure detail |
| `GET /administration/ai-config` | `provider`/`model`/`is_configured`/`status` — only ever reads the already-safe properties of the resolved `AIProvider` instance, never the raw API key fields on `Settings` |

Audit logging (`services/audit.py::record_audit_event`) is wired into exactly what the brief
names — the user-management endpoints above, `PUT /settings/{key}`, `POST /reports`, `POST
/what-if/scenarios`, and `POST /ai-insights/run` — not every CRUD endpoint in every router, to
bound regression risk. Every audit row records `action`/`user`/`resource`/`resource_id`/
`timestamp`/`status`/`metadata`; never a password, API key, or other secret. A logging failure is
caught and logged, never raised — it can't break the action it's describing.

## Validation tiers (shared by manual entry and CSV import)
`backend/app/services/production_validation.py` is the single source for all three:
**invalid** (rejected — negative production/pressure, implausible temperature), **warning**
(saved/imported anyway, surfaced to the user — extreme-but-plausible values, missing
pressure/temperature), **duplicate** (import-only — `(well_id, record_date)` collision,
resolved via `action`). Both `routers/production.py` (manual create/update) and
`routers/production_import.py` (CSV) call the same function — the rules only live in one
place.
