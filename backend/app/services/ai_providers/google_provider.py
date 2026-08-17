"""Thin synchronous REST adapter for Google's Generative Language API — no SDK dependency. Never
exercised with a real key in this session's tests; every test mocks `httpx.Client`.
"""

import httpx

from app.services.ai_providers.base import AIInterpretation, AIProvider, StructuredPrompt, render_prompt_text

DEFAULT_MODEL = "gemini-2.0-flash"


class GoogleProvider(AIProvider):
    provider_name = "google"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model

    def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
        response = httpx.Client(timeout=30).post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            params={"key": self.api_key},
            json={
                "contents": [{"parts": [{"text": render_prompt_text(prompt)}]}],
                "systemInstruction": {"parts": [{"text": prompt.constraints}]},
            },
        )
        response.raise_for_status()
        body = response.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        return AIInterpretation(text=text, provider=self.provider_name, model=self.model)
