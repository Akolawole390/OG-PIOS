import pytest

from app.core.security import create_access_token

NON_ADMIN_ROLES = (
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
    "Viewer",
)


def _role_id(db_session, name: str) -> int:
    from app.models.role import Role

    role = db_session.query(Role).filter_by(name=name).first()
    if role is None:
        role = Role(name=name)
        db_session.add(role)
        db_session.commit()
    return role.id


def test_create_user_never_exposes_password(client, auth_headers, db_session):
    headers = auth_headers("Administrator")
    role_id = _role_id(db_session, "Analyst")
    resp = client.post(
        "/users",
        json={
            "email": "newuser@test.dev",
            "full_name": "New User",
            "password": "supersecret1",
            "role_id": role_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "password" not in body
    assert "hashed_password" not in body
    assert body["email"] == "newuser@test.dev"


def test_create_user_duplicate_email_rejected(client, auth_headers, db_session):
    headers = auth_headers("Administrator")
    role_id = _role_id(db_session, "Analyst")
    payload = {
        "email": "dupe@test.dev", "full_name": "Dupe", "password": "supersecret1", "role_id": role_id,
    }
    first = client.post("/users", json=payload, headers=headers)
    assert first.status_code == 201
    second = client.post("/users", json=payload, headers=headers)
    assert second.status_code == 400


def test_create_user_unknown_role_rejected(client, auth_headers):
    headers = auth_headers("Administrator")
    resp = client.post(
        "/users",
        json={"email": "x@test.dev", "full_name": "X", "password": "supersecret1", "role_id": 999999},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("role_name", NON_ADMIN_ROLES)
def test_non_admin_cannot_create_user(client, auth_headers, role_name):
    resp = client.post(
        "/users",
        json={"email": "blocked@test.dev", "full_name": "Blocked", "password": "supersecret1", "role_id": 1},
        headers=auth_headers(role_name),
    )
    assert resp.status_code == 403


def test_update_user_role_and_active_status(client, auth_headers, db_session):
    admin_headers = auth_headers("Administrator")
    analyst_role_id = _role_id(db_session, "Analyst")
    create_resp = client.post(
        "/users",
        json={"email": "update-me@test.dev", "full_name": "Update Me", "password": "supersecret1", "role_id": analyst_role_id},
        headers=admin_headers,
    )
    user_id = create_resp.json()["id"]

    mgmt_role_id = _role_id(db_session, "Management")
    resp = client.put(
        f"/users/{user_id}",
        json={"role_id": mgmt_role_id, "is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["role_id"] == mgmt_role_id
    assert body["is_active"] is False


def test_update_user_never_accepts_password_field(client, auth_headers, db_session):
    admin_headers = auth_headers("Administrator")
    role_id = _role_id(db_session, "Analyst")
    create_resp = client.post(
        "/users",
        json={"email": "nopw@test.dev", "full_name": "No PW", "password": "supersecret1", "role_id": role_id},
        headers=admin_headers,
    )
    user_id = create_resp.json()["id"]

    # UserUpdate schema has no password field — extra fields are ignored by pydantic default config
    resp = client.put(f"/users/{user_id}", json={"password": "hacked123"}, headers=admin_headers)
    assert resp.status_code == 200
    assert "password" not in resp.json()


def test_deactivating_user_invalidates_existing_token(client, auth_headers, db_session):
    """Proves the deps.py/auth.py is_active fix: an already-issued JWT for a user who gets
    deactivated must stop working immediately, not merely block future logins."""
    admin_headers = auth_headers("Administrator")
    role_id = _role_id(db_session, "Analyst")
    create_resp = client.post(
        "/users",
        json={"email": "todeactivate@test.dev", "full_name": "To Deactivate", "password": "supersecret1", "role_id": role_id},
        headers=admin_headers,
    )
    user_id = create_resp.json()["id"]
    victim_token = create_access_token(subject=str(user_id))
    victim_headers = {"Authorization": f"Bearer {victim_token}"}

    # Token works before deactivation
    assert client.get("/auth/me", headers=victim_headers).status_code == 200

    deactivate_resp = client.put(f"/users/{user_id}", json={"is_active": False}, headers=admin_headers)
    assert deactivate_resp.status_code == 200

    # Same token must now be rejected
    assert client.get("/auth/me", headers=victim_headers).status_code == 401


def test_deactivated_user_cannot_log_in(client, auth_headers, db_session):
    admin_headers = auth_headers("Administrator")
    role_id = _role_id(db_session, "Analyst")
    client.post(
        "/users",
        json={"email": "loginblocked@test.dev", "full_name": "Login Blocked", "password": "supersecret1", "role_id": role_id},
        headers=admin_headers,
    )
    from app.models.user import User

    u = db_session.query(User).filter_by(email="loginblocked@test.dev").first()
    u.is_active = False
    db_session.commit()

    resp = client.post(
        "/auth/login",
        data={"username": "loginblocked@test.dev", "password": "supersecret1"},
    )
    assert resp.status_code == 401


def test_get_user_requires_admin(client, auth_headers, db_session):
    admin_headers = auth_headers("Administrator")
    role_id = _role_id(db_session, "Analyst")
    create_resp = client.post(
        "/users",
        json={"email": "getme@test.dev", "full_name": "Get Me", "password": "supersecret1", "role_id": role_id},
        headers=admin_headers,
    )
    user_id = create_resp.json()["id"]

    non_admin = auth_headers("Viewer")
    assert client.get(f"/users/{user_id}", headers=non_admin).status_code == 403
    assert client.get(f"/users/{user_id}", headers=admin_headers).status_code == 200


def test_list_users_unaffected_for_existing_caller(client, auth_headers):
    """GET /users (unpaginated, active-only) must stay usable by any authenticated user —
    the Maintenance module's technician dropdown depends on this exact shape."""
    resp = client.get("/users", headers=auth_headers("Maintenance Engineer"))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
