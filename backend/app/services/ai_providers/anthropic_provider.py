"""Thin synchronous REST adapter for Anthropic's Messages API — no SDK dependency. Never
exercised with a real key in this session's tests; every test mocks `httpx.Client`.
"""

import httpx

from app.services.ai_providers.base import AIInterpretation, AIProvider, StructuredPrompt, render_prompt_text

DEFAULT_MODEL = "claude-sonnet-5"


class AnthropicProvider(AIProvider):
    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
        response = httpx.Client(timeout=30).post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "system": prompt.constraints,
                "messages": [{"role": "user", "content": render_prompt_text(prompt)}],
            },
        )
        response.raise_for_status()
        body = response.json()
        text = "".join(block.get("text", "") for block in body.get("content", []))
        return AIInterpretation(text=text, provider=self.provider_name, model=self.model)
