from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.ai import AIInsightFeedback, AIRecommendation
from app.models.economics import ProductionLoss
from app.models.equipment import MaintenanceRecord
from app.models.user import User
from app.routers.cost_revenue import _latest_period
from app.routers.equipment import get_equipment_issues
from app.routers.maintenance import get_maintenance_dashboard
from app.routers.production import get_production_kpis
from app.schemas.ai_insight import (
    AssistantAnswerResponse,
    AssistantQuestionRequest,
    DailyBriefResponse,
    DailyBriefSection,
    InsightCategoryCount,
    InsightEvidenceRead,
    InsightFeedbackCreate,
    InsightFeedbackRead,
    InsightListResponse,
    InsightRead,
    InsightRunCategoryResult,
    InsightRunResponse,
    InsightSeverityCounts,
    InsightStatusUpdateRequest,
    InsightSummaryResponse,
    InterpretResponse,
    InvestigateRequest,
    InvestigationResponse,
    ManagementSummaryResponse,
    ManagementSummarySection,
    PossibleCauseRead,
    SourceReferenceRead,
)
from app.services.ai_assistant import answer_question
from app.services.ai_providers.base import AIProvider, StructuredPrompt
from app.services.ai_providers.factory import get_ai_provider_dependency
from app.services.audit import AuditAction, record_audit_event
from app.services.insight_calculations import compute_is_stale, to_aware_utc
from app.services.insight_engine import INSIGHT_DISCLAIMER, run_insight_engine
from app.services.rate_limit import rate_limiter
from app.services.report_export import build_daily_brief_pdf
from app.services.root_cause import InvestigationTargetNotFound, investigate
from app.services.system_settings import get_insight_stale_after_days

router = APIRouter(prefix="/ai-insights", tags=["ai-insights"])

NON_VIEWER_ROLES = (
    "Administrator",
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
)

SORTABLE_FIELDS = {
    "generated_at": AIRecommendation.generated_at,
    "last_confirmed_at": AIRecommendation.last_confirmed_at,
    "severity": AIRecommendation.severity,
    "confidence_level": AIRecommendation.confidence_level,
    "status": AIRecommendation.status,
    "title": AIRecommendation.title,
    "category": AIRecommendation.category,
}

OPEN_STATUSES = ("new", "reviewed")


def _insight_query(db: Session):
    return db.query(AIRecommendation).options(
        joinedload(AIRecommendation.well),
        joinedload(AIRecommendation.field),
        joinedload(AIRecommendation.facility),
        joinedload(AIRecommendation.equipment),
        joinedload(AIRecommendation.maintenance_record),
        joinedload(AIRecommendation.evidence),
        joinedload(AIRecommendation.feedback).joinedload(AIInsightFeedback.submitted_by),
    )


