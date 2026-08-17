from datetime import date, datetime, timedelta, timezone

from app.models.ai import Alert
from app.models.economics import CommodityPrice, OperatingCost, ProductionLoss
from app.models.equipment import DowntimeEvent, EquipmentReading, MaintenanceRecord
from app.models.production import ProductionRecord, ProductionTarget
from app.services.alert_rules import (
    _dedup_key,
    _generate_economics_alerts,
    _generate_equipment_alerts,
    _generate_maintenance_alerts,
    _generate_production_alerts,
    _generate_production_loss_alerts,
    _tiered_severity,
    run_alert_rules,
)

TODAY = date.today()


def _seed_baseline_production(db_session, well, days=30, oil=100.0):
    """A steady, unremarkable production history ending YESTERDAY (never today) so callers can
    freely add their own record for today without a unique-constraint collision, and so
    decline/unusual-change rules don't fire incidentally while a test targets a different rule."""
    for i in range(days):
        db_session.add(
            ProductionRecord(well_id=well.id, record_date=TODAY - timedelta(days=days - i), oil_bopd=oil, gas_mscfd=50.0)
        )
    db_session.commit()


def test_tiered_severity_helper():
    tiers = [(1.0, "medium"), (1.5, "high"), (2.0, "critical")]
    assert _tiered_severity(100, 100, tiers) == "medium"
    assert _tiered_severity(160, 100, tiers) == "high"
    assert _tiered_severity(250, 100, tiers) == "critical"
    assert _tiered_severity(100, 0, tiers) == "critical"  # zero threshold guards to the top tier


def test_dedup_key_format():
    assert _dedup_key("production_below_target", "well", 42) == "production_below_target:well:42"


def test_production_below_target_tiered_severity(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="PB-01")
    _seed_baseline_production(db_session, well, days=29)
    db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=50.0, gas_mscfd=50.0))
    db_session.add(ProductionTarget(well_id=well.id, effective_date=TODAY - timedelta(days=60), oil_target_bopd=100.0))
    db_session.commit()

    candidates = _generate_production_alerts(db_session)
    below_target = [c for c in candidates if c.alert_type == "production_below_target" and c.well_id == well.id]
    assert len(below_target) == 1
    assert below_target[0].severity == "critical"  # 50% deficit vs. 10% default threshold => >3.5x
    assert below_target[0].dedup_key == f"production_below_target:well:{well.id}"


def test_production_decline_fires_on_trailing_average_drop(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="PD-01")
    for i in range(30):
        record_date = TODAY - timedelta(days=29 - i)
        oil = 50.0 if record_date >= TODAY - timedelta(days=6) else 100.0
        db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil, gas_mscfd=50.0))
    db_session.commit()

    candidates = _generate_production_alerts(db_session)
    decline = [c for c in candidates if c.alert_type == "production_decline" and c.well_id == well.id]
    assert len(decline) == 1
    assert decline[0].severity in ("medium", "high", "critical")


def test_production_outage_fires_for_open_downtime_event(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="OUT-01")
    _seed_baseline_production(db_session, well, days=5)
    db_session.add(DowntimeEvent(well_id=well.id, start_time=datetime.now(timezone.utc) - timedelta(hours=5), end_time=None))
    db_session.commit()

    candidates = _generate_production_alerts(db_session)
    outage = [c for c in candidates if c.alert_type == "production_outage" and c.well_id == well.id]
    assert len(outage) == 1
    assert outage[0].severity == "critical"


def test_equipment_failure_and_health_are_mutually_exclusive(db_session, make_equipment):
    failed = make_equipment(equipment_tag="EQ-FAIL", status="failed")
    failed.health_score = 10  # even with a critical-range score, status=failed should win, not double-alert
    db_session.commit()

    candidates = _generate_equipment_alerts(db_session)
    failed_candidates = [c for c in candidates if c.equipment_id == failed.id]
    assert len(failed_candidates) == 1
    assert failed_candidates[0].alert_type == "equipment_failure"
    assert failed_candidates[0].severity == "critical"


def test_equipment_critical_vs_low_health_thresholds(db_session, make_equipment):
    critical_eq = make_equipment(equipment_tag="EQ-CRIT", status="operating")
    critical_eq.health_score = 20
    low_eq = make_equipment(equipment_tag="EQ-LOW", status="operating")
    low_eq.health_score = 40
    healthy_eq = make_equipment(equipment_tag="EQ-OK", status="operating")
    healthy_eq.health_score = 90
    db_session.commit()

    candidates = _generate_equipment_alerts(db_session)
    by_equipment = {c.equipment_id: c for c in candidates if c.alert_type.startswith("equipment_")}
    assert by_equipment[critical_eq.id].alert_type == "equipment_critical_health"
    assert by_equipment[low_eq.id].alert_type == "equipment_low_health"
    assert healthy_eq.id not in by_equipment


