# Data Model

Defined in `backend/app/models/`, versioned by Alembic (`backend/alembic/versions/`). Plain
integer primary keys and portable `sqlalchemy.JSON`/standard types are used deliberately (not
UUIDs or Postgres-only types like `JSONB`) so the schema also builds against an in-memory
SQLite engine for pytest, independent of the Docker/Postgres stack.

**Note on test coverage**: pytest builds tables via `Base.metadata.create_all()` against SQLite
directly — it does not run Alembic migrations. This means Alembic migrations are not exercised
by the automated test suite; they're verified manually via `alembic upgrade head` against the
real Postgres service.

## Tables

| Model | File | Notes |
|---|---|---|
| `Role` | `role.py` | 7 fixed roles, seeded by `app/db/seed.py` |
| `User` | `user.py` | FK → `Role` |
| `Field`, `Facility`, `Well` | `field.py` | `Field → Facility → Well` hierarchy. `Well` carries completion fields (`completion_date`, `completion_type`, `total_depth_ft`), added by the Wells module (revision `408beac6a9ce`) |
| `ProductionRecord`, `PressureRecord`, `TemperatureRecord` | `production.py` | FK → `Well`. Each carries a **unique constraint on `(well_id, record_date)`** (added by the Production module, revision `8876892ab81c`) — enforces "one record per well per day," the invariant the Production module's composite-record API, CSV import dedup, and edit semantics all assume. |
| `ProductionTarget` | `production.py` | FK → `Well`. Per-well, effective-dated rate targets (`oil_target_bopd`/`gas_target_mscfd`/`water_target_bwpd`); unique on `(well_id, effective_date)`. Resolution rule: the most recent row with `effective_date <= record_date` for that well applies. Added by the Production module. |
| `SystemSetting` | `settings.py` | Generic admin-configurable key/value config (`key` unique, `value`, `description`) — not a demo-data table. Holds `boe_gas_factor_scf_per_bbl` (default `6000`, Production), `equipment_health_operating_hours_threshold` (default `40000`, Equipment), `maintenance_schedule_lookahead_days` (default `30`, Maintenance), the 18 `alert_*`/7 `insight_*`/1 `whatif_*` threshold keys, and 8 company/display keys (`company_name`, `default_currency`, `unit_system`, `date_format`, `timezone`, `default_production_unit`, `default_gas_unit`, `default_volume_unit`, added by the Administration module, revision `107095967769`) — all seeded by their migration, not a seed script, since app config must exist in every environment. Editable via `PUT /settings/{key}` (Administrator-only); browsable as a grouped UI at `/administration/settings`. |
| `Equipment`, `EquipmentReading`, `MaintenanceRecord`, `DowntimeEvent` | `equipment.py` | `Equipment` FK → `Facility`/`Well` (both independently nullable — well-linked, facility-linked, or standalone); `facility`/`well` relationships added by the Equipment module (revision `3b9c217baa6d`), alongside `name`, `commissioning_date`, `operating_hours`, `description`, `next_maintenance_due` (all nullable), plus `maintenance_frequency_days` (nullable, Maintenance module). `equipment_type` and `status` are free-text/validated-Literal-on-write strings, not DB enums — see the health-score note below for `health_score`/`health_band`. `MaintenanceRecord`/`DowntimeEvent` carry a **direct** `equipment_id` FK (simpler than routing through `Well`) — see the "Maintenance work orders" section below for `MaintenanceRecord`'s full field set. |
| `ProductionLoss`, `CommodityPrice` | `economics.py` | Extended by the Production Loss module (revision `9ec63324886e`) — see the dedicated section below. |
| `OperatingCost` | `economics.py` | Extended by the Cost & Revenue module (revision `3b65bf411ca3`) — see the dedicated section below. |
| `Alert`, `AlertStatusHistory` | `ai.py` | Extended/added by the Alerts module (revision `904e02efa718`) — see the dedicated section below. |
| `AIRecommendation`, `AIInsightEvidence`, `AIInsightFeedback` | `ai.py` | Extended/added by the AI Insights module (revisions `fea98f807a60`, `709cc3909898`) — see the dedicated section below. |
| `AIPrediction` | `ai.py` | Genuine forecasting/ML — deliberately left dormant by every module through AI Insights; reserved for a future, explicitly-scoped forecasting module. |
| `Report` | `reporting.py` | Extended by the Reports module (revision `742f03778de9`) — see the dedicated section below. |
| `AuditLog` | `reporting.py` | FK → `User`. Extended by the Administration module (revision `107095967769`, added `status`/`metadata_json`) and, for the first time, actually written — see the dedicated section below. |
| `Scenario` | `simulation.py` | Added by the What-If Simulator module (revision `f2a150e1c63d`) — the first genuinely new table since the original schema, not an extension of a pre-existing dormant one; see the dedicated section below. |

## Relationships
```
Field 1──* Facility 1──* Well 1──* {ProductionRecord, PressureRecord, TemperatureRecord, ProductionTarget}
Facility/Well 1──* Equipment 1──* {EquipmentReading, MaintenanceRecord}
Well/Equipment ──o {AIPrediction, AIRecommendation, ProductionLoss, DowntimeEvent}
Well/Equipment/DowntimeEvent/MaintenanceRecord ──o ProductionLoss
Field/Facility/Well/Equipment ──o OperatingCost (each independently nullable)
Field/Facility/Well/Equipment/MaintenanceRecord/ProductionLoss ──o Alert (each independently nullable)
Alert 1──* AlertStatusHistory
User 1──* {MaintenanceRecord (technician), Report (generated_by), AuditLog, Alert (acknowledged_by/resolved_by), AlertStatusHistory (changed_by)}
Field/Facility/Well/Equipment ──o Scenario (each independently nullable — the baseline scope); User 1──* Scenario (created_by)
Scenario ──o Report (via filters.scenario_id, the What-If Scenario Report — a JSON reference, not an FK)
```

## The "composite production record" API concept
`ProductionRecord`, `PressureRecord`, and `TemperatureRecord` remain three separate tables
(deliberately not merged — that would have meant rebuilding the Wells module's existing
schema). The Production API (`backend/app/routers/production.py`) composes them into one
logical resource keyed by `(well_id, record_date)`: creating/updating/deleting a "production
record" through the API transparently creates/updates/deletes the matching rows across all
three tables (pressure/temperature rows only when at least one of their fields is supplied).
`DowntimeEvent` (owned by Wells/Equipment) is joined in **read-only** as a derived
`downtime_hours` value on each composite record — never duplicated or written back, so
downtime data has exactly one source of truth. `water_cut_pct`, `gor`, and `BOE` are always
computed server-side (`backend/app/services/production_calculations.py`) from oil/gas/water —
never accepted as direct input — so they can't drift from the values they're derived from.

