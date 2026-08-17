from app.services.audit import AuditAction, record_audit_event


def test_record_audit_event_writes_row(db_session, auth_headers):
    auth_headers("Administrator")
    from app.models.reporting import AuditLog
    from app.models.user import User

    user = db_session.query(User).first()

    record_audit_event(
        db_session, user, AuditAction.SYSTEM_SETTING_CHANGED, "system_setting",
        resource_id=None, details="Changed setting 'company_name'",
        metadata={"key": "company_name", "from_value": "OG-PIOS", "to_value": "Acme"},
    )

    rows = db_session.query(AuditLog).all()
    assert len(rows) == 1
    assert rows[0].action == AuditAction.SYSTEM_SETTING_CHANGED
    assert rows[0].status == "success"
    assert rows[0].metadata_json == {"key": "company_name", "from_value": "OG-PIOS", "to_value": "Acme"}


def test_record_audit_event_never_raises_on_bad_session(db_session, auth_headers):
    auth_headers("Administrator")
    from app.models.user import User

    user = db_session.query(User).first()
    db_session.close()  # simulate a broken/closed session

    # Must not raise even though the underlying session is unusable.
    record_audit_event(db_session, user, AuditAction.USER_CREATED, "user", resource_id=1)


def test_record_audit_event_with_no_user(db_session):
    from app.models.reporting import AuditLog

    record_audit_event(db_session, None, AuditAction.REPORT_GENERATED, "report", resource_id=1)
    row = db_session.query(AuditLog).first()
    assert row.user_id is None


def test_hooked_endpoints_produce_audit_rows_without_secrets(client, auth_headers, db_session):
    headers = auth_headers("Administrator")

    from app.models.role import Role

    role = db_session.query(Role).filter_by(name="Analyst").first()
    if role is None:
        role = Role(name="Analyst")
        db_session.add(role)
        db_session.commit()
    resp = client.post(
        "/users",
        json={"email": "audited@test.dev", "full_name": "Audited User", "password": "supersecret1", "role_id": role.id},
        headers=headers,
    )
    assert resp.status_code == 201

    from app.models.settings import SystemSetting

    setting = SystemSetting(key="company_name", value="OG-PIOS", description="test setting")
    db_session.add(setting)
    db_session.commit()

    update_resp = client.put("/settings/company_name", json={"value": "Acme Oil"}, headers=headers)
    assert update_resp.status_code == 200

    audit_resp = client.get("/administration/audit-log?page=1&page_size=50", headers=headers)
    assert audit_resp.status_code == 200
    body = audit_resp.json()

    assert any(item["action"] == "user_created" for item in body["items"])
    assert any(item["action"] == "system_setting_changed" for item in body["items"])
    assert "supersecret1" not in audit_resp.text
