"""AI provider abstraction — the seam that keeps this application from being tightly coupled to
any single AI vendor. Every adapter is synchronous (this codebase has zero `async def` routes
or services anywhere; introducing async here would make the AI layer the one inconsistent code
path rather than a clean addition) and implements exactly one method: `interpret()`.

This layer is NEVER used for insight *generation* — `services/insight_engine.py` is 100%
deterministic and never imports anything from this package. Providers are only invoked from
`routers/ai_insights.py`'s explicit, opt-in `/interpret` and `/assistant` endpoints, and
optionally by the Daily Brief/Management Summary narrative flag. See docs/ai-architecture.md
for the full hybrid-intelligence boundary.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# Verbatim safety instructions every provider call carries, per the module's prompt-safety
# requirement — never invent data/causes/values, never present an estimate as an audited
# result, always state missing information and uncertainty explicitly.
AI_SAFETY_INSTRUCTIONS = (
    "You are interpreting already-computed oil & gas production data for an engineering/"
    "operations audience. Rules:\n"
    "- Do not invent data, causes, production values, costs, or equipment conditions.\n"
    "- Only use the figures and facts provided below — do not introduce numbers not present here.\n"
    "- Do not present estimates as actual, audited financial or production results.\n"
    "- If information needed to fully answer is missing, say so explicitly.\n"
    "- State uncertainty where it exists — never claim a confirmed root cause; use "
    "'possible contributor', 'correlation', or 'may be associated with' language instead.\n"
    "- Never recommend or imply automatic changes to equipment, chokes, pumps, pressure, or "
    "production rates — recommendations must be framed as decision-support for a human to review."
)


@dataclass
class StructuredPrompt:
    """Everything a provider needs to interpret already-computed figures — never asked to
    calculate anything itself (see AI_SAFETY_INSTRUCTIONS and the module's Hybrid Intelligence
    principle: the app calculates, the AI only interprets)."""

    task: str
    data: dict
    data_sources: list[str] = field(default_factory=list)
    time_period: str | None = None
    constraints: str = AI_SAFETY_INSTRUCTIONS


@dataclass
class AIInterpretation:
    text: str
    provider: str
    model: str | None = None


def render_prompt_text(prompt: StructuredPrompt) -> str:
    """Serializes a StructuredPrompt into the single user-facing text block every real
    provider adapter sends — one shared renderer so the exact same data/sources/constraints
    reach every provider identically."""
    lines = [prompt.task, ""]
    if prompt.time_period:
        lines.append(f"Time period: {prompt.time_period}")
    lines.append("Data:")
    for key, value in prompt.data.items():
        lines.append(f"- {key.replace('_', ' ')}: {value}")
    if prompt.data_sources:
        lines.append("")
        lines.append("Data sources:")
        for source in prompt.data_sources:
            lines.append(f"- {source}")
    return "\n".join(lines)


class AIProvider(ABC):
    """One method, one contract. `provider_name` identifies which adapter produced a response
    (stored on AIRecommendation.ai_provider / AssistantAnswer.answered_by) for transparency."""

    provider_name: str = "unknown"

    @abstractmethod
    def interpret(self, prompt: StructuredPrompt) -> AIInterpretation:
        raise NotImplementedError

    @property
    def is_configured(self) -> bool:
        """True if this provider has real credentials and would make a network call. The
        NullProvider always returns False — used by callers to label a response as
        deterministic vs. AI-generated."""
        return True
