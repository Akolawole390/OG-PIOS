"""Enterprise-style audit logging — the one write path for `AuditLog`
(`models/reporting.py`), a table that existed since the initial scaffold with zero rows ever
written until this module. See `services/permissions.py`'s module docstring for the parallel
reasoning on why this codebase doesn't introduce a second authorization system here — audit
logging is a much smaller concern: a record of what happened, never a gate on what's allowed.

Never logs passwords, API keys, or other secrets — callers must never pass them in `details`/
`metadata`. Never raises: a logging failure must not break the action it's describing, so the
write here is wrapped and only ever logged to the application logger on failure.
"""

import logging

from sqlalchemy.orm import Session

from app.models.reporting import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditAction:
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    ROLE_CHANGED = "role_changed"
    SYSTEM_SETTING_CHANGED = "system_setting_changed"
    REPORT_GENERATED = "report_generated"
    WHATIF_SCENARIO_CREATED = "whatif_scenario_created"
    AI_INSIGHT_RUN = "ai_insight_run"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION_REQUESTED = "email_verification_requested"
    EMAIL_VERIFIED = "email_verified"


def record_audit_event(
    db: Session,
    user: User | None,
    action: str,
    resource: str,
    *,
    resource_id: int | None = None,
    status: str = "success",
    details: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Writes one audit row and commits it. Called AFTER the action it's describing has already
    committed successfully — never wraps the primary action's own transaction, so a rollback
    here can never undo real work. Swallows and logs any failure rather than propagating it."""
    try:
        entry = AuditLog(
            action=action,
            entity_type=resource,
            entity_id=resource_id,
            details=details,
            status=status,
            metadata_json=metadata,
            user_id=user.id if user else None,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record audit event: action=%s resource=%s", action, resource)
