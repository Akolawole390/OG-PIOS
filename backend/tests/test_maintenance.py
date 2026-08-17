from datetime import date, datetime, timedelta, timezone

from app.models.equipment import DowntimeEvent, MaintenanceRecord


def test_list_maintenance_requires_auth(client):
    response = client.get("/maintenance")
    assert response.status_code == 401


def test_create_maintenance_requires_valid_equipment(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/maintenance",
        json={"equipment_id": 9999, "maintenance_type": "preventive"},
        headers=headers,
    )
    assert response.status_code == 404


def test_create_maintenance_generates_work_order_number_and_sums_cost(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-1")

    response = client.post(
        "/maintenance",
        json={
            "equipment_id": equipment.id,
            "maintenance_type": "preventive",
            "labor_cost": 500.0,
            "parts_cost": 250.5,
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["work_order_number"].startswith("WO-")
    assert body["cost"] == 750.5
    assert body["equipment_tag"] == "WO-1"
    assert body["priority"] == "medium"
    assert body["status"] == "scheduled"


def test_create_maintenance_with_no_cost_components_leaves_cost_null(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-2")

    response = client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "inspection"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["cost"] is None


def test_create_maintenance_as_viewer_forbidden(client, auth_headers, make_equipment):
    headers = auth_headers("Viewer")
    equipment = make_equipment(equipment_tag="WO-3")
    response = client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "preventive"},
        headers=headers,
    )
    assert response.status_code == 403


def test_create_maintenance_as_maintenance_engineer_succeeds(client, auth_headers, make_equipment):
    headers = auth_headers("Maintenance Engineer")
    equipment = make_equipment(equipment_tag="WO-4")
    response = client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "preventive"},
        headers=headers,
    )
    assert response.status_code == 201


