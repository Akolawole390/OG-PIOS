"""AI Operations Assistant — answers a fixed set of known question patterns deterministically
from real OG-PIOS data (never inventing facts), falling through to the configured AI provider
(or a clear "can't answer" message) only for questions that don't match a known pattern. This
is NOT a general chatbot: every deterministic answer is built from the same tables/queries
proven elsewhere in the app, with source citations the user can follow back to the record.
"""

import re
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.ai import AIRecommendation
from app.models.economics import ProductionLoss
from app.models.equipment import DowntimeEvent, Equipment, MaintenanceRecord
from app.models.field import Field, Well
from app.models.production import ProductionRecord
from app.routers.cost_revenue import (
    _compute_scope_totals,
    _latest_period,
    _load_price_series,
    _per_unit_by_currency,
)
from app.services.ai_providers.base import AIProvider, StructuredPrompt
from app.services.system_settings import get_boe_gas_factor

# Matches this dataset's well-code format, e.g. "PBF-03-003", "NSF-05-014".
WELL_CODE_PATTERN = re.compile(r"\b[A-Z]{2,5}-\d{2,3}-\d{2,4}\b")


@dataclass
class SourceReference:
    source_type: str
    source_id: int | None
    source_label: str


@dataclass
class AssistantAnswer:
    answer: str
    sources: list[SourceReference] = field(default_factory=list)
    answered_by: str = "deterministic"  # "deterministic" or "ai"


def _extract_well_code(text: str) -> str | None:
    match = WELL_CODE_PATTERN.search(text.upper())
    return match.group(0) if match else None


def _match_production_problems(db: Session, question: str) -> AssistantAnswer | None:
    if not any(kw in question for kw in ("production problem", "biggest problem", "what's wrong")):
        return None
    down_events = db.query(DowntimeEvent).filter(DowntimeEvent.end_time.is_(None), DowntimeEvent.well_id.isnot(None)).all()
    down_well_ids = {e.well_id for e in down_events if e.well_id}
    reference_date = db.query(ProductionRecord.record_date).order_by(ProductionRecord.record_date.desc()).first()
    zero_well_ids: set[int] = set()
    if reference_date:
        zero_records = db.query(ProductionRecord).filter(
            ProductionRecord.record_date == reference_date[0], ProductionRecord.oil_bopd == 0, ProductionRecord.gas_mscfd == 0
        ).all()
        zero_well_ids = {r.well_id for r in zero_records}
    problem_well_ids = down_well_ids | zero_well_ids
    if not problem_well_ids:
        return AssistantAnswer("No active production outages or zero-production wells are recorded today.", [])
    wells = db.query(Well).filter(Well.id.in_(problem_well_ids)).all()
    names = ", ".join(w.well_id for w in wells)
    return AssistantAnswer(
        f"{len(wells)} well(s) currently show a production problem (open downtime event or zero recorded "
        f"production): {names}.",
        [SourceReference("well", w.id, w.well_id) for w in wells],
    )


def _match_wells_lost_most_production(db: Session, question: str) -> AssistantAnswer | None:
    if not any(kw in question for kw in ("lost the most production", "lost most production", "production loss")):
        return None
    window_start = _latest_period(db)[0] - timedelta(days=30)
    losses = db.query(ProductionLoss).filter(ProductionLoss.loss_date >= window_start, ProductionLoss.well_id.isnot(None)).all()
    totals: dict[int, float] = {}
    for loss in losses:
        if loss.estimated_bopd_lost:
            totals[loss.well_id] = totals.get(loss.well_id, 0.0) + loss.estimated_bopd_lost
    if not totals:
        return AssistantAnswer("No production-loss events with an estimated volume are recorded in the last 30 days.", [])
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:5]
    wells_by_id = {w.id: w for w in db.query(Well).filter(Well.id.in_([wid for wid, _ in top])).all()}
    lines = [f"{wells_by_id[wid].well_id}: {amount:.1f} bbl estimated lost" for wid, amount in top if wid in wells_by_id]
    return AssistantAnswer(
        "Wells with the highest estimated lost production in the last 30 days: " + "; ".join(lines) + ".",
        [SourceReference("well", wid, wells_by_id[wid].well_id) for wid, _ in top if wid in wells_by_id],
    )


