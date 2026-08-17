"""Foundation-level equipment reliability metrics: MTBF, MTTR, availability, failure frequency.

`compute_reliability()` is a pure function (plain `DowntimeInterval` values in, no DB/ORM/
FastAPI imports) so it is directly unit-testable
(backend/tests/test_reliability_metrics.py), mirroring services/equipment_health.py's shape.
The DB-querying wrapper lives in backend/app/routers/equipment.py's
`GET /equipment/{id}/reliability` endpoint, which gathers one equipment's `DowntimeEvent`
history and calls this function.

This is explicitly a **foundation**, not a certified reliability-engineering system — per this
project's standing AI/analytics-output guardrail (root CLAUDE.md), every result carries
RELIABILITY_DISCLAIMER and a documented list of assumptions, and each metric declares whether
its own minimum sample size was met rather than returning a misleading number from thin data.

Documented assumptions:
- Failure/repair events are sourced from `DowntimeEvent` (the only place with real start/end
  timestamps) — not from `MaintenanceRecord`'s date-only fields.
- MTBF (Mean Time Between Failures) = mean gap between consecutive failure START times.
  Needs >=2 events in the observation window to be meaningful.
- MTTR (Mean Time To Repair) = mean `(end - start)` across CLOSED events only (an open/ongoing
  event's duration isn't known yet, so it's excluded). Needs >=1 closed event.
- Availability % = `(period_hours - total_downtime_hours) / period_hours * 100` over the
  observation window. With zero recorded events this is 100% — meaning "no downtime was
  recorded in this window," not a certified uptime guarantee; the absence of `DowntimeEvent`
  rows is not proof the equipment never failed, only that nothing was logged.
- Failure frequency is annualized (`count * 365*24 / period_hours`) from the observed window —
  a description of the past, not a predictive rate.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

RELIABILITY_DISCLAIMER = (
    "Foundational reliability estimate computed from recorded downtime events only; not a "
    "certified reliability-engineering analysis or failure prediction. Requires engineering "
    "review before acting on it."
)

MIN_EVENTS_FOR_MTBF = 2
MIN_EVENTS_FOR_MTTR = 1

ASSUMPTIONS = [
    "MTBF is the mean gap between consecutive failure start times; needs at least 2 recorded "
    "downtime events in the observation window.",
    "MTTR is the mean duration of closed downtime events only; needs at least 1 closed event.",
    "Availability is (period - downtime) / period over the observation window; zero recorded "
    "events means 100% (no downtime logged), not a guarantee nothing ever failed.",
    "Failure frequency is annualized from the observed window, not a predictive rate.",
]


@dataclass
class DowntimeInterval:
    start: datetime
    end: datetime | None  # None = still open/ongoing


def _merge_intervals(spans: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Merges overlapping or exactly-adjacent (start, end) spans into the minimal set of
    non-overlapping spans. Two `DowntimeEvent` rows for the same equipment can legitimately
    overlap in the data today (nothing in the write path currently prevents it — see
    docs/data-model.md's Equipment/Maintenance section) — without this, summing each interval's
    duration independently would double-count the overlapping wall-clock period. Only the total
    *downtime-hours* figure (used for availability%) needs this; MTBF (gaps between distinct
    start times) and MTTR (duration of each distinct closed event) are correctly computed
    per-event, not merged, since those describe individual failure/repair events rather than
    aggregate unavailable time."""
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: s[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:  # overlapping, or exactly touching with zero gap
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


@dataclass
class ReliabilityResult:
    mtbf_hours: float | None
    mtbf_data_sufficient: bool
    mttr_hours: float | None
    mttr_data_sufficient: bool
    availability_pct: float | None
    failure_count: int
    failure_count_annualized: float | None
    observation_period_hours: float
    disclaimer_text: str
    assumptions: list[str]
    computed_at: datetime


def compute_reliability(
    intervals: list[DowntimeInterval],
    observation_period_hours: float,
    now: datetime | None = None,
) -> ReliabilityResult:
    now = now or datetime.now(timezone.utc)

    closed = [i for i in intervals if i.end is not None]
    starts = sorted(i.start for i in intervals)

    mtbf_hours: float | None = None
    if len(starts) >= MIN_EVENTS_FOR_MTBF:
        gaps = [(b - a).total_seconds() / 3600 for a, b in zip(starts, starts[1:])]
        mtbf_hours = round(sum(gaps) / len(gaps), 1)
    mtbf_data_sufficient = mtbf_hours is not None

    mttr_hours: float | None = None
    if len(closed) >= MIN_EVENTS_FOR_MTTR:
        durations = [(i.end - i.start).total_seconds() / 3600 for i in closed]
        mttr_hours = round(sum(durations) / len(durations), 1)
    mttr_data_sufficient = mttr_hours is not None

    spans = [(interval.start, interval.end or now) for interval in intervals]
    total_downtime_hours = sum(
        max(0.0, (end - start).total_seconds() / 3600) for start, end in _merge_intervals(spans)
    )

    availability_pct: float | None = None
    if observation_period_hours > 0:
        availability_pct = round(
            max(0.0, (observation_period_hours - total_downtime_hours) / observation_period_hours * 100),
            2,
        )

    failure_count = len(intervals)
    failure_count_annualized: float | None = None
    if observation_period_hours > 0:
        failure_count_annualized = round(failure_count * (365 * 24 / observation_period_hours), 2)

    return ReliabilityResult(
        mtbf_hours=mtbf_hours,
        mtbf_data_sufficient=mtbf_data_sufficient,
        mttr_hours=mttr_hours,
        mttr_data_sufficient=mttr_data_sufficient,
        availability_pct=availability_pct,
        failure_count=failure_count,
        failure_count_annualized=failure_count_annualized,
        observation_period_hours=observation_period_hours,
        disclaimer_text=RELIABILITY_DISCLAIMER,
        assumptions=ASSUMPTIONS,
        computed_at=now,
    )
