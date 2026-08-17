from datetime import datetime, timedelta, timezone

from app.services.reliability_metrics import DowntimeInterval, _merge_intervals, compute_reliability

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
PERIOD_HOURS = 365 * 24


def test_no_events_gives_perfect_availability_and_insufficient_mtbf_mttr():
    result = compute_reliability([], PERIOD_HOURS, now=NOW)
    assert result.failure_count == 0
    assert result.mtbf_hours is None
    assert result.mtbf_data_sufficient is False
    assert result.mttr_hours is None
    assert result.mttr_data_sufficient is False
    assert result.availability_pct == 100.0
    assert result.disclaimer_text
    assert result.assumptions


def test_single_closed_event_computes_mttr_but_not_mtbf():
    intervals = [DowntimeInterval(start=NOW - timedelta(days=10), end=NOW - timedelta(days=10) + timedelta(hours=6))]
    result = compute_reliability(intervals, PERIOD_HOURS, now=NOW)
    assert result.mttr_hours == 6.0
    assert result.mttr_data_sufficient is True
    assert result.mtbf_hours is None
    assert result.mtbf_data_sufficient is False
    assert result.failure_count == 1


def test_open_event_excluded_from_mttr_but_counted_as_a_failure():
    intervals = [DowntimeInterval(start=NOW - timedelta(hours=5), end=None)]
    result = compute_reliability(intervals, PERIOD_HOURS, now=NOW)
    assert result.mttr_hours is None
    assert result.mttr_data_sufficient is False
    assert result.failure_count == 1
    # Open event still counts toward downtime/availability, clipped to `now`.
    assert result.availability_pct is not None
    assert result.availability_pct < 100.0


def test_mtbf_needs_at_least_two_events():
    one_event = [DowntimeInterval(start=NOW - timedelta(days=10), end=NOW - timedelta(days=9))]
    result = compute_reliability(one_event, PERIOD_HOURS, now=NOW)
    assert result.mtbf_data_sufficient is False
    assert result.mtbf_hours is None


def test_mtbf_averages_gaps_between_consecutive_starts():
    intervals = [
        DowntimeInterval(start=NOW - timedelta(days=30), end=NOW - timedelta(days=30) + timedelta(hours=4)),
        DowntimeInterval(start=NOW - timedelta(days=20), end=NOW - timedelta(days=20) + timedelta(hours=4)),
        DowntimeInterval(start=NOW - timedelta(days=10), end=NOW - timedelta(days=10) + timedelta(hours=4)),
    ]
    result = compute_reliability(intervals, PERIOD_HOURS, now=NOW)
    assert result.mtbf_data_sufficient is True
    # Two 10-day gaps -> mean gap = 10 days = 240 hours.
    assert result.mtbf_hours == 240.0


def test_availability_reflects_total_downtime_in_window():
    # 48 hours of downtime out of a 240-hour observation period.
    intervals = [DowntimeInterval(start=NOW - timedelta(hours=100), end=NOW - timedelta(hours=52))]
    result = compute_reliability(intervals, observation_period_hours=240, now=NOW)
    assert result.availability_pct == round((240 - 48) / 240 * 100, 2)


def test_failure_count_annualized_scales_to_a_365_day_rate():
    intervals = [
        DowntimeInterval(start=NOW - timedelta(days=i * 10), end=NOW - timedelta(days=i * 10) + timedelta(hours=1))
        for i in range(3)
    ]
    # Observation window is only 30 days, but 3 failures in 30 days annualizes to 36.5/year.
    result = compute_reliability(intervals, observation_period_hours=30 * 24, now=NOW)
    assert result.failure_count == 3
    assert result.failure_count_annualized == round(3 * (365 * 24 / (30 * 24)), 2)


def test_zero_period_hours_leaves_availability_and_annualized_rate_unset():
    result = compute_reliability([], observation_period_hours=0, now=NOW)
    assert result.availability_pct is None
    assert result.failure_count_annualized is None


