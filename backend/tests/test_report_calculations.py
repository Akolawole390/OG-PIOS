from datetime import date, datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.ai import Alert
from app.models.economics import CommodityPrice, OperatingCost, ProductionLoss
from app.models.equipment import MaintenanceRecord
from app.models.production import ProductionRecord
from app.models.role import Role
from app.models.user import User
from app.services.report_calculations import (
    REPORT_TYPES,
    ReportFilterValues,
    SYNTHETIC_DATA_DISCLAIMER,
    build_report,
    build_what_if_scenario_report,
    default_sections,
)

TODAY = date.today()


def _make_user(db_session) -> User:
    role = db_session.query(Role).filter_by(name="Administrator").first()
    if role is None:
        role = Role(name="Administrator")
        db_session.add(role)
        db_session.flush()
    user = User(email="report-tester@test.dev", full_name="Report Tester", hashed_password=hash_password("x"), role_id=role.id)
    db_session.add(user)
    db_session.commit()
    return user


def _seed_period(db_session, well, facility, days=10, oil=100.0, gas=50.0):
    start = TODAY - timedelta(days=days - 1)
    for i in range(days):
        db_session.add(ProductionRecord(well_id=well.id, record_date=start + timedelta(days=i), oil_bopd=oil, gas_mscfd=gas))
    db_session.add(CommodityPrice(effective_date=start.replace(day=1), commodity="oil", price=70.0, currency="USD"))
    db_session.add(CommodityPrice(effective_date=start.replace(day=1), commodity="gas", price=3.0, currency="USD"))
    db_session.add(OperatingCost(cost_date=start, category="Production", amount=5000.0, currency="USD", facility_id=facility.id))
    db_session.commit()
    return start, TODAY


def test_default_sections_match_report_types():
    for report_type, meta in REPORT_TYPES.items():
        assert default_sections(report_type) == meta["sections"]


def test_daily_operations_report_reflects_seeded_production(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-01")
    start, end = _seed_period(db_session, well, facility, days=1, oil=200.0, gas=80.0)
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=start, date_to=end, field_id=field.id)
    result = build_report(db_session, user, "daily_operations", filters, None)

    assert result["report_type"] == "daily_operations"
    assert result["synthetic_data_disclaimer"] == SYNTHETIC_DATA_DISCLAIMER
    production = result["sections"]["production"]
    assert production["kpis"]["total_oil_bbl"] == 200.0
    assert production["_traceability"]["source_module"] == "production.get_production_kpis"


def test_field_filter_scopes_production_section(db_session, make_field_facility_well):
    field_a, facility_a, well_a = make_field_facility_well(well_id="RPT-A")
    field_b, facility_b, well_b = make_field_facility_well(well_id="RPT-B")
    start, end = _seed_period(db_session, well_a, facility_a, days=1, oil=100.0)
    _seed_period(db_session, well_b, facility_b, days=1, oil=999.0)
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=start, date_to=end, field_id=field_a.id)
    result = build_report(db_session, user, "daily_operations", filters, None)

    assert result["sections"]["production"]["kpis"]["total_oil_bbl"] == 100.0


def test_section_toggle_skips_unrequested_sections(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-02")
    start, end = _seed_period(db_session, well, facility, days=1)
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=start, date_to=end, field_id=field.id)
    result = build_report(db_session, user, "daily_operations", filters, ["production"])

    assert set(result["sections"].keys()) == {"production"}


def test_maintenance_type_filter(db_session, make_field_facility_well, make_equipment):
    field, facility, well = make_field_facility_well(well_id="RPT-03")
    equipment = make_equipment(equipment_tag="RPT-EQ-1", well=well)
    db_session.add(MaintenanceRecord(
        equipment_id=equipment.id, maintenance_type="preventive", status="completed",
        start_date=TODAY, labor_cost=100.0, parts_cost=0, contractor_cost=0, other_cost=0,
    ))
    db_session.add(MaintenanceRecord(
        equipment_id=equipment.id, maintenance_type="emergency", status="completed",
        start_date=TODAY, labor_cost=500.0, parts_cost=0, contractor_cost=0, other_cost=0,
    ))
    db_session.commit()
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=TODAY, date_to=TODAY, maintenance_type="emergency")
    result = build_report(db_session, user, "daily_operations", filters, ["maintenance"])

    maintenance = result["sections"]["maintenance"]
    assert maintenance["record_count"] == 1
    assert maintenance["emergency_count"] == 1
    assert maintenance["preventive_count"] == 0


