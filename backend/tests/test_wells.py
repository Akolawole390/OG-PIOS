from datetime import date, datetime, timedelta, timezone

from app.models.equipment import DowntimeEvent, Equipment, MaintenanceRecord
from app.models.field import Facility, Field, Well
from app.models.production import PressureRecord, ProductionRecord


def _make_field_facility_well(db_session, *, well_id="W-001", status="active"):
    field = Field(name="Test Field")
    db_session.add(field)
    db_session.flush()
    facility = Facility(name="Test Facility", field_id=field.id)
    db_session.add(facility)
    db_session.flush()
    well = Well(well_id=well_id, name="Test Well", status=status, facility_id=facility.id)
    db_session.add(well)
    db_session.commit()
    return field, facility, well


def test_list_wells_requires_auth(client):
    response = client.get("/wells")
    assert response.status_code == 401


def test_list_wells_search_filter_sort_pagination(client, db_session, auth_headers):
    _make_field_facility_well(db_session, well_id="A-001")

    field2 = Field(name="Field 2")
    db_session.add(field2)
    db_session.flush()
    facility2 = Facility(name="Facility 2", field_id=field2.id)
    db_session.add(facility2)
    db_session.flush()
    db_session.add(Well(well_id="B-002", name="Second Well", status="shut_in", facility_id=facility2.id))
    db_session.commit()

    headers = auth_headers("Viewer")

    response = client.get("/wells", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 2

    response = client.get("/wells", params={"search": "Second"}, headers=headers)
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["well_id"] == "B-002"

    response = client.get("/wells", params={"status": "shut_in"}, headers=headers)
    assert response.json()["total"] == 1

    response = client.get("/wells", params={"sort": "well_id", "order": "desc"}, headers=headers)
    assert response.json()["items"][0]["well_id"] == "B-002"

    response = client.get("/wells", params={"page": 1, "page_size": 1}, headers=headers)
    body = response.json()
    assert len(body["items"]) == 1
    assert body["page_size"] == 1


def test_create_well_as_admin_succeeds(client, db_session, auth_headers):
    field = Field(name="Field")
    db_session.add(field)
    db_session.flush()
    facility = Facility(name="Facility", field_id=field.id)
    db_session.add(facility)
    db_session.commit()

    headers = auth_headers("Administrator")
    payload = {"well_id": "NEW-001", "name": "New Well", "facility_id": facility.id}
    response = client.post("/wells", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["well_id"] == "NEW-001"
    assert body["facility"]["field"]["name"] == "Field"


def test_create_well_as_viewer_forbidden(client, db_session, auth_headers):
    field = Field(name="Field")
    db_session.add(field)
    db_session.flush()
    facility = Facility(name="Facility", field_id=field.id)
    db_session.add(facility)
    db_session.commit()

    headers = auth_headers("Viewer")
    payload = {"well_id": "NEW-002", "name": "New Well", "facility_id": facility.id}
    response = client.post("/wells", json=payload, headers=headers)
    assert response.status_code == 403


def test_create_well_duplicate_well_id_rejected(client, db_session, auth_headers):
    _, facility, _well = _make_field_facility_well(db_session, well_id="DUP-001")
    headers = auth_headers("Administrator")
    payload = {"well_id": "DUP-001", "name": "Dup", "facility_id": facility.id}
    response = client.post("/wells", json=payload, headers=headers)
    assert response.status_code == 400


def test_get_well_detail_includes_facility_and_field(client, db_session, auth_headers):
    field, facility, well = _make_field_facility_well(db_session)
    headers = auth_headers("Viewer")
    response = client.get(f"/wells/{well.id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["facility"]["name"] == facility.name
    assert body["facility"]["field"]["name"] == field.name


def test_get_well_detail_404(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/wells/9999", headers=headers)
    assert response.status_code == 404


def test_update_well(client, db_session, auth_headers):
    _, _, well = _make_field_facility_well(db_session)
    headers = auth_headers("Administrator")
    response = client.put(f"/wells/{well.id}", json={"status": "shut_in"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "shut_in"


def test_well_production_endpoint_respects_days_param(client, db_session, auth_headers):
    _, _, well = _make_field_facility_well(db_session)
    db_session.add_all(
        [
            ProductionRecord(record_date=date.today() - timedelta(days=200), oil_bopd=100, well_id=well.id),
            ProductionRecord(record_date=date.today() - timedelta(days=5), oil_bopd=200, well_id=well.id),
        ]
    )
    db_session.commit()

    headers = auth_headers("Viewer")
    response = client.get(f"/wells/{well.id}/production", params={"days": 30}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["oil_bopd"] == 200


def test_well_pressure_endpoint(client, db_session, auth_headers):
    _, _, well = _make_field_facility_well(db_session)
    db_session.add(PressureRecord(record_date=date.today(), wellhead_pressure=1500, well_id=well.id))
    db_session.commit()

    headers = auth_headers("Viewer")
    response = client.get(f"/wells/{well.id}/pressure", headers=headers)
    assert response.status_code == 200
    assert response.json()[0]["wellhead_pressure"] == 1500


def test_well_downtime_endpoint_summary(client, db_session, auth_headers):
    _, _, well = _make_field_facility_well(db_session)
    start = datetime.now(timezone.utc) - timedelta(hours=10)
    end = datetime.now(timezone.utc) - timedelta(hours=5)
    db_session.add(DowntimeEvent(start_time=start, end_time=end, reason="test", well_id=well.id))
    db_session.commit()

    headers = auth_headers("Viewer")
    response = client.get(f"/wells/{well.id}/downtime", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["event_count"] == 1
    assert abs(body["summary"]["total_hours"] - 5.0) < 0.1


def test_well_maintenance_endpoint_via_linked_equipment(client, db_session, auth_headers):
    _, _, well = _make_field_facility_well(db_session)
    equipment = Equipment(equipment_tag="ESP-1", equipment_type="ESP", well_id=well.id)
    db_session.add(equipment)
    db_session.flush()
    db_session.add(
        MaintenanceRecord(
            maintenance_type="preventive",
            status="completed",
            cost=1000,
            equipment_id=equipment.id,
        )
    )
    db_session.commit()

    headers = auth_headers("Viewer")
    response = client.get(f"/wells/{well.id}/maintenance", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["record_count"] == 1
    assert body["summary"]["total_cost"] == 1000
    assert body["records"][0]["equipment_tag"] == "ESP-1"