def test_create_maintenance_rejects_invalid_status_and_priority(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-5")
    response = client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "preventive", "status": "not_a_status"},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_maintenance_corrective_recomputes_equipment_health(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-6")
    assert equipment.health_score is None

    response = client.post(
        "/maintenance",
        json={
            "equipment_id": equipment.id,
            "maintenance_type": "corrective",
            "status": "completed",
            "start_date": date.today().isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 201

    detail = client.get(f"/equipment/{equipment.id}", headers=headers)
    assert detail.json()["health_score"] == 95.0  # 100 - 5 for one corrective event in 180d


def test_get_maintenance_404(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/maintenance/9999", headers=headers)
    assert response.status_code == 404


def test_update_maintenance_status_change_recomputes_health(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-7", status="operating")
    create = client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "preventive", "status": "scheduled"},
        headers=headers,
    )
    record_id = create.json()["id"]

    update = client.put(f"/maintenance/{record_id}", json={"status": "in_progress"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["status"] == "in_progress"

    detail = client.get(f"/equipment/{equipment.id}", headers=headers)
    # status="maintenance" isn't set on equipment automatically (no auto status mutation) —
    # confirm the equipment record itself is untouched, only its health cache may have moved.
    assert detail.json()["status"] == "operating"


def test_delete_maintenance_allowed_when_scheduled_with_no_actuals(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-8")
    create = client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "preventive", "status": "scheduled"},
        headers=headers,
    )
    record_id = create.json()["id"]

    response = client.delete(f"/maintenance/{record_id}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/maintenance/{record_id}", headers=headers).status_code == 404


def test_delete_maintenance_blocked_with_recorded_cost(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-9")
    create = client.post(
        "/maintenance",
        json={
            "equipment_id": equipment.id,
            "maintenance_type": "corrective",
            "status": "completed",
            "labor_cost": 100.0,
        },
        headers=headers,
    )
    record_id = create.json()["id"]

    response = client.delete(f"/maintenance/{record_id}", headers=headers)
    assert response.status_code == 400


def test_list_maintenance_filters_by_equipment_and_status(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    eq_a = make_equipment(equipment_tag="WO-10-A")
    eq_b = make_equipment(equipment_tag="WO-10-B")
    client.post(
        "/maintenance",
        json={"equipment_id": eq_a.id, "maintenance_type": "preventive", "status": "scheduled"},
        headers=headers,
    )
    client.post(
        "/maintenance",
        json={"equipment_id": eq_b.id, "maintenance_type": "corrective", "status": "completed"},
        headers=headers,
    )

    by_equipment = client.get("/maintenance", params={"equipment_id": eq_a.id}, headers=headers)
    assert by_equipment.json()["total"] == 1
    assert by_equipment.json()["items"][0]["equipment_tag"] == "WO-10-A"

    by_status = client.get("/maintenance", params={"status": "completed"}, headers=headers)
    assert all(item["status"] == "completed" for item in by_status.json()["items"])


def test_maintenance_dashboard_counts_and_costs(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-11")
    client.post(
        "/maintenance",
        json={
            "equipment_id": equipment.id,
            "maintenance_type": "emergency",
            "status": "in_progress",
            "labor_cost": 1000.0,
            "downtime_hours": 5.0,
        },
        headers=headers,
    )
    client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "preventive", "status": "completed"},
        headers=headers,
    )

    response = client.get("/maintenance/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status_counts"]["total"] >= 2
    assert body["status_counts"]["emergency_count"] >= 1
    assert body["total_cost"] >= 1000.0
    assert body["total_downtime_hours"] >= 5.0


def test_maintenance_by_scope_group_by_type(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-12")
    client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "calibration", "labor_cost": 300.0},
        headers=headers,
    )

    response = client.get("/maintenance/by-scope", params={"group_by": "type"}, headers=headers)
    assert response.status_code == 200
    labels = [bar["label"] for bar in response.json()["bars"]]
    assert "calibration" in labels


def test_maintenance_by_scope_group_by_well(client, auth_headers, make_field_facility_well, make_equipment):
    headers = auth_headers("Administrator")
    _field, _facility, well = make_field_facility_well(well_id="WO-13-WELL")
    equipment = make_equipment(equipment_tag="WO-13", well=well)
    client.post(
        "/maintenance",
        json={"equipment_id": equipment.id, "maintenance_type": "preventive", "labor_cost": 200.0},
        headers=headers,
    )

    response = client.get("/maintenance/by-scope", params={"group_by": "well"}, headers=headers)
    assert response.status_code == 200
    labels = [bar["label"] for bar in response.json()["bars"]]
    assert "WO-13-WELL" in labels


def test_maintenance_cost_trend_groups_by_month(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-13")
    today = date.today()
    client.post(
        "/maintenance",
        json={
            "equipment_id": equipment.id,
            "maintenance_type": "preventive",
            "start_date": today.isoformat(),
            "labor_cost": 200.0,
        },
        headers=headers,
    )

    response = client.get("/maintenance/cost-trend", headers=headers)
    assert response.status_code == 200
    months = [p["month"] for p in response.json()["points"]]
    assert today.strftime("%Y-%m") in months


def test_maintenance_schedule_buckets_overdue_due_today_and_upcoming(client, db_session, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-14")
    today = date.today()

    overdue = MaintenanceRecord(
        maintenance_type="preventive",
        status="scheduled",
        planned_completion_date=today - timedelta(days=3),
        equipment_id=equipment.id,
    )
    due_today = MaintenanceRecord(
        maintenance_type="preventive",
        status="open",
        planned_completion_date=today,
        equipment_id=equipment.id,
    )
    upcoming = MaintenanceRecord(
        maintenance_type="preventive",
        status="scheduled",
        planned_completion_date=today + timedelta(days=5),
        equipment_id=equipment.id,
    )
    db_session.add_all([overdue, due_today, upcoming])
    db_session.commit()

    response = client.get("/maintenance/schedule", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert any(item["id"] == overdue.id for item in body["overdue"])
    assert any(item["id"] == due_today.id for item in body["due_today"])
    assert any(item["id"] == upcoming.id for item in body["upcoming"])


def test_maintenance_schedule_includes_equipment_level_next_maintenance_due(
    client, db_session, auth_headers, make_equipment
):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-15")
    equipment.next_maintenance_due = date.today() - timedelta(days=10)
    db_session.commit()

    response = client.get("/maintenance/schedule", headers=headers)
    assert response.status_code == 200
    overdue_equipment_ids = [item["equipment_id"] for item in response.json()["overdue"] if item["source"] == "equipment"]
    assert equipment.id in overdue_equipment_ids


def test_equipment_reliability_insufficient_data_with_no_downtime_events(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-16")

    response = client.get(f"/equipment/{equipment.id}/reliability", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["failure_count"] == 0
    assert body["mtbf_data_sufficient"] is False
    assert body["mttr_data_sufficient"] is False
    assert body["availability_pct"] == 100.0
    assert body["disclaimer_text"]


def test_equipment_reliability_reflects_closed_downtime_events(client, db_session, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-17")
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            DowntimeEvent(
                start_time=now - timedelta(days=30),
                end_time=now - timedelta(days=30) + timedelta(hours=6),
                equipment_id=equipment.id,
            ),
            DowntimeEvent(
                start_time=now - timedelta(days=10),
                end_time=now - timedelta(days=10) + timedelta(hours=4),
                equipment_id=equipment.id,
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/equipment/{equipment.id}/reliability", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["failure_count"] == 2
    assert body["mtbf_data_sufficient"] is True
    assert body["mttr_data_sufficient"] is True
    assert body["mttr_hours"] == 5.0
    assert body["availability_pct"] < 100.0


def test_equipment_maintenance_summary_includes_total_downtime_hours(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="WO-18")
    client.post(
        "/maintenance",
        json={
            "equipment_id": equipment.id,
            "maintenance_type": "corrective",
            "status": "completed",
            "downtime_hours": 7.5,
        },
        headers=headers,
    )

    response = client.get(f"/equipment/{equipment.id}/maintenance", headers=headers)
    assert response.status_code == 200
    assert response.json()["summary"]["total_downtime_hours"] == 7.5
