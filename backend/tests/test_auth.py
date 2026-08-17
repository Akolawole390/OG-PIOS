from app.core.security import create_purpose_token, hash_password, password_fingerprint
from app.models.reporting import AuditLog
from app.models.role import Role
from app.models.user import User
from app.services.rate_limit import reset_rate_limits


def _make_user(db_session, *, email="user@test.dev", password="supersecret1", is_active=True, role_name="Analyst"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    if role is None:
        role = Role(name=role_name)
        db_session.add(role)
        db_session.flush()
    user = User(
        email=email, full_name="Test User", hashed_password=hash_password(password),
        role_id=role.id, is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    return user


# ----- Login -----

def test_login_success(client, db_session):
    reset_rate_limits()
    _make_user(db_session, email="login@test.dev", password="supersecret1")
    resp = client.post("/auth/login", data={"username": "login@test.dev", "password": "supersecret1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password(client, db_session):
    reset_rate_limits()
    _make_user(db_session, email="login2@test.dev", password="supersecret1")
    resp = client.post("/auth/login", data={"username": "login2@test.dev", "password": "wrong"})
    assert resp.status_code == 401


def test_login_inactive_user(client, db_session):
    reset_rate_limits()
    _make_user(db_session, email="inactive@test.dev", password="supersecret1", is_active=False)
    resp = client.post("/auth/login", data={"username": "inactive@test.dev", "password": "supersecret1"})
    assert resp.status_code == 401


def test_login_rate_limited(client, db_session):
    reset_rate_limits()
    _make_user(db_session, email="loginlimit@test.dev", password="supersecret1")

    for _ in range(10):
        client.post("/auth/login", data={"username": "loginlimit@test.dev", "password": "wrong"})

    resp = client.post("/auth/login", data={"username": "loginlimit@test.dev", "password": "supersecret1"})
    assert resp.status_code == 429


# ----- Change password -----

def test_change_password_success(client, db_session):
    _make_user(db_session, email="changeme@test.dev", password="oldpassword1")
    login = client.post("/auth/login", data={"username": "changeme@test.dev", "password": "oldpassword1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post(
        "/auth/change-password", json={"current_password": "oldpassword1", "new_password": "newpassword1"},
        headers=headers,
    )
    assert resp.status_code == 200

    assert client.post("/auth/login", data={"username": "changeme@test.dev", "password": "oldpassword1"}).status_code == 401
    assert client.post("/auth/login", data={"username": "changeme@test.dev", "password": "newpassword1"}).status_code == 200


def test_change_password_wrong_current_password(client, db_session):
    _make_user(db_session, email="wrongcur@test.dev", password="oldpassword1")
    login = client.post("/auth/login", data={"username": "wrongcur@test.dev", "password": "oldpassword1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post(
        "/auth/change-password", json={"current_password": "notright", "new_password": "newpassword1"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_change_password_too_short_rejected(client, db_session):
    _make_user(db_session, email="short@test.dev", password="oldpassword1")
    login = client.post("/auth/login", data={"username": "short@test.dev", "password": "oldpassword1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post(
        "/auth/change-password", json={"current_password": "oldpassword1", "new_password": "short"},
        headers=headers,
    )
    assert resp.status_code == 422


# ----- Forgot password -----

def test_forgot_password_existing_active_account(client, db_session, mock_mail_provider):
    reset_rate_limits()
    _make_user(db_session, email="forgot1@test.dev", password="supersecret1")

    resp = client.post("/auth/forgot-password", json={"email": "forgot1@test.dev"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["debug_token"] is not None
    assert body["debug_reset_url"] is not None
    assert len(mock_mail_provider.calls) == 1
    assert mock_mail_provider.calls[0][0] == "forgot1@test.dev"

    rows = db_session.query(AuditLog).filter_by(action="password_reset_requested").all()
    assert len(rows) == 1


def test_forgot_password_nonexistent_email_generic_response(client, db_session, mock_mail_provider):
    reset_rate_limits()
    audit_count_before = db_session.query(AuditLog).count()

    resp = client.post("/auth/forgot-password", json={"email": "doesnotexist@test.dev"})

    assert resp.status_code == 200
    assert resp.json()["message"] == "If an account exists for that email, a password reset link has been sent."
    assert resp.json()["debug_token"] is None
    assert len(mock_mail_provider.calls) == 0
    assert db_session.query(AuditLog).count() == audit_count_before


def test_forgot_password_deactivated_account_no_token(client, db_session, mock_mail_provider):
    reset_rate_limits()
    _make_user(db_session, email="deactivated@test.dev", password="supersecret1", is_active=False)

    resp = client.post("/auth/forgot-password", json={"email": "deactivated@test.dev"})
    assert resp.status_code == 200
    assert resp.json()["debug_token"] is None
    assert len(mock_mail_provider.calls) == 0


def test_forgot_password_rate_limited(client, db_session, mock_mail_provider):
    reset_rate_limits()
    _make_user(db_session, email="ratelimited@test.dev", password="supersecret1")

    for _ in range(3):
        assert client.post("/auth/forgot-password", json={"email": "ratelimited@test.dev"}).status_code == 200

    resp = client.post("/auth/forgot-password", json={"email": "ratelimited@test.dev"})
    assert resp.status_code == 429


def test_forgot_password_debug_fields_hidden_outside_development(client, db_session, mock_mail_provider, monkeypatch):
    reset_rate_limits()
    from app.core.config import get_settings

    _make_user(db_session, email="proddebug@test.dev", password="supersecret1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    # A real production deployment always sets a real SECRET_KEY too — Settings now refuses to
    # construct with the default placeholder while ENVIRONMENT=production (see config.py), so
    # this simulates that pairing rather than an unrealistic production-with-default-key state.
    monkeypatch.setenv("SECRET_KEY", "test-only-non-default-secret-key-for-this-test")
    get_settings.cache_clear()
    try:
        resp = client.post("/auth/forgot-password", json={"email": "proddebug@test.dev"})
        assert resp.status_code == 200
        assert resp.json()["debug_token"] is None
        assert resp.json()["debug_reset_url"] is None
    finally:
        get_settings.cache_clear()


# ----- Reset password -----

def test_reset_password_success(client, db_session):
    user = _make_user(db_session, email="reset1@test.dev", password="oldpassword1")
    token = create_purpose_token(str(user.id), "reset", 30, fp=password_fingerprint(user.hashed_password))

    resp = client.post("/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})
    assert resp.status_code == 200
    assert client.post("/auth/login", data={"username": "reset1@test.dev", "password": "brandnewpass1"}).status_code == 200


def test_reset_password_token_single_use(client, db_session):
    user = _make_user(db_session, email="reset2@test.dev", password="oldpassword1")
    token = create_purpose_token(str(user.id), "reset", 30, fp=password_fingerprint(user.hashed_password))

    first = client.post("/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})
    assert first.status_code == 200

    second = client.post("/auth/reset-password", json={"token": token, "new_password": "anotherpass1"})
    assert second.status_code == 400


def test_reset_password_garbage_token_rejected(client, db_session):
    resp = client.post("/auth/reset-password", json={"token": "not-a-real-token", "new_password": "brandnewpass1"})
    assert resp.status_code == 400


def test_reset_password_wrong_purpose_token_rejected(client, db_session):
    user = _make_user(db_session, email="reset3@test.dev", password="oldpassword1")
    verify_token = create_purpose_token(str(user.id), "verify_email", 30)

    resp = client.post("/auth/reset-password", json={"token": verify_token, "new_password": "brandnewpass1"})
    assert resp.status_code == 400


def test_reset_password_deactivated_account_rejected(client, db_session):
    user = _make_user(db_session, email="reset4@test.dev", password="oldpassword1")
    token = create_purpose_token(str(user.id), "reset", 30, fp=password_fingerprint(user.hashed_password))

    user.is_active = False
    db_session.commit()

    resp = client.post("/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})
    assert resp.status_code == 400


# ----- Email verification -----

def test_send_verification_and_verify_email_round_trip(client, db_session, mock_mail_provider):
    reset_rate_limits()
    user = _make_user(db_session, email="verify1@test.dev", password="supersecret1")
    assert user.is_email_verified is False
    login = client.post("/auth/login", data={"username": "verify1@test.dev", "password": "supersecret1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    send_resp = client.post("/auth/send-verification", headers=headers)
    assert send_resp.status_code == 200
    token = send_resp.json()["debug_token"]
    assert token is not None
    assert len(mock_mail_provider.calls) == 1

    verify_resp = client.post("/auth/verify-email", json={"token": token})
    assert verify_resp.status_code == 200

    db_session.refresh(user)
    assert user.is_email_verified is True


def test_send_verification_already_verified_is_idempotent(client, db_session, mock_mail_provider):
    reset_rate_limits()
    user = _make_user(db_session, email="verify2@test.dev", password="supersecret1")
    user.is_email_verified = True
    db_session.commit()
    login = client.post("/auth/login", data={"username": "verify2@test.dev", "password": "supersecret1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.post("/auth/send-verification", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["debug_token"] is None
    assert len(mock_mail_provider.calls) == 0


def test_verify_email_twice_is_idempotent(client, db_session):
    user = _make_user(db_session, email="verify3@test.dev", password="supersecret1")
    token = create_purpose_token(str(user.id), "verify_email", 30)

    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200


def test_verify_email_garbage_token_rejected(client, db_session):
    resp = client.post("/auth/verify-email", json={"token": "garbage"})
    assert resp.status_code == 400


def test_send_verification_rate_limited(client, db_session, mock_mail_provider):
    reset_rate_limits()
    _make_user(db_session, email="verifylimit@test.dev", password="supersecret1")
    login = client.post("/auth/login", data={"username": "verifylimit@test.dev", "password": "supersecret1"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    for _ in range(3):
        assert client.post("/auth/send-verification", headers=headers).status_code == 200

    resp = client.post("/auth/send-verification", headers=headers)
    assert resp.status_code == 429


# ----- No secrets ever leak -----

def test_no_password_or_token_leaks_into_audit_log(client, db_session, mock_mail_provider):
    reset_rate_limits()
    _make_user(db_session, email="noleaks@test.dev", password="supersecret1")

    resp = client.post("/auth/forgot-password", json={"email": "noleaks@test.dev"})
    token = resp.json()["debug_token"]

    client.post("/auth/reset-password", json={"token": token, "new_password": "brandnewpass1"})

    rows = db_session.query(AuditLog).all()
    for row in rows:
        haystack = f"{row.details} {row.metadata_json}"
        assert "supersecret1" not in haystack
        assert "brandnewpass1" not in haystack
        assert token not in haystack
