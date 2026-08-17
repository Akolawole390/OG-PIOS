from datetime import date, datetime, timedelta, timezone

from app.models.economics import CommodityPrice
from app.models.equipment import DowntimeEvent, MaintenanceRecord
from app.models.production import ProductionRecord, ProductionTarget


def _seed_target_actual_prices(db_session, well, *, target_date, record_date, oil_target=500.0,
                                 gas_target=300.0, oil_actual=400.0, gas_actual=250.0,
                                 oil_price=70.0, gas_price=3.0):
    db_session.add(
        ProductionTarget(well_id=well.id, effective_date=target_date, oil_target_bopd=oil_target, gas_target_mscfd=gas_target)
    )
    db_session.add(
        ProductionRecord(well_id=well.id, record_date=record_date, oil_bopd=oil_actual, gas_mscfd=gas_actual)
    )
    db_session.add(CommodityPrice(effective_date=target_date, commodity="oil", price=oil_price, currency="USD"))
    db_session.add(CommodityPrice(effective_date=target_date, commodity="gas", price=gas_price, currency="USD"))
    db_session.commit()


def test_list_production_loss_requires_auth(client):
    response = client.get("/production-loss")
    assert response.status_code == 401


def test_create_production_loss_requires_valid_well(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": 9999},
        headers=headers,
    )
    assert response.status_code == 404


