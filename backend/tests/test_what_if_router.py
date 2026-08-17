from datetime import date, timedelta

from app.models.economics import CommodityPrice, OperatingCost
from app.models.production import ProductionRecord
from app.services.rate_limit import reset_rate_limits


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def _seed_baseline(db_session, make_field_facility_well, well_id="WI-01", *, oil_bopd=100.0, gas_mscfd=50.0, days=10):
    field, facility, well = make_field_facility_well(well_id=well_id)
    today = date.today()
    start = today - timedelta(days=days - 1)
    for i in range(days):
        db_session.add(
            ProductionRecord(well_id=well.id, record_date=start + timedelta(days=i), oil_bopd=oil_bopd, gas_mscfd=gas_mscfd)
        )
    db_session.add(CommodityPrice(effective_date=_first_of_month(start), commodity="oil", price=70.0, currency="USD"))
    db_session.add(CommodityPrice(effective_date=_first_of_month(start), commodity="gas", price=3.0, currency="USD"))
    db_session.add(OperatingCost(cost_date=start, category="Production", amount=10000.0, currency="USD", facility_id=facility.id))
    db_session.commit()
    return field, facility, well, start, today


def _baseline_payload(field_id, date_from, date_to):
    return {"date_from": date_from.isoformat(), "date_to": date_to.isoformat(), "field_id": field_id}


# ----- Auth -----


def test_list_scenarios_requires_auth(client):
    response = client.get("/what-if/scenarios")
    assert response.status_code == 401


def test_preview_requires_auth(client):
    response = client.post("/what-if/preview", json={"baseline": {"date_from": "2026-01-01", "date_to": "2026-01-31"}, "assumptions": {}})
    assert response.status_code == 401


def test_viewer_can_preview_but_cannot_create(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    viewer_headers = auth_headers("Viewer")

    preview = client.post(
        "/what-if/preview",
        json={"baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=viewer_headers,
    )
    assert preview.status_code == 200

    create = client.post(
        "/what-if/scenarios",
        json={"name": "x", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=viewer_headers,
    )
    assert create.status_code == 403


# ----- Baseline resolution -----


def test_preview_baseline_matches_seeded_production(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well, oil_bopd=100.0, gas_mscfd=50.0, days=10)
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/preview",
        json={"baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=headers,
    )
    assert response.status_code == 200
    baseline = response.json()["results"]["baseline"]
    assert baseline["oil_bbl"] == 1000.0
    assert baseline["gas_mscf"] == 500.0
    assert baseline["data_sufficient"] is True


def test_preview_insufficient_data_never_fabricates_baseline(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well = make_field_facility_well(well_id="WI-EMPTY")
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/preview",
        json={
            "baseline": {"date_from": "2020-01-01", "date_to": "2020-01-31", "field_id": field.id},
            "assumptions": {},
        },
        headers=headers,
    )
    assert response.status_code == 200
    baseline = response.json()["results"]["baseline"]
    assert baseline["data_sufficient"] is False
    assert baseline["missing_data_note"]


def test_preview_no_assumptions_matches_baseline_revenue_when_price_changes_mid_period(
    client, db_session, auth_headers, make_field_facility_well
):
    """Regression test for a real bug found during pilot-demo validation: baseline revenue is
    priced day-by-day against the real commodity-price history, so a commodity-price change
    partway through the queried period previously made even a zero-assumption ("nothing
    changed") scenario report a different revenue/margin than its own baseline."""
    field, facility, well = make_field_facility_well(well_id="WI-PRICE-CHANGE")
    start = date(2026, 1, 1)
    mid = date(2026, 1, 16)
    end = date(2026, 1, 31)
    for i in range(31):
        record_date = start + timedelta(days=i)
        db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=100.0, gas_mscfd=0.0))
    # Oil price is $70 for the first half of the period, then drops to $60 for the second half.
    db_session.add(CommodityPrice(effective_date=start, commodity="oil", price=70.0, currency="USD"))
    db_session.add(CommodityPrice(effective_date=mid, commodity="oil", price=60.0, currency="USD"))
    db_session.commit()
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/preview",
        json={"baseline": _baseline_payload(field.id, start, end), "assumptions": {}},
        headers=headers,
    )
    assert response.status_code == 200
    results = response.json()["results"]
    baseline_revenue = {r["currency"]: r["amount"] for r in results["baseline"]["revenue"]}
    scenario_revenue = {r["currency"]: r["amount"] for r in results["scenario"]["revenue"]}
    assert scenario_revenue == baseline_revenue
    baseline_margin = {r["currency"]: r["amount"] for r in results["baseline"]["margin"]}
    scenario_margin = {r["currency"]: r["amount"] for r in results["scenario"]["margin"]}
    assert scenario_margin == baseline_margin