def _match_equipment_requires_attention(db: Session, question: str) -> AssistantAnswer | None:
    if not any(kw in question for kw in ("equipment requires attention", "equipment need attention", "equipment attention")):
        return None
    equipment = db.query(Equipment).filter((Equipment.status == "failed") | (Equipment.health_score < 75)).order_by(Equipment.health_score.asc().nullslast()).limit(5).all()
    if not equipment:
        return AssistantAnswer("No equipment currently shows a failed status or a health score below 75.", [])
    lines = [f"{e.equipment_tag} (status={e.status}, health score={e.health_score if e.health_score is not None else 'n/a'})" for e in equipment]
    return AssistantAnswer(
        f"{len(equipment)} equipment item(s) require attention: " + "; ".join(lines) + ".",
        [SourceReference("equipment", e.id, e.equipment_tag) for e in equipment],
    )


def _match_why_well_underperforming(db: Session, question: str) -> AssistantAnswer | None:
    well_code = _extract_well_code(question)
    if well_code is None or not any(kw in question for kw in ("why is", "underperform", "why does")):
        return None
    well = db.query(Well).filter(Well.well_id == well_code).first()
    if well is None:
        return AssistantAnswer(f"No well with code {well_code} was found.", [])
    insights = (
        db.query(AIRecommendation)
        .filter(AIRecommendation.well_id == well.id, AIRecommendation.status != "dismissed")
        .order_by(AIRecommendation.generated_at.desc())
        .limit(5)
        .all()
    )
    if not insights:
        return AssistantAnswer(
            f"No open insights are currently recorded for {well_code} — its production is not showing a "
            "flagged decline, anomaly, or below-target condition in the most recent analysis.",
            [SourceReference("well", well.id, well_code)],
        )
    lines = [f"{i.title}: {i.summary}" for i in insights]
    return AssistantAnswer(
        f"Insights recorded for {well_code}: " + " | ".join(lines),
        [SourceReference("well", well.id, well_code)] + [SourceReference("insight", i.id, i.title) for i in insights],
    )


def _match_highest_maintenance_cost(db: Session, question: str) -> AssistantAnswer | None:
    if "maintenance cost" not in question or "highest" not in question:
        return None
    window_start = _latest_period(db)[0] - timedelta(days=90)
    records = db.query(MaintenanceRecord).filter(MaintenanceRecord.start_date.isnot(None), MaintenanceRecord.start_date >= window_start, MaintenanceRecord.equipment_id.isnot(None)).all()
    totals: dict[int, float] = {}
    for r in records:
        totals[r.equipment_id] = totals.get(r.equipment_id, 0.0) + (r.cost or 0)
    if not totals:
        return AssistantAnswer("No maintenance cost data is recorded in the last 90 days.", [])
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:5]
    equipment_by_id = {e.id: e for e in db.query(Equipment).filter(Equipment.id.in_([eid for eid, _ in top])).all()}
    lines = [f"{equipment_by_id[eid].equipment_tag}: USD {amount:,.0f}" for eid, amount in top if eid in equipment_by_id]
    return AssistantAnswer(
        "Equipment with the highest maintenance cost in the last 90 days: " + "; ".join(lines) + ".",
        [SourceReference("equipment", eid, equipment_by_id[eid].equipment_tag) for eid, _ in top if eid in equipment_by_id],
    )


def _match_biggest_loss_opportunities(db: Session, question: str) -> AssistantAnswer | None:
    if not any(kw in question for kw in ("loss opportunit", "biggest opportunit")):
        return None
    window_start = _latest_period(db)[0] - timedelta(days=30)
    losses = db.query(ProductionLoss).filter(ProductionLoss.loss_date >= window_start, ProductionLoss.currency == "USD", ProductionLoss.estimated_revenue_impact.isnot(None)).order_by(ProductionLoss.estimated_revenue_impact.desc()).limit(5).all()
    if not losses:
        return AssistantAnswer("No USD-denominated production-loss revenue impact is recorded in the last 30 days.", [])
    lines = [f"Loss #{loss.id} ({loss.cause or loss.category or 'unspecified cause'}): USD {loss.estimated_revenue_impact:,.0f}" for loss in losses]
    return AssistantAnswer(
        "The largest estimated production-loss revenue opportunities in the last 30 days: " + "; ".join(lines) + ".",
        [SourceReference("production_loss", loss.id, f"Loss #{loss.id}") for loss in losses],
    )


