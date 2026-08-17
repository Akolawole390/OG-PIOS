"""The single seam every AI-interpretation consumer depends on — trivially overridden in tests
the same way `get_db` already is via `app.dependency_overrides`.
"""

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.ai_providers.anthropic_provider import AnthropicProvider
from app.services.ai_providers.base import AIProvider
from app.services.ai_providers.google_provider import GoogleProvider
from app.services.ai_providers.local_provider import LocalProvider
from app.services.ai_providers.null_provider import NullProvider
from app.services.ai_providers.openai_provider import OpenAIProvider


def get_ai_provider(settings: Settings) -> AIProvider:
    provider = (settings.ai_provider or "none").lower()

    if provider == "openai" and settings.openai_api_key:
        return OpenAIProvider(api_key=settings.openai_api_key)
    if provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicProvider(api_key=settings.anthropic_api_key)
    if provider == "google" and settings.google_api_key:
        return GoogleProvider(api_key=settings.google_api_key)
    if provider == "local" and settings.local_ai_base_url:
        return LocalProvider(
            base_url=settings.local_ai_base_url, model=settings.local_ai_model or "llama3"
        )

    # Unset, unrecognized, or missing the required key/URL for the selected provider — fall
    # back to the deterministic NullProvider rather than raising, so the app never breaks on
    # incomplete AI configuration.
    return NullProvider()


def get_ai_provider_dependency(settings: Settings = Depends(get_settings)) -> AIProvider:
    """FastAPI dependency wrapper — overridden in tests via `app.dependency_overrides` exactly
    like `get_db`, so no test ever makes a real network call."""
    return get_ai_provider(settings)
