from datetime import datetime, timedelta, timezone

from app.services.insight_calculations import classify_trend, compute_is_stale, derive_confidence_level


def test_classify_trend_rising():
    assert classify_trend([100.0, 105.0, 120.0]) == "rising"


def test_classify_trend_declining():
    assert classify_trend([120.0, 110.0, 90.0]) == "declining"


def test_classify_trend_flat():
    assert classify_trend([100.0, 101.0, 102.0]) == "flat"


def test_classify_trend_insufficient_data():
    assert classify_trend([100.0, 105.0]) is None


def test_classify_trend_zero_baseline_guard():
    assert classify_trend([0.0, 50.0, 100.0]) is None


def test_derive_confidence_level_high_with_three_or_more_categories():
    assert derive_confidence_level(3) == "high"
    assert derive_confidence_level(4) == "high"


def test_derive_confidence_level_medium_with_two_categories():
    assert derive_confidence_level(2) == "medium"


def test_derive_confidence_level_low_with_one_or_zero_categories():
    assert derive_confidence_level(1) == "low"
    assert derive_confidence_level(0) == "low"


def test_compute_is_stale_true_past_threshold():
    now = datetime.now(timezone.utc)
    last_confirmed = now - timedelta(days=10)
    assert compute_is_stale(last_confirmed, now, threshold_days=7) is True


def test_compute_is_stale_false_within_threshold():
    now = datetime.now(timezone.utc)
    last_confirmed = now - timedelta(days=3)
    assert compute_is_stale(last_confirmed, now, threshold_days=7) is False
