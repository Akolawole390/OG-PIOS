from datetime import date, timedelta

from app.models.economics import CommodityPrice, OperatingCost
from app.models.production import ProductionRecord
from app.services.rate_limit import reset_rate_limits


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _seed_baseline(db_session, make_field_facility_well, well_id="RP-01", *, oil_bopd=100.0, gas_mscfd=50.0, days=10):
    field, facility, well = make_field_facility_well(well_id=well_id)
    today = date.today()
    start = today - timedelta(days=days - 1)
    for i in range(days):
        db_session.add(
            ProductionRecord(well_id=well.id, record_date=start + timedelta(days=i), oil_bopd=oil_bopd, gas_mscfd=gas_mscfd)
        )
    db_session.add(CommodityPrice(effective_date=_first_of_month(start), commodity="oil", price=70.0, currency="USD"))
    db_session.add(CommodityPrice(effective_date=_first_of_month(start), commodity="gas", price=3.0, currency="USD"))
    db_session.add(OperatingCost(cost_date=start, category="Production", amount=5000.0, currency="USD", facility_id=facility.id))
    db_session.commit()
    return field, facility, well, start, today


def _filters_payload(field_id, date_from, date_to):
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "field_id": field_id}


# ----- Auth -----


def test_list_reports_requires_auth(client):
    response = client.get("/reports")
    assert response.status_code == 401


def test_preview_requires_auth(client):
    response = client.post("/reports/preview", json={"report_type": "daily_operations", "filters": {}})
    assert response.status_code == 401


