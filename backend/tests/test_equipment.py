from datetime import date, datetime, timedelta, timezone

from app.models.equipment import DowntimeEvent, Equipment, EquipmentReading, MaintenanceRecord


def test_list_equipment_requires_auth(client):
    response = client.get("/equipment")
    assert response.status_code == 401


def test_create_equipment_well_linked_resolves_field_facility_well(client, make_field_facility_well, auth_headers):
    field, facility, well = make_field_facility_well(well_id="E-001")
    headers = auth_headers("Administrator")

    payload = {
        "equipment_tag": "ESP-E-001",
        "name": "ESP Unit 1",
        "equipment_type": "ESP",
        "status": "operating",
        "well_id": well.id,
    }
    response = client.post("/equipment", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["well_code"] == "E-001"
    assert body["facility_name"] == facility.name
    assert body["field_name"] == field.name
    assert body["health_score"] is not None  # computed at create time


def test_create_equipment_facility_linked_resolves_field_facility_no_well(
    client, make_field_facility_well, auth_headers
):
    field, facility, _well = make_field_facility_well(well_id="E-002")
    headers = auth_headers("Administrator")

    payload = {
        "equipment_tag": "COMP-01",
        "name": "Compressor 1",
        "equipment_type": "compressor",
        "status": "operating",
        "facility_id": facility.id,
    }
    response = client.post("/equipment", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["well_code"] is None
    assert body["facility_name"] == facility.name
    assert body["field_name"] == field.name


def test_create_equipment_standalone_has_no_scope(client, auth_headers):
    headers = auth_headers("Administrator")
    payload = {
        "equipment_tag": "INSTR-01",
        "name": "Standalone Transmitter",
        "equipment_type": "instrumentation",
        "status": "operating",
    }
    response = client.post("/equipment", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["field_id"] is None
    assert body["facility_id"] is None
    assert body["well_id"] is None


def test_create_equipment_as_viewer_forbidden(client, auth_headers):
    headers = auth_headers("Viewer")
    payload = {"equipment_tag": "X-1", "name": "X", "equipment_type": "valve", "status": "operating"}
    response = client.post("/equipment", json=payload, headers=headers)
    assert response.status_code == 403


def test_create_equipment_as_maintenance_engineer_succeeds(client, auth_headers):
    headers = auth_headers("Maintenance Engineer")
    payload = {"equipment_tag": "X-2", "name": "X", "equipment_type": "valve", "status": "operating"}
    response = client.post("/equipment", json=payload, headers=headers)
    assert response.status_code == 201


def test_create_equipment_duplicate_tag_rejected(client, auth_headers):
    headers = auth_headers("Administrator")
    payload = {"equipment_tag": "DUP-1", "name": "X", "equipment_type": "valve", "status": "operating"}
    first = client.post("/equipment", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/equipment", json=payload, headers=headers)
    assert second.status_code == 400


def test_get_equipment_404(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/equipment/9999", headers=headers)
    assert response.status_code == 404


def test_update_equipment_status_recomputes_health(client, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/equipment",
        json={"equipment_tag": "UPD-1", "name": "X", "equipment_type": "valve", "status": "operating"},
        headers=headers,
    )
    equipment_id = create.json()["id"]
    healthy_score = create.json()["health_score"]

    update = client.put(f"/equipment/{equipment_id}", json={"status": "failed"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["status"] == "failed"
    assert update.json()["health_score"] < healthy_score


def test_delete_equipment_blocked_when_history_exists(client, db_session, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/equipment",
        json={"equipment_tag": "DEL-1", "name": "X", "equipment_type": "valve", "status": "operating"},
        headers=headers,
    )
    equipment_id = create.json()["id"]

    db_session.add(
        MaintenanceRecord(maintenance_type="preventive", status="completed", equipment_id=equipment_id)
    )
    db_session.commit()

    response = client.delete(f"/equipment/{equipment_id}", headers=headers)
    assert response.status_code == 400


def test_delete_equipment_allowed_without_history(client, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/equipment",
        json={"equipment_tag": "DEL-2", "name": "X", "equipment_type": "valve", "status": "operating"},
        headers=headers,
    )
    equipment_id = create.json()["id"]

    response = client.delete(f"/equipment/{equipment_id}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/equipment/{equipment_id}", headers=headers).status_code == 404


def test_equipment_health_endpoint_returns_breakdown_and_disclaimer(client, db_session, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/equipment",
        json={
            "equipment_tag": "HLTH-1",
            "name": "X",
            "equipment_type": "ESP",
            "status": "operating",
            "operating_hours": 90000,
        },
        headers=headers,
    )
    equipment_id = create.json()["id"]

    response = client.get(f"/equipment/{equipment_id}/health", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["score"] < 100
    assert any(f["factor"] == "operating_hours" for f in body["factors"])
    assert body["disclaimer_text"]


def test_readings_write_requires_role_and_read_is_open(client, auth_headers):
    admin_headers = auth_headers("Administrator")
    viewer_headers = auth_headers("Viewer")

    create = client.post(
        "/equipment",
        json={"equipment_tag": "RD-1", "name": "X", "equipment_type": "compressor", "status": "operating"},
        headers=admin_headers,
    )
    equipment_id = create.json()["id"]

    forbidden = client.post(
        f"/equipment/{equipment_id}/readings",
        json={"reading_at": datetime.now(timezone.utc).isoformat(), "parameter": "temperature", "value": 180.0},
        headers=viewer_headers,
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        f"/equipment/{equipment_id}/readings",
        json={"reading_at": datetime.now(timezone.utc).isoformat(), "parameter": "temperature", "value": 180.0},
        headers=admin_headers,
    )
    assert allowed.status_code == 201

    listed = client.get(f"/equipment/{equipment_id}/readings", params={"parameter": "temperature"}, headers=viewer_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_readings_date_to_filter_includes_readings_taken_later_the_same_day(client, auth_headers):
    """Regression test for a real bug found during pilot-demo validation: date_to is a calendar
    date with no time-of-day, but reading_at is a timestamp. A reading taken "now" (this instant,
    today) must still be returned when filtering with date_to=today — a naive
    "reading_at <= date_to" comparison would silently exclude it once today has passed midnight."""
    admin_headers = auth_headers("Administrator")
    create = client.post(
        "/equipment",
        json={"equipment_tag": "RD-2", "name": "X", "equipment_type": "compressor", "status": "operating"},
        headers=admin_headers,
    )
    equipment_id = create.json()["id"]
    client.post(
        f"/equipment/{equipment_id}/readings",
        json={"reading_at": datetime.now(timezone.utc).isoformat(), "parameter": "temperature", "value": 180.0},
        headers=admin_headers,
    )

    today = date.today()
    listed = client.get(
        f"/equipment/{equipment_id}/readings",
        params={"date_from": str(today), "date_to": str(today)},
        headers=admin_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_equipment_maintenance_and_downtime_direct_fk(client, db_session, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/equipment",
        json={"equipment_tag": "MD-1", "name": "X", "equipment_type": "compressor", "status": "operating"},
        headers=headers,
    )
    equipment_id = create.json()["id"]

    db_session.add(
        MaintenanceRecord(maintenance_type="corrective", status="completed", cost=1000, equipment_id=equipment_id)
    )
    db_session.add(
        DowntimeEvent(
            start_time=datetime.now(timezone.utc) - timedelta(hours=5),
            end_time=datetime.now(timezone.utc),
            reason="test",
            equipment_id=equipment_id,
        )
    )
    db_session.commit()

    maintenance = client.get(f"/equipment/{equipment_id}/maintenance", headers=headers)
    assert maintenance.status_code == 200
    assert maintenance.json()["summary"]["record_count"] == 1

    downtime = client.get(f"/equipment/{equipment_id}/downtime", headers=headers)
    assert downtime.status_code == 200
    assert downtime.json()["summary"]["event_count"] == 1


def test_equipment_dashboard_counts_and_distribution(client, auth_headers):
    headers = auth_headers("Administrator")
    client.post(
        "/equipment",
        json={"equipment_tag": "DASH-1", "name": "X", "equipment_type": "valve", "status": "operating"},
        headers=headers,
    )
    client.post(
        "/equipment",
        json={"equipment_tag": "DASH-2", "name": "Y", "equipment_type": "valve", "status": "failed"},
        headers=headers,
    )

    response = client.get("/equipment/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status_counts"]["total"] >= 2
    assert body["status_counts"]["failed"] >= 1
    total_bucketed = sum(b["count"] for b in body["health_distribution"]["buckets"])
    assert total_bucketed + body["health_distribution"]["unscored_count"] == body["status_counts"]["total"]


def test_equipment_by_scope_group_by_type(client, auth_headers):
    headers = auth_headers("Administrator")
    client.post(
        "/equipment",
        json={"equipment_tag": "SCOPE-1", "name": "X", "equipment_type": "generator", "status": "operating"},
        headers=headers,
    )
    response = client.get("/equipment/by-scope", params={"group_by": "type"}, headers=headers)
    assert response.status_code == 200
    labels = [bar["label"] for bar in response.json()["bars"]]
    assert "generator" in labels


def test_equipment_issues_lists_failed_equipment(client, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/equipment",
        json={"equipment_tag": "ISSUE-1", "name": "X", "equipment_type": "valve", "status": "failed"},
        headers=headers,
    )
    equipment_id = create.json()["id"]

    response = client.get("/equipment/issues", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert equipment_id in ids