def _build_entry(insight: AIRecommendation, db: Session) -> InsightRead:
    now = datetime.now(timezone.utc)
    stale_after_days = get_insight_stale_after_days(db)
    days_since_confirmed = (now - to_aware_utc(insight.last_confirmed_at)).days
    is_stale = compute_is_stale(insight.last_confirmed_at, now, stale_after_days)

    return InsightRead(
        id=insight.id,
        insight_type=insight.insight_type,
        category=insight.category,
        severity=insight.severity,
        status=insight.status,
        generated_by=insight.generated_by,
        ai_provider=insight.ai_provider,
        ai_model=insight.ai_model,
        ai_interpretation=insight.ai_interpretation,
        title=insight.title,
        summary=insight.summary,
        recommended_investigation=insight.recommended_investigation,
        data_quality_note=insight.data_quality_note,
        confidence_level=insight.confidence_level,
        estimated_production_impact_value=insight.estimated_production_impact_value,
        estimated_production_impact_unit=insight.estimated_production_impact_unit,
        estimated_production_impact_note=insight.estimated_production_impact_note,
        estimated_financial_impact_value=insight.estimated_financial_impact_value,
        estimated_financial_impact_currency=insight.estimated_financial_impact_currency,
        estimated_financial_impact_note=insight.estimated_financial_impact_note,
        well_id=insight.well_id,
        well_code=insight.well.well_id if insight.well else None,
        field_id=insight.field_id,
        field_name=insight.field.name if insight.field else None,
        facility_id=insight.facility_id,
        facility_name=insight.facility.name if insight.facility else None,
        equipment_id=insight.equipment_id,
        equipment_tag=insight.equipment.equipment_tag if insight.equipment else None,
        maintenance_record_id=insight.maintenance_record_id,
        maintenance_work_order_number=(
            insight.maintenance_record.work_order_number if insight.maintenance_record else None
        ),
        production_loss_id=insight.production_loss_id,
        alert_id=insight.alert_id,
        dedup_key=insight.dedup_key,
        occurrence_count=insight.occurrence_count,
        generated_at=insight.generated_at,
        last_confirmed_at=insight.last_confirmed_at,
        is_stale=is_stale,
        days_since_confirmed=days_since_confirmed,
        created_at=insight.created_at,
        updated_at=insight.updated_at,
        disclaimer_text=insight.disclaimer_text,
        evidence=[
            InsightEvidenceRead(
                id=e.id, evidence_type=e.evidence_type, description=e.description,
                source_type=e.source_type, source_id=e.source_id, source_label=e.source_label,
                value=e.value, unit=e.unit,
            )
            for e in insight.evidence
        ],
        feedback=[
            InsightFeedbackRead(
                id=f.id, feedback=f.feedback, notes=f.notes,
                submitted_by_name=f.submitted_by.full_name if f.submitted_by else None,
                submitted_at=f.submitted_at,
            )
            for f in insight.feedback
        ],
    )


def _get_insight_or_404(db: Session, id: int) -> AIRecommendation:
    insight = _insight_query(db).filter(AIRecommendation.id == id).first()
    if insight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    return insight


# ----- List (must come before /{id}) -----


@router.get("", response_model=InsightListResponse)
def list_insights(
    search: str | None = None,
    category: str | None = None,
    insight_type: str | None = None,
    severity: str | None = None,
    confidence_level: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    equipment_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "generated_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InsightListResponse:
    query = _insight_query(db)

    if search:
        like = f"%{search}%"
        query = query.filter((AIRecommendation.title.ilike(like)) | (AIRecommendation.summary.ilike(like)))
    if category:
        query = query.filter(AIRecommendation.category == category)
    if insight_type:
        query = query.filter(AIRecommendation.insight_type == insight_type)
    if severity:
        query = query.filter(AIRecommendation.severity == severity)
    if confidence_level:
        query = query.filter(AIRecommendation.confidence_level == confidence_level)
    if status_filter:
        query = query.filter(AIRecommendation.status == status_filter)
    if field_id:
        query = query.filter(AIRecommendation.field_id == field_id)
    if facility_id:
        query = query.filter(AIRecommendation.facility_id == facility_id)
    if well_id:
        query = query.filter(AIRecommendation.well_id == well_id)
    if equipment_id:
        query = query.filter(AIRecommendation.equipment_id == equipment_id)
    if date_from:
        query = query.filter(AIRecommendation.generated_at >= date_from)
    if date_to:
        # date_to is a calendar date; generated_at is a timestamp, so compare against the start
        # of the following day rather than midnight of date_to itself, or same-day insights
        # generated after midnight would be silently excluded (e.g. date_to=today).
        query = query.filter(AIRecommendation.generated_at < date_to + timedelta(days=1))

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, AIRecommendation.generated_at)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [_build_entry(r, db) for r in records]

    return InsightListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/summary", response_model=InsightSummaryResponse)
