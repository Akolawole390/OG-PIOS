"""The single seam every mail-sending consumer depends on — trivially overridden in tests the
same way `get_db`/`get_ai_provider_dependency` already are, via `app.dependency_overrides`.
"""

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.mail_providers.base import MailProvider
from app.services.mail_providers.console_provider import ConsoleMailProvider
from app.services.mail_providers.resend_provider import ResendMailProvider


def get_mail_provider(settings: Settings) -> MailProvider:
    provider = (settings.mail_provider or "console").lower()

    if provider == "resend" and settings.resend_api_key:
        return ResendMailProvider(api_key=settings.resend_api_key, from_address=settings.mail_from_address)

    # Unset, unrecognized, or missing the required key for the selected provider — fall back to
    # the console provider rather than raising, so the app never breaks on incomplete mail
    # configuration, the same rule `ai_providers/factory.py` follows for `ai_provider`.
    return ConsoleMailProvider()


def get_mail_provider_dependency(settings: Settings = Depends(get_settings)) -> MailProvider:
    """FastAPI dependency wrapper — overridden in tests via `app.dependency_overrides` exactly
    like `get_ai_provider_dependency`, so no test ever writes a real log line for a fake email."""
    return get_mail_provider(settings)
