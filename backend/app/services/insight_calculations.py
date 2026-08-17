"""Pure, DB-free calculations backing the AI Insights engine — mirrors equipment_health.py's
shape (plain values in, plain result out) so the logic is directly unit-testable and reusable
from both the API and the seed script.

`derive_confidence_level()` is the transparent, documented alternative to a fabricated
statistical confidence score: confidence is a function of how many independent evidence
*categories* (observed_fact / calculated_metric / correlation / possible_contributor) support
an insight, never a number implying a statistical model that doesn't exist here.
"""

from datetime import datetime, timezone
from typing import Literal

TrendDirection = Literal["rising", "declining", "flat"]
ConfidenceLevel = Literal["high", "medium", "low"]


def to_aware_utc(value: datetime) -> datetime:
    """SQLite (used by the test suite) doesn't reliably round-trip tzinfo on a `DateTime
    (timezone=True)` column the way Postgres does — a value written as UTC-aware can come back
    naive on a fresh query. Normalize defensively before any arithmetic against an aware
    reference time."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

# Slope-sign check over a windowed series — the same statistical rigor level as
# equipment_health.py's _pct_change/_zscore_anomaly (simple, deterministic, not ML). A change
# smaller than this fraction of the series mean is treated as noise, not a trend.
FLAT_TOLERANCE_FRACTION = 0.03


def classify_trend(values: list[float]) -> TrendDirection | None:
    """First-vs-last comparison over an ordered (oldest-first) series. None if too little data
    or a zero/negative baseline (can't compute a meaningful direction)."""
    if len(values) < 3:
        return None
    first, last = values[0], values[-1]
    if first <= 0:
        return None
    change = (last - first) / first
    if abs(change) < FLAT_TOLERANCE_FRACTION:
        return "flat"
    return "rising" if change > 0 else "declining"


def derive_confidence_level(evidence_category_count: int) -> ConfidenceLevel:
    """The documented rule: 3+ independent evidence categories present = high, 2 = medium,
    1 (or 0, defensively) = low. Never a numeric/statistical score."""
    if evidence_category_count >= 3:
        return "high"
    if evidence_category_count == 2:
        return "medium"
    return "low"


def compute_is_stale(last_confirmed_at: datetime, now: datetime, threshold_days: int) -> bool:
    return (now - to_aware_utc(last_confirmed_at)).days > threshold_days