def test_viewer_can_preview_but_cannot_create(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    viewer_headers = auth_headers("Viewer")

    preview = client.post(
        "/reports/preview",
        json={"report_type": "daily_operations", "filters": _filters_payload(field.id, start, today)},
        headers=viewer_headers,
    )
    assert preview.status_code == 200

    create = client.post(
        "/reports",
        json={"report_type": "daily_operations", "name": "x", "filters": _filters_payload(field.id, start, today)},
        headers=viewer_headers,
    )
    assert create.status_code == 403


# ----- Report types -----


def test_get_report_types_lists_all_four(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.get("/reports/types", headers=headers)
    assert response.status_code == 200
    ids = {t["id"] for t in response.json()["types"]}
    assert ids == {"daily_operations", "weekly_production", "monthly_management", "what_if_scenario"}


# ----- Preview -----


def test_preview_unknown_field_returns_404(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/reports/preview",
        json={"report_type": "daily_operations", "filters": {"field_id": 999999}},
        headers=headers,
    )
    assert response.status_code == 404


def test_preview_invalid_date_range_returns_422(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/reports/preview",
        json={"report_type": "daily_operations", "filters": {"date_from": "2026-06-10", "date_to": "2026-06-01"}},
        headers=headers,
    )
    assert response.status_code == 422


# ----- CRUD + reproducibility -----


def test_create_get_update_delete_report(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    create = client.post(
        "/reports",
        json={
            "report_type": "daily_operations",
            "name": "Daily Ops - test",
            "description": "test report",
            "filters": _filters_payload(field.id, start, today),
        },
        headers=headers,
    )
    assert create.status_code == 201, create.text
    report_id = create.json()["id"]
    assert create.json()["calculation_version"]
    stored_results = create.json()["results"]

    get_response = client.get(f"/reports/{report_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["results"] == stored_results  # GET never recomputes

    update = client.put(f"/reports/{report_id}", json={"name": "Renamed Report"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["name"] == "Renamed Report"
    assert update.json()["results"] == stored_results  # rename never recomputes

    delete = client.delete(f"/reports/{report_id}", headers=headers)
    assert delete.status_code == 204
    assert client.get(f"/reports/{report_id}", headers=headers).status_code == 404


def test_get_report_404(client, auth_headers):
    headers = auth_headers("Administrator")
    assert client.get("/reports/999999", headers=headers).status_code == 404


def test_viewer_cannot_delete_report(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    admin_headers = auth_headers("Administrator")
    create = client.post(
        "/reports",
        json={"report_type": "daily_operations", "name": "x", "filters": _filters_payload(field.id, start, today)},
        headers=admin_headers,
    )
    report_id = create.json()["id"]

    viewer_headers = auth_headers("Viewer")
    response = client.delete(f"/reports/{report_id}", headers=viewer_headers)
    assert response.status_code == 403


def test_regenerate_reflects_new_data_get_does_not(client, db_session, auth_headers, make_field_facility_well):
    field, facility, well, start, today = _seed_baseline(db_session, make_field_facility_well, oil_bopd=100.0, days=1)
    headers = auth_headers("Administrator")

    create = client.post(
        "/reports",
        json={"report_type": "daily_operations", "name": "Reproducibility check", "filters": _filters_payload(field.id, start, today)},
        headers=headers,
    )
    report_id = create.json()["id"]
    original_oil_bbl = create.json()["results"]["sections"]["production"]["kpis"]["total_oil_bbl"]

    existing = db_session.query(ProductionRecord).filter(ProductionRecord.well_id == well.id, ProductionRecord.record_date == start).one()
    existing.oil_bopd = 99999.0
    db_session.commit()

    unchanged = client.get(f"/reports/{report_id}", headers=headers)
    assert unchanged.json()["results"]["sections"]["production"]["kpis"]["total_oil_bbl"] == original_oil_bbl

    regenerated = client.post(f"/reports/{report_id}/regenerate", headers=headers)
    assert regenerated.status_code == 200
    assert regenerated.json()["results"]["sections"]["production"]["kpis"]["total_oil_bbl"] != original_oil_bbl


# ----- Export -----


def test_export_csv(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    create = client.post(
        "/reports",
        json={"report_type": "daily_operations", "name": "Export CSV test", "filters": _filters_payload(field.id, start, today)},
        headers=headers,
    )
    report_id = create.json()["id"]

    response = client.get(f"/reports/{report_id}/export", params={"format": "csv"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert len(response.content) > 50
    assert b"Export CSV test" in response.content


def test_export_pdf(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    create = client.post(
        "/reports",
        json={"report_type": "daily_operations", "name": "Export PDF test", "filters": _filters_payload(field.id, start, today)},
        headers=headers,
    )
    report_id = create.json()["id"]

    response = client.get(f"/reports/{report_id}/export", params={"format": "pdf"}, headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_export_ungenerated_report_returns_400(client, db_session, auth_headers, make_field_facility_well):
    # A report is always generated at creation time in this v1 (synchronous), but the export
    # endpoint still guards against a null `results` defensively.
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    create = client.post(
        "/reports",
        json={"report_type": "daily_operations", "name": "x", "filters": _filters_payload(field.id, start, today)},
        headers=headers,
    )
    report_id = create.json()["id"]

    from app.models.reporting import Report
    record = db_session.get(Report, report_id)
    record.results = None
    db_session.commit()

    response = client.get(f"/reports/{report_id}/export", params={"format": "csv"}, headers=headers)
    assert response.status_code == 400


# ----- What-If Scenario Report -----


def test_what_if_scenario_report_embeds_saved_scenario(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    scenario = client.post(
        "/what-if/scenarios",
        json={
            "name": "Report smoke scenario",
            "baseline": {"date_from": start.isoformat(), "date_to": today.isoformat(), "field_id": field.id},
            "assumptions": {"downtime_change_pct": -10},
        },
        headers=headers,
    )
    assert scenario.status_code == 201, scenario.text
    scenario_id = scenario.json()["id"]

    preview = client.post(
        "/reports/preview",
        json={"report_type": "what_if_scenario", "filters": {"scenario_id": scenario_id}},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    scenario_section = preview.json()["results"]["sections"]["scenario"]
    assert scenario_section["scenario_id"] == scenario_id
    assert scenario_section["results"] is not None
    assert scenario_section["label"] == "Scenario Estimate"


def test_what_if_scenario_report_unknown_scenario_returns_404(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/reports/preview",
        json={"report_type": "what_if_scenario", "filters": {"scenario_id": 999999}},
        headers=headers,
    )
    assert response.status_code == 404


# ----- AI narrative (mocked provider, never a real external call) -----


def test_narrative_uses_mocked_provider(client, db_session, auth_headers, make_field_facility_well, mock_ai_provider):
    reset_rate_limits()
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    response = client.post(
        "/reports/preview",
        json={
            "report_type": "monthly_management",
            "filters": _filters_payload(field.id, start, today),
            "narrative": True,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["results"]["ai_narrative"] == "Fake AI interpretation."
    assert len(mock_ai_provider.calls) == 1


# ----- List filtering / pagination -----


def test_list_reports_search_and_type_filter(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post(
        "/reports",
        json={"report_type": "daily_operations", "name": "Findable Report", "filters": _filters_payload(field.id, start, today)},
        headers=headers,
    )
    client.post(
        "/reports",
        json={"report_type": "weekly_production", "name": "Other Report", "filters": {"date_from": start.isoformat(), "date_to": today.isoformat()}},
        headers=headers,
    )

    response = client.get("/reports", params={"search": "Findable"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Findable Report"

    response = client.get("/reports", params={"report_type": "weekly_production"}, headers=headers)
    assert response.status_code == 200
    assert all(item["report_type"] == "weekly_production" for item in response.json()["items"])
