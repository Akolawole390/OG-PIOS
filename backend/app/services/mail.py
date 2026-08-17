"""Thin message-building layer over `services/mail_providers/` — the one place
`routers/auth.py` calls into for sending the reset/verification email, so the router itself never
touches provider details. A delivery failure is caught and logged here, never propagated: a mail
outage must not turn a password-reset request into a 500, the same "a side-channel failure must
never break the primary action" rule `services/audit.py` already follows.
"""

import logging

from app.models.user import User
from app.services.mail_providers.base import MailDeliveryError, MailProvider

logger = logging.getLogger(__name__)


def send_reset_email(mail_provider: MailProvider, user: User, reset_url: str) -> None:
    body = (
        f"Hi {user.full_name},\n\n"
        "A password reset was requested for your OG-PIOS account. Use the link below to set a "
        "new password. This link expires shortly and can only be used once.\n\n"
        f"{reset_url}\n\n"
        "If you didn't request this, you can safely ignore this email."
    )
    try:
        mail_provider.send(user.email, "Reset your OG-PIOS password", body)
    except MailDeliveryError:
        logger.exception("Failed to send password reset email to user_id=%s", user.id)


def send_verification_email(mail_provider: MailProvider, user: User, verify_url: str) -> None:
    body = (
        f"Hi {user.full_name},\n\n"
        "Please verify your email address for your OG-PIOS account by visiting the link below.\n\n"
        f"{verify_url}"
    )
    try:
        mail_provider.send(user.email, "Verify your OG-PIOS email address", body)
    except MailDeliveryError:
        logger.exception("Failed to send verification email to user_id=%s", user.id)
