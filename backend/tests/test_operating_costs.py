def test_list_operating_costs_requires_auth(client):
    response = client.get("/operating-costs")
    assert response.status_code == 401


def test_create_operating_cost_requires_valid_field(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": 5000.0, "field_id": 9999},
        headers=headers,
    )
    assert response.status_code == 404


def test_create_operating_cost_requires_valid_equipment(client, auth_headers, make_equipment):
    headers = auth_headers("Administrator")
    response = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Equipment", "amount": 1000.0, "equipment_id": 9999},
        headers=headers,
    )
    assert response.status_code == 404


def test_create_operating_cost_rejects_negative_amount(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": -100.0},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_operating_cost_rejects_invalid_currency(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": 1000.0, "currency": "EUR"},
        headers=headers,
    )
    assert response.status_code == 422


def test_create_operating_cost_accepts_ngn(client, auth_headers, make_field_facility_well):
    headers = auth_headers("Administrator")
    field, facility, _well = make_field_facility_well(well_id="OC-1")
    response = client.post(
        "/operating-costs",
        json={
            "cost_date": "2026-01-15",
            "category": "Labour",
            "amount": 25000000.0,
            "currency": "NGN",
            "facility_id": facility.id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["currency"] == "NGN"
    assert body["facility_name"] == facility.name
    assert body["field_name"] == field.name


def test_create_operating_cost_as_production_engineer_forbidden(client, auth_headers):
    headers = auth_headers("Production Engineer")
    response = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": 1000.0},
        headers=headers,
    )
    assert response.status_code == 403


def test_create_operating_cost_as_viewer_forbidden(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": 1000.0},
        headers=headers,
    )
    assert response.status_code == 403


def test_create_operating_cost_as_management_succeeds(client, auth_headers):
    headers = auth_headers("Management")
    response = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": 1000.0},
        headers=headers,
    )
    assert response.status_code == 201


def test_get_operating_cost_404(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.get("/operating-costs/9999", headers=headers)
    assert response.status_code == 404


def test_update_operating_cost(client, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": 1000.0},
        headers=headers,
    )
    cost_id = create.json()["id"]

    update = client.put(f"/operating-costs/{cost_id}", json={"amount": 2500.0}, headers=headers)
    assert update.status_code == 200
    assert update.json()["amount"] == 2500.0


def test_delete_operating_cost(client, auth_headers):
    headers = auth_headers("Administrator")
    create = client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Other", "amount": 500.0},
        headers=headers,
    )
    cost_id = create.json()["id"]

    response = client.delete(f"/operating-costs/{cost_id}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/operating-costs/{cost_id}", headers=headers).status_code == 404


def test_list_operating_costs_filters_by_category_and_currency(client, auth_headers):
    headers = auth_headers("Administrator")
    client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Energy", "amount": 1000.0, "currency": "USD"},
        headers=headers,
    )
    client.post(
        "/operating-costs",
        json={"cost_date": "2026-01-15", "category": "Labour", "amount": 5000000.0, "currency": "NGN"},
        headers=headers,
    )

    by_category = client.get("/operating-costs", params={"category": "Energy"}, headers=headers)
    assert all(item["category"] == "Energy" for item in by_category.json()["items"])

    by_currency = client.get("/operating-costs", params={"currency": "NGN"}, headers=headers)
    assert all(item["currency"] == "NGN" for item in by_currency.json()["items"])
    assert by_currency.json()["total"] == 1
