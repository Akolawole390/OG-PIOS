# Synthetic Demo Data — Planned Generator

This documents the *future full-scale* design for generating realistic demo data.

**Partial implementation exists**: `backend/app/db/seed_wells.py` (run via
`docker compose exec backend python -m app.db.seed_wells`) has grown module-by-module and now
covers most of the planned scope below — 3 Fields, ~2-3 Facilities each, 25 Wells, 365 days of
daily production/pressure/temperature history, downtime events, well/facility-linked equipment
with ~90 days of sensor readings, maintenance work orders across the full type/status/priority
vocabulary, monthly USD commodity prices, incident-linked production-loss records, operating
cost records at field/facility/well/equipment level (split USD/NGN by field), and finally a real
run of the Alerts module's rule engine against all of the above. It uses stdlib `random`/
`datetime` only (no numpy/pandas), and is idempotent — safe to re-run, only actually re-seeds
against an empty database. What remains deferred from the full-scale design below:
hourly-cadence equipment readings across the full fleet (currently a representative subset) and
the intentional-abnormal-event time series woven in for future anomaly detection/AI insights.

## Planned scope (full-scale, future)
- **3 Fields**, multiple **Facilities**, **25 Wells**.
- **365 days** of daily production history per well: oil (BOPD), gas (MSCFD), water (BWPD),
  water cut, GOR, choke size, wellhead/tubing/casing/flowline pressure, temperature.
- **Equipment** per facility/well (pumps, ESPs, compressors, motors, generators, valves,
  separators, heat exchangers, instrumentation) with maintenance history and failure events.
- **Operating costs** (maintenance, fuel, electricity, chemicals, labour, logistics, spare
  parts, intervention) and **commodity prices** (oil/gas, multiple currencies).
- **Intentional abnormal events** woven into the time series so anomaly detection, alerts, and
  AI insights have something real to demonstrate: production decline, pressure anomaly,
  water-cut increase, equipment degradation, downtime events.

## Cadence
Daily granularity for production/pressure/temperature records; equipment readings at a higher
frequency (e.g. hourly) for a representative subset of equipment; maintenance/downtime/cost
records at realistic irregular intervals.

## Implementation plan (not yet built)
A future `scripts/seed/generate_demo_data.py` (or `backend/app/db/generate_demo_data.py`) will
use `numpy`/`pandas` to synthesize the above against the schema in
`backend/app/models/`, seeded for reproducibility, and clearly labeled as synthetic data
(never real operational data) per the root `CLAUDE.md` data-handling rule.
