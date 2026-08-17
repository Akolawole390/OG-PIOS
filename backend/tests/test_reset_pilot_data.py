"""Regression coverage for the pilot/demo reset tool (app/db/reset_pilot_data.py).

Doesn't run the tool's actual TRUNCATE/reseed against a real database (that requires Postgres —
verified manually via `docker compose exec backend python -m app.db.reset_pilot_data --yes`).
Instead statically cross-checks PILOT_DATA_TABLES against the real ORM schema, so a future
migration that adds a new operational table can't silently go un-reset, and so the "users/roles/
system_settings/audit_logs are never touched" guarantee stays true as the schema evolves.
"""

import app.models  # noqa: F401  registers every model on Base.metadata
from app.core.database import Base
from app.db.reset_pilot_data import PILOT_DATA_TABLES

NEVER_RESET_TABLES = {"users", "roles", "system_settings", "audit_logs"}


def test_pilot_data_tables_has_no_duplicates():
    assert len(PILOT_DATA_TABLES) == len(set(PILOT_DATA_TABLES))


def test_pilot_data_tables_never_includes_auth_or_audit_tables():
    assert set(PILOT_DATA_TABLES).isdisjoint(NEVER_RESET_TABLES)


def test_pilot_data_tables_plus_never_reset_tables_covers_the_full_schema():
    """Every real table is accounted for as either "wiped on reset" or "preserved" — if a new
    model/table is added without updating one of these two lists, this test fails."""
    all_tables = set(Base.metadata.tables.keys())
    assert set(PILOT_DATA_TABLES) | NEVER_RESET_TABLES == all_tables