def get_insight_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InsightSummaryResponse:
    all_insights = _insight_query(db).all()

    severity_counts = InsightSeverityCounts()
    category_totals: dict[str, int] = {}
    confidence_totals: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    open_count = 0

    for insight in all_insights:
        if hasattr(severity_counts, insight.severity):
            setattr(severity_counts, insight.severity, getattr(severity_counts, insight.severity) + 1)
        if insight.status in OPEN_STATUSES:
            open_count += 1
        category_totals[insight.category] = category_totals.get(insight.category, 0) + 1
        if insight.confidence_level in confidence_totals:
            confidence_totals[insight.confidence_level] += 1

    recent = sorted(all_insights, key=lambda i: i.generated_at, reverse=True)[:10]
    critical = [i for i in all_insights if i.severity == "critical" and i.status in OPEN_STATUSES][:10]

    return InsightSummaryResponse(
        total=len(all_insights),
        open_count=open_count,
        by_severity=severity_counts,
        by_category=[InsightCategoryCount(category=c, count=n) for c, n in sorted(category_totals.items())],
        by_confidence=confidence_totals,
        recent=[_build_entry(i, db) for i in recent],
        critical=[_build_entry(i, db) for i in critical],
        disclaimer_text=INSIGHT_DISCLAIMER,
    )


@router.post("/run", response_model=InsightRunResponse)
def trigger_insight_run(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
) -> InsightRunResponse:
    result = run_insight_engine(db)
    record_audit_event(
        db, current_user, AuditAction.AI_INSIGHT_RUN, "ai_insight",
        details=f"Ran insight engine — created {result.created}, updated {result.updated}",
    )
    return InsightRunResponse(
        created=result.created,
        updated=result.updated,
        by_category={k: InsightRunCategoryResult(**v) for k, v in result.by_category.items()},
        disclaimer_text=result.disclaimer_text,
    )


@router.post("/assistant", response_model=AssistantAnswerResponse)
def ask_assistant(
    payload: AssistantQuestionRequest,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
    _rate_limited: User = Depends(rate_limiter("assistant", limit=10, window_seconds=60)),
) -> AssistantAnswerResponse:
    if not payload.question.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="question is required")
    answer = answer_question(db, payload.question, provider)
    return AssistantAnswerResponse(
        answer=answer.answer,
        sources=[
            SourceReferenceRead(source_type=s.source_type, source_id=s.source_id, source_label=s.source_label)
            for s in answer.sources
        ],
        answered_by=answer.answered_by,
        disclaimer_text=INSIGHT_DISCLAIMER,
    )


@router.post("/investigate", response_model=InvestigationResponse)
def investigate_event(
    payload: InvestigateRequest,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
    _rate_limited: User = Depends(rate_limiter("investigate", limit=10, window_seconds=60)),
) -> InvestigationResponse:
    if payload.insight_id is None and payload.well_id is None and payload.equipment_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One of insight_id, well_id, or equipment_id is required",
        )
    try:
        result = investigate(
            db, provider, insight_id=payload.insight_id, well_id=payload.well_id, equipment_id=payload.equipment_id
        )
    except InvestigationTargetNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return InvestigationResponse(
        event=result.event,
        impact_summary=result.impact_summary,
        primary_contributor=result.primary_contributor,
        possible_causes=[PossibleCauseRead(description=c.description, evidence_type=c.evidence_type) for c in result.possible_causes],
        ai_assessment=result.ai_assessment,
        confidence_level=result.confidence_level,
        recommended_investigation=result.recommended_investigation,
        sources=[SourceReferenceRead(source_type=s.source_type, source_id=s.source_id, source_label=s.source_label) for s in result.sources],
        answered_by=result.answered_by,
        disclaimer_text=INSIGHT_DISCLAIMER,
    )


