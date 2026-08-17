from datetime import date, timedelta

from app.models.production import PressureRecord, ProductionRecord, ProductionTarget, TemperatureRecord


def test_list_production_requires_auth(client):
    response = client.get("/production")
    assert response.status_code == 401


def test_create_production_record_computes_fields(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-001")
    headers = auth_headers("Administrator")

    payload = {
        "well_id": well.id,
        "record_date": "2026-06-01",
        "oil_bopd": 800,
        "gas_mscfd": 480,
        "water_bwpd": 200,
        "wellhead_pressure": 1500,
    }
    response = client.post("/production", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["water_cut_pct"] == 20.0  # 200 / (800+200) * 100
    assert body["gor"] == 600.0  # 480*1000/800
    assert body["boe"] == 880.0  # 800 + 480*1000/6000
    assert body["well_code"] == "P-001"
    assert body["downtime_hours"] == 0
    assert body["warnings"] is None


def test_create_production_record_as_viewer_forbidden(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-002")
    headers = auth_headers("Viewer")
    payload = {"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}
    response = client.post("/production", json=payload, headers=headers)
    assert response.status_code == 403


def test_create_production_duplicate_rejected(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-003")
    headers = auth_headers("Administrator")
    payload = {"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}
    first = client.post("/production", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/production", json=payload, headers=headers)
    assert second.status_code == 400


def test_create_production_negative_oil_rejected(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-004")
    headers = auth_headers("Administrator")
    payload = {"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": -50}
    response = client.post("/production", json=payload, headers=headers)
    assert response.status_code == 422


def test_create_production_unusual_value_returns_warning(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-005")
    headers = auth_headers("Administrator")
    payload = {"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 60000}
    response = client.post("/production", json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["warnings"]


def test_get_production_detail_404(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/production/9999", headers=headers)
    assert response.status_code == 404


def test_update_production_record_recomputes_fields(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-006")
    headers = auth_headers("Administrator")
    create = client.post(
        "/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 500, "water_bwpd": 100},
        headers=headers,
    )
    record_id = create.json()["id"]

    update = client.put(f"/production/{record_id}", json={"water_bwpd": 500}, headers=headers)
    assert update.status_code == 200
    body = update.json()
    assert body["water_cut_pct"] == 50.0  # 500 / (500+500) * 100
    assert body["well_id"] == well.id  # unchanged


def test_update_production_ignores_well_id_and_record_date(client, make_field_facility_well, auth_headers, db_session):
    _, _, well = make_field_facility_well(well_id="P-007")
    headers = auth_headers("Administrator")
    create = client.post(
        "/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}, headers=headers
    )
    record_id = create.json()["id"]

    client.put(f"/production/{record_id}", json={"well_id": 99999, "record_date": "2099-01-01"}, headers=headers)

    stored = db_session.query(ProductionRecord).filter(ProductionRecord.id == record_id).first()
    assert stored.well_id == well.id
    assert stored.record_date == date(2026, 6, 1)


def test_delete_production_record_cascades_siblings_not_downtime(
    client, make_field_facility_well, auth_headers, db_session
):
    from app.models.equipment import DowntimeEvent
    from datetime import datetime, timezone

    _, _, well = make_field_facility_well(well_id="P-008")
    headers = auth_headers("Administrator")
    create = client.post(
        "/production",
        json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100, "wellhead_pressure": 1000, "wellhead_temperature": 150},
        headers=headers,
    )
    record_id = create.json()["id"]

    downtime = DowntimeEvent(start_time=datetime.now(timezone.utc), reason="test", well_id=well.id)
    db_session.add(downtime)
    db_session.commit()
    downtime_id = downtime.id

    response = client.delete(f"/production/{record_id}", headers=headers)
    assert response.status_code == 204

    assert db_session.query(ProductionRecord).filter(ProductionRecord.id == record_id).first() is None
    assert (
        db_session.query(PressureRecord)
        .filter(PressureRecord.well_id == well.id, PressureRecord.record_date == date(2026, 6, 1))
        .first()
        is None
    )
    assert (
        db_session.query(TemperatureRecord)
        .filter(TemperatureRecord.well_id == well.id, TemperatureRecord.record_date == date(2026, 6, 1))
        .first()
        is None
    )
    assert db_session.query(DowntimeEvent).filter(DowntimeEvent.id == downtime_id).first() is not None


def test_export_production_csv(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-009")
    headers = auth_headers("Administrator")
    client.post("/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}, headers=headers)

    response = client.get("/production/export", headers=headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "P-009" in response.text


def test_production_kpis_volume_weighted_water_cut(client, make_field_facility_well, auth_headers):
    _, _, well_a = make_field_facility_well(well_id="P-010")
    _, _, well_b = make_field_facility_well(well_id="P-011")
    headers = auth_headers("Administrator")

    # well_a: high volume, low water cut. well_b: low volume, high water cut.
    client.post(
        "/production", json={"well_id": well_a.id, "record_date": "2026-06-01", "oil_bopd": 900, "water_bwpd": 100},
        headers=headers,
    )
    client.post(
        "/production", json={"well_id": well_b.id, "record_date": "2026-06-01", "oil_bopd": 10, "water_bwpd": 90},
        headers=headers,
    )

    response = client.get("/production/kpis", headers=headers)
    assert response.status_code == 200
    body = response.json()
    # naive mean of (10%, 90%) would be 50%; volume-weighted should be much lower
    assert body["avg_water_cut_pct"] < 25
    assert body["total_oil_bbl"] == 910
    assert body["reference_date"] == "2026-06-01"


def test_production_trends_oil_gas_water(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-012")
    headers = auth_headers("Administrator")
    client.post("/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}, headers=headers)
    client.post("/production", json={"well_id": well.id, "record_date": "2026-06-02", "oil_bopd": 200}, headers=headers)

    response = client.get("/production/trends", params={"metric": "oil_gas_water"}, headers=headers)
    assert response.status_code == 200
    points = response.json()["points"]
    assert len(points) == 2
    assert points[0]["oil_bopd"] == 100
    assert points[1]["oil_bopd"] == 200


def test_production_by_scope_group_by_well(client, make_field_facility_well, auth_headers):
    _, _, well_a = make_field_facility_well(well_id="P-013")
    _, _, well_b = make_field_facility_well(well_id="P-014")
    headers = auth_headers("Administrator")
    client.post("/production", json={"well_id": well_a.id, "record_date": "2026-06-01", "oil_bopd": 900}, headers=headers)
    client.post("/production", json={"well_id": well_b.id, "record_date": "2026-06-01", "oil_bopd": 100}, headers=headers)

    response = client.get("/production/by-scope", params={"group_by": "well", "order": "desc"}, headers=headers)
    assert response.status_code == 200
    bars = response.json()["bars"]
    assert bars[0]["label"] == "P-013"
    assert bars[0]["oil_bopd"] == 900


def test_actual_vs_target(client, make_field_facility_well, auth_headers, db_session):
    _, _, well = make_field_facility_well(well_id="P-015")
    headers = auth_headers("Administrator")
    client.post("/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 400}, headers=headers)

    db_session.add(ProductionTarget(well_id=well.id, effective_date=date(2026, 1, 1), oil_target_bopd=500))
    db_session.commit()

    response = client.get("/production/actual-vs-target", headers=headers)
    assert response.status_code == 200
    points = response.json()["points"]
    assert points[0]["actual_oil_bopd"] == 400
    assert points[0]["target_oil_bopd"] == 500


def test_production_issues_reports_down_and_zero_production_wells(
    client, make_field_facility_well, auth_headers, db_session
):
    from app.models.equipment import DowntimeEvent
    from datetime import datetime, timezone

    _, _, down_well = make_field_facility_well(well_id="P-016", status="active")
    _, _, zero_well = make_field_facility_well(well_id="P-017", status="active")
    headers = auth_headers("Administrator")

    client.post("/production", json={"well_id": zero_well.id, "record_date": "2026-06-01", "oil_bopd": 0, "gas_mscfd": 0}, headers=headers)

    db_session.add(DowntimeEvent(start_time=datetime.now(timezone.utc), end_time=None, well_id=down_well.id, reason="test"))
    db_session.commit()

    response = client.get("/production/issues", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert any(w["well_code"] == "P-016" for w in body["down_wells"])
    assert any(w["well_code"] == "P-017" for w in body["zero_production_wells"])


def test_production_targets_crud_and_roles(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="P-018")
    admin_headers = auth_headers("Administrator")
    viewer_headers = auth_headers("Viewer")

    create = client.post(
        "/production/targets",
        json={"well_id": well.id, "effective_date": "2026-01-01", "oil_target_bopd": 600},
        headers=admin_headers,
    )
    assert create.status_code == 201
    target_id = create.json()["id"]

    forbidden = client.post(
        "/production/targets",
        json={"well_id": well.id, "effective_date": "2026-02-01", "oil_target_bopd": 700},
        headers=viewer_headers,
    )
    assert forbidden.status_code == 403

    listed = client.get("/production/targets", params={"well_id": well.id}, headers=viewer_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    updated = client.put(f"/production/targets/{target_id}", json={"oil_target_bopd": 650}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["oil_target_bopd"] == 650

    deleted = client.delete(f"/production/targets/{target_id}", headers=admin_headers)
    assert deleted.status_code == 204
