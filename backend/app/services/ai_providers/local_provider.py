"""Thin synchronous REST adapter for a local/self-hosted, OpenAI-compatible model server (e.g.
Ollama, LM Studio) — targets a configurable base URL, no API key required. No SDK dependency.
Never exercised with a real endpoint in this session's tests; every test mocks `httpx.Client`.
"""

import httpx

from app.services.ai_providers.base import AIInterpretation, AIProvider, StructuredPrompt, render_prompt_text

DEFAULT_MODEL = "llama3"


class LocalProvider(AIProvider):
    provider_name = "local"

    def __init__(self, base_url: str, model: str = DEFAULT_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
        response = httpx.Client(timeout=60).post(
            f"{self.base_url}/chat/completions",
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