def test_abnormal_equipment_readings_detects_zscore_outlier(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-ANOM", status="operating")
    now = datetime.now(timezone.utc)
    # Small variance history so std_dev > 0 (the real _zscore_anomaly guards against a
    # zero-variance division), then a huge outlier as the latest reading.
    history_values = [10.0, 11.0, 9.0, 10.0, 12.0, 9.0, 11.0, 10.0, 9.0]
    for i, value in enumerate(history_values):
        db_session.add(
            EquipmentReading(
                equipment_id=equipment.id, reading_at=now - timedelta(days=len(history_values) - i), parameter="current", value=value
            )
        )
    db_session.add(EquipmentReading(equipment_id=equipment.id, reading_at=now, parameter="current", value=500.0))
    db_session.commit()

    candidates = _generate_equipment_alerts(db_session)
    anomalies = [c for c in candidates if c.alert_type == "abnormal_equipment_readings" and c.equipment_id == equipment.id]
    assert len(anomalies) == 1


def test_maintenance_overdue_severity_tiers(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-OD", status="operating")
    db_session.add(
        MaintenanceRecord(
            equipment_id=equipment.id, maintenance_type="preventive", status="open",
            planned_completion_date=TODAY - timedelta(days=10),
        )
    )
    db_session.commit()

    candidates = _generate_maintenance_alerts(db_session)
    overdue = [c for c in candidates if c.alert_type == "maintenance_overdue" and c.equipment_id == equipment.id]
    assert len(overdue) == 1
    assert overdue[0].severity == "high"  # 10 days overdue falls in the 8-30 day band


def test_maintenance_due_soon_fires_within_lookahead(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-SOON", status="operating")
    db_session.add(
        MaintenanceRecord(
            equipment_id=equipment.id, maintenance_type="preventive", status="scheduled",
            planned_completion_date=TODAY + timedelta(days=5),
        )
    )
    db_session.commit()

    candidates = _generate_maintenance_alerts(db_session)
    due_soon = [c for c in candidates if c.alert_type == "maintenance_due_soon" and c.equipment_id == equipment.id]
    assert len(due_soon) == 1
    assert due_soon[0].severity == "low"


def test_critical_maintenance_priority_fires(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-CRITM", status="operating")
    db_session.add(
        MaintenanceRecord(equipment_id=equipment.id, maintenance_type="corrective", status="open", priority="critical")
    )
    db_session.commit()

    candidates = _generate_maintenance_alerts(db_session)
    critical = [c for c in candidates if c.alert_type == "critical_maintenance" and c.equipment_id == equipment.id]
    assert len(critical) == 1
    assert critical[0].severity == "critical"


def test_repeated_maintenance_events_fires_at_default_threshold(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-REPEAT", status="operating")
    for i in range(3):
        db_session.add(
            MaintenanceRecord(
                equipment_id=equipment.id, maintenance_type="corrective", status="completed",
                start_date=TODAY - timedelta(days=10 * (i + 1)),
            )
        )
    db_session.commit()

    candidates = _generate_maintenance_alerts(db_session)
    repeated = [c for c in candidates if c.alert_type == "repeated_maintenance_events" and c.equipment_id == equipment.id]
    assert len(repeated) == 1
    assert repeated[0].current_value == 3


def test_high_production_loss_tiered_severity(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="PL-01")
    db_session.add(ProductionLoss(loss_date=TODAY, well_id=well.id, estimated_bopd_lost=250.0))  # 5x default 50bbl
    db_session.commit()

    candidates = _generate_production_loss_alerts(db_session)
    high_loss = [c for c in candidates if c.alert_type == "high_production_loss" and c.well_id == well.id]
    assert len(high_loss) == 1
    assert high_loss[0].severity == "critical"


def test_high_downtime_fires_above_threshold(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="DT-01")
    db_session.add(ProductionLoss(loss_date=TODAY, well_id=well.id, downtime_hours=30.0))
    db_session.commit()

    candidates = _generate_production_loss_alerts(db_session)
    high_downtime = [c for c in candidates if c.alert_type == "high_downtime" and c.well_id == well.id]
    assert len(high_downtime) == 1
    assert high_downtime[0].severity == "medium"  # 30h vs. 24h threshold => 1.25x


def test_high_estimated_lost_revenue_is_usd_only(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="REV-01")
    db_session.add(ProductionLoss(loss_date=TODAY, well_id=well.id, estimated_revenue_impact=50000.0, currency="USD"))
    db_session.commit()

    candidates = _generate_production_loss_alerts(db_session)
    high_revenue = [c for c in candidates if c.alert_type == "high_estimated_lost_revenue" and c.well_id == well.id]
    assert len(high_revenue) == 1
    assert high_revenue[0].severity == "critical"  # 5x default $10,000 threshold


def test_high_estimated_lost_revenue_ignores_non_usd(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="REV-02")
    db_session.add(ProductionLoss(loss_date=TODAY, well_id=well.id, estimated_revenue_impact=5_000_000.0, currency="NGN"))
    db_session.commit()

    candidates = _generate_production_loss_alerts(db_session)
    high_revenue = [c for c in candidates if c.alert_type == "high_estimated_lost_revenue" and c.well_id == well.id]
    assert high_revenue == []


def test_repeated_production_loss_events_fires_at_default_threshold(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="REP-01")
    for i in range(3):
        db_session.add(ProductionLoss(loss_date=TODAY - timedelta(days=10 * (i + 1)), well_id=well.id))
    db_session.commit()

    candidates = _generate_production_loss_alerts(db_session)
    repeated = [c for c in candidates if c.alert_type == "repeated_production_loss_events" and c.well_id == well.id]
    assert len(repeated) == 1


def test_declining_operating_margin_uses_configurable_threshold(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="MARGIN-01")
    this_month = TODAY.replace(day=1)
    prev_month_end = this_month - timedelta(days=1)
    prev_month = prev_month_end.replace(day=1)

    db_session.add(ProductionRecord(well_id=well.id, record_date=this_month, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(ProductionRecord(well_id=well.id, record_date=prev_month, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(CommodityPrice(effective_date=prev_month, commodity="oil", price=70.0, currency="USD"))
    db_session.add(OperatingCost(cost_date=this_month, category="Energy", amount=25000.0, currency="USD", field_id=field.id))
    db_session.add(OperatingCost(cost_date=prev_month, category="Energy", amount=1000.0, currency="USD", field_id=field.id))
    db_session.commit()

    candidates = _generate_economics_alerts(db_session)
    declining = [c for c in candidates if c.alert_type == "declining_operating_margin" and c.field_id == field.id]
    assert len(declining) == 1
    assert declining[0].severity == "high"


def test_high_maintenance_cost_reuses_fleet_average_check(db_session, make_equipment, make_field_facility_well):
    _field, facility, well = make_field_facility_well(well_id="HMC-01")
    # 3 low-cost equipment pull the fleet average down so the expensive one clearly clears
    # the default 2x-fleet-average threshold (2 equal-weighted items can never mathematically
    # exceed 2x their own pairwise average).
    for i in range(3):
        normal_eq = make_equipment(equipment_tag=f"EQ-NORMAL-{i}", facility=facility)
        db_session.add(MaintenanceRecord(equipment_id=normal_eq.id, maintenance_type="preventive", status="completed",
                                          start_date=TODAY - timedelta(days=10), labor_cost=10.0, cost=10.0))
    expensive_eq = make_equipment(equipment_tag="EQ-EXPENSIVE", facility=facility)
    db_session.add(MaintenanceRecord(equipment_id=expensive_eq.id, maintenance_type="corrective", status="completed",
                                      start_date=TODAY - timedelta(days=10), labor_cost=10000.0, cost=10000.0))
    db_session.commit()

    candidates = _generate_economics_alerts(db_session)
    high_cost = [c for c in candidates if c.alert_type == "high_maintenance_cost" and c.equipment_id == expensive_eq.id]
    assert len(high_cost) == 1


def test_run_alert_rules_creates_alerts_from_real_data(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="RUN-01")
    db_session.add(DowntimeEvent(well_id=well.id, start_time=datetime.now(timezone.utc) - timedelta(hours=2), end_time=None))
    db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=0.0, gas_mscfd=0.0))
    db_session.commit()

    result = run_alert_rules(db_session)
    assert result.created >= 1
    assert result.updated == 0
    assert result.auto_resolved == 0

    alerts = db_session.query(Alert).filter(Alert.well_id == well.id).all()
    assert len(alerts) >= 1
    assert all(a.dedup_key for a in alerts)
    assert all(a.triggered_at is not None and a.last_detected_at is not None for a in alerts)
