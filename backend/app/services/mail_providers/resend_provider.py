"""Thin synchronous REST adapter for the Resend API — no SDK dependency, matching this project's
minimal-dependency convention (only `httpx`, already a dependency), mirroring the shape of
`services/ai_providers/openai_provider.py` etc. Never exercised with a real key in this session's
tests; every test mocks `httpx.Client`.
"""

import httpx

from app.services.mail_providers.base import MailDeliveryError, MailProvider


class ResendMailProvider(MailProvider):
    provider_name = "resend"

    def __init__(self, api_key: str, from_address: str):
        self.api_key = api_key
        self.from_address = from_address

    def send(self, to: str, subject: str, body: str) -> None:
        try:
            response = httpx.Client(timeout=10).post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "from": self.from_address,
                    "to": [to],
                    "subject": subject,
                    "text": body,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MailDeliveryError(str(exc)) from exc
