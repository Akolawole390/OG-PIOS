from datetime import date, datetime, timedelta, timezone

from app.models.ai import AIRecommendation
from app.models.economics import CommodityPrice, OperatingCost, ProductionLoss
from app.models.equipment import DowntimeEvent, EquipmentReading, MaintenanceRecord
from app.models.production import ProductionRecord, ProductionTarget
from app.services.insight_engine import (
    _generate_cross_domain_insights,
    _generate_economics_insights,
    _generate_equipment_insights,
    _generate_maintenance_insights,
    _generate_production_insights,
    _generate_production_loss_insights,
    run_insight_engine,
)
from app.services.alert_rules import (
    _generate_economics_alerts,
    _generate_equipment_alerts,
    _generate_maintenance_alerts,
    _generate_production_alerts,
    _generate_production_loss_alerts,
)

TODAY = date.today()


def _seed_baseline_production(db_session, well, days=30, oil=100.0):
    for i in range(days):
        db_session.add(
            ProductionRecord(well_id=well.id, record_date=TODAY - timedelta(days=days - i), oil_bopd=oil, gas_mscfd=50.0)
        )


def test_production_decline_insight_has_observed_and_calculated_evidence(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="ID-01")
    for i in range(30):
        record_date = TODAY - timedelta(days=29 - i)
        oil = 50.0 if record_date >= TODAY - timedelta(days=6) else 100.0
        db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil, gas_mscfd=50.0))
    db_session.commit()

    alerts = _generate_production_alerts(db_session)
    insights = _generate_production_insights(db_session, alerts)
    decline = [i for i in insights if i.insight_type == "production_decline" and i.well_id == well.id]
    assert len(decline) == 1
    types = {e.evidence_type for e in decline[0].evidence}
    assert "observed_fact" in types
    assert "calculated_metric" in types
    assert decline[0].confidence_level == "medium"  # 2 evidence categories


def test_production_below_target_insight(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="ID-02")
    _seed_baseline_production(db_session, well, days=29)
    db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=50.0, gas_mscfd=50.0))
    db_session.add(ProductionTarget(well_id=well.id, effective_date=TODAY - timedelta(days=60), oil_target_bopd=100.0))
    db_session.commit()

    alerts = _generate_production_alerts(db_session)
    insights = _generate_production_insights(db_session, alerts)
    below_target = [i for i in insights if i.insight_type == "production_below_target" and i.well_id == well.id]
    assert len(below_target) == 1
    assert below_target[0].severity == "critical"


def test_production_increase_insight_fires_on_sustained_rise(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="ID-03")
    for i in range(30):
        record_date = TODAY - timedelta(days=29 - i)
        oil = 200.0 if record_date >= TODAY - timedelta(days=6) else 100.0
        db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil, gas_mscfd=50.0))
    db_session.commit()

    alerts = _generate_production_alerts(db_session)
    insights = _generate_production_insights(db_session, alerts)
    increase = [i for i in insights if i.insight_type == "production_increase" and i.well_id == well.id]
    assert len(increase) == 1
    assert increase[0].severity == "informational"


def test_production_trend_insight_classifies_direction(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="ID-04")
    for month_offset in range(3):
        record_date = TODAY - timedelta(days=30 * (2 - month_offset))
        oil = 100.0 + month_offset * 50.0
        db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil, gas_mscfd=50.0))
    db_session.commit()

    alerts = _generate_production_alerts(db_session)
    insights = _generate_production_insights(db_session, alerts)
    trend = [i for i in insights if i.insight_type == "production_trend" and i.well_id == well.id]
    assert len(trend) == 1
    assert "rising" in trend[0].title.lower()


def test_well_performance_comparison_flags_underperforming_well(db_session, make_field_facility_well):
    field, facility, well_low = make_field_facility_well(well_id="ID-05")
    from app.models.field import Well

    well_mid = Well(well_id="ID-06", name="Well ID-06", status="active", facility_id=facility.id)
    well_high = Well(well_id="ID-07", name="Well ID-07", status="active", facility_id=facility.id)
    db_session.add_all([well_mid, well_high])
    db_session.commit()

    for well, oil in ((well_low, 10.0), (well_mid, 100.0), (well_high, 100.0)):
        db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=oil, gas_mscfd=50.0))
    db_session.commit()

    alerts = _generate_production_alerts(db_session)
    insights = _generate_production_insights(db_session, alerts)
    comparison = [i for i in insights if i.insight_type == "well_performance_comparison" and i.field_id == field.id]
    assert len(comparison) == 1
    assert "ID-05" in comparison[0].summary