# ----- Overlapping downtime events (regression coverage for the master-audit remediation) -----
# Nothing in the write path currently prevents two DowntimeEvent rows for the same equipment
# from overlapping in time (there is no create/update API for DowntimeEvent at all today — only
# the demo seed script writes them, and its random generation can produce overlapping windows
# for the same well/equipment). _merge_intervals ensures overlapping wall-clock downtime is
# never double-counted in the aggregate downtime-hours/availability figure, regardless of how
# the overlap arose.

def _hours(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600


def test_merge_non_overlapping_intervals_stays_separate():
    a = (NOW - timedelta(hours=10), NOW - timedelta(hours=8))
    b = (NOW - timedelta(hours=4), NOW - timedelta(hours=2))
    merged = _merge_intervals([a, b])
    assert merged == [a, b]


def test_merge_adjacent_intervals_combines_into_one_span():
    a = (NOW - timedelta(hours=10), NOW - timedelta(hours=6))
    b = (NOW - timedelta(hours=6), NOW - timedelta(hours=2))  # b starts exactly when a ends
    merged = _merge_intervals([a, b])
    assert merged == [(NOW - timedelta(hours=10), NOW - timedelta(hours=2))]


def test_merge_overlapping_intervals_combines_and_does_not_double_count():
    a = (NOW - timedelta(hours=10), NOW - timedelta(hours=4))
    b = (NOW - timedelta(hours=6), NOW - timedelta(hours=2))  # overlaps a's last 2 hours
    merged = _merge_intervals([a, b])
    assert merged == [(NOW - timedelta(hours=10), NOW - timedelta(hours=2))]
    # Naive per-interval summation would give 6 + 4 = 10 hours; the true wall-clock span is 8.
    assert sum(_hours(s, e) for s, e in merged) == 8.0


def test_merge_identical_start_and_end_collapses_to_a_single_span():
    a = (NOW - timedelta(hours=5), NOW - timedelta(hours=1))
    b = (NOW - timedelta(hours=5), NOW - timedelta(hours=1))  # exact duplicate
    merged = _merge_intervals([a, b])
    assert merged == [a]
    assert sum(_hours(s, e) for s, e in merged) == 4.0


def test_merge_multiple_overlapping_events_collapse_to_one_chained_span():
    a = (NOW - timedelta(hours=20), NOW - timedelta(hours=15))
    b = (NOW - timedelta(hours=16), NOW - timedelta(hours=10))
    c = (NOW - timedelta(hours=11), NOW - timedelta(hours=5))
    merged = _merge_intervals([c, a, b])  # deliberately out of order — merge must sort first
    assert merged == [(NOW - timedelta(hours=20), NOW - timedelta(hours=5))]


def test_merge_empty_list_returns_empty():
    assert _merge_intervals([]) == []


def test_compute_reliability_availability_reflects_merged_downtime_not_double_counted():
    # Two overlapping DowntimeEvent-equivalent intervals for the same equipment: without
    # merging, a naive sum would report 10 hours of downtime (6 + 4); the true wall-clock
    # downtime is only 8 hours, since the two intervals share a 2-hour overlap.
    intervals = [
        DowntimeInterval(start=NOW - timedelta(hours=10), end=NOW - timedelta(hours=4)),
        DowntimeInterval(start=NOW - timedelta(hours=6), end=NOW - timedelta(hours=2)),
    ]
    result = compute_reliability(intervals, observation_period_hours=24, now=NOW)
    # availability = (24 - 8) / 24 * 100, NOT (24 - 10) / 24 * 100.
    assert result.availability_pct == round((24 - 8) / 24 * 100, 2)
    # MTBF/MTTR are unaffected by merging — each event is still a distinct failure/repair.
    assert result.failure_count == 2
    assert result.mttr_hours == 5.0  # mean of the two individual (unmerged) durations: (6+4)/2