## Equipment health score — cached, not stored as truth
`Equipment.health_score`/`health_band` are a **write-triggered cache**, not authoritative
stored data — the source of truth is `backend/app/services/equipment_health.py`'s
`compute_health()`, a pure function of plain inputs (operating hours vs. a configurable
threshold, temperature/vibration trend over the last 30 days, a current/flow z-score anomaly,
corrective-maintenance count over 180 days, current status, downtime hours over 90 days, and
recent alert frequency — each factor optional; missing data means zero deduction, not a
penalty). The cache is refreshed on equipment create, on status/operating-hours update, and on
any new health-relevant reading; `GET /equipment/{id}/health` always recomputes fresh (never
trusts the cache) and writes the result back. Every score response carries a fixed
`disclaimer_text` — mirrors `AIRecommendation.disclaimer_text`'s guardrail spirit, but as a
response field rather than a DB column, since a health score is computed per-request, not a
persisted entity. Per this project's standing guardrail, it is explicitly documented as a
**decision-support indicator, not a certified safety or engineering system** — see
`backend/app/services/equipment_health.py`'s `HEALTH_SCORE_DISCLAIMER`.

## Maintenance work orders — one record, no duplicate model
`MaintenanceRecord` doubles as the work order itself (the Maintenance module deliberately does
not add a separate `WorkOrder` table). Added by that module (revision `ef2abc3c147d`):
`work_order_number` (unique, auto-generated as `WO-{id:06d}` after insert — every writer,
including `backend/app/db/seed_wells.py`, generates it the same way), `priority` (`Literal`
critical/high/medium/low, not null, default `medium`), `planned_start_date`/
`planned_completion_date` (the *planned* dates — new), `labor_cost`/`parts_cost`/
`contractor_cost`/`other_cost` (the only cost inputs) plus `downtime_hours`, `failure_cause`,
`corrective_action`, `notes`, and a `technician` relationship wired onto the previously-unused
`technician_id` FK to `User`.

`start_date`/`completion_date` (pre-existing columns) keep their original meaning — the
*actual* dates work began/finished — unchanged, because `backend/app/services/
equipment_health.py`'s maintenance-history health factor and the Equipment module's
last-maintenance-date lookup both key off them. `maintenance_type` stays a free string (not a
DB enum) with a documented canonical list (preventive/corrective/emergency/predictive/
inspection/calibration/routine) for the frontend's suggestions — same "closed status/priority
vocab as `Literal`, open type vocab as free text" split Equipment established for
`status`/`equipment_type`.

**`cost` is always server-computed**, never a direct write input: `cost = sum(labor_cost,
parts_cost, contractor_cost, other_cost)`, or `None` if all four are unset. This is the
"clearly label all costs as operational estimates unless they represent entered financial
records" requirement made structural — the total can never drift from its components because
nothing can set it independently of them.

## Well → Production → Equipment → Maintenance → Failure/Downtime → Production Loss → Financial Impact
The complete relationship chain, closed by the Production Loss module:
```
Well 1──* ProductionRecord / ProductionTarget          (actual / expected production)
Well ──o Equipment (well_id, nullable — some equipment is facility-level, not well-specific)
Equipment 1──* MaintenanceRecord (equipment_id, required — every work order is equipment-scoped)
Equipment ──o DowntimeEvent (equipment_id, nullable) ──o Well (well_id, nullable, independent FK)
{Well, Equipment, DowntimeEvent, MaintenanceRecord} ──o ProductionLoss ──o CommodityPrice (resolved, not stored)
```
`MaintenanceRecord` and `ProductionLoss` both have no `field_id`/`facility_id` columns of their
own — scope is always resolved live through `Equipment.well`/`Equipment.facility` (or, for
`ProductionLoss`, through its own `well` first, falling back to its `equipment`'s resolved
scope), reusing the Equipment module's `_resolve_scope()` helper — the same "derive, don't
duplicate" rule Equipment applied to its own `field_id`. Failure/downtime detail lives in two
places by design: precise start/end timestamps on `DowntimeEvent` (used for the reliability
metrics below and for deriving a loss record's `downtime_hours` when linked), and a
work-order-level `downtime_hours`/`failure_cause`/`corrective_action` on `MaintenanceRecord`
itself for the common case where no separate `DowntimeEvent` was logged. Neither is derived
from the other.

## Production Loss — auto-computed with manual override, never fabricated
`ProductionLoss` (extended by the Production Loss module, revision `9ec63324886e`) holds
`estimated_bopd_lost`, `estimated_mscf_lost`, `estimated_revenue_impact`, and `currency`. On
create/update, `backend/app/routers/production_loss.py`'s `_compute_derived_fields()`
auto-resolves and computes whichever of these the caller left unset: lost volume =
`max(expected − actual, 0)` per commodity, using the *same* `ProductionTarget` resolution rule
already used by `/production/actual-vs-target` (`_resolve_target`, imported directly rather
than duplicated a 3rd time) for "expected" and the matching `ProductionRecord` for "actual";
revenue impact sums whichever commodity has both a lost volume and a `CommodityPrice` resolved
the same way (most recent `effective_date <= loss_date` per commodity — now backed by a
`(commodity, effective_date)` unique constraint). A caller may supply any of the four fields
directly instead (e.g. a historical entry predating target data) — the manual value always
wins over the computed one. **A field this can't resolve for (no target, no production record,
or no well link at all) stays `None` — never fabricated.** `downtime_hours` follows the same
derive-or-accept pattern, sourced from a linked `DowntimeEvent`'s duration or a linked
`MaintenanceRecord.downtime_hours` when not supplied directly. Every read carries
`PRODUCTION_LOSS_DISCLAIMER` (`services/production_loss_calculations.py`) plus the resolved
`oil_price_per_bbl`/`gas_price_per_mscf` that actually drove the number — transparency on the
price, not just the total. `DELETE` is blocked when linked to a real `DowntimeEvent`/
`MaintenanceRecord` (edit instead, preserving the audit trail); a purely manual/speculative
entry can be deleted freely.