def test_preview_unknown_field_returns_404(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/what-if/preview",
        json={"baseline": {"date_from": "2026-01-01", "date_to": "2026-01-31", "field_id": 999999}, "assumptions": {}},
        headers=headers,
    )
    assert response.status_code == 404


# ----- Guardrails via the API -----


def test_create_scenario_hard_invalid_assumption_returns_422(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/scenarios",
        json={
            "name": "Impossible",
            "baseline": _baseline_payload(field.id, start, today),
            "assumptions": {"production_change_pct": -150},
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["severity"] == "error"


def test_create_scenario_soft_warn_still_computes(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/scenarios",
        json={
            "name": "Unusual but valid",
            "baseline": _baseline_payload(field.id, start, today),
            "assumptions": {"production_change_pct": -80},
        },
        headers=headers,
    )
    assert response.status_code == 201
    flags = response.json()["results"]["guardrail_flags"]
    assert any(f["severity"] == "warning" for f in flags)


# ----- Currency mismatch never blended (this module's own version of the load-bearing test) -----


def test_scenario_margin_never_blended_across_mismatched_currencies(client, db_session, auth_headers, make_field_facility_well):
    field, facility, well = make_field_facility_well(well_id="WI-MISMATCH")
    today = date.today()
    record_date = today.replace(day=min(today.day, 15)) if today.day >= 15 else today

    db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(CommodityPrice(effective_date=_first_of_month(record_date), commodity="oil", price=70.0, currency="USD"))
    db_session.add(
        OperatingCost(cost_date=record_date, category="Energy", amount=5_000_000.0, currency="NGN", facility_id=facility.id)
    )
    db_session.commit()
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/preview",
        json={
            "baseline": {"date_from": record_date.isoformat(), "date_to": record_date.isoformat(), "field_id": field.id},
            "assumptions": {"production_change_pct": 10},
        },
        headers=headers,
    )
    assert response.status_code == 200
    scenario = response.json()["results"]["scenario"]
    assert scenario["margin"] == []
    assert scenario["margin_currency_mismatch"] is True
    assert scenario["operating_cost"] == [{"currency": "NGN", "amount": 5_000_000.0}]


# ----- CRUD + reproducibility -----


def test_create_get_update_delete_scenario(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    create = client.post(
        "/what-if/scenarios",
        json={
            "name": "Downtime -20%",
            "description": "test",
            "baseline": _baseline_payload(field.id, start, today),
            "assumptions": {"downtime_change_pct": -20},
        },
        headers=headers,
    )
    assert create.status_code == 201
    scenario_id = create.json()["id"]
    assert create.json()["calculation_version"]
    stored_results = create.json()["results"]

    get_response = client.get(f"/what-if/scenarios/{scenario_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["results"] == stored_results  # GET never recomputes

    update = client.put(f"/what-if/scenarios/{scenario_id}", json={"name": "Renamed"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["name"] == "Renamed"

    delete = client.delete(f"/what-if/scenarios/{scenario_id}", headers=headers)
    assert delete.status_code == 204
    assert client.get(f"/what-if/scenarios/{scenario_id}", headers=headers).status_code == 404


def test_get_scenario_404(client, auth_headers):
    headers = auth_headers("Administrator")
    assert client.get("/what-if/scenarios/999999", headers=headers).status_code == 404


def test_viewer_cannot_delete_scenario(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    admin_headers = auth_headers("Administrator")
    create = client.post(
        "/what-if/scenarios",
        json={"name": "x", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=admin_headers,
    )
    scenario_id = create.json()["id"]

    viewer_headers = auth_headers("Viewer")
    response = client.delete(f"/what-if/scenarios/{scenario_id}", headers=viewer_headers)
    assert response.status_code == 403


def test_rerun_reflects_new_data_get_does_not(client, db_session, auth_headers, make_field_facility_well):
    """Reproducibility: a plain GET always returns the frozen snapshot; only /rerun recomputes
    against current data. This is the crux of the frozen-snapshot design decision."""
    field, facility, well, start, today = _seed_baseline(db_session, make_field_facility_well, oil_bopd=100.0, days=10)
    headers = auth_headers("Administrator")

    create = client.post(
        "/what-if/scenarios",
        json={"name": "Reproducibility check", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=headers,
    )
    scenario_id = create.json()["id"]
    original_oil_bbl = create.json()["results"]["baseline"]["oil_bbl"]

    # Change existing production data for the same period/scope after the scenario was saved.
    existing = (
        db_session.query(ProductionRecord)
        .filter(ProductionRecord.well_id == well.id, ProductionRecord.record_date == start)
        .one()
    )
    existing.oil_bopd = 99999.0
    db_session.commit()

    unchanged = client.get(f"/what-if/scenarios/{scenario_id}", headers=headers)
    assert unchanged.json()["results"]["baseline"]["oil_bbl"] == original_oil_bbl

    rerun = client.post(f"/what-if/scenarios/{scenario_id}/rerun", headers=headers)
    assert rerun.status_code == 200
    assert rerun.json()["results"]["baseline"]["oil_bbl"] != original_oil_bbl


# ----- Sensitivity -----


def test_sensitivity_sweep_returns_a_point_per_value(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/sensitivity",
        json={
            "baseline": _baseline_payload(field.id, start, today),
            "base_assumptions": {},
            "variable": "downtime_change_pct",
            "values": [0, -10, -20, -30, -40, -50],
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert len(response.json()["points"]) == 6


def test_sensitivity_unknown_variable_returns_422(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    response = client.post(
        "/what-if/sensitivity",
        json={
            "baseline": _baseline_payload(field.id, start, today),
            "base_assumptions": {},
            "variable": "not_a_real_variable",
            "values": [0, 1],
        },
        headers=headers,
    )
    assert response.status_code == 422


# ----- Compare -----


def test_compare_requires_at_least_two_scenarios(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    create = client.post(
        "/what-if/scenarios",
        json={"name": "solo", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=headers,
    )
    scenario_id = create.json()["id"]

    response = client.post("/what-if/compare", json={"scenario_ids": [scenario_id]}, headers=headers)
    assert response.status_code == 422


def test_compare_two_scenarios_uses_stored_results(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")

    ids = []
    for pct in (-10, -30):
        create = client.post(
            "/what-if/scenarios",
            json={
                "name": f"downtime {pct}",
                "baseline": _baseline_payload(field.id, start, today),
                "assumptions": {"downtime_change_pct": pct},
            },
            headers=headers,
        )
        ids.append(create.json()["id"])

    response = client.post("/what-if/compare", json={"scenario_ids": ids}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body["scenarios"]) == 2
    assert body["ai_narrative"] is None


def test_compare_missing_scenario_returns_404(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    create = client.post(
        "/what-if/scenarios",
        json={"name": "solo", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=headers,
    )
    scenario_id = create.json()["id"]

    response = client.post("/what-if/compare", json={"scenario_ids": [scenario_id, 999999]}, headers=headers)
    assert response.status_code == 404


# ----- AI interpretation (mocked provider, never a real external call) -----


def test_interpret_scenario_uses_mocked_provider(client, db_session, auth_headers, make_field_facility_well, mock_ai_provider):
    reset_rate_limits()
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    create = client.post(
        "/what-if/scenarios",
        json={"name": "interpret me", "baseline": _baseline_payload(field.id, start, today), "assumptions": {"downtime_change_pct": -20}},
        headers=headers,
    )
    scenario_id = create.json()["id"]

    response = client.post(f"/what-if/scenarios/{scenario_id}/interpret", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["interpretation"] == "Fake AI interpretation."
    assert body["provider"] == "fake"
    assert len(mock_ai_provider.calls) == 1


def test_viewer_cannot_interpret_scenario(client, db_session, auth_headers, make_field_facility_well, mock_ai_provider):
    reset_rate_limits()
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    admin_headers = auth_headers("Administrator")
    create = client.post(
        "/what-if/scenarios",
        json={"name": "x", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=admin_headers,
    )
    scenario_id = create.json()["id"]

    viewer_headers = auth_headers("Viewer")
    response = client.post(f"/what-if/scenarios/{scenario_id}/interpret", headers=viewer_headers)
    assert response.status_code == 403


# ----- List filtering -----


def test_list_scenarios_search_by_name(client, db_session, auth_headers, make_field_facility_well):
    field, _facility, _well, start, today = _seed_baseline(db_session, make_field_facility_well)
    headers = auth_headers("Administrator")
    client.post(
        "/what-if/scenarios",
        json={"name": "Findable Scenario", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=headers,
    )
    client.post(
        "/what-if/scenarios",
        json={"name": "Other", "baseline": _baseline_payload(field.id, start, today), "assumptions": {}},
        headers=headers,
    )

    response = client.get("/what-if/scenarios", params={"search": "Findable"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Findable Scenario"
