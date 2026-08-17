"""The default (and, today, only) mail provider. Deliberately NOT a silent no-op — it logs the
full message so the password-reset/email-verification flow is genuinely testable end-to-end with
zero mail infrastructure configured. Never opens a network connection, never raises.

MUST NOT be selected in a real deployment — see the `mail_provider` setting's docstring in
`core/config.py`. Logging a reset/verification token is only acceptable in development.
"""

import logging

from app.services.mail_providers.base import MailProvider

logger = logging.getLogger(__name__)


class ConsoleMailProvider(MailProvider):
    provider_name = "console"

    def send(self, to: str, subject: str, body: str) -> None:
        logger.info("=== DEV-MODE EMAIL (no mail provider configured) ===\nTo: %s\nSubject: %s\n\n%s\n=== END EMAIL ===", to, subject, body)