## Cost & Revenue — Production → Revenue → Operating Cost → Maintenance Cost → Production Loss → Estimated Financial Impact
`OperatingCost` (extended by the Cost & Revenue module, revision `3b65bf411ca3`) gained
`equipment_id` (nullable FK, alongside the pre-existing independently-nullable `field_id`/
`facility_id`/`well_id` — a cost may be scoped at any level, and well/equipment are never
required for a field- or facility-level cost), `description`, `cost_period` (e.g. `monthly`/
`one_time`), `source` (e.g. `invoice`/`estimate`/`manual_entry`), and `notes`. `category` stays
free text with an 11-item canonical suggestion list (Production/Maintenance/Energy/Chemicals/
Labour/Contractor/Logistics/Utilities/Facility/Equipment/Other) — the same "closed spec list,
open storage" split `maintenance_type` established. `currency` is a strict `Literal["USD",
"NGN"]` at the write boundary.

**Economic Calculation Methodology** (`backend/app/services/economics_calculations.py`,
`backend/app/routers/cost_revenue.py`) — the four formulas exactly as specified:
- **Revenue = Production × Commodity Price** — `estimate_revenue()` multiplies each
  `ProductionRecord`'s oil/gas volume by the `CommodityPrice` resolved for that date/commodity
  (reusing Production Loss's `_resolve_commodity_price`, most-recent `effective_date <=` the
  record date). Revenue is **always computed live, never stored** — the same "always live"
  philosophy Production applies to `water_cut`/`GOR`/`BOE`. A commodity with no resolvable price
  contributes `None`, never a fabricated figure, and every revenue figure in the API is
  presented as "Estimated Revenue."
- **Estimated Operating Margin = Estimated Revenue − Operating Costs** —
  `estimate_operating_margin()` is a plain, currency-agnostic subtraction; the caller only
  invokes it when revenue and cost resolve to the *same* currency for that scope (see below).
  Never called "profit" or "audited" anywhere in the API or UI.
- **Cost per barrel = Operating Cost ÷ Production** — `compute_per_unit()`, reused for cost/bbl,
  cost/BOE, revenue/bbl, revenue/BOE, and margin/bbl, margin/BOE; returns `None` (not zero or an
  error) when the production denominator is `None` or `<= 0`.
- **Production Loss Financial Impact = Estimated Lost Production × Commodity Price** — this is
  `ProductionLoss.estimated_revenue_impact`, computed once by the Production Loss module and
  **read directly, never recomputed here** — the structural guarantee against double-counting
  the spec requires. Cost & Revenue's dashboard/trends/scope-economics endpoints all pull this
  figure from `/production-loss`'s own aggregation logic rather than re-deriving it.

All four are documented, in the API's own `disclaimer_text` (`ECONOMICS_DISCLAIMER`) and here,
as **management/analytical estimates for decision support — not audited accounting figures.**

**Currency is never silently blended.** Every aggregate response (`CostRevenueDashboard`,
`UnitEconomics`, `EconomicsByScopeResponse`, the three trend responses) returns money as
`list[{currency, amount}]`, grouped by currency, never summed across differing currencies. A
margin or per-unit figure is computed only when revenue and cost share a currency for that
scope; otherwise the API returns an empty list plus `currency_mismatch: true` rather than
inventing an exchange rate — the literal, load-bearing reading of "do not perform currency
conversion unless an explicit exchange-rate source exists." `MaintenanceRecord.cost` has no
currency column of its own (never added by the Maintenance module); Cost & Revenue treats it as
USD via a single documented constant (`MAINTENANCE_COST_CURRENCY` in `cost_revenue.py`) rather
than guessing silently or retrofitting a working module's schema.

**Field/Well Economics share one endpoint** (`GET /cost-revenue/economics-by-scope?scope=field|
well`) with a unified row shape; well-scope rows carry additional nullable rule-based flags
(`high_production`/`high_cost`/`low_margin`/`high_loss`) plus a `review_note` reading "Requires
further economic review — ..." when data is too thin to classify — a well is never
automatically labeled "uneconomic." Classification always compares a well's own-currency value
against a same-currency company-wide average.

**Cost Alerts** (`GET /cost-revenue/alerts`) are computed on read, never persisted — the same
"live, rule-based, not AI" precedent as Production's `/production/issues` and Equipment's
`/equipment/issues`. Six categories: rapid cost increase (>25% month-over-month per field),
high maintenance cost (>2x fleet average, trailing 90 days), high cost per barrel (>1.5x
company average), high production loss (lost oil >15% of actual, per well), declining margin
(month-over-month, currency-matched scopes only), and unusually high energy cost (>2x a
facility's own trailing 6-month average).

## Alerts — centralized, rule-based Alert & Event Intelligence
`Alert` (extended by the Alerts module, revision `904e02efa718`) existed since the initial
schema with only `alert_type`/`severity`/`state`/`message`/`triggered_at`/`well_id`/
`equipment_id` and **zero rows ever written** — but it was not dead code: `equipment_health.py`'s
`recompute_equipment_health()` already read `Alert.equipment_id`/`triggered_at` for its
`alarm_frequency` scoring factor. This module is the first to populate the table, which
activates that factor for real for the first time. Extended with `category`, `source_module`,
`title`, `recommended_action`, `notes`, `field_id`/`facility_id`/`maintenance_record_id`/
`production_loss_id` (nullable FKs), `threshold_value`/`current_value`/`unit`, `dedup_key`
(indexed, not unique), `occurrence_count`, `last_detected_at`, `acknowledged_at`/`resolved_at`
+ `acknowledged_by_id`/`resolved_by_id` (FK → `User`); `message` was renamed to `description`.
A new `AlertStatusHistory` table (`alert_id` FK, `from_state`/`to_state`, `note`,
`changed_by_id` nullable FK → `User` — null means system-generated, `changed_at`) provides the
per-transition audit trail — added fresh rather than force-fit into the generic, also-unused
`AuditLog` model, which has no per-row from/to state or timestamp-per-transition shape.

**Rule engine** (`backend/app/services/alert_rules.py`, DB-using — mirrors
`cost_revenue.py`'s existing alert-logic shape rather than the pure `*_calculations.py`
services, since cross-module aggregation needs real queries). `run_alert_rules(db)` is the
single entry point: it calls one generator per category, then reconciles the results against
existing `Alert` rows (dedup below), and is invoked by `POST /alerts/run` and once by
`seed_wells.py` after all other synthetic data exists. Every rule reuses an existing detection
mechanism directly where one exists (`production.py`'s `/issues` conditions,
`equipment_health.py`'s `compute_health()`-cached `health_score` and its `_zscore_anomaly()`
helper, `maintenance.py`'s `/schedule` overdue/due-soon bucketing, and — for two of six
economics rules — `cost_revenue.py`'s existing `declining_margin`/`high_maintenance_cost`
checks) rather than re-deriving the condition a second way.

### Severity rubric
Two rules, applied consistently rather than 22 ad hoc judgment calls:
1. **Fixed severity** for conditions that are inherently binary/severe regardless of magnitude
   (production outage, equipment failure, critical-priority maintenance, critical health band,
   declining margin, high maintenance cost, abnormal readings, due-soon/repeated-event notices).
2. **Tiered severity** for magnitude-over-threshold conditions, based on how far past the
   configured threshold the current value sits (e.g. 1–1.5× threshold = medium, 1.5–2× = high,
   >2× = critical — exact bands per type in the table below), via a shared
   `_tiered_severity(current, threshold, tiers)` helper.

### Deduplication and lifecycle
`dedup_key = f"{alert_type}:{scope_type}:{scope_id}"` (e.g. `"production_below_target:well:42"`),
built deterministically per rule and matched only against **open** states (`new`/
`acknowledged`/`investigating`) — enforced in application logic, not a DB unique constraint,
since resolved/dismissed history for the same key legitimately persists across multiple rows.
On each run: a condition matching an open alert's `dedup_key` **updates that row in place**
(bumps `occurrence_count`/`last_detected_at`, refreshes severity/values) rather than creating a
duplicate; a condition with no matching open alert **creates a fresh row** — including when the
prior alert for that key was resolved/dismissed, so a recurring problem is never silently
suppressed just because someone closed the last occurrence. `triggered_at` is set once at
creation and never moves, which is also what keeps the `alarm_frequency` health factor bounded
(an alert ages out of that factor's 30-day window regardless of how long it stays open).

**Auto-resolution is asymmetric by severity**: on each run, an open alert whose condition is no
longer detected auto-resolves **only if its severity is not `critical`** (system-generated
`AlertStatusHistory` note) — critical alerts are never auto-resolved, the literal reading of
"do not automatically mark critical alerts as resolved." Manually created alerts
(`source_module="manual"`, `dedup_key="manual:{uuid}"`) are excluded from this sweep entirely,
regardless of severity, since their dedup key can never match a rule-generated condition.

### Rule table (22 types, default thresholds are `SystemSetting` rows seeded by the migration)

| alert_type | category | condition | default threshold | severity |
|---|---|---|---|---|
| `production_below_target` | production | actual oil < target by >X% (reuses `_resolve_target`) | 10% (`alert_production_below_target_pct`) | tiered 10–20%=medium, 20–35%=high, >35%=critical |
| `production_decline` | production | trailing 7-day avg oil < trailing 30-day avg by >Y% | 15% (`alert_production_decline_pct`) | tiered 15–25%=medium, 25–40%=high, >40%=critical |
| `unusual_production_change` | production | day-over-day oil swing >Z% (either direction) | 30% (`alert_production_unusual_change_pct`) | fixed low |
| `production_outage` | production | open downtime event or zero production on latest date | n/a | fixed critical |
| `equipment_low_health` | equipment | `health_score` < attention threshold, ≥ critical threshold | 50 (`alert_equipment_health_attention_threshold`) | fixed high |
| `equipment_critical_health` | equipment | `health_score` < critical threshold | 25 (`alert_equipment_health_critical_threshold`) | fixed critical |
| `equipment_failure` | equipment | `status == "failed"` | n/a | fixed critical |
| `abnormal_equipment_readings` | equipment | `_zscore_anomaly()` (2σ) on latest current/flow readings | n/a | fixed medium |
| `maintenance_overdue` | maintenance | reuses `/maintenance/schedule`'s overdue condition | n/a | tiered 1–7d=medium, 8–30d=high, >30d=critical |
| `maintenance_due_soon` | maintenance | reuses schedule's due-today/upcoming buckets | lookahead days (existing setting) | fixed low |
| `critical_maintenance` | maintenance | `priority == "critical"`, status not terminal | n/a | fixed critical |
| `repeated_maintenance_events` | maintenance | ≥N corrective/emergency records per equipment in window | 3 events / 90 days | fixed high |
| `high_production_loss` | production_loss | one `estimated_bopd_lost` > threshold | 50 bbl (`alert_production_loss_high_threshold_bbl`) | tiered 1–2×=medium, 2–4×=high, >4×=critical |
| `repeated_production_loss_events` | production_loss | ≥N loss records per well in window | 3 events / 90 days | fixed high |
| `high_downtime` | production_loss | one `downtime_hours` > threshold | 24h (`alert_downtime_high_threshold_hours`) | tiered 24–48h=medium, 48–96h=high, >96h=critical |
| `high_estimated_lost_revenue` | production_loss | one `estimated_revenue_impact` > threshold (USD only) | $10,000 (`alert_high_lost_revenue_threshold_usd`) | tiered 1–2×=medium, 2–4×=high, >4×=critical |
| `high_operating_cost` | economics | field's this-period operating cost > threshold, per currency | $100,000 / ₦50,000,000 | tiered 1–1.5×=medium, 1.5–2×=high, >2×=critical |
| `rising_cost_per_barrel` | economics | field's cost/bbl this month vs. last month, per currency | 20% (`alert_cost_per_bbl_increase_pct`) | tiered 20–40%=medium, >40%=high |
| `rising_cost_per_boe` | economics | same, cost/BOE | 20% (`alert_cost_per_boe_increase_pct`) | tiered 20–40%=medium, >40%=high |
| `declining_operating_margin` | economics | reuses the existing MoM margin-decline check, now configurable | 25% (`alert_margin_decline_pct`) | fixed high |
| `high_maintenance_cost` | economics | reuses the existing equipment-vs-fleet-avg check, now configurable | 2.0× (`alert_high_maintenance_cost_multiplier`) | fixed medium |
| `high_estimated_financial_impact` | economics | field's trailing-30d summed `estimated_revenue_impact` > threshold (USD only) | $25,000 (`alert_high_financial_impact_threshold_usd`) | tiered 1–2×=high, >2×=critical |

Two production-loss/economics types (`high_estimated_lost_revenue`, `high_estimated_financial_impact`)
are USD-only — they read `ProductionLoss.estimated_revenue_impact`, which is itself seeded/
computed in USD only (see the Production Loss and README limitations). `high_operating_cost`
uses two independent, non-converted per-currency thresholds instead of inventing an exchange
rate, matching the Cost & Revenue module's own currency-safety rule.

### Notification foundation
Per this project's standing "prepare support for future notifications, don't implement external
messaging yet" scope: the Alert model's status pipeline plus `GET /alerts/summary`'s `new`
count *is* the foundation — the real, useful signal a future email/SMS/WhatsApp dispatcher or
UI badge would consume. No notification-preferences table/columns and no Sidebar unread-badge
were added speculatively; both are deferred until a concrete channel exists (a live-fetch on a
component every page renders would be a broader footprint than this module's ask needed).

Every alert response carries `ALERT_DISCLAIMER` (`services/alert_rules.py`) — a rule-based
decision-support indicator requiring engineering/management review, never a guaranteed
conclusion or autonomous action, per this project's standing AI/analytics-output guardrail.

## AI Insights — evidence-based analysis, not prediction
`AIRecommendation` (extended by the AI Insights module, revisions `fea98f807a60`/`709cc3909898`;
called "Insight" in API/docs, table name kept as `ai_recommendations`) existed since the initial
schema with only `observation`/`evidence`/`possible_contributors`/`recommended_investigation`/
`potential_impact`/`confidence` and zero rows ever written — the same situation `Alert` was in
before the prior module. Extended with `insight_type`, `category` (production/equipment/
maintenance/production_loss/economics/**cross_domain**), `severity`, `status` (new/reviewed/
dismissed — deliberately lighter than `Alert`'s 5-state pipeline), `generated_by`
(rule_based/ai_interpreted), `ai_provider`/`ai_model`/`ai_interpretation` (populated only by the
opt-in `/interpret` action), `title`, `summary` (renamed from `observation`), `data_quality_note`,
`confidence_level` (replaces the numeric `confidence` outright), paired
`estimated_production_impact_value`/`_unit`/`_note` and `estimated_financial_impact_value`/
`_currency`/`_note` (replaces `potential_impact`), `field_id`/`facility_id`/
`maintenance_record_id`/`production_loss_id`/`alert_id` (nullable FKs, mirrors `Alert`'s own
scope-FK set), `dedup_key`/`occurrence_count`/`generated_at`/`last_confirmed_at` (mirrors
`Alert`'s dedup/reaffirm columns). The inherited `ai_prediction_id` FK was **dropped** — nothing
in this module writes an `AIPrediction` row, so a permanently-null FK to a permanently-empty
table would be exactly the dead scaffolding this project's conventions avoid.

Two new child tables: **`AIInsightEvidence`** (`insight_id` FK, `evidence_type` — one of
`observed_fact`/`calculated_metric`/`correlation`/`possible_contributor`, `description`,
`source_type`/`source_id`/`source_label` for click-through — `source_type="computed"` and
`source_id=None` for aggregate evidence with no single backing row — `value`/`unit` for
calculated metrics) is the data-level mechanism for the brief's required OBSERVED/CALCULATED/
CORRELATION/POSSIBLE-CONTRIBUTOR UI distinction — a free-text column can't guarantee that
separation survives into the UI the way a typed child table does. Deliberately a different,
citation-oriented shape from `AuditLog.entity_type`/`entity_id` (an audit row records *who did
what*; this records *what fact backs this claim*). **`AIInsightFeedback`** (`insight_id` FK,
`feedback` — useful/not_useful/incorrect/needs_review, `notes`, `submitted_by_id` FK → `User`,
`submitted_at`) is storage only — never used to auto-train or auto-tune anything.

**Insight engine** (`backend/app/services/insight_engine.py`, DB-using, mirrors
`alert_rules.py`'s shape). `run_insight_engine(db)` calls `alert_rules.py`'s private
`_generate_*_alerts` functions **directly** (never the public `run_alert_rules()`) to source
candidates for the ~14 insight types that check a condition Alerts already detects — this keeps
insight generation free of any side effect on the `alerts` table. Each reused candidate becomes
an insight whose primary evidence is 2 items built from the alert candidate itself: an
`observed_fact` (the condition, in its own words) and a `calculated_metric` (the figure that
crossed the threshold). ~6 genuinely new types (`production_increase`, `production_trend`,
`well_performance_comparison`, `increasing_maintenance_frequency`,
`high_maintenance_cost_vs_production`, and the cross-domain generator) get small fresh
detection queries using the same existing helpers (`_resolve_scope`, `_compute_scope_totals`,
`_resolve_target`, `_compute_scope_totals`'s currency-safe per-unit helpers). Two Economics
types (`rising_operating_cost`, `high_cost_per_barrel`) reuse `cost_revenue.py`'s own
still-unreused `rapid_cost_increase`/`high_cost_per_barrel` comparison shape (mirroring its
exact 1.25×/1.5× embedded thresholds, since these are a "reused logic" framing choice rather
than a new configurable rule) rather than `alert_rules.py`'s differently-framed versions.

### Confidence rubric
`confidence_level` (high/medium/low, `services/insight_calculations.py::derive_confidence_level`)
is computed from the count of **distinct evidence categories** present on an insight — never a
fabricated statistical score, per the brief's explicit warning: 3+ categories = high, 2 =
medium, 1 (or 0) = low. This is why the cross-domain generator's equipment-health evidence is
typed `calculated_metric` (the health score is itself computed by `equipment_health.py`'s
`compute_health()`) rather than `observed_fact` like the production-decline evidence next to
it — two evidence items of the *same* type only count as one category, so getting the typing
right is what makes 2 independent data sources actually read as `medium` confidence rather than
`low`.

### Deduplication and lifecycle — no auto-dismiss, unlike Alerts
`dedup_key = f"{insight_type}:{scope_type}:{scope_id}"`, matched only against **non-dismissed**
statuses (`new`/`reviewed`) — same update-in-place-or-create mechanics as `Alert`. Unlike
Alerts, there is **no auto-resolution branch**: an insight whose condition stops being
reaffirmed is left exactly as it was, since it remains valid historical analytical commentary
even after the triggering condition passes (an alert says "this needs attention now"; an insight
says "here's what the data showed"). Staleness is instead exposed as a **derived**
`is_stale`/`days_since_confirmed` pair (`compute_is_stale`, compared against the
`insight_stale_after_days` setting, default 7) computed at read time from `last_confirmed_at` —
not a 4th status value.

### Rule table (24 types)

| insight_type | category | reuse source |
|---|---|---|
| `production_decline` | production | `alert_rules` decline candidate, direct |
| `production_increase` | production | new — trailing 7d vs. 30d avg, opposite sign of decline |
| `production_anomaly` | production | `alert_rules` `unusual_production_change` candidate, direct |
| `production_below_target` | production | `alert_rules` candidate + `production.py`'s `_resolve_target` |
| `production_trend` | production | new — `classify_trend()` over a 3-month window of monthly averages |
| `well_performance_comparison` | production | new — flags wells below a configurable fraction of field median |
| `equipment_health_deterioration` | equipment | `alert_rules` low/critical/failure candidates, collapsed |
| `equipment_repeated_issues` | equipment | `alert_rules`' repeated-events query, equipment-framed |
| `abnormal_equipment_readings` | equipment | `alert_rules` candidate (`_zscore_anomaly`), direct |
| `increasing_maintenance_frequency` | maintenance | new — trailing vs. prior window event count per equipment |
| `maintenance_overdue` | maintenance | `alert_rules` overdue/critical candidates, collapsed |
| `high_maintenance_cost` | maintenance | `alert_rules` candidate (settings-driven), direct |
| `recurring_corrective_maintenance` | maintenance | generalized repeated-events query, corrective-only filter |
| `high_production_loss` | production_loss | `alert_rules` candidate, direct |
| `repeated_production_loss_events` | production_loss | `alert_rules` candidate, direct |
| `high_downtime` | production_loss | `alert_rules` candidate, direct |
| `high_lost_revenue` | production_loss | `alert_rules` `high_estimated_lost_revenue` candidate, direct (populates estimated_financial_impact_*) |
| `rising_operating_cost` | economics | `cost_revenue.py`'s unreused `rapid_cost_increase`, direct |
| `high_cost_per_barrel` | economics | `cost_revenue.py`'s unreused `high_cost_per_barrel` (vs. company avg), direct |
| `declining_operating_margin` | economics | `alert_rules` candidate, direct |
| `high_maintenance_cost_vs_production` | economics | new — maintenance_total ÷ oil_total via `_compute_scope_totals` |
| `high_downtime_financial_impact` | economics | `alert_rules` `high_estimated_financial_impact` candidate, direct (populates estimated_financial_impact_*) |
| `equipment_linked_to_production_decline` | cross_domain | cross-domain generator, 2-signal tier (production decline + equipment health) |
| `equipment_production_maintenance_downtime_correlation` | cross_domain | cross-domain generator, 4-signal flagship tier (+ recent maintenance + downtime) |

Cross-domain insights always use correlation/possible-contributor language and never claim
causation, per the brief's explicit prohibition — enforced by the evidence typing itself
(`possible_contributor` for the maintenance/downtime supplementary facts), not only by prose.

### AI provider abstraction and hybrid intelligence
See `docs/ai-architecture.md` for the full provider abstraction, the assistant's question-
template design, and the deterministic-vs-AI-touched boundary. In one sentence: `run_insight_
engine()` and `POST /ai-insights/run` are 100% deterministic and never call an AI provider,
even if one is configured — AI is invoked only by the opt-in `/interpret` endpoint, the
assistant's fallback for unmatched questions, and an off-by-default narrative flag on the daily
brief/management summary.

Every insight response carries `INSIGHT_DISCLAIMER` (`services/insight_engine.py`) — an
evidence-cited observation requiring engineering/management review, never a guaranteed
conclusion, per this project's standing AI/analytics-output guardrail.

## What-If Simulator — deterministic scenario comparison, never a forecast
`Scenario` (`backend/app/models/simulation.py`, migration `f2a150e1c63d`) is a genuinely new
table — the first since the original schema that isn't a "modeled but never populated" table
extended in place. Fields: `name`, `description`, `created_by_id` (FK → `User`), baseline scope
(`baseline_date_from`/`_date_to`, nullable `field_id`/`facility_id`/`well_id`/`equipment_id`),
`assumptions` (JSON — the scenario's `*_change_pct`/`*_reduction_pct`/price-override fields, only
the ones actually set), `results` (JSON, nullable until first run), `calculation_version`
(string, currently `"1.0"`), `last_run_at`. `assumptions`/`results` are the first real use of
`sqlalchemy.JSON` in this codebase — already sanctioned by this file's own stated portability
principle ("portable `sqlalchemy.JSON`... so the schema also builds against SQLite for pytest"),
just not previously exercised.

**`results` is a frozen snapshot, not a live view.** Written once at `POST`/`PUT`/`rerun` time; a
plain `GET /what-if/scenarios/{id}` never recomputes it. This is the literal reading of "store
the assumptions and calculation version used — important for reproducibility": a saved scenario
shows exactly what was seen when it was saved, not a number that silently drifts as production/
cost data changes underneath it. `POST /what-if/scenarios/{id}/rerun` is the one explicit way to
refresh it against current data.

**Calculation methodology** (`backend/app/services/whatif_calculations.py`, pure, no DB/AI import)
— every formula exactly as specified:
- **Scenario Production = Baseline Production × (1 + Production Change %)** — applied separately
  to oil and gas.
- **Scenario Revenue = Scenario Production × Commodity Price** — Commodity Price is a price
  override if supplied, else the baseline's resolved current price adjusted by a price-change %
  if supplied, else the baseline price unchanged. Baseline revenue itself stays the real,
  per-record historical figure (`_compute_scope_totals`, priced per record's own date) — never
  recomputed via the flat formula, since a baseline must reflect what actually happened.
- **Scenario Operating Cost = Baseline Operating Cost × (1 + Cost Change %)** — with one
  exception: if `energy_cost_change_pct` is supplied, the energy slice of operating cost (via
  `_split_operating_costs`'s existing energy/other split) and the rest are scaled independently,
  so `operating_cost_change_pct` is never applied to the same dollars twice.
- **Scenario Production Loss = Baseline Production Loss × (1 − Loss Reduction %)** — applied to
  both estimated lost oil and lost gas.
- **Scenario Operating Margin = Scenario Revenue − Scenario Operating Costs** — currency-matched
  only, via the same `_margin_by_currency` mismatch logic Cost & Revenue established.

Two figures are always computed and reported **separately**, never folded into the headline
production number (folding either in would double-count the same barrels under two levers):
`recovered_production_bbl` (`recovered_downtime_hours × (baseline_oil_bbl / (period_days × 24))`,
from the downtime lever) and `potential_loss_reduction_oil_bbl`/`_gas_mscf` (`baseline_lost −
scenario_lost`, from the production-loss-reduction lever) — both explicitly labeled "estimated/
potential," never guaranteed.

**Two-tier guardrails, never a silent rejection.** `validate_assumptions()` checks every
`*_change_pct`/`*_reduction_pct` and price-override field against a hard bound (below −100% for
any `(1 + pct/100)` formula, above 100% for `production_loss_reduction_pct`'s `(1 − pct/100)`
formula, ≤ 0 for a price override) — any hard violation is a `severity="error"` flag and the API
returns 422 with the exact field and reason. A value beyond a separate, configurable
`whatif_reasonable_change_pct_bound` `SystemSetting` (default 50) but still mathematically valid
is a `severity="warning"` flag carrying "Scenario is outside configured operating assumptions" —
still computed and returned, never dropped.

**Currency is never blended**, same rule as Cost & Revenue: every money field is
`list[{currency, amount}]`; margin is computed only for currencies present on both revenue and
cost, otherwise `margin_currency_mismatch: true` and an empty margin rather than a fabricated
number.

**Baseline resolution never invents data.** `_resolve_baseline()` (`routers/what_if.py`) reuses
`cost_revenue.py`'s `_compute_scope_totals`/`_load_price_series`/`_price_on` directly (the 4th
consumer of that private-helper-reuse convention, after `alert_rules.py`/`insight_engine.py`/
`ai_assistant.py`) — extended with `facility_id`/`equipment_id` kwargs additively for this module.
When zero production records resolve for the selected scope/period, `data_sufficient=false` plus
an explicit `missing_data_note` is returned instead of a baseline built from nothing.

**Endpoints**: create/list/get/update/delete/rerun a saved scenario, `POST /what-if/preview`
(ad-hoc run, nothing persisted — the Scenario Builder's live-preview step), `POST /what-if/compare`
(N saved scenarios' **stored** results, never recomputed), `POST /what-if/sensitivity` (sweeps one
assumption field across a list of values, reusing the same formulas once per point — not a
statistical model), `POST /what-if/scenarios/{id}/interpret` (mirrors AI Insights' `/interpret`
exactly — `StructuredPrompt` built from the scenario's already-computed stored results, rate-
limited via the same `rate_limiter()` factory, never given raw DB access).

Every response carries `WHATIF_DISCLAIMER` (`services/whatif_calculations.py`) — a planning/
decision-support estimate, never a forecast, guaranteed outcome, or instruction to change any
equipment, production parameter, or SCADA/DCS setting, per this project's standing AI/analytics-
output guardrail, which explicitly names the What-If Simulator.

## Reports — converts every other module's data into Daily/Weekly/Monthly/What-If reports
`Report` (`backend/app/models/reporting.py`, migration `742f03778de9`) existed since the initial
scaffold with only `report_type`/`period_start`/`period_end`/`file_path`/`generated_by_id` and
zero rows ever written — the same "modeled but never populated" situation `Alert`/
`AIRecommendation`/`OperatingCost`/`ProductionLoss` were in before their modules extended them in
place. Extended with `name` (required), `description`, `filters` (JSON — the section-4 filter
set: date range, field/facility/well/equipment, commodity, maintenance_type, alert_severity,
production_loss_category, scenario_id), `sections` (JSON list of selected section keys),
`results` (JSON, nullable until generated), `calculation_version`, `status` (currently only ever
`"generated"` — v1 generation is synchronous, no queue), `last_generated_at`. `generated_by_id`
was altered to NOT NULL (the table was empty, zero data risk). `file_path` stays unused/nullable
— exports are generated on demand from `results`, never written to disk.

**`results` is a frozen snapshot, exactly like `Scenario`'s** — written once at `POST /reports`
or `POST /reports/{id}/regenerate`; a plain `GET /reports/{id}` never recomputes it.

**Exactly 4 report types**, each with a fixed set of available sections a user can toggle on/off
(`GET /reports/types` returns this declaratively):
- **`daily_operations`**: production, equipment, maintenance, production_loss, alerts, ai_insights
- **`weekly_production`**: production_trend, production_by_scope, actual_vs_target, production_loss
- **`monthly_management`**: executive_summary, production, equipment, maintenance,
  production_loss, economics, alerts, ai_insights
- **`what_if_scenario`**: scenario (a near-passthrough of one saved `Scenario`'s own results)

**Every section is built by calling an existing function directly — never a re-derived formula**
(`backend/app/services/report_calculations.py`):

| Section | Reused from | Notes |
|---|---|---|
| production | `production.get_production_kpis` | natively scope-filterable |
| production_trend | `production.get_production_trends` | |
| production_by_scope | `production.get_production_by_scope` | field/facility/well rankings |
| actual_vs_target | `production.get_actual_vs_target` | |
| equipment | `equipment.list_equipment` | aggregated in Python from filtered `.items` — `list_equipment` supports scope filters, `get_equipment_dashboard` doesn't |
| maintenance | `maintenance.list_maintenance` + `maintenance.get_maintenance_schedule` | cost/downtime/type counts from the filtered list; overdue/due-today from the schedule view, filtered to matching equipment |
| production_loss | `production_loss.list_production_loss` | top events/wells/equipment by estimated revenue impact |
| economics | `cost_revenue._compute_scope_totals` | the one section that's a true calculation-layer reuse rather than a list-aggregation workaround; requires a date range or reports `data_sufficient: false` |
| alerts | `alerts.list_alerts` | counts by severity/status |
| ai_insights | `ai_insights.list_insights` | top 10 by severity, with evidence |
| scenario | `what_if._results_json_to_schema` on the selected saved `Scenario` | pure passthrough, labeled "Scenario Estimate" |

This is the same "call the router function as a plain Python function" precedent
`ai_insights.py`'s `get_daily_brief`/`get_management_summary` already established. **Two-tier
filter support discovered while building this**: every `*_dashboard`/`*_summary`/`*_issues`
endpoint (equipment, maintenance, alerts, insights) is permanently unfiltered
(`db.query(X).all()`); only the paginated `list_*` endpoints accept the field/facility/well/
equipment/date/category/severity/type filters a report needs — so Reports calls those directly
(generous `page_size`, aggregates `.items` in Python) rather than duplicating a sixth copy of
every module's WHERE-clause logic.

**A note on calling FastAPI route functions directly**: several of these functions declare
parameters like `status_filter: str | None = Query(None, alias="status")` — FastAPI resolves the
`Query(...)` sentinel from the request when the function is a route handler, but calling it
directly as plain Python uses the *literal* `Query(...)` object as the default, not `None`. Every
direct call site in `report_calculations.py` explicitly passes every `Query(...)`-defaulted
parameter (`status_filter=None`, `page=1`, etc.) to avoid this — caught during integration
testing (a real `psycopg.ProgrammingError`), not left for a user to find.

**Executive Summary** (`monthly_management` only) is built entirely from sections already
computed above (top alert, top insight, top loss event) — never a separate calculation or LLM
call. An optional `narrative=true` flag (same shape as AI Insights' daily brief/management
summary) additionally phrases those same figures via the existing `StructuredPrompt`/
`AIProvider` abstraction — the deterministic calculation always runs first, per this module's
standing hybrid-intelligence rule.

**`results` is a plain JSON dict on the API response (`ReportRead.results: dict`), not ~30 fully-
typed nested schema classes** — a deliberate departure from `Scenario`'s fully-typed
`ScenarioResultsRead`. What-If's single result shape justified full typing; Reports' 4 types have
structurally different section sets, and each section already embeds an upstream-typed schema's
own `model_dump(mode="json")` output. The frontend still gets full clarity via hand-written
TypeScript interfaces in `lib/api.ts` — documented, just not backend-pydantic-enforced.

**Traceability** (per this module's own explicit requirement): every section carries a
`_traceability` block — `source_module`, `methodology` (a plain-English sentence describing the
calculation), and `record_count` where meaningful — so every figure in a report is traceable back
to which module computed it and how.

**Export** (`backend/app/services/report_export.py`) reads only from the stored `results` — never
recomputes, matching the frozen-snapshot design. CSV reuses `production.py`'s existing
`io.StringIO`/`csv.writer`/`StreamingResponse` pattern (this codebase's only prior export
endpoint). PDF uses `fpdf2` — the first new backend dependency added in this entire build, chosen
for having zero system/apt dependencies (unlike `weasyprint`) — and stays deliberately tabular/
text plus at most 1-2 simple native bar charts (drawn with `fpdf2`'s own rect primitives, not a
charting library); the full 10-chart set from the module spec stays on the frontend preview, a
disclosed v1 scope line. `fpdf2`'s core "Helvetica" font is latin-1-only, but this codebase's
prose freely uses em-dashes/curly quotes, so `FPDF.cell`/`multi_cell` are overridden once to
normalize text to ASCII at that one boundary, rather than editing every string literal that might
end up in a report.

Both `disclaimer_text` (`REPORT_DISCLAIMER`) and a synthetic-data disclaimer
(`SYNTHETIC_DATA_DISCLAIMER`) are present on every report — the latter unconditionally, since no
verified-production-data mode exists anywhere in this codebase (every environment this app has
ever run in is the seeded/demo one).

## Reliability metrics — a documented foundation, not a certified analysis
`backend/app/services/reliability_metrics.py`'s `compute_reliability()` is pure/DB-free (mirrors
`equipment_health.py`'s shape) and computes MTBF, MTTR, availability, and failure frequency from
one equipment's `DowntimeEvent` history, exposed via `GET /equipment/{id}/reliability`. Each
metric declares its own `*_data_sufficient` flag (MTBF needs ≥2 events, MTTR needs ≥1 closed
event) rather than returning a number from too little data. Every response carries
`RELIABILITY_DISCLAIMER` and a documented `assumptions` list — per this project's standing
AI/analytics-output guardrail, it is explicitly a **foundation for future predictive-maintenance
work, not a certified reliability-engineering system**.

## AI-output guardrail encoded in schema
`AIRecommendation.disclaimer_text` defaults to:
> "AI-generated estimate requiring engineering review; not a guaranteed conclusion."

This bakes the product's required framing into the data itself, not just UI copy — every AI
recommendation carries the disclaimer whether or not the frontend renders it explicitly.

## Administration module — user management, permissions, settings, audit log, system health
Eleventh and final planned module. Unlike every other module, it is **Administrator-only end to
end, including reads** — it exposes user PII, system configuration, and the full audit trail,
none of which belongs to the other six roles the way every other module's operational data does.

**Authorization has exactly one primitive in this codebase**: `deps.py`'s `require_role(*role_
names)`, checked against `current_user.role.name`. There is no permissions table, no decorator
system, no middleware-based authorization anywhere. "Permission management" (`GET
/administration/permissions`) is therefore a **read-only, code-derived matrix**
(`services/permissions.py`) that mirrors the real `require_role(...)` calls already in every
router — never a database-editable permission-granting system, which would require rewriting
authorization across every router and would silently drift from what's actually enforced. Role
management is read-only for the same reason: a role name is a hard-coded string literal inside
`require_role(...)` calls, so a UI-created role would have zero actual enforcement anywhere.
**User → role assignment**, by contrast, is fully real and functional (`PUT /users/{id}`), since
`role_id` is a genuine FK.

**A real, previously-existing security gap, fixed as part of "deactivate users" being asked
for**: neither `deps.py`'s `get_current_user` nor `routers/auth.py`'s `login` checked
`User.is_active` before this module — an administrator "deactivating" a user did not actually
invalidate that user's still-valid JWT. Both now reject inactive users (`get_current_user` at
request time, `login` at issuance time), verified end-to-end: a token issued before deactivation
is rejected on its very next request.

**`AuditLog` (`reporting.py`) is a sixth "modeled but never populated" table** — `action`/
`entity_type`/`entity_id`/`details`/`user_id` existed since the initial scaffold with zero rows
ever written (confirmed by grep), the same situation `Alert`/`AIRecommendation`/`OperatingCost`/
`ProductionLoss`/`Report` were all in before their modules populated them. Extended with `status`
(default `"success"`) and `metadata_json` (a JSON column — named `_json` because SQLAlchemy's
declarative `Base` reserves the plain `metadata` attribute name), and written for the first time
via `services/audit.py::record_audit_event()` — the one write path, wrapped in try/except so a
logging failure can never break the action it's describing. Scoped narrowly to what the brief
names: user create/update/role-change/activate/deactivate, `PUT /settings/{key}`, `POST /reports`,
`POST /what-if/scenarios`, `POST /ai-insights/run` — not touching every CRUD endpoint in every
other router, to bound regression risk. Never logs passwords, API keys, or other secrets.

**AI configuration is surfaced with zero secret exposure by construction, not by redaction.**
`GET /administration/ai-config` only ever touches the already-safe `provider_name`/`model`/
`is_configured` properties of the resolved `AIProvider` instance (`services/ai_providers/
factory.py::get_ai_provider`) — the raw key fields on `Settings` (`openai_api_key` etc.) and other
secrets (`secret_key`, `database_url`) are never read by any Administration code path, so there is
no key-shaped string for a bug to accidentally leak. The Null provider fallback means the app
keeps functioning deterministically with zero AI key configured, same guarantee as AI Insights.

**System health is computed live on every request** (`SELECT 1` for the database check, `Settings.
environment`/a hardcoded app version string, the same AI-provider status check as above) — never
cached, and never returns a connection string, port, or other infrastructure detail.

See `docs/api.md` for the `/administration` and extended `/users` endpoint summary, and
`docs/security.md` for the full list of security/data-protection controls this module adds.

## Migrations
```
docker compose exec backend alembic revision --autogenerate -m "<message>"
docker compose exec backend alembic upgrade head
```
