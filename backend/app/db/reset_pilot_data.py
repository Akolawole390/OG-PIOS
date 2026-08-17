"""OG-PIOS PILOT / SYNTHETIC DATA — reset tool.

Wipes every synthetic *operational* table (wells, production, equipment, maintenance, downtime,
production loss, costs, commodity prices, alerts, AI insights, saved What-If scenarios, saved
reports) and regenerates a fresh copy of the same deterministic demo dataset `seed_wells.py`
produces, so a pilot demo can always be reset to a known-good starting state.

Deliberately does NOT touch `users`, `roles`, `system_settings`, or `audit_logs` — those are
application/tenant configuration and the administrative record of who did what, not pilot
"operational" data; wiping the audit log on every reset would itself be an auditability gap.

Authorization model: this is a CLI tool, not a web API endpoint — running it requires the same
level of access as the existing `seed`/`seed_wells` scripts (`docker compose exec backend ...`),
which is an intentional, existing security boundary in this project, not a new one. Two
additional safeguards specific to a *destructive* reset:
  1. Refuses to run at all when `ENVIRONMENT=production` — this tool must never be pointed at a
     real deployment's database.
  2. Requires an explicit `--yes` flag; running it bare only prints what it *would* do.

Usage:
    docker compose exec backend python -m app.db.reset_pilot_data --yes
"""

import argparse
import sys

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.db.seed_wells import seed_wells

# Every synthetic operational table — explicit and exhaustive so nothing is missed, and scoped
# so it can never accidentally reach users/roles/system_settings/audit_logs.
PILOT_DATA_TABLES = [
    "fields", "facilities", "wells",
    "production_records", "pressure_records", "temperature_records", "production_targets",
    "equipment", "equipment_readings", "maintenance_records", "downtime_events",
    "production_losses", "operating_costs", "commodity_prices",
    "alerts", "alert_status_history",
    "ai_recommendations", "ai_insight_evidence", "ai_insight_feedback", "ai_predictions",
    "scenarios", "reports",
]


def reset_pilot_data() -> None:
    settings = get_settings()
    if settings.environment == "production":
        print("Refusing to run: ENVIRONMENT=production. This tool only ever runs against a pilot/demo database.")
        sys.exit(1)

    print("=== OG-PIOS PILOT / SYNTHETIC DATA RESET ===")
    print(f"Wiping {len(PILOT_DATA_TABLES)} synthetic operational tables (users/roles/settings/audit log untouched)...")

    db = SessionLocal()
    try:
        db.execute(text(f"TRUNCATE TABLE {', '.join(PILOT_DATA_TABLES)} RESTART IDENTITY CASCADE"))
        db.commit()
    finally:
        db.close()

    print("Wipe complete. Regenerating the deterministic demo dataset...")
    seed_wells()
    print("=== RESET COMPLETE — pilot dataset regenerated ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Actually perform the reset (required — bare invocation is a dry-run notice only).")
    args = parser.parse_args()

    if not args.yes:
        print("This will PERMANENTLY DELETE all synthetic wells/production/equipment/maintenance/")
        print("downtime/loss/cost/alert/insight/scenario/report data and regenerate it fresh.")
        print("Users, roles, system settings, and the audit log are never touched.")
        print()
        print("Re-run with --yes to actually perform the reset:")
        print("    docker compose exec backend python -m app.db.reset_pilot_data --yes")
        sys.exit(0)

    reset_pilot_data()