def test_equipment_health_deterioration_insight_collapses_tiers(db_session, make_equipment):
    critical_eq = make_equipment(equipment_tag="EQ-ID-01", status="operating")
    critical_eq.health_score = 15
    db_session.commit()

    alerts = _generate_equipment_alerts(db_session)
    insights = _generate_equipment_insights(db_session, alerts)
    matched = [i for i in insights if i.insight_type == "equipment_health_deterioration" and i.equipment_id == critical_eq.id]
    assert len(matched) == 1
    assert matched[0].severity == "critical"


def test_abnormal_equipment_readings_insight(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-ID-02", status="operating")
    now = datetime.now(timezone.utc)
    history_values = [10.0, 11.0, 9.0, 10.0, 12.0, 9.0, 11.0, 10.0, 9.0]
    for i, value in enumerate(history_values):
        db_session.add(EquipmentReading(equipment_id=equipment.id, reading_at=now - timedelta(days=len(history_values) - i), parameter="current", value=value))
    db_session.add(EquipmentReading(equipment_id=equipment.id, reading_at=now, parameter="current", value=500.0))
    db_session.commit()

    alerts = _generate_equipment_alerts(db_session)
    insights = _generate_equipment_insights(db_session, alerts)
    matched = [i for i in insights if i.insight_type == "abnormal_equipment_readings" and i.equipment_id == equipment.id]
    assert len(matched) == 1


def test_equipment_repeated_issues_insight(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-ID-03", status="operating")
    for i in range(3):
        db_session.add(MaintenanceRecord(equipment_id=equipment.id, maintenance_type="corrective", status="completed", start_date=TODAY - timedelta(days=10 * (i + 1))))
    db_session.commit()

    alerts = _generate_equipment_alerts(db_session)
    insights = _generate_equipment_insights(db_session, alerts)
    matched = [i for i in insights if i.insight_type == "equipment_repeated_issues" and i.equipment_id == equipment.id]
    assert len(matched) == 1
    assert matched[0].severity == "high"


def test_maintenance_overdue_insight(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-ID-04", status="operating")
    db_session.add(MaintenanceRecord(equipment_id=equipment.id, maintenance_type="preventive", status="open", planned_completion_date=TODAY - timedelta(days=10)))
    db_session.commit()

    maintenance_alerts = _generate_maintenance_alerts(db_session)
    economics_alerts = _generate_economics_alerts(db_session)
    insights = _generate_maintenance_insights(db_session, maintenance_alerts, economics_alerts)
    matched = [i for i in insights if i.insight_type == "maintenance_overdue" and i.equipment_id == equipment.id]
    assert len(matched) == 1


def test_evidence_source_id_matches_its_own_source_type_not_a_different_fk(db_session, make_field_facility_well, make_equipment):
    """Regression test: a well-linked equipment's overdue-maintenance candidate carries both
    well_id and equipment_id. The evidence row's source_type="equipment" must carry the
    equipment's own id — never silently fall back to the well's id just because well_id happens
    to be set on the same candidate."""
    _field, _facility, well = make_field_facility_well(well_id="ID-16")
    # Separate tables have independent autoincrement sequences, so a single well/equipment pair
    # could coincidentally both land on id=1 — create two throwaway equipment rows first so
    # well.id and equipment.id are guaranteed to differ, making the assertion below meaningful.
    make_equipment(equipment_tag="EQ-DECOY-1", status="operating")
    make_equipment(equipment_tag="EQ-DECOY-2", status="operating")
    equipment = make_equipment(equipment_tag="EQ-ID-16", well=well, status="operating")
    assert equipment.id != well.id
    equipment.next_maintenance_due = TODAY - timedelta(days=5)
    db_session.commit()

    maintenance_alerts = _generate_maintenance_alerts(db_session)
    economics_alerts = _generate_economics_alerts(db_session)
    insights = _generate_maintenance_insights(db_session, maintenance_alerts, economics_alerts)
    matched = [i for i in insights if i.insight_type == "maintenance_overdue" and i.equipment_id == equipment.id]
    assert len(matched) == 1

    equipment_evidence = [e for e in matched[0].evidence if e.source_type == "equipment"]
    assert len(equipment_evidence) >= 1
    for e in equipment_evidence:
        assert e.source_id == equipment.id
        assert e.source_id != well.id


def test_increasing_maintenance_frequency_insight(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-ID-05", status="operating")
    for i in range(2):
        db_session.add(MaintenanceRecord(equipment_id=equipment.id, maintenance_type="preventive", status="completed", start_date=TODAY - timedelta(days=150 + i * 10)))
    for i in range(6):
        db_session.add(MaintenanceRecord(equipment_id=equipment.id, maintenance_type="preventive", status="completed", start_date=TODAY - timedelta(days=10 * (i + 1))))
    db_session.commit()

    maintenance_alerts = _generate_maintenance_alerts(db_session)
    economics_alerts = _generate_economics_alerts(db_session)
    insights = _generate_maintenance_insights(db_session, maintenance_alerts, economics_alerts)
    matched = [i for i in insights if i.insight_type == "increasing_maintenance_frequency" and i.equipment_id == equipment.id]
    assert len(matched) == 1


def test_recurring_corrective_maintenance_insight(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-ID-06", status="operating")
    for i in range(3):
        db_session.add(MaintenanceRecord(equipment_id=equipment.id, maintenance_type="corrective", status="completed", start_date=TODAY - timedelta(days=10 * (i + 1))))
    db_session.commit()

    maintenance_alerts = _generate_maintenance_alerts(db_session)
    economics_alerts = _generate_economics_alerts(db_session)
    insights = _generate_maintenance_insights(db_session, maintenance_alerts, economics_alerts)
    matched = [i for i in insights if i.insight_type == "recurring_corrective_maintenance" and i.equipment_id == equipment.id]
    assert len(matched) == 1


def test_high_production_loss_and_high_lost_revenue_insights(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="ID-08")
    db_session.add(ProductionLoss(loss_date=TODAY, well_id=well.id, estimated_bopd_lost=250.0, estimated_revenue_impact=50000.0, currency="USD"))
    db_session.commit()

    alerts = _generate_production_loss_alerts(db_session)
    insights = _generate_production_loss_insights(db_session, alerts)
    loss_insight = [i for i in insights if i.insight_type == "high_production_loss" and i.well_id == well.id]
    revenue_insight = [i for i in insights if i.insight_type == "high_lost_revenue" and i.well_id == well.id]
    assert len(loss_insight) == 1
    assert len(revenue_insight) == 1
    assert revenue_insight[0].estimated_financial_impact_value == 50000.0
    assert revenue_insight[0].estimated_financial_impact_currency == "USD"


def test_declining_operating_margin_insight(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="ID-09")
    this_month = TODAY.replace(day=1)
    prev_month_end = this_month - timedelta(days=1)
    prev_month = prev_month_end.replace(day=1)

    db_session.add(ProductionRecord(well_id=well.id, record_date=this_month, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(ProductionRecord(well_id=well.id, record_date=prev_month, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(CommodityPrice(effective_date=prev_month, commodity="oil", price=70.0, currency="USD"))
    db_session.add(OperatingCost(cost_date=this_month, category="Energy", amount=25000.0, currency="USD", field_id=field.id))
    db_session.add(OperatingCost(cost_date=prev_month, category="Energy", amount=1000.0, currency="USD", field_id=field.id))
    db_session.commit()

    economics_alerts = _generate_economics_alerts(db_session)
    insights = _generate_economics_insights(db_session, economics_alerts)
    matched = [i for i in insights if i.insight_type == "declining_operating_margin" and i.field_id == field.id]
    assert len(matched) == 1


def test_rising_operating_cost_insight(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="ID-10")
    this_month = TODAY.replace(day=1)
    prev_month_end = this_month - timedelta(days=1)
    prev_month = prev_month_end.replace(day=1)
    db_session.add(ProductionRecord(well_id=well.id, record_date=this_month, oil_bopd=100.0, gas_mscfd=0.0))
    db_session.add(OperatingCost(cost_date=this_month, category="Energy", amount=10000.0, currency="USD", field_id=field.id))
    db_session.add(OperatingCost(cost_date=prev_month, category="Energy", amount=1000.0, currency="USD", field_id=field.id))
    db_session.commit()

    economics_alerts = _generate_economics_alerts(db_session)
    insights = _generate_economics_insights(db_session, economics_alerts)
    matched = [i for i in insights if i.insight_type == "rising_operating_cost" and i.field_id == field.id]
    assert len(matched) == 1


def test_high_maintenance_cost_vs_production_insight(db_session, make_field_facility_well, make_equipment):
    field, facility, well = make_field_facility_well(well_id="ID-11")
    equipment = make_equipment(equipment_tag="EQ-ID-11", well=well)
    this_month = TODAY.replace(day=1)
    db_session.add(ProductionRecord(well_id=well.id, record_date=this_month, oil_bopd=10.0, gas_mscfd=0.0))
    db_session.add(MaintenanceRecord(equipment_id=equipment.id, maintenance_type="corrective", status="completed", start_date=this_month, cost=1000.0))
    db_session.commit()

    economics_alerts = _generate_economics_alerts(db_session)
    insights = _generate_economics_insights(db_session, economics_alerts)
    matched = [i for i in insights if i.insight_type == "high_maintenance_cost_vs_production" and i.field_id == field.id]
    assert len(matched) == 1


def test_cross_domain_two_signal_insight(db_session, make_field_facility_well, make_equipment):
    _field, _facility, well = make_field_facility_well(well_id="ID-12")
    equipment = make_equipment(equipment_tag="EQ-ID-12", well=well)
    equipment.health_score = 15
    for i in range(30):
        record_date = TODAY - timedelta(days=29 - i)
        oil = 50.0 if record_date >= TODAY - timedelta(days=6) else 100.0
        db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil, gas_mscfd=50.0))
    db_session.commit()

    production_alerts = _generate_production_alerts(db_session)
    equipment_alerts = _generate_equipment_alerts(db_session)
    insights = _generate_cross_domain_insights(db_session, production_alerts, equipment_alerts)
    matched = [i for i in insights if i.insight_type == "equipment_linked_to_production_decline"]
    assert len(matched) == 1
    assert matched[0].confidence_level == "medium"


def test_cross_domain_four_signal_flagship_insight(db_session, make_field_facility_well, make_equipment):
    _field, _facility, well = make_field_facility_well(well_id="ID-13")
    equipment = make_equipment(equipment_tag="EQ-ID-13", well=well)
    equipment.health_score = 15
    for i in range(30):
        record_date = TODAY - timedelta(days=29 - i)
        oil = 50.0 if record_date >= TODAY - timedelta(days=6) else 100.0
        db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil, gas_mscfd=50.0))
    db_session.add(MaintenanceRecord(equipment_id=equipment.id, maintenance_type="corrective", status="completed", start_date=TODAY - timedelta(days=10)))
    db_session.add(DowntimeEvent(equipment_id=equipment.id, well_id=well.id, start_time=datetime.now(timezone.utc) - timedelta(hours=5), end_time=datetime.now(timezone.utc) - timedelta(hours=2)))
    db_session.commit()

    production_alerts = _generate_production_alerts(db_session)
    equipment_alerts = _generate_equipment_alerts(db_session)
    insights = _generate_cross_domain_insights(db_session, production_alerts, equipment_alerts)
    matched = [i for i in insights if i.insight_type == "equipment_production_maintenance_downtime_correlation"]
    assert len(matched) == 1
    assert matched[0].severity == "high"
    evidence_types = {e.evidence_type for e in matched[0].evidence}
    assert "possible_contributor" in evidence_types
    # Never claims causation — correlation/possible-contributor language only.
    assert "caused" not in matched[0].summary.lower()
    assert "confirmed cause" not in matched[0].summary.lower() or "not a confirmed cause" in matched[0].summary.lower()


def test_run_insight_engine_dedup_updates_in_place(db_session, make_field_facility_well):
    _field, _facility, well = make_field_facility_well(well_id="ID-14")
    _seed_baseline_production(db_session, well, days=29)
    db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=50.0, gas_mscfd=50.0))
    db_session.add(ProductionTarget(well_id=well.id, effective_date=TODAY - timedelta(days=60), oil_target_bopd=100.0))
    db_session.commit()

    first = run_insight_engine(db_session)
    assert first.created >= 1
    assert first.updated == 0

    second = run_insight_engine(db_session)
    assert second.created == 0
    assert second.updated == first.created

    insight = db_session.query(AIRecommendation).filter(AIRecommendation.well_id == well.id).first()
    assert insight is not None
    assert insight.occurrence_count == 2


def test_insight_never_auto_dismissed_when_condition_clears(db_session, make_equipment):
    equipment = make_equipment(equipment_tag="EQ-ID-15", status="operating")
    equipment.health_score = 15  # critical range
    db_session.commit()

    run_insight_engine(db_session)
    insight = (
        db_session.query(AIRecommendation)
        .filter(AIRecommendation.equipment_id == equipment.id, AIRecommendation.insight_type == "equipment_health_deterioration")
        .first()
    )
    assert insight is not None
    assert insight.status == "new"

    # Clear the condition (health recovers) and re-run — the engine must never auto-dismiss;
    # dismissal is always a manual action, unlike Alerts' auto-resolve.
    equipment.health_score = 95
    db_session.commit()
    run_insight_engine(db_session)

    db_session.refresh(insight)
    assert insight.status == "new"