def _match_highest_cost_per_barrel(db: Session, question: str) -> AssistantAnswer | None:
    if "cost per barrel" not in question and "cost per bbl" not in question:
        return None
    this_start, this_end = _latest_period(db)
    boe_gas_factor = get_boe_gas_factor(db)
    price_series = _load_price_series(db)
    # Never compare cost-per-barrel across currencies by raw magnitude (NGN and USD are not on
    # the same numeric scale) — track the highest field independently per currency, same
    # currency-safety rule Cost & Revenue's own aggregates follow.
    best_by_currency: dict[str, tuple[str, float]] = {}
    for f in db.query(Field).all():
        totals = _compute_scope_totals(db, this_start, this_end, price_series, boe_gas_factor, field_id=f.id)
        cost_per_bbl = _per_unit_by_currency(totals["operating_dict"], totals["oil_total"])
        for currency, value in cost_per_bbl.items():
            current_best = best_by_currency.get(currency)
            if current_best is None or value > current_best[1]:
                best_by_currency[currency] = (f.name, value)
    if not best_by_currency:
        return AssistantAnswer("No cost-per-barrel figure could be computed for the latest period.", [])
    lines = [f"{currency}: {name} at {currency} {value:,.2f}/bbl" for currency, (name, value) in sorted(best_by_currency.items())]
    sources = [SourceReference("field", None, name) for name, _ in best_by_currency.values()]
    return AssistantAnswer(
        "Highest cost per barrel this period, by currency (never blended across currencies): " + "; ".join(lines) + ".",
        sources,
    )


def _match_what_changed(db: Session, question: str) -> AssistantAnswer | None:
    if "what changed" not in question and "compared" not in question and "vs last month" not in question:
        return None
    this_start, this_end = _latest_period(db)
    prev_end = this_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    this_records = db.query(ProductionRecord).filter(ProductionRecord.record_date >= this_start, ProductionRecord.record_date <= this_end).all()
    prev_records = db.query(ProductionRecord).filter(ProductionRecord.record_date >= prev_start, ProductionRecord.record_date <= prev_end).all()
    this_oil = sum(r.oil_bopd for r in this_records)
    prev_oil = sum(r.oil_bopd for r in prev_records)
    if prev_oil <= 0:
        return AssistantAnswer("Not enough prior-month production data to compare.", [])
    pct = (this_oil - prev_oil) / prev_oil * 100
    direction = "up" if pct >= 0 else "down"
    return AssistantAnswer(
        f"Total oil production this period is {direction} {abs(pct):.1f}% vs. last month "
        f"({this_oil:,.0f} bbl vs. {prev_oil:,.0f} bbl).",
        [],
    )


_MATCHERS = (
    _match_production_problems,
    _match_wells_lost_most_production,
    _match_equipment_requires_attention,
    _match_why_well_underperforming,
    _match_highest_maintenance_cost,
    _match_biggest_loss_opportunities,
    _match_highest_cost_per_barrel,
    _match_what_changed,
)

KNOWN_QUESTION_PATTERNS = (
    "What are the biggest production problems today?",
    "Which wells lost the most production this month?",
    "Which equipment requires attention?",
    "Why is Well <code> underperforming? (e.g. Why is Well PBF-03-003 underperforming?)",
    "Which wells have the highest maintenance cost?",
    "What are the biggest production-loss opportunities?",
    "Which field has the highest cost per barrel?",
    "What changed compared with last month?",
)


def answer_question(db: Session, question: str, provider: AIProvider) -> AssistantAnswer:
    normalized = question.strip().lower()
    for matcher in _MATCHERS:
        result = matcher(db, normalized)
        if result is not None:
            return result

    if provider.is_configured:
        interpretation = provider.interpret(
            StructuredPrompt(
                task=(
                    "Answer this oil & gas production operations question using only general "
                    "domain knowledge — no OG-PIOS-specific data matched this question, so do "
                    "not claim any specific figures from this system."
                ),
                data={"question": question},
            )
        )
        return AssistantAnswer(interpretation.text, [], answered_by="ai")

    return AssistantAnswer(
        "I can answer questions matching these patterns using real OG-PIOS data: "
        + " | ".join(KNOWN_QUESTION_PATTERNS)
        + ". No AI provider is configured for open-ended questions outside these patterns.",
        [],
    )
