"""Thin synchronous REST adapter for OpenAI's Chat Completions API — no SDK dependency, matching
this project's minimal-dependency convention (only `httpx`, already a dependency). Never
exercised with a real key in this session's tests; every test mocks `httpx.Client`.
"""

import httpx

from app.services.ai_providers.base import AIInterpretation, AIProvider, StructuredPrompt, render_prompt_text

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(AIProvider):
    provider_name = "openai"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
        response = httpx.Client(timeout=30).post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": prompt.constraints},
                    {"role": "user", "content": render_prompt_text(prompt)},
                ],
            },
        )
        response.raise_for_status()
        body = response.json()
        text = body["choices"][0]["message"]["content"]
        return AIInterpretation(text=text, provider=self.provider_name, model=self.model)
