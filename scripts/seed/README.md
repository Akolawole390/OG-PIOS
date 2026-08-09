# Synthetic Demo Data — Planned Generator

This documents the *future* design for generating realistic demo data. **No generator code
exists yet** — this session only seeds the minimum needed to test auth end-to-end (7 roles +
1 admin user, via `backend/app/db/seed.py`).

## Planned scope
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
