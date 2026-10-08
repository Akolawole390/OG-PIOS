"""AI Orchestrator — the coordination layer behind "Ask OG-PIOS" for broad, open-ended
operational questions that don't name a specific well/equipment/insight (e.g. "Why is
production down?", "What needs attention?").

This does not introduce a parallel multi-agent framework: it tries the existing
`ai_assistant.py` pattern matchers first, completely unchanged. Only when a question doesn't
match any of those *and* reads as a broad "what's wrong / why" question does it take over —
auto-selecting the single highest-priority open insight right now and running the same
root-cause investigation `root_cause.investigate()` already does for a user-picked target. That
investigation itself already pulls together whichever of production, equipment, alerts, and
maintenance data are relevant to that specific issue — which is the actual "combine the right
specialist agents into one answer, without the user choosing which ones" behavior this module is
for. The user is never asked to pick a domain/agent themselves.
"""

import re

from sqlalchemy.orm import Session

from app.models.ai import AIRecommendation
from app.services.ai_assistant import AssistantAnswer, SourceReference, answer_question, try_known_patterns
from app.services.ai_providers.base import AIProvider
from app.services.root_cause import investigate

_BROAD_QUESTION_PATTERN = re.compile(
    r"\bwhy\b.*\b(down|drop|declin|low|wrong|underperform|worse)\b"
    r"|\bwhat('?s| is) wrong\b"
    r"|\bwhat needs attention\b"
    r"|\btop (priority|issue)\b"
    r"|\bwhat should (i|we) (do|look at|investigate)\b",
    re.IGNORECASE,
)

# Same ordering as AI Insights' own severity vocabulary — lower rank = more urgent.
SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}


def _find_highest_priority_open_insight(db: Session) -> AIRecommendation | None:
    open_insights = db.query(AIRecommendation).filter(AIRecommendation.status.in_(("new", "reviewed"))).all()
    if not open_insights:
        return None
    return min(open_insights, key=lambda i: (SEVERITY_RANK.get(i.severity, len(SEVERITY_RANK)), -i.generated_at.timestamp()))


def answer_broad_question(db: Session, question: str, provider: AIProvider) -> AssistantAnswer:
    matched = try_known_patterns(db, question)
    if matched is not None:
        return matched

    if not _BROAD_QUESTION_PATTERN.search(question.strip().lower()):
        # Not a recognized narrow pattern, and not a broad "why/what's wrong" question either —
        # exactly the prior behavior: general-knowledge AI answer, or the static pattern list.
        return answer_question(db, question, provider)

    top = _find_highest_priority_open_insight(db)
    if top is None:
        return AssistantAnswer(
            "No open insights are currently flagged, so there is no single issue to point to right now.", []
        )

    result = investigate(db, provider, insight_id=top.id)
    causes = "; ".join(c.description for c in result.possible_causes)
    answer_text = (
        f"The highest-priority open issue right now is: {result.event} (impact: {result.impact_summary}). "
        f"Possible causes: {causes}. {result.ai_assessment}"
    )
    return AssistantAnswer(
        answer_text,
        [SourceReference("insight", top.id, top.title)] + result.sources,
        answered_by=result.answered_by,
    )
