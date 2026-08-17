"""The default provider when `AI_PROVIDER` is unset or unconfigured. Deliberately NOT a bare
"not configured" stub — it composes a genuinely useful, deterministic response from the exact
structured data it was given, so the app stays useful with zero AI provider configured, not
merely non-crashing. Never opens a network connection.
"""

from app.services.ai_providers.base import AIInterpretation, AIProvider, StructuredPrompt


def _format_value(value) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, list):
        return "; ".join(str(v) for v in value) if value else "none"
    return str(value)


class NullProvider(AIProvider):
    provider_name = "none"

    @property
    def is_configured(self) -> bool:
        return False

    def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
        lines = [prompt.task.rstrip(".") + ":"]
        for key, value in prompt.data.items():
            label = key.replace("_", " ")
            lines.append(f"- {label}: {_format_value(value)}")
        if prompt.data_sources:
            lines.append("Data sources: " + "; ".join(prompt.data_sources))
        lines.append(
            "(Deterministic summary — no AI interpretation provider is configured. Set "
            "AI_PROVIDER and the matching API key to enable natural-language interpretation of "
            "these same figures.)"
        )
        return AIInterpretation(text="\n".join(lines), provider=self.provider_name, model=None)
