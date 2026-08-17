"""Mail provider abstraction — mirrors `services/ai_providers/` exactly. Only a console/dev
implementation exists today (see `console_provider.py`); a real SMTP/API-based provider can be
added later behind this same interface without touching any caller.
"""

from abc import ABC, abstractmethod


class MailDeliveryError(Exception):
    """Raised by a provider's `send()` on delivery failure. Callers (see `services/mail.py`)
    catch this and log-only — a mail failure must never break the request that triggered it."""


class MailProvider(ABC):
    provider_name: str = "unknown"

    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None:
        raise NotImplementedError