def test_production_loss_category_filter(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-04")
    db_session.add(ProductionLoss(
        loss_date=TODAY, well_id=well.id, category="equipment_failure",
        estimated_bopd_lost=50.0, estimated_revenue_impact=3500.0, currency="USD",
    ))
    db_session.add(ProductionLoss(
        loss_date=TODAY, well_id=well.id, category="scheduled_maintenance",
        estimated_bopd_lost=10.0, estimated_revenue_impact=700.0, currency="USD",
    ))
    db_session.commit()
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=TODAY, date_to=TODAY, production_loss_category="equipment_failure")
    result = build_report(db_session, user, "daily_operations", filters, ["production_loss"])

    loss = result["sections"]["production_loss"]
    assert loss["event_count"] == 1
    assert loss["total_oil_bopd_lost"] == 50.0


def test_alert_severity_filter(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-05")
    now = datetime.now(timezone.utc)
    db_session.add(Alert(
        alert_type="production_below_target", category="production", source_module="production",
        severity="critical", title="Critical alert", description="desc", well_id=well.id,
        dedup_key="k1", triggered_at=now, last_detected_at=now,
    ))
    db_session.add(Alert(
        alert_type="production_below_target", category="production", source_module="production",
        severity="low", title="Low alert", description="desc", well_id=well.id,
        dedup_key="k2", triggered_at=now, last_detected_at=now,
    ))
    db_session.commit()
    user = _make_user(db_session)

    filters = ReportFilterValues(alert_severity="critical")
    result = build_report(db_session, user, "daily_operations", filters, ["alerts"])

    alerts = result["sections"]["alerts"]
    assert alerts["total"] == 1
    assert alerts["critical_count"] == 1


def test_economics_section_never_blends_mismatched_currencies(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-06")
    start, end = _seed_period(db_session, well, facility, days=1, oil=500.0, gas=0.0)
    # Override with an NGN cost so operating cost currency mismatches USD revenue.
    db_session.add(OperatingCost(cost_date=start, category="Energy", amount=2_000_000.0, currency="NGN", facility_id=facility.id))
    db_session.commit()
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=start, date_to=end, field_id=field.id)
    result = build_report(db_session, user, "monthly_management", filters, ["economics"])

    economics = result["sections"]["economics"]
    assert economics["margin_currency_mismatch"] is True
    currencies_in_margin = {m["currency"] for m in economics["estimated_operating_margin"]}
    assert "NGN" not in currencies_in_margin


def test_economics_section_reports_insufficient_data_without_date_range(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-07")
    user = _make_user(db_session)

    filters = ReportFilterValues(field_id=field.id)
    result = build_report(db_session, user, "monthly_management", filters, ["economics"])

    assert result["sections"]["economics"]["data_sufficient"] is False


def test_monthly_report_executive_summary_built_from_computed_sections(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-08")
    start, end = _seed_period(db_session, well, facility, days=1, oil=300.0)
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=start, date_to=end, field_id=field.id)
    result = build_report(db_session, user, "monthly_management", filters, None)

    summary = result["sections"]["executive_summary"]
    assert "300" in summary["what_happened"]
    assert isinstance(summary["biggest_risks"], list)


def test_weekly_report_has_no_executive_summary_or_economics(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-09")
    start, end = _seed_period(db_session, well, facility, days=3)
    user = _make_user(db_session)

    filters = ReportFilterValues(date_from=start, date_to=end)
    result = build_report(db_session, user, "weekly_production", filters, None)

    assert "executive_summary" not in result["sections"]
    assert "economics" not in result["sections"]
    assert "production_trend" in result["sections"]


def test_what_if_scenario_report_without_scenario_id_reports_missing_data(db_session):
    filters = ReportFilterValues()
    result = build_what_if_scenario_report(db_session, filters)
    assert result["data_sufficient"] is False
    assert result["missing_data_note"]


def test_every_report_carries_synthetic_data_disclaimer(db_session, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="RPT-10")
    start, end = _seed_period(db_session, well, facility, days=1)
    user = _make_user(db_session)

    for report_type in ("daily_operations", "weekly_production", "monthly_management"):
        filters = ReportFilterValues(date_from=start, date_to=end, field_id=field.id)
        result = build_report(db_session, user, report_type, filters, None)
        assert result["synthetic_data_disclaimer"] == SYNTHETIC_DATA_DISCLAIMER
        assert result["disclaimer_text"]
