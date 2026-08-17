from datetime import date, datetime, timedelta, timezone

from app.models.ai import Alert
from app.models.economics import ProductionLoss
from app.models.equipment import DowntimeEvent

TODAY = date.today()


def test_list_alerts_requires_auth(client):
    response = client.get("/alerts")
    assert response.status_code == 401


def test_run_alert_rules_requires_administrator(client, auth_headers):
    headers = auth_headers("Production Engineer")
    response = client.post("/alerts/run", headers=headers)
    assert response.status_code == 403


def test_run_alert_rules_second_run_dedups_instead_of_duplicating(
    client, db_session, auth_headers, make_field_facility_well
):
    """The module's central lifecycle guarantee: a condition that's still true on a second
    rule run updates the existing open alert (bumping occurrence_count) rather than creating
    a duplicate row."""
    headers = auth_headers("Administrator")
    _field, _facility, well = make_field_facility_well(well_id="DEDUP-01")
    db_session.add(
        DowntimeEvent(well_id=well.id, start_time=datetime.now(timezone.utc) - timedelta(hours=3), end_time=None)
    )
    db_session.commit()

    first = client.post("/alerts/run", headers=headers)
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["created"] >= 1
    assert first_body["updated"] == 0

    second = client.post("/alerts/run", headers=headers)
    second_body = second.json()
    assert second_body["created"] == 0
    assert second_body["updated"] == first_body["created"]

    alerts = db_session.query(Alert).filter(Alert.well_id == well.id, Alert.alert_type == "production_outage").all()
    assert len(alerts) == 1
    assert alerts[0].occurrence_count == 2


def test_auto_resolve_non_critical_alert_when_condition_clears(
    client, db_session, auth_headers, make_field_facility_well
):
    headers = auth_headers("Administrator")
    _field, _facility, well = make_field_facility_well(well_id="AUTORES-01")
    loss = ProductionLoss(loss_date=TODAY, well_id=well.id, downtime_hours=30.0)  # medium severity, non-critical
    db_session.add(loss)
    db_session.commit()

    client.post("/alerts/run", headers=headers)
    alert = db_session.query(Alert).filter(Alert.well_id == well.id, Alert.alert_type == "high_downtime").first()
    assert alert is not None
    assert alert.severity != "critical"
    assert alert.state == "new"

    db_session.delete(loss)
    db_session.commit()

    run_result = client.post("/alerts/run", headers=headers).json()
    assert run_result["auto_resolved"] >= 1

    db_session.refresh(alert)
    assert alert.state == "resolved"
    assert alert.resolved_at is not None