@router.get("/daily-brief", response_model=DailyBriefResponse)
def get_daily_brief(
    narrative: bool = False,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(get_current_user),
) -> DailyBriefResponse:
    now = datetime.now(timezone.utc)
    period_start, period_end = _latest_period(db)

    kpis = get_production_kpis(db=db, current_user=current_user)
    equipment_issues = get_equipment_issues(db=db, current_user=current_user, limit=10)
    maintenance_dashboard = get_maintenance_dashboard(db=db, current_user=current_user)

    losses = db.query(ProductionLoss).filter(ProductionLoss.loss_date >= period_start).all()
    lost_oil = sum(loss.estimated_bopd_lost or 0 for loss in losses)
    lost_revenue = sum(loss.estimated_revenue_impact or 0 for loss in losses if loss.currency == "USD")

    open_insights = db.query(AIRecommendation).filter(AIRecommendation.status.in_(OPEN_STATUSES)).all()
    critical_insights = [i for i in open_insights if i.severity == "critical"]

    sections = [
        DailyBriefSection(
            title="1. Production Performance",
            summary=f"Oil: {kpis.total_oil_bbl:,.1f} bbl, Gas: {kpis.total_gas_mscf:,.1f} mscf, {kpis.producing_wells_count} producing wells.",
            items=[f"Target variance: {kpis.target_variance_pct:.1f}%"] if kpis.target_variance_pct is not None else [],
        ),
        DailyBriefSection(
            title="2. Critical Equipment",
            summary=f"{len(equipment_issues.items)} equipment item(s) currently flagged for attention.",
            items=[f"{i.equipment_tag}: {i.detail}" for i in equipment_issues.items[:5]],
        ),
        DailyBriefSection(
            title="3. Maintenance Issues",
            summary=f"{maintenance_dashboard.status_counts.emergency_count} emergency, {maintenance_dashboard.status_counts.computed_overdue_count} overdue work orders.",
            items=[],
        ),
        DailyBriefSection(
            title="4. Production Loss",
            summary=f"Estimated {lost_oil:,.1f} bbl lost this period across {len(losses)} event(s).",
            items=[],
        ),
        DailyBriefSection(
            title="5. Economic Impact",
            summary=f"Estimated USD {lost_revenue:,.0f} in lost revenue this period (USD-denominated events only).",
            items=[],
        ),
        DailyBriefSection(
            title="6. Critical Alerts & Insights",
            summary=f"{len(critical_insights)} open critical insight(s).",
            items=[i.title for i in critical_insights[:5]],
        ),
        DailyBriefSection(
            title="7. Top Investigation Priorities",
            summary="Highest-severity open insights requiring engineering review.",
            items=[i.title for i in sorted(open_insights, key=lambda x: x.severity)[:5]],
        ),
    ]

    narrative_text = None
    if narrative:
        interpretation = provider.interpret(
            StructuredPrompt(
                task="Write a concise narrative summary of today's operations brief for an engineering audience.",
                data={s.title: s.summary for s in sections},
                time_period=f"{period_start} to {period_end}",
            )
        )
        narrative_text = interpretation.text

    return DailyBriefResponse(
        generated_at=now,
        period_label=f"{period_start} to {period_end}",
        sections=sections,
        narrative=narrative_text,
        disclaimer_text=INSIGHT_DISCLAIMER,
    )