def test_create_production_loss_auto_computes_from_resolved_data(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-1")
    _seed_target_actual_prices(
        db_session, well, target_date=date(2026, 1, 1), record_date=date(2026, 1, 15)
    )

    response = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id, "category": "equipment_failure"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["estimated_bopd_lost"] == 100.0
    assert body["estimated_mscf_lost"] == 50.0
    assert body["estimated_revenue_impact"] == 100.0 * 70.0 + 50.0 * 3.0
    assert body["currency"] == "USD"
    assert body["oil_price_per_bbl"] == 70.0
    assert body["gas_price_per_mscf"] == 3.0
    assert body["disclaimer_text"]


def test_create_production_loss_with_no_resolvable_data_leaves_fields_null(
    client, auth_headers, make_field_facility_well
):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-2")

    response = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["estimated_bopd_lost"] is None
    assert body["estimated_mscf_lost"] is None
    assert body["estimated_revenue_impact"] is None
    assert body["currency"] is None


def test_create_production_loss_manual_override_respected(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-3")
    _seed_target_actual_prices(db_session, well, target_date=date(2026, 1, 1), record_date=date(2026, 1, 15))

    response = client.post(
        "/production-loss",
        json={
            "loss_date": "2026-01-15",
            "well_id": well.id,
            "estimated_bopd_lost": 9999.0,
            "estimated_revenue_impact": 123456.0,
            "currency": "NGN",
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["estimated_bopd_lost"] == 9999.0
    assert body["estimated_revenue_impact"] == 123456.0
    assert body["currency"] == "NGN"
    # gas wasn't manually overridden — still auto-computed.
    assert body["estimated_mscf_lost"] == 50.0


def test_create_production_loss_as_viewer_forbidden(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.post("/production-loss", json={"loss_date": "2026-01-15"}, headers=headers)
    assert response.status_code == 403


def test_create_production_loss_as_production_engineer_succeeds(client, auth_headers):
    headers = auth_headers("Production Engineer")
    response = client.post("/production-loss", json={"loss_date": "2026-01-15"}, headers=headers)
    assert response.status_code == 201


def test_create_production_loss_rejects_invalid_category(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "category": "not_a_category"},
        headers=headers,
    )
    assert response.status_code == 422


def test_get_production_loss_404(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/production-loss/9999", headers=headers)
    assert response.status_code == 404


def test_update_production_loss_recomputes_on_date_change(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-4")
    _seed_target_actual_prices(db_session, well, target_date=date(2026, 1, 1), record_date=date(2026, 1, 15))
    # A second day with a different actual, to prove recompute picks up the new date's data.
    db_session.add(ProductionRecord(well_id=well.id, record_date=date(2026, 1, 20), oil_bopd=350.0, gas_mscfd=200.0))
    db_session.commit()

    create = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id},
        headers=headers,
    )
    loss_id = create.json()["id"]
    assert create.json()["estimated_bopd_lost"] == 100.0

    update = client.put(f"/production-loss/{loss_id}", json={"loss_date": "2026-01-20"}, headers=headers)
    assert update.status_code == 200
    assert update.json()["estimated_bopd_lost"] == 150.0


def test_delete_production_loss_blocked_when_linked_to_downtime_event(
    client, db_session, auth_headers, make_field_facility_well
):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-5")
    now = datetime.now(timezone.utc)
    event = DowntimeEvent(start_time=now - timedelta(hours=5), end_time=now, well_id=well.id)
    db_session.add(event)
    db_session.commit()

    create = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id, "downtime_event_id": event.id},
        headers=headers,
    )
    loss_id = create.json()["id"]

    response = client.delete(f"/production-loss/{loss_id}", headers=headers)
    assert response.status_code == 400


def test_delete_production_loss_allowed_when_manual(client, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-6")

    create = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id},
        headers=headers,
    )
    loss_id = create.json()["id"]

    response = client.delete(f"/production-loss/{loss_id}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/production-loss/{loss_id}", headers=headers).status_code == 404


def test_downtime_hours_derived_from_linked_downtime_event(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-7")
    now = datetime.now(timezone.utc)
    event = DowntimeEvent(start_time=now - timedelta(hours=6), end_time=now, well_id=well.id)
    db_session.add(event)
    db_session.commit()

    response = client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id, "downtime_event_id": event.id},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["downtime_hours"] == 6.0


def test_downtime_hours_derived_from_linked_maintenance_record_when_no_event(
    client, db_session, auth_headers, make_field_facility_well, make_equipment
):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-8")
    equipment = make_equipment(equipment_tag="PL-EQ-1", well=well)
    record = MaintenanceRecord(
        maintenance_type="corrective", status="completed", downtime_hours=4.5, equipment_id=equipment.id
    )
    db_session.add(record)
    db_session.commit()

    response = client.post(
        "/production-loss",
        json={
            "loss_date": "2026-01-15",
            "well_id": well.id,
            "equipment_id": equipment.id,
            "maintenance_record_id": record.id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["downtime_hours"] == 4.5
    assert response.json()["work_order_number"] is None  # never assigned via direct DB insert here


def test_list_production_loss_filters_by_well_and_category(client, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well_a = make_field_facility_well(well_id="PL-9-A")
    _, _, well_b = make_field_facility_well(well_id="PL-9-B")
    client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well_a.id, "category": "weather"},
        headers=headers,
    )
    client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well_b.id, "category": "reservoir"},
        headers=headers,
    )

    by_well = client.get("/production-loss", params={"well_id": well_a.id}, headers=headers)
    assert by_well.json()["total"] == 1

    by_category = client.get("/production-loss", params={"category": "reservoir"}, headers=headers)
    assert all(item["category"] == "reservoir" for item in by_category.json()["items"])


def test_production_loss_dashboard_totals(client, db_session, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-10")
    _seed_target_actual_prices(db_session, well, target_date=date(2026, 1, 1), record_date=date(2026, 1, 15))

    client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id, "category": "equipment_failure", "downtime_hours": 8.0},
        headers=headers,
    )

    response = client.get("/production-loss/dashboard", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["event_count"] >= 1
    assert body["total_oil_bopd_lost"] >= 100.0
    assert body["total_revenue_impact"] >= 7150.0
    assert any(c["category"] == "equipment_failure" for c in body["by_category"])


def test_production_loss_by_scope_group_by_category(client, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-11")
    client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id, "category": "weather"},
        headers=headers,
    )

    response = client.get("/production-loss/by-scope", params={"group_by": "category"}, headers=headers)
    assert response.status_code == 200
    labels = [bar["label"] for bar in response.json()["bars"]]
    assert "weather" in labels


def test_production_loss_trend_groups_by_month(client, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    _, _, well = make_field_facility_well(well_id="PL-12")
    client.post(
        "/production-loss",
        json={"loss_date": "2026-01-15", "well_id": well.id},
        headers=headers,
    )

    response = client.get("/production-loss/trend", headers=headers)
    assert response.status_code == 200
    months = [p["month"] for p in response.json()["points"]]
    assert "2026-01" in months
