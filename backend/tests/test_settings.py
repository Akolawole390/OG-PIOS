from app.models.settings import SystemSetting


def test_list_settings_any_authenticated_role(client, db_session, auth_headers):
    db_session.add(SystemSetting(key="boe_gas_factor_scf_per_bbl", value="6000", description="test"))
    db_session.commit()

    headers = auth_headers("Viewer")
    response = client.get("/settings", headers=headers)
    assert response.status_code == 200
    assert any(s["key"] == "boe_gas_factor_scf_per_bbl" for s in response.json())


def test_update_setting_requires_administrator(client, db_session, auth_headers):
    db_session.add(SystemSetting(key="boe_gas_factor_scf_per_bbl", value="6000"))
    db_session.commit()

    engineer_headers = auth_headers("Production Engineer")
    forbidden = client.put(
        "/settings/boe_gas_factor_scf_per_bbl", json={"value": "6500"}, headers=engineer_headers
    )
    assert forbidden.status_code == 403

    admin_headers = auth_headers("Administrator")
    allowed = client.put("/settings/boe_gas_factor_scf_per_bbl", json={"value": "6500"}, headers=admin_headers)
    assert allowed.status_code == 200
    assert allowed.json()["value"] == "6500"


def test_update_setting_rejects_non_numeric_value_for_known_key(client, db_session, auth_headers):
    db_session.add(SystemSetting(key="boe_gas_factor_scf_per_bbl", value="6000"))
    db_session.commit()

    headers = auth_headers("Administrator")
    response = client.put("/settings/boe_gas_factor_scf_per_bbl", json={"value": "not-a-number"}, headers=headers)
    assert response.status_code == 400


def test_update_setting_404_for_unknown_key(client, auth_headers):
    headers = auth_headers("Administrator")
    response = client.put("/settings/does-not-exist", json={"value": "1"}, headers=headers)
    assert response.status_code == 404