def test_critical_alert_is_never_auto_resolved(client, db_session, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    equipment = make_equipment(equipment_tag="EQ-NEVERAUTO", status="failed")

    client.post("/alerts/run", headers=headers)
    alert = db_session.query(Alert).filter(Alert.equipment_id == equipment.id, Alert.alert_type == "equipment_failure").first()
    assert alert is not None
    assert alert.severity == "critical"

    equipment.status = "operating"  # condition clears
    db_session.commit()

    client.post("/alerts/run", headers=headers)
    db_session.refresh(alert)
    assert alert.state == "new"  # still open — critical alerts are never auto-resolved
    assert alert.resolved_at is None


def test_resolved_alert_reopens_as_a_new_row_if_condition_recurs(
    client, db_session, auth_headers, make_field_facility_well
):
    headers = auth_headers("Administrator")
    _field, _facility, well = make_field_facility_well(well_id="REOPEN-01")
    db_session.add(
        DowntimeEvent(well_id=well.id, start_time=datetime.now(timezone.utc) - timedelta(hours=1), end_time=None)
    )
    db_session.commit()

    client.post("/alerts/run", headers=headers)
    first_alert = db_session.query(Alert).filter(Alert.well_id == well.id, Alert.alert_type == "production_outage").first()

    client.put(f"/alerts/{first_alert.id}/resolve", json={"note": "restored"}, headers=headers)
    db_session.refresh(first_alert)
    assert first_alert.state == "resolved"

    run_result = client.post("/alerts/run", headers=headers).json()
    assert run_result["created"] >= 1  # a fresh alert opens since the prior one is resolved, not open

    all_alerts = db_session.query(Alert).filter(Alert.well_id == well.id, Alert.alert_type == "production_outage").all()
    assert len(all_alerts) == 2
    assert any(a.state == "new" for a in all_alerts)


def test_alert_lifecycle_and_audit_trail(client, db_session, auth_headers, make_field_facility_well):
    admin_headers = auth_headers("Administrator")
    field, _facility, _well = make_field_facility_well(well_id="LIFECYCLE-01")

    create_response = client.post(
        "/alerts",
        json={
            "category": "production",
            "alert_type": "manual_note",
            "severity": "low",
            "title": "Manual test alert",
            "description": "Created directly for a lifecycle test.",
            "field_id": field.id,
        },
        headers=admin_headers,
    )
    assert create_response.status_code == 201
    alert_id = create_response.json()["id"]
    assert create_response.json()["source_module"] == "manual"

    ack = client.put(f"/alerts/{alert_id}/acknowledge", json={"note": "on it"}, headers=admin_headers)
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged"
    assert ack.json()["acknowledged_by_name"]

    investigate = client.put(f"/alerts/{alert_id}/investigate", json={}, headers=admin_headers)
    assert investigate.json()["status"] == "investigating"

    resolve = client.put(f"/alerts/{alert_id}/resolve", json={"note": "fixed"}, headers=admin_headers)
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "resolved"
    assert resolve.json()["resolved_by_name"]

    history = client.get(f"/alerts/{alert_id}/history", headers=admin_headers)
    assert history.status_code == 200
    transitions = [(h["from_state"], h["to_state"]) for h in history.json()["items"]]
    assert (None, "new") in transitions
    assert ("new", "acknowledged") in transitions
    assert ("acknowledged", "investigating") in transitions
    assert ("investigating", "resolved") in transitions


def test_dismiss_alert(client, auth_headers):
    headers = auth_headers("Administrator")
    created = client.post(
        "/alerts",
        json={
            "category": "equipment", "alert_type": "manual_note", "severity": "informational",
            "title": "Dismiss me", "description": "test",
        },
        headers=headers,
    ).json()

    response = client.put(f"/alerts/{created['id']}/dismiss", json={"note": "not actionable"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"


def test_viewer_cannot_acknowledge_alerts(client, auth_headers):
    admin_headers = auth_headers("Administrator")
    viewer_headers = auth_headers("Viewer")
    created = client.post(
        "/alerts",
        json={
            "category": "equipment", "alert_type": "manual_note", "severity": "low",
            "title": "Viewer test", "description": "test",
        },
        headers=admin_headers,
    ).json()

    response = client.put(f"/alerts/{created['id']}/acknowledge", json={}, headers=viewer_headers)
    assert response.status_code == 403


def test_manual_alert_create_requires_management_or_administrator(client, auth_headers):
    headers = auth_headers("Production Engineer")
    response = client.post(
        "/alerts",
        json={
            "category": "production", "alert_type": "manual_note", "severity": "low",
            "title": "Should fail", "description": "test",
        },
        headers=headers,
    )
    assert response.status_code == 403


def test_manual_alert_is_never_touched_by_auto_resolve_sweep(client, auth_headers):
    admin_headers = auth_headers("Administrator")
    created = client.post(
        "/alerts",
        json={
            "category": "economics", "alert_type": "manual_note", "severity": "low",
            "title": "Manual, never auto-resolved", "description": "test",
        },
        headers=admin_headers,
    ).json()
    assert created["dedup_key"].startswith("manual:")

    client.post("/alerts/run", headers=admin_headers)

    still_open = client.get(f"/alerts/{created['id']}", headers=admin_headers)
    assert still_open.json()["status"] == "new"


def test_add_alert_note_requires_a_note(client, auth_headers):
    headers = auth_headers("Administrator")
    created = client.post(
        "/alerts",
        json={
            "category": "maintenance", "alert_type": "manual_note", "severity": "low",
            "title": "Note test", "description": "test",
        },
        headers=headers,
    ).json()

    empty = client.post(f"/alerts/{created['id']}/notes", json={}, headers=headers)
    assert empty.status_code == 400

    with_note = client.post(f"/alerts/{created['id']}/notes", json={"note": "Following up."}, headers=headers)
    assert with_note.status_code == 200
    assert with_note.json()["notes"] == "Following up."


def test_alert_filtering_by_severity_category_and_status(client, auth_headers):
    headers = auth_headers("Administrator")
    client.post(
        "/alerts",
        json={
            "category": "equipment", "alert_type": "manual_note", "severity": "critical",
            "title": "Critical equipment thing", "description": "test",
        },
        headers=headers,
    )
    client.post(
        "/alerts",
        json={
            "category": "production", "alert_type": "manual_note", "severity": "low",
            "title": "Low production thing", "description": "test",
        },
        headers=headers,
    )

    response = client.get("/alerts", params={"severity": "critical", "category": "equipment"}, headers=headers)
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["severity"] == "critical"

    status_response = client.get("/alerts", params={"status": "new"}, headers=headers)
    assert status_response.json()["total"] == 2


def test_date_to_filter_includes_alerts_triggered_later_the_same_day(client, auth_headers):
    """Regression test for a real bug found during pilot-demo validation: date_to is a calendar
    date with no time-of-day, but triggered_at is a timestamp. An alert manually created "now"
    (this instant, today) must still be returned when filtering with date_to=today — a naive
    "triggered_at <= date_to" comparison would silently exclude it whenever today has already
    passed midnight, which broke the pilot's Alerts step and its Management Report section."""
    headers = auth_headers("Administrator")
    client.post(
        "/alerts",
        json={
            "category": "equipment", "alert_type": "manual_note", "severity": "critical",
            "title": "Same-day alert", "description": "test",
        },
        headers=headers,
    )

    response = client.get("/alerts", params={"date_from": str(TODAY), "date_to": str(TODAY)}, headers=headers)
    assert response.json()["total"] == 1


def test_alert_summary_shape(client, auth_headers):
    headers = auth_headers("Administrator")
    client.post(
        "/alerts",
        json={
            "category": "equipment", "alert_type": "manual_note", "severity": "high",
            "title": "Summary test", "description": "test",
        },
        headers=headers,
    )
    response = client.get("/alerts/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["by_severity"]["high"] >= 1
    assert body["by_status"]["new"] >= 1
    assert body["disclaimer_text"]


def test_get_alert_404(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.get("/alerts/999999", headers=headers)
    assert response.status_code == 404
