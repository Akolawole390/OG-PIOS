from datetime import date, timedelta

from app.models.economics import CommodityPrice, OperatingCost
from app.models.production import ProductionRecord


def _first_of_month(d: date) -> date:
    return d.replace(day=1)


def test_dashboard_requires_auth(client):
    response = client.get("/cost-revenue/dashboard")
    assert response.status_code == 401


def test_dashboard_currency_mismatch_never_blended_into_a_fabricated_margin(
    client, db_session, auth_headers, make_field_facility_well
):
    """The single most important test in this module: revenue resolves in USD (from
    CommodityPrice), operating cost is entered in NGN — the dashboard must show both totals
    separately and report margin as unavailable (empty list + currency_mismatch flag), never
    a blended/fabricated number."""
    headers = auth_headers("Administrator")
    _field, facility, well = make_field_facility_well(well_id="CR-MISMATCH")
    today = date.today()
    record_date = today.replace(day=min(today.day, 15)) if today.day >= 15 else today

    db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(
        CommodityPrice(effective_date=_first_of_month(record_date), commodity="oil", price=70.0, currency="USD")
    )
    db_session.add(
        OperatingCost(
            cost_date=record_date, category="Energy", amount=5_000_000.0, currency="NGN", facility_id=facility.id
        )
    )
    db_session.commit()

    response = client.get("/cost-revenue/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["revenue"]["total"] == [{"currency": "USD", "amount": 35000.0}]
    assert body["costs"]["operating"] == [{"currency": "NGN", "amount": 5000000.0}]
    assert body["economics"]["margin"] == []
    assert body["economics"]["currency_mismatch"] is True
    assert body["disclaimer_text"]


def test_dashboard_partial_currency_mismatch_still_flagged_when_one_currency_matches(
    client, db_session, auth_headers, make_field_facility_well
):
    """A scope can have costs split across two currencies (e.g. NGN energy cost alongside a
    USD labour cost) while revenue only resolves in USD. The USD-matching cost may still net
    against USD revenue, but the NGN cost must never be silently dropped without a flag —
    `currency_mismatch` must be True even though `margin` is non-empty, so a consumer never
    mistakes the partial margin for the full picture."""
    headers = auth_headers("Administrator")
    _field, facility, well = make_field_facility_well(well_id="CR-PARTIAL")
    today = date.today()
    record_date = today.replace(day=min(today.day, 15)) if today.day >= 15 else today

    db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(
        CommodityPrice(effective_date=_first_of_month(record_date), commodity="oil", price=70.0, currency="USD")
    )
    db_session.add(
        OperatingCost(cost_date=record_date, category="Energy", amount=2_000_000.0, currency="NGN", facility_id=facility.id)
    )
    db_session.add(
        OperatingCost(cost_date=record_date, category="Labour", amount=4000.0, currency="USD", facility_id=facility.id)
    )
    db_session.commit()

    response = client.get("/cost-revenue/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["revenue"]["total"] == [{"currency": "USD", "amount": 35000.0}]
    assert {"currency": "NGN", "amount": 2000000.0} in body["costs"]["operating"]
    assert {"currency": "USD", "amount": 4000.0} in body["costs"]["operating"]
    assert body["economics"]["margin"] == [{"currency": "USD", "amount": 31000.0}]
    assert body["economics"]["currency_mismatch"] is True


def test_dashboard_matched_currency_computes_real_margin(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _field, facility, well = make_field_facility_well(well_id="CR-MATCH")
    today = date.today()
    record_date = today.replace(day=min(today.day, 15)) if today.day >= 15 else today

    db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=500.0, gas_mscfd=0.0))
    db_session.add(
        CommodityPrice(effective_date=_first_of_month(record_date), commodity="oil", price=70.0, currency="USD")
    )
    db_session.add(
        OperatingCost(cost_date=record_date, category="Energy", amount=5000.0, currency="USD", facility_id=facility.id)
    )
    db_session.commit()

    response = client.get("/cost-revenue/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["revenue"]["total"] == [{"currency": "USD", "amount": 35000.0}]
    assert body["economics"]["margin"] == [{"currency": "USD", "amount": 30000.0}]
    assert body["economics"]["currency_mismatch"] is False
    assert body["economics"]["cost_per_bbl"] == [{"currency": "USD", "amount": 10.0}]
    assert body["economics"]["revenue_per_bbl"] == [{"currency": "USD", "amount": 70.0}]


def test_dashboard_with_no_production_data_returns_zeroed_shape(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/cost-revenue/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["production"]["oil_bbl"] == 0
    assert body["revenue"]["total"] == []
    assert body["economics"]["margin"] == []


def test_unit_economics_filterable_by_well(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _field, facility, well = make_field_facility_well(well_id="CR-UNIT")
    record_date = date.today()

    db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=200.0, gas_mscfd=0.0))
    db_session.add(
        CommodityPrice(effective_date=_first_of_month(record_date), commodity="oil", price=80.0, currency="USD")
    )
    db_session.commit()

    response = client.get(
        "/cost-revenue/unit-economics",
        params={"well_id": well.id, "date_from": record_date.isoformat(), "date_to": record_date.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["production"]["oil_bbl"] == 200.0
    assert body["revenue"]["oil"] == [{"currency": "USD", "amount": 16000.0}]


def test_economics_by_scope_field_rows_present(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/cost-revenue/economics-by-scope", params={"scope": "field"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "field"
    assert isinstance(body["rows"], list)


def test_economics_by_scope_field_row_flags_partial_currency_mismatch(
    client, db_session, auth_headers, make_field_facility_well
):
    headers = auth_headers("Viewer")
    field, facility, well = make_field_facility_well(well_id="CR-SCOPE-MISMATCH")
    today = date.today()
    record_date = today.replace(day=min(today.day, 15)) if today.day >= 15 else today

    db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=300.0, gas_mscfd=0.0))
    db_session.add(
        CommodityPrice(effective_date=_first_of_month(record_date), commodity="oil", price=70.0, currency="USD")
    )
    db_session.add(
        OperatingCost(cost_date=record_date, category="Energy", amount=1_000_000.0, currency="NGN", facility_id=facility.id)
    )
    db_session.commit()

    response = client.get("/cost-revenue/economics-by-scope", params={"scope": "field"}, headers=headers)
    assert response.status_code == 200
    rows_by_key = {row["key"]: row for row in response.json()["rows"]}
    row = rows_by_key[str(field.id)]
    assert row["currency_mismatch"] is True
    assert row["review_note"] is not None
    assert "currency" in row["review_note"].lower()


def test_economics_by_scope_well_without_production_gets_review_note(
    client, db_session, auth_headers, make_field_facility_well
):
    headers = auth_headers("Viewer")
    # A well with zero production records anywhere should surface a review note, never a
    # fabricated "uneconomic" classification.
    _field, _facility, well = make_field_facility_well(well_id="CR-NODATA")
    db_session.commit()

    response = client.get("/cost-revenue/economics-by-scope", params={"scope": "well"}, headers=headers)
    assert response.status_code == 200
    rows_by_key = {row["key"]: row for row in response.json()["rows"]}
    row = rows_by_key.get(str(well.id))
    assert row is not None
    assert row["review_note"] is not None
    assert "requires further economic review" in row["review_note"].lower()
    assert row["high_production"] is None


def test_revenue_trend_shape(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Viewer")
    _field, _facility, well = make_field_facility_well(well_id="CR-TREND")
    record_date = date.today()
    db_session.add(ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=100.0, gas_mscfd=0.0))
    db_session.add(
        CommodityPrice(effective_date=_first_of_month(record_date), commodity="oil", price=70.0, currency="USD")
    )
    db_session.commit()

    response = client.get("/cost-revenue/revenue-trend", params={"well_id": well.id}, headers=headers)
    assert response.status_code == 200
    months = [p["month"] for p in response.json()["points"]]
    assert record_date.strftime("%Y-%m") in months


def test_cost_trend_shape(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Viewer")
    _field, facility, _well = make_field_facility_well(well_id="CR-COSTTREND")
    cost_date = date.today()
    db_session.add(OperatingCost(cost_date=cost_date, category="Chemicals", amount=1234.0, currency="USD", facility_id=facility.id))
    db_session.commit()

    response = client.get("/cost-revenue/cost-trend", params={"facility_id": facility.id}, headers=headers)
    assert response.status_code == 200
    points = response.json()["points"]
    assert any(p["month"] == cost_date.strftime("%Y-%m") for p in points)


def test_margin_trend_shape(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/cost-revenue/margin-trend", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json()["points"], list)


def test_alerts_rapid_cost_increase_fires(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    field, facility, well = make_field_facility_well(well_id="CR-ALERT")
    today = date.today()
    this_month_date = today.replace(day=min(today.day, 20)) if today.day >= 20 else today
    prev_month_date = (this_month_date.replace(day=1) - timedelta(days=1)).replace(day=1)

    # Need at least one production record so `_latest_period` resolves to this month.
    db_session.add(ProductionRecord(well_id=well.id, record_date=this_month_date, oil_bopd=100.0, gas_mscfd=0.0))
    db_session.add(OperatingCost(cost_date=prev_month_date, category="Energy", amount=10000.0, currency="USD", facility_id=facility.id))
    db_session.add(OperatingCost(cost_date=this_month_date, category="Energy", amount=20000.0, currency="USD", facility_id=facility.id))
    db_session.commit()

    response = client.get("/cost-revenue/alerts", headers=headers)
    assert response.status_code == 200
    alerts = response.json()["alerts"]
    assert any(a["category"] == "rapid_cost_increase" and a["scope_label"] == field.name for a in alerts)
