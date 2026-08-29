from datetime import date, datetime, timedelta, timezone

from app.models.equipment import Equipment
from app.models.production import ProductionRecord, ProductionTarget
from app.services.rate_limit import reset_rate_limits

TODAY = date.today()


def _seed_below_target_well(db_session, make_field_facility_well, well_id="INV-01-001"):
    _field, _facility, well = make_field_facility_well(well_id=well_id)
    for i in range(29):
        db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY - timedelta(days=29 - i), oil_bopd=100.0, gas_mscfd=50.0))
    db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=50.0, gas_mscfd=50.0))
    db_session.add(ProductionTarget(well_id=well.id, effective_date=TODAY - timedelta(days=60), oil_target_bopd=100.0))
    db_session.commit()
    return well


def test_investigate_requires_a_target(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Analyst")
    response = client.post("/ai-insights/investigate", json={}, headers=headers)
    assert response.status_code == 400


def test_investigate_unknown_insight_404(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Analyst")
    response = client.post("/ai-insights/investigate", json={"insight_id": 999999}, headers=headers)
    assert response.status_code == 404


def test_viewer_cannot_investigate(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Viewer")
    response = client.post("/ai-insights/investigate", json={"well_id": 1}, headers=headers)
    assert response.status_code == 403


def test_investigate_by_insight_id_returns_structured_result(client, db_session, auth_headers, make_field_facility_well):
    reset_rate_limits()
    well = _seed_below_target_well(db_session, make_field_facility_well)
    admin_headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=admin_headers)
    insight_id = client.get("/ai-insights", headers=admin_headers).json()["items"][0]["id"]

    response = client.post("/ai-insights/investigate", json={"insight_id": insight_id}, headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["event"]
    assert body["confidence_level"] in ("high", "medium", "low")
    assert body["answered_by"] in ("deterministic", "ai")
    assert len(body["possible_causes"]) >= 1
    assert body["primary_contributor"] == well.well_id
    assert "disclaimer_text" in body


def test_investigate_by_well_id_with_no_correlating_data_still_returns_a_cause(
    client, auth_headers, make_field_facility_well
):
    reset_rate_limits()
    _field, _facility, well = make_field_facility_well(well_id="INV-02-002")
    headers = auth_headers("Analyst")

    response = client.post("/ai-insights/investigate", json={"well_id": well.id}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["primary_contributor"] == well.well_id
    assert len(body["possible_causes"]) == 1
    assert "no correlating" in body["possible_causes"][0]["description"].lower()


def test_investigate_by_equipment_id_surfaces_open_downtime(client, db_session, auth_headers, make_field_facility_well):
    reset_rate_limits()
    _field, facility, _well = make_field_facility_well(well_id="INV-03-003")
    equipment = Equipment(equipment_tag="INV-COMP-1", equipment_type="compressor", facility_id=facility.id)
    db_session.add(equipment)
    db_session.commit()
    db_session.refresh(equipment)

    from app.models.equipment import DowntimeEvent

    db_session.add(DowntimeEvent(start_time=datetime.now(timezone.utc), end_time=None, reason="Vibration trip", equipment_id=equipment.id))
    db_session.commit()

    headers = auth_headers("Analyst")
    response = client.post("/ai-insights/investigate", json={"equipment_id": equipment.id}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["primary_contributor"] == "INV-COMP-1"
    descriptions = [c["description"] for c in body["possible_causes"]]
    assert any("Vibration trip" in d for d in descriptions)
