from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.services.mail_providers.base import MailDeliveryError
from app.services.mail_providers.console_provider import ConsoleMailProvider
from app.services.mail_providers.factory import get_mail_provider
from app.services.mail_providers.resend_provider import ResendMailProvider


def test_factory_returns_console_provider_by_default():
    settings = Settings()
    provider = get_mail_provider(settings)
    assert isinstance(provider, ConsoleMailProvider)


def test_factory_falls_back_to_console_when_resend_selected_without_key():
    settings = Settings(mail_provider="resend", resend_api_key=None)
    provider = get_mail_provider(settings)
    assert isinstance(provider, ConsoleMailProvider)


def test_factory_returns_resend_provider_when_configured():
    settings = Settings(mail_provider="resend", resend_api_key="test-key")
    provider = get_mail_provider(settings)
    assert isinstance(provider, ResendMailProvider)


def test_console_provider_logs_and_never_raises(caplog):
    provider = ConsoleMailProvider()
    provider.send("user@example.com", "Subject", "Body")
    assert "user@example.com" in caplog.text


def test_resend_provider_send_calls_api():
    provider = ResendMailProvider(api_key="test-key", from_address="OG-PIOS <onboarding@resend.dev>")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    with patch("httpx.Client.post", return_value=fake_response) as mock_post:
        provider.send("user@example.com", "Subject", "Body")
    mock_post.assert_called_once()
    assert "api.resend.com" in mock_post.call_args.args[0]
    assert mock_post.call_args.kwargs["json"]["to"] == ["user@example.com"]


def test_resend_provider_raises_mail_delivery_error_on_http_failure():
    provider = ResendMailProvider(api_key="test-key", from_address="OG-PIOS <onboarding@resend.dev>")
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "boom", request=MagicMock(), response=fake_response
    )
    with patch("httpx.Client.post", return_value=fake_response):
        with pytest.raises(MailDeliveryError):
            provider.send("user@example.com", "Subject", "Body")