@router.get("/daily-brief/export")
def export_daily_brief_pdf(
    narrative: bool = False,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    brief = get_daily_brief(narrative=narrative, db=db, provider=provider, current_user=current_user)
    pdf_bytes = build_daily_brief_pdf(
        generated_at=brief.generated_at,
        period_label=brief.period_label,
        sections=[s.model_dump() for s in brief.sections],
        narrative=brief.narrative,
        disclaimer_text=brief.disclaimer_text,
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=og-pios-daily-brief.pdf"},
    )


@router.get("/management-summary", response_model=ManagementSummaryResponse)
def get_management_summary(
    narrative: bool = False,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(get_current_user),
) -> ManagementSummaryResponse:
    now = datetime.now(timezone.utc)
    period_start, period_end = _latest_period(db)

    open_insights = db.query(AIRecommendation).filter(AIRecommendation.status.in_(OPEN_STATUSES)).all()
    critical_insights = sorted(
        [i for i in open_insights if i.severity == "critical"], key=lambda x: x.generated_at, reverse=True
    )

    losses = db.query(ProductionLoss).filter(ProductionLoss.loss_date >= period_start).all()
    lost_revenue = sum(loss.estimated_revenue_impact or 0 for loss in losses if loss.currency == "USD")
    top_loss = max(losses, key=lambda loss: loss.estimated_revenue_impact or 0, default=None)

    maintenance_high_cost = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.start_date.isnot(None), MaintenanceRecord.start_date >= period_start)
        .order_by(MaintenanceRecord.cost.desc().nullslast())
        .first()
    )

    sections = [
        ManagementSummarySection(
            question="What changed?",
            answer=f"{len(open_insights)} open insight(s) as of {period_end}, {len(critical_insights)} of them critical.",
        ),
        ManagementSummarySection(
            question="What matters most?",
            answer=(
                "; ".join(i.title for i in critical_insights[:3]) if critical_insights else "No critical insights are currently open."
            ),
        ),
        ManagementSummarySection(
            question="Where are the largest risks?",
            answer=(
                f"Highest single production-loss event: {top_loss.cause or 'unspecified cause'}, estimated USD "
                f"{top_loss.estimated_revenue_impact:,.0f}." if top_loss and top_loss.estimated_revenue_impact else
                "No significant single production-loss event stands out this period."
            ),
        ),
        ManagementSummarySection(
            question="Where are the largest production opportunities?",
            answer=f"Estimated USD {lost_revenue:,.0f} in recoverable revenue is tied to production-loss events this period.",
        ),
        ManagementSummarySection(
            question="What has the largest financial impact / what should management investigate?",
            answer=(
                f"Equipment with the highest single maintenance cost this period: {maintenance_high_cost.equipment.equipment_tag}, USD {maintenance_high_cost.cost:,.0f}."
                if maintenance_high_cost and maintenance_high_cost.cost else
                "No single maintenance event stands out as a high-cost outlier this period."
            ),
        ),
    ]

    narrative_text = None
    if narrative:
        interpretation = provider.interpret(
            StructuredPrompt(
                task="Write a concise management-oriented narrative summary from these already-computed answers.",
                data={s.question: s.answer for s in sections},
                time_period=f"{period_start} to {period_end}",
            )
        )
        narrative_text = interpretation.text

    return ManagementSummaryResponse(
        generated_at=now,
        period_label=f"{period_start} to {period_end}",
        sections=sections,
        narrative=narrative_text,
        disclaimer_text=INSIGHT_DISCLAIMER,
    )


# ----- Single-insight routes -----


@router.get("/{id}", response_model=InsightRead)
def get_insight(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InsightRead:
    return _build_entry(_get_insight_or_404(db, id), db)


@router.put("/{id}/status", response_model=InsightRead)
def update_insight_status(
    id: int,
    payload: InsightStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> InsightRead:
    insight = _get_insight_or_404(db, id)
    insight.status = payload.status
    db.commit()
    db.refresh(insight)
    return _build_entry(_get_insight_or_404(db, id), db)


@router.post("/{id}/feedback", response_model=InsightRead, status_code=status.HTTP_201_CREATED)
def submit_insight_feedback(
    id: int,
    payload: InsightFeedbackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> InsightRead:
    insight = _get_insight_or_404(db, id)
    db.add(
        AIInsightFeedback(
            insight_id=insight.id,
            feedback=payload.feedback,
            notes=payload.notes,
            submitted_by_id=current_user.id,
            submitted_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return _build_entry(_get_insight_or_404(db, id), db)


@router.post("/{id}/interpret", response_model=InterpretResponse)
def interpret_insight(
    id: int,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider_dependency),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
    _rate_limited: User = Depends(rate_limiter("interpret", limit=10, window_seconds=60)),
) -> InterpretResponse:
    insight = _get_insight_or_404(db, id)

    prompt = StructuredPrompt(
        task=f"Interpret this {insight.category} insight for an engineering/operations audience: {insight.title}",
        data={
            "summary": insight.summary,
            "severity": insight.severity,
            "confidence_level": insight.confidence_level,
            "evidence": [e.description for e in insight.evidence],
            "recommended_investigation": insight.recommended_investigation or "none recorded",
        },
        data_sources=[e.source_label for e in insight.evidence if e.source_label],
    )
    interpretation = provider.interpret(prompt)

    insight.ai_interpretation = interpretation.text
    insight.ai_provider = interpretation.provider
    insight.ai_model = interpretation.model
    db.commit()

    return InterpretResponse(
        insight_id=insight.id,
        interpretation=interpretation.text,
        provider=interpretation.provider,
        model=interpretation.model,
        disclaimer_text=INSIGHT_DISCLAIMER,
    )
