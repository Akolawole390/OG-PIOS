import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  registers every model on Base.metadata
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.equipment import Equipment
from app.models.field import Facility, Field, Well
from app.models.role import Role
from app.models.user import User

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# pysqlite's default transaction handling doesn't play well with SAVEPOINT
# (Session.begin_nested(), used by the CSV import confirm endpoint for per-row isolation)
# unless its own BEGIN handling is disabled — this is SQLAlchemy's documented workaround.
@event.listens_for(engine, "connect")
def _sqlite_disable_pysqlite_begin(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None


@event.listens_for(engine, "begin")
def _sqlite_emit_begin(conn):
    conn.exec_driver_sql("BEGIN")


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(db_session):
    """Factory fixture: auth_headers("Administrator") -> {"Authorization": "Bearer ..."}."""

    def _make(role_name: str = "Administrator") -> dict[str, str]:
        role = db_session.query(Role).filter_by(name=role_name).first()
        if role is None:
            role = Role(name=role_name)
            db_session.add(role)
            db_session.flush()
        user = User(
            email=f"{role_name.lower().replace(' ', '-')}@test.dev",
            full_name="Test User",
            hashed_password=hash_password("x"),
            role_id=role.id,
        )
        db_session.add(user)
        db_session.commit()
        token = create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def make_field_facility_well(db_session):
    """Factory fixture: make_field_facility_well(well_id="W-001", status="active") ->
    (field, facility, well). Shared helper for tests that need a minimal Well to hang
    production records off of."""

    def _make(*, well_id: str = "W-001", status: str = "active") -> tuple[Field, Facility, Well]:
        field = Field(name=f"Field for {well_id}")
        db_session.add(field)
        db_session.flush()
        facility = Facility(name=f"Facility for {well_id}", field_id=field.id)
        db_session.add(facility)
        db_session.flush()
        well = Well(well_id=well_id, name=f"Well {well_id}", status=status, facility_id=facility.id)
        db_session.add(well)
        db_session.commit()
        return field, facility, well

    return _make


@pytest.fixture()
def mock_ai_provider(client):
    """Overrides the AI provider dependency with a fake, network-free provider — every
    interpret/assistant test that needs a "configured" provider path goes through this, never
    a real httpx.Client call. `mock_ai_provider.calls` records every StructuredPrompt it was
    asked to interpret, for assertions."""
    from app.services.ai_providers.base import AIInterpretation, AIProvider, StructuredPrompt
    from app.services.ai_providers.factory import get_ai_provider_dependency

    class FakeProvider(AIProvider):
        provider_name = "fake"

        def __init__(self):
            self.calls: list[StructuredPrompt] = []

        def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
            self.calls.append(prompt)
            return AIInterpretation(text="Fake AI interpretation.", provider="fake", model="fake-model")

    fake = FakeProvider()
    app.dependency_overrides[get_ai_provider_dependency] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_ai_provider_dependency, None)


@pytest.fixture()
def mock_mail_provider(client):
    """Overrides the mail provider dependency with a fake, no-log provider — every
    forgot-password/send-verification test goes through this rather than the real
    `ConsoleMailProvider`. `mock_mail_provider.calls` records every `(to, subject, body)` send
    for assertions (e.g. that the body never appears in an API response, only in the "email")."""
    from app.services.mail_providers.base import MailProvider
    from app.services.mail_providers.factory import get_mail_provider_dependency

    class FakeMailProvider(MailProvider):
        provider_name = "fake"

        def __init__(self):
            self.calls: list[tuple[str, str, str]] = []

        def send(self, to: str, subject: str, body: str) -> None:
            self.calls.append((to, subject, body))

    fake = FakeMailProvider()
    app.dependency_overrides[get_mail_provider_dependency] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_mail_provider_dependency, None)


@pytest.fixture()
def make_equipment(db_session):
    """Factory fixture: make_equipment(equipment_tag="EQ-1", well=None, facility=None) ->
    Equipment. Shared by Equipment- and Maintenance-module tests that need a minimal
    Equipment row to hang readings/maintenance/downtime off of."""

    def _make(
        *,
        equipment_tag: str = "EQ-1",
        equipment_type: str = "valve",
        status: str = "operating",
        well: Well | None = None,
        facility: Facility | None = None,
    ) -> Equipment:
        equipment = Equipment(
            equipment_tag=equipment_tag,
            name=equipment_tag,
            equipment_type=equipment_type,
            status=status,
            well_id=well.id if well else None,
            facility_id=facility.id if facility else None,
        )
        db_session.add(equipment)
        db_session.commit()
        return equipment

    return _make
