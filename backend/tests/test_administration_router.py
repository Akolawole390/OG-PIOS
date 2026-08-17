import pytest

NON_ADMIN_ROLES = (
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
    "Viewer",
)

ADMINISTRATION_ENDPOINTS = (
    "/administration/dashboard",
    "/administration/roles",
    "/administration/permissions",
    "/administration/users",
    "/administration/audit-log",
    "/administration/system-health",
    "/administration/ai-config",
)


@pytest.mark.parametrize("path", ADMINISTRATION_ENDPOINTS)
@pytest.mark.parametrize("role_name", NON_ADMIN_ROLES)
def test_non_admin_gets_403_on_every_administration_endpoint(client, auth_headers, role_name, path):
    resp = client.get(path, headers=auth_headers(role_name))
    assert resp.status_code == 403


@pytest.mark.parametrize("path", ADMINISTRATION_ENDPOINTS)
def test_admin_can_access_every_administration_endpoint(client, auth_headers, path):
    resp = client.get(path, headers=auth_headers("Administrator"))
    assert resp.status_code == 200


def test_dashboard_shape(client, auth_headers):
    resp = client.get("/administration/dashboard", headers=auth_headers("Administrator"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] >= 1
    assert body["active_users"] + body["inactive_users"] == body["total_users"]
    assert isinstance(body["roles"], list)
    assert isinstance(body["recent_activity"], list)


def test_permission_matrix_includes_administration_entries(client, auth_headers):
    resp = client.get("/administration/permissions", headers=auth_headers("Administrator"))
    assert resp.status_code == 200
    entries = resp.json()
    admin_entries = [e for e in entries if e["module"] == "Administration"]
    assert len(admin_entries) >= 4
    for e in admin_entries:
        assert e["roles"] == ["Administrator"]


def test_ai_config_never_leaks_key(client, auth_headers, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-never-appear-in-response")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        resp = client.get("/administration/ai-config", headers=auth_headers("Administrator"))
        assert resp.status_code == 200
        assert "sk-should-never-appear-in-response" not in resp.text
        body = resp.json()
        assert set(body.keys()) == {"provider", "model", "is_configured", "status"}
    finally:
        get_settings.cache_clear()


def test_system_health_reports_no_infra_details(client, auth_headers):
    resp = client.get("/administration/system-health", headers=auth_headers("Administrator"))
    assert resp.status_code == 200
    body = resp.json()
    assert "database_url" not in resp.text
    assert "secret_key" not in resp.text
    assert set(body.keys()) == {
        "backend_status", "database_status", "api_status", "ai_provider_status", "app_version", "environment",
    }


def test_audit_log_pagination_params(client, auth_headers):
    resp = client.get("/administration/audit-log?page=1&page_size=5", headers=auth_headers("Administrator"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 5


def test_audit_log_detail_404_for_unknown_id(client, auth_headers):
    resp = client.get("/administration/audit-log/999999", headers=auth_headers("Administrator"))
    assert resp.status_code == 404


def test_administration_users_list_is_paginated_and_filterable(client, auth_headers):
    resp = client.get(
        "/administration/users?page=1&page_size=10&is_active=true", headers=auth_headers("Administrator")
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body and "total" in body
    for item in body["items"]:
        assert item["is_active"] is True


def test_roles_list_matches_seeded_seven_roles(client, auth_headers):
    all_roles = (
        "Administrator", "Production Operator", "Production Engineer",
        "Maintenance Engineer", "Management", "Analyst", "Viewer",
    )
    admin_headers = None
    for role_name in all_roles:
        headers = auth_headers(role_name)
        if role_name == "Administrator":
            admin_headers = headers

    resp = client.get("/administration/roles", headers=admin_headers)
    assert resp.status_code == 200
    names = {r["name"] for r in resp.json()}
    assert names == set(all_roles)
