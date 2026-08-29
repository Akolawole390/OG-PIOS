"""Root-cause investigation — the Command Centre's "Investigate Event" / "WHY?" capability.

Gathers, from real recorded data, everything already connected to a target (an existing
Insight, or a well/equipment directly): the insight's own evidence, open alerts on the same
well/equipment, and recent maintenance/downtime history — into one structured answer. This is
deterministic data-gathering first, exactly like ai_assistant.py; the AI provider (if
configured) only adds a phrased assessment over that already-gathered evidence, never
introducing new facts of its own.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.ai import Alert, AIRecommendation
from app.models.equipment import DowntimeEvent, Equipment, MaintenanceRecord
from app.models.field import Well
from app.services.ai_assistant import SourceReference
from app.services.ai_providers.base import AIProvider, StructuredPrompt
from app.services.insight_calculations import derive_confidence_level

OPEN_ALERT_STATES = ("new", "acknowledged", "investigating")


@dataclass
class PossibleCause:
    description: str
    evidence_type: str  # observed_fact / calculated_metric / correlation / possible_contributor


@dataclass
class Investigation:
    event: str
    impact_summary: str
    primary_contributor: str | None
    possible_causes: list[PossibleCause]
    ai_assessment: str
    confidence_level: str
    recommended_investigation: str
    sources: list[SourceReference]
    answered_by: str  # "deterministic" or "ai"


class InvestigationTargetNotFound(Exception):
    pass


def investigate(
    db: Session,
    provider: AIProvider,
    *,
    insight_id: int | None = None,
    well_id: int | None = None,
    equipment_id: int | None = None,
) -> Investigation:
    insight: AIRecommendation | None = None
    if insight_id is not None:
        insight = db.query(AIRecommendation).filter(AIRecommendation.id == insight_id).first()
        if insight is None:
            raise InvestigationTargetNotFound(f"Insight {insight_id} not found")
        well_id = well_id or insight.well_id
        equipment_id = equipment_id or insight.equipment_id

    well = db.query(Well).filter(Well.id == well_id).first() if well_id is not None else None
    equipment = db.query(Equipment).filter(Equipment.id == equipment_id).first() if equipment_id is not None else None

    if insight is None and well is None and equipment is None:
        raise InvestigationTargetNotFound("No matching insight, well, or equipment found for the given id(s)")

    sources: list[SourceReference] = []
    possible_causes: list[PossibleCause] = []

    if insight is not None:
        sources.append(SourceReference("insight", insight.id, insight.title))
        for e in insight.evidence:
            if e.evidence_type == "possible_contributor":
                possible_causes.append(PossibleCause(e.description, e.evidence_type))
            if e.source_type and e.source_id:
                sources.append(SourceReference(e.source_type, e.source_id, e.source_label or e.description))

    if well is not None or equipment is not None:
        alert_query = db.query(Alert).filter(Alert.state.in_(OPEN_ALERT_STATES))
        alert_query = alert_query.filter(Alert.well_id == well.id) if well is not None else alert_query.filter(Alert.equipment_id == equipment.id)
        for a in alert_query.order_by(Alert.triggered_at.desc()).limit(5).all():
            possible_causes.append(PossibleCause(f"Open alert: {a.title} ({a.severity})", "correlation"))
            sources.append(SourceReference("alert", a.id, a.title))

    target_equipment_ids: list[int] = []
    if equipment is not None:
        target_equipment_ids = [equipment.id]
    elif well is not None:
        target_equipment_ids = [e.id for e in db.query(Equipment).filter(Equipment.well_id == well.id).all()]

    if target_equipment_ids:
        window_start = datetime.now(timezone.utc) - timedelta(days=30)
        recent_maintenance = (
            db.query(MaintenanceRecord)
            .filter(MaintenanceRecord.equipment_id.in_(target_equipment_ids))
            .filter(MaintenanceRecord.start_date.isnot(None))
            .order_by(MaintenanceRecord.start_date.desc())
            .limit(3)
            .all()
        )
        for m in recent_maintenance:
            possible_causes.append(
                PossibleCause(f"Recent maintenance on {m.equipment.equipment_tag}: {m.maintenance_type} ({m.status})", "correlation")
            )
            sources.append(SourceReference("maintenance_record", m.id, m.work_order_number or f"WO #{m.id}"))

        for d in db.query(DowntimeEvent).filter(DowntimeEvent.equipment_id.in_(target_equipment_ids), DowntimeEvent.end_time.is_(None)).all():
            possible_causes.append(PossibleCause(f"Ongoing downtime: {d.reason or 'reason not recorded'}", "observed_fact"))
            sources.append(SourceReference("downtime_event", d.id, d.reason or f"Downtime #{d.id}"))
        _ = window_start  # reserved for a future "within N days" filter on maintenance/downtime

    if not possible_causes:
        possible_causes.append(
            PossibleCause(
                "No correlating alerts, maintenance activity, or downtime events were found for this scope in "
                "the available data — the cause may not yet be reflected in recorded data, or may require "
                "manual field investigation.",
                "possible_contributor",
            )
        )

    confidence_level = derive_confidence_level(len({c.evidence_type for c in possible_causes}))

    event = insight.title if insight is not None else f"Investigation: {well.well_id if well is not None else equipment.equipment_tag}"
    impact_summary = (
        f"{insight.estimated_production_impact_value:,.1f} {insight.estimated_production_impact_unit}"
        if insight is not None and insight.estimated_production_impact_value is not None and insight.estimated_production_impact_unit
        else "No quantified impact is recorded for this event yet."
    )
    primary_contributor = (
        insight.well.well_id if insight is not None and insight.well is not None
        else well.well_id if well is not None
        else equipment.equipment_tag if equipment is not None
        else None
    )
    recommended_investigation = (
        insight.recommended_investigation
        if insight is not None and insight.recommended_investigation
        else "Review the possible causes below on-site and confirm against current field conditions before taking action."
    )

    answered_by = "deterministic"
    ai_assessment = (
        "No AI provider is configured — showing the deterministic evidence gathered above only. Configure an "
        "AI provider to receive a phrased assessment over this same evidence."
    )
    if provider.is_configured:
        interpretation = provider.interpret(
            StructuredPrompt(
                task=f"Assess the likely root cause of this operational event: {event}",
                data={
                    "impact": impact_summary,
                    "primary_contributor": primary_contributor or "not identified",
                    "possible_causes": [c.description for c in possible_causes],
                },
                data_sources=[s.source_label for s in sources],
            )
        )
        ai_assessment = interpretation.text
        answered_by = "ai"

    return Investigation(
        event=event,
        impact_summary=impact_summary,
        primary_contributor=primary_contributor,
        possible_causes=possible_causes,
        ai_assessment=ai_assessment,
        confidence_level=confidence_level,
        recommended_investigation=recommended_investigation,
        sources=sources,
        answered_by=answered_by,
    )
