from unittest.mock import MagicMock, patch

from app.core.config import Settings
from app.services.ai_providers.anthropic_provider import AnthropicProvider
from app.services.ai_providers.base import StructuredPrompt
from app.services.ai_providers.factory import get_ai_provider
from app.services.ai_providers.google_provider import GoogleProvider
from app.services.ai_providers.local_provider import LocalProvider
from app.services.ai_providers.null_provider import NullProvider
from app.services.ai_providers.openai_provider import OpenAIProvider


def _prompt() -> StructuredPrompt:
    return StructuredPrompt(task="Interpret this insight", data={"decline_pct": 18.0}, data_sources=["Production records: Well A-12"])


def test_null_provider_is_not_configured():
    provider = NullProvider()
    assert provider.is_configured is False
    assert provider.provider_name == "none"


def test_null_provider_composes_answer_from_structured_data_without_network(monkeypatch):
    # Assert no httpx.Client is ever instantiated/used by NullProvider.
    def _fail(*args, **kwargs):
        raise AssertionError("NullProvider must never make a network call")

    monkeypatch.setattr("httpx.Client.post", _fail)
    provider = NullProvider()
    result = provider.interpret(_prompt())
    assert "decline pct" in result.text
    assert "18.0" in result.text or "18" in result.text
    assert "Production records: Well A-12" in result.text
    assert "no ai interpretation provider is configured" in result.text.lower()
    assert result.provider == "none"


def test_factory_returns_null_provider_when_unset():
    settings = Settings(ai_provider="none")
    provider = get_ai_provider(settings)
    assert isinstance(provider, NullProvider)


def test_factory_returns_null_provider_when_selected_provider_missing_key():
    settings = Settings(ai_provider="openai", openai_api_key=None)
    provider = get_ai_provider(settings)
    assert isinstance(provider, NullProvider)


def test_factory_returns_openai_provider_when_configured():
    settings = Settings(ai_provider="openai", openai_api_key="test-key")
    provider = get_ai_provider(settings)
    assert isinstance(provider, OpenAIProvider)


def test_factory_returns_anthropic_provider_when_configured():
    settings = Settings(ai_provider="anthropic", anthropic_api_key="test-key")
    provider = get_ai_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_factory_returns_google_provider_when_configured():
    settings = Settings(ai_provider="google", google_api_key="test-key")
    provider = get_ai_provider(settings)
    assert isinstance(provider, GoogleProvider)


def test_factory_returns_local_provider_when_configured():
    settings = Settings(ai_provider="local", local_ai_base_url="http://localhost:11434/v1")
    provider = get_ai_provider(settings)
    assert isinstance(provider, LocalProvider)


def test_openai_provider_interpret_parses_response():
    provider = OpenAIProvider(api_key="test-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"choices": [{"message": {"content": "Mocked OpenAI interpretation."}}]}
    with patch("httpx.Client.post", return_value=fake_response) as mock_post:
        result = provider.interpret(_prompt())
    assert result.text == "Mocked OpenAI interpretation."
    assert result.provider == "openai"
    mock_post.assert_called_once()
    assert "api.openai.com" in mock_post.call_args.args[0]


def test_anthropic_provider_interpret_parses_response():
    provider = AnthropicProvider(api_key="test-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"content": [{"text": "Mocked Anthropic interpretation."}]}
    with patch("httpx.Client.post", return_value=fake_response) as mock_post:
        result = provider.interpret(_prompt())
    assert result.text == "Mocked Anthropic interpretation."
    assert result.provider == "anthropic"
    mock_post.assert_called_once()
    assert "api.anthropic.com" in mock_post.call_args.args[0]


def test_google_provider_interpret_parses_response():
    provider = GoogleProvider(api_key="test-key")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Mocked Google interpretation."}]}}]}
    with patch("httpx.Client.post", return_value=fake_response) as mock_post:
        result = provider.interpret(_prompt())
    assert result.text == "Mocked Google interpretation."
    assert result.provider == "google"
    mock_post.assert_called_once()


def test_local_provider_interpret_parses_response():
    provider = LocalProvider(base_url="http://localhost:11434/v1")
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"choices": [{"message": {"content": "Mocked local interpretation."}}]}
    with patch("httpx.Client.post", return_value=fake_response) as mock_post:
        result = provider.interpret(_prompt())
    assert result.text == "Mocked local interpretation."
    assert result.provider == "local"
    mock_post.assert_called_once()
    assert "localhost:11434" in mock_post.call_args.args[0]


def test_render_prompt_text_includes_safety_constraints_by_default():
    from app.services.ai_providers.base import AI_SAFETY_INSTRUCTIONS

    prompt = _prompt()
    assert prompt.constraints == AI_SAFETY_INSTRUCTIONS
    assert "do not invent" in prompt.constraints.lower()
