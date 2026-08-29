from datetime import date, timedelta

from app.models.production import ProductionRecord, ProductionTarget
from app.services.rate_limit import reset_rate_limits

TODAY = date.today()


def _seed_below_target_well(db_session, make_field_facility_well, well_id="RT-01-001"):
    _field, _facility, well = make_field_facility_well(well_id=well_id)
    for i in range(29):
        db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY - timedelta(days=29 - i), oil_bopd=100.0, gas_mscfd=50.0))
    db_session.add(ProductionRecord(well_id=well.id, record_date=TODAY, oil_bopd=50.0, gas_mscfd=50.0))
    db_session.add(ProductionTarget(well_id=well.id, effective_date=TODAY - timedelta(days=60), oil_target_bopd=100.0))
    db_session.commit()
    return well


def test_list_insights_requires_auth(client):
    response = client.get("/ai-insights")
    assert response.status_code == 401


def test_run_insight_engine_requires_administrator(client, auth_headers):
    headers = auth_headers("Analyst")
    response = client.post("/ai-insights/run", headers=headers)
    assert response.status_code == 403


def test_run_and_list_insights(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    run_response = client.post("/ai-insights/run", headers=headers)
    assert run_response.status_code == 200
    body = run_response.json()
    assert body["created"] >= 1
    assert "disclaimer_text" in body

    list_response = client.get("/ai-insights", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1


def test_date_to_filter_includes_insights_generated_later_the_same_day(
    client, db_session, auth_headers, make_field_facility_well
):
    """Regression test for a real bug found during pilot-demo validation: date_to is a calendar
    date with no time-of-day, but generated_at is a timestamp. An insight generated "now" (this
    instant, today) must still be returned when filtering with date_to=today — a naive
    "generated_at <= date_to" comparison would silently exclude it once today has passed
    midnight, which broke the pilot's AI Insights step and its Management Report section."""
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=headers)

    response = client.get("/ai-insights", params={"date_from": str(TODAY), "date_to": str(TODAY)}, headers=headers)
    assert response.json()["total"] >= 1


def test_run_twice_dedups_instead_of_duplicating(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    first = client.post("/ai-insights/run", headers=headers).json()
    second = client.post("/ai-insights/run", headers=headers).json()

    assert second["created"] == 0
    assert second["updated"] == first["created"]


def test_insight_detail_includes_structured_evidence(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=headers)

    list_response = client.get("/ai-insights", headers=headers, params={"insight_type": "production_below_target"})
    insight_id = list_response.json()["items"][0]["id"]

    detail = client.get(f"/ai-insights/{insight_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["evidence"]) >= 1
    evidence_types = {e["evidence_type"] for e in body["evidence"]}
    assert evidence_types.issubset({"observed_fact", "calculated_metric", "correlation", "possible_contributor"})
    assert body["confidence_level"] in ("high", "medium", "low")
    assert body["status"] == "new"
    assert body["well_code"] == "RT-01-001"


def test_get_insight_404(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.get("/ai-insights/999999", headers=headers)
    assert response.status_code == 404


def test_update_insight_status(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=headers)
    insight_id = client.get("/ai-insights", headers=headers).json()["items"][0]["id"]

    response = client.put(f"/ai-insights/{insight_id}/status", json={"status": "reviewed"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "reviewed"


def test_viewer_cannot_update_insight_status(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    admin_headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=admin_headers)
    insight_id = client.get("/ai-insights", headers=admin_headers).json()["items"][0]["id"]

    viewer_headers = auth_headers("Viewer")
    response = client.put(f"/ai-insights/{insight_id}/status", json={"status": "dismissed"}, headers=viewer_headers)
    assert response.status_code == 403


def test_submit_insight_feedback(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=headers)
    insight_id = client.get("/ai-insights", headers=headers).json()["items"][0]["id"]

    response = client.post(
        f"/ai-insights/{insight_id}/feedback", json={"feedback": "useful", "notes": "Confirmed in the field."}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["feedback"]) == 1
    assert body["feedback"][0]["feedback"] == "useful"


def test_viewer_cannot_submit_feedback(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    admin_headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=admin_headers)
    insight_id = client.get("/ai-insights", headers=admin_headers).json()["items"][0]["id"]

    viewer_headers = auth_headers("Viewer")
    response = client.post(f"/ai-insights/{insight_id}/feedback", json={"feedback": "useful"}, headers=viewer_headers)
    assert response.status_code == 403


def test_interpret_insight_uses_mocked_provider(client, db_session, auth_headers, make_field_facility_well, mock_ai_provider):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=headers)
    insight_id = client.get("/ai-insights", headers=headers).json()["items"][0]["id"]

    response = client.post(f"/ai-insights/{insight_id}/interpret", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["interpretation"] == "Fake AI interpretation."
    assert body["provider"] == "fake"
    assert len(mock_ai_provider.calls) == 1

    detail = client.get(f"/ai-insights/{insight_id}", headers=headers).json()
    assert detail["ai_interpretation"] == "Fake AI interpretation."
    assert detail["ai_provider"] == "fake"


def test_assistant_endpoint_deterministic_answer(client, db_session, auth_headers, make_field_facility_well):
    reset_rate_limits()
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    response = client.post("/ai-insights/assistant", json={"question": "Which equipment requires attention?"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["answered_by"] == "deterministic"
    assert "disclaimer_text" in body


def test_assistant_rejects_empty_question(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Administrator")
    response = client.post("/ai-insights/assistant", json={"question": "   "}, headers=headers)
    assert response.status_code == 400


def test_assistant_rate_limit_returns_429_after_limit(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Administrator")
    statuses = []
    for _ in range(12):
        r = client.post("/ai-insights/assistant", json={"question": "test"}, headers=headers)
        statuses.append(r.status_code)
    assert statuses.count(429) >= 1
    assert statuses[:10] == [200] * 10


def test_viewer_cannot_use_assistant(client, auth_headers):
    reset_rate_limits()
    headers = auth_headers("Viewer")
    response = client.post("/ai-insights/assistant", json={"question": "test"}, headers=headers)
    assert response.status_code == 403


def test_daily_brief_shape(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    response = client.get("/ai-insights/daily-brief", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["sections"]) == 7
    assert body["narrative"] is None
    assert "disclaimer_text" in body


def test_daily_brief_with_narrative_uses_mocked_provider(client, db_session, auth_headers, make_field_facility_well, mock_ai_provider):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    response = client.get("/ai-insights/daily-brief", params={"narrative": "true"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["narrative"] == "Fake AI interpretation."


def test_daily_brief_export_returns_a_pdf(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    response = client.get("/ai-insights/daily-brief/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_daily_brief_export_requires_auth(client):
    response = client.get("/ai-insights/daily-brief/export")
    assert response.status_code == 401


def test_management_summary_shape(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    response = client.get("/ai-insights/management-summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["sections"]) == 5


def test_insight_summary_endpoint(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=headers)

    response = client.get("/ai-insights/summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert "by_severity" in body
    assert "by_category" in body


def test_filter_insights_by_category_and_severity(client, db_session, auth_headers, make_field_facility_well):
    _seed_below_target_well(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post("/ai-insights/run", headers=headers)

    response = client.get("/ai-insights", headers=headers, params={"category": "production", "severity": "critical"})
    assert response.status_code == 200
    for item in response.json()["items"]:
        assert item["category"] == "production"
        assert item["severity"] == "critical"
