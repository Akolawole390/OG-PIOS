from app.services.equipment_health import (
    BAND_CRITICAL,
    BAND_EXCELLENT,
    BAND_GOOD,
    HealthInputs,
    band_for,
    compute_health,
)


def test_no_data_scores_perfect_excellent():
    result = compute_health(HealthInputs(status="operating"))
    assert result.score == 100.0
    assert result.band == BAND_EXCELLENT
    assert result.factors == []
    assert result.disclaimer_text


def test_operating_hours_over_threshold_deducts():
    result = compute_health(HealthInputs(status="operating", operating_hours=80000, operating_hours_threshold=40000))
    assert result.score < 100.0
    assert any(f.factor == "operating_hours" for f in result.factors)


def test_operating_hours_under_threshold_no_deduction():
    result = compute_health(HealthInputs(status="operating", operating_hours=10000, operating_hours_threshold=40000))
    assert result.score == 100.0
    assert result.factors == []


def test_temperature_trend_increasing_deducts():
    flat = [180.0] * 10
    rising = [180.0 + i * 5 for i in range(10)]  # ~28% increase
    result = compute_health(HealthInputs(status="operating", temperature_readings=rising))
    assert any(f.factor == "temperature_trend" for f in result.factors)

    baseline = compute_health(HealthInputs(status="operating", temperature_readings=flat))
    assert baseline.score == 100.0


def test_temperature_trend_needs_at_least_five_points():
    result = compute_health(HealthInputs(status="operating", temperature_readings=[180.0, 250.0, 300.0]))
    assert result.factors == []  # too few points to compute a trend — never penalized


def test_vibration_trend_weighted_higher_than_temperature():
    # A modest ~15% rise, deliberately kept under both factors' 15-point caps so the
    # weighting difference (0.5x vs 0.6x) is actually observable in the result.
    rising = [1.0 + i * 0.015 for i in range(10)]
    temp_result = compute_health(HealthInputs(status="operating", temperature_readings=rising))
    vib_result = compute_health(HealthInputs(status="operating", vibration_readings=rising))
    temp_deduction = next(f.deduction for f in temp_result.factors if f.factor == "temperature_trend")
    vib_deduction = next(f.deduction for f in vib_result.factors if f.factor == "vibration_trend")
    assert vib_deduction > temp_deduction


def test_current_anomaly_detected_via_zscore():
    stable = [50.0, 51.0, 49.0, 50.5, 49.5, 200.0]  # last value is a huge outlier
    result = compute_health(HealthInputs(status="operating", current_readings=stable))
    assert any(f.factor == "current_flow_anomaly" for f in result.factors)


def test_maintenance_history_capped_at_20():
    result = compute_health(HealthInputs(status="operating", corrective_maintenance_count_180d=10))
    factor = next(f for f in result.factors if f.factor == "maintenance_history")
    assert factor.deduction == 20.0


def test_preventive_maintenance_not_modeled_as_a_deduction():
    # corrective_maintenance_count_180d only counts corrective events by construction —
    # confirms the API layer's job of excluding preventive records, not this function's.
    result = compute_health(HealthInputs(status="operating", corrective_maintenance_count_180d=0))
    assert result.factors == []


def test_failed_status_floors_score_regardless_of_clean_data():
    result = compute_health(HealthInputs(status="failed"))
    assert result.score <= 70  # 100 - 30 flat deduction
    assert result.band in (BAND_CRITICAL, "Maintenance Required", "Monitor")
    assert result.band != BAND_EXCELLENT
    assert result.band != BAND_GOOD


def test_maintenance_status_deducts_flat_ten():
    result = compute_health(HealthInputs(status="maintenance"))
    assert result.score == 90.0
    assert any(f.factor == "status" and f.deduction == 10.0 for f in result.factors)


def test_downtime_deduction_capped_at_15():
    result = compute_health(HealthInputs(status="operating", downtime_hours_90d=1000))
    factor = next(f for f in result.factors if f.factor == "downtime")
    assert factor.deduction == 15.0


def test_alarm_frequency_deduction_capped_at_10():
    result = compute_health(HealthInputs(status="operating", recent_alert_count_30d=50))
    factor = next(f for f in result.factors if f.factor == "alarm_frequency")
    assert factor.deduction == 10.0


def test_score_never_goes_below_zero():
    rising = [100.0 + i * 5 for i in range(10)]  # ~45% increase, saturates both trend caps
    result = compute_health(
        HealthInputs(
            status="failed",
            operating_hours=100000,
            operating_hours_threshold=1000,
            temperature_readings=rising,
            vibration_readings=rising,
            corrective_maintenance_count_180d=10,
            downtime_hours_90d=2000,
            recent_alert_count_30d=50,
        )
    )
    # Sum of every factor's max deduction (15+15+15+20+30+15+10 = 120) exceeds 100 —
    # confirms the floor clamps rather than going negative.
    assert result.score == 0.0
    assert result.band == BAND_CRITICAL


def test_band_boundaries():
    assert band_for(100) == "Excellent"
    assert band_for(90) == "Excellent"
    assert band_for(89.9) == "Good"
    assert band_for(75) == "Good"
    assert band_for(74.9) == "Monitor"
    assert band_for(50) == "Monitor"
    assert band_for(49.9) == "Maintenance Required"
    assert band_for(25) == "Maintenance Required"
    assert band_for(24.9) == "Critical"
    assert band_for(0) == "Critical"
