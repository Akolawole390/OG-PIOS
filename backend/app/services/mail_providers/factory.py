"""The single seam every mail-sending consumer depends on — trivially overridden in tests the
same way `get_db`/`get_ai_provider_dependency` already are, via `app.dependency_overrides`.
"""

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.mail_providers.base import MailProvider
from app.services.mail_providers.console_provider import ConsoleMailProvider


def get_mail_provider(settings: Settings) -> MailProvider:
    # Only "console" is implemented today — any other/unrecognized value still falls back to it
    # rather than raising, so the app never breaks on mail configuration. A real SMTP/API-based
    # provider can be added here later, selected the same way `ai_provider` selects among the AI
    # providers.
    return ConsoleMailProvider()


def get_mail_provider_dependency(settings: Settings = Depends(get_settings)) -> MailProvider:
    """FastAPI dependency wrapper — overridden in tests via `app.dependency_overrides` exactly
    like `get_ai_provider_dependency`, so no test ever writes a real log line for a fake email."""
    return get_mail_provider(settings)
