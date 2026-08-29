from datetime import datetime
from typing import Literal

from pydantic import BaseModel

InsightCategory = Literal["production", "equipment", "maintenance", "production_loss", "economics", "cross_domain", "optimization"]

# Lighter than Alert's 5-state pipeline, deliberately: an insight is analytical commentary to
# review, not a problem to resolve. Dismissal is always a 100% manual action — the engine never
# auto-dismisses on condition-clear (see insight_engine.py's module docstring).
InsightStatus = Literal["new", "reviewed", "dismissed"]

# Never a fabricated statistical score — derived from evidence-category count, see
# insight_calculations.derive_confidence_level.
ConfidenceLevel = Literal["high", "medium", "low"]

EvidenceType = Literal["observed_fact", "calculated_metric", "correlation", "possible_contributor"]

FeedbackType = Literal["useful", "not_useful", "incorrect", "needs_review"]


class InsightEvidenceRead(BaseModel):
    id: int
    evidence_type: EvidenceType
    description: str
    source_type: str | None
    source_id: int | None
    source_label: str | None
    value: float | None
    unit: str | None


class InsightFeedbackRead(BaseModel):
    id: int
    feedback: FeedbackType
    notes: str | None
    submitted_by_name: str | None
    submitted_at: datetime


class InsightRead(BaseModel):
    id: int
    insight_type: str
    category: InsightCategory
    severity: str
    status: InsightStatus
    generated_by: str
    ai_provider: str | None
    ai_model: str | None
    ai_interpretation: str | None

    title: str
    summary: str
    recommended_investigation: str | None
    data_quality_note: str | None
    confidence_level: ConfidenceLevel

    estimated_production_impact_value: float | None
    estimated_production_impact_unit: str | None
    estimated_production_impact_note: str | None
    estimated_financial_impact_value: float | None
    estimated_financial_impact_currency: str | None
    estimated_financial_impact_note: str | None

    well_id: int | None
    well_code: str | None
    field_id: int | None
    field_name: str | None
    facility_id: int | None
    facility_name: str | None
    equipment_id: int | None
    equipment_tag: str | None
    maintenance_record_id: int | None
    maintenance_work_order_number: str | None
    production_loss_id: int | None
    alert_id: int | None

    dedup_key: str
    occurrence_count: int

    generated_at: datetime
    last_confirmed_at: datetime
    is_stale: bool
    days_since_confirmed: int

    created_at: datetime
    updated_at: datetime

    disclaimer_text: str
    evidence: list[InsightEvidenceRead]
    feedback: list[InsightFeedbackRead]


class InsightListResponse(BaseModel):
    items: list[InsightRead]
    total: int
    page: int
    page_size: int


class InsightStatusUpdateRequest(BaseModel):
    status: Literal["reviewed", "dismissed"]


class InsightFeedbackCreate(BaseModel):
    feedback: FeedbackType
    notes: str | None = None


class InsightRunCategoryResult(BaseModel):
    created: int
    updated: int


class InsightRunResponse(BaseModel):
    created: int
    updated: int
    by_category: dict[str, InsightRunCategoryResult]
    disclaimer_text: str


class InterpretResponse(BaseModel):
    insight_id: int
    interpretation: str
    provider: str
    model: str | None
    disclaimer_text: str


class SourceReferenceRead(BaseModel):
    source_type: str
    source_id: int | None
    source_label: str


class AssistantQuestionRequest(BaseModel):
    question: str


class AssistantAnswerResponse(BaseModel):
    answer: str
    sources: list[SourceReferenceRead]
    answered_by: Literal["deterministic", "ai"]
    disclaimer_text: str


class InsightSeverityCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    informational: int = 0


class InsightCategoryCount(BaseModel):
    category: str
    count: int


class InsightSummaryResponse(BaseModel):
    total: int
    open_count: int
    by_severity: InsightSeverityCounts
    by_category: list[InsightCategoryCount]
    by_confidence: dict[str, int]
    recent: list[InsightRead]
    critical: list[InsightRead]
    disclaimer_text: str


class DailyBriefSection(BaseModel):
    title: str
    summary: str
    items: list[str]


class DailyBriefResponse(BaseModel):
    generated_at: datetime
    period_label: str
    sections: list[DailyBriefSection]
    narrative: str | None
    disclaimer_text: str


class ManagementSummarySection(BaseModel):
    question: str
    answer: str


class ManagementSummaryResponse(BaseModel):
    generated_at: datetime
    period_label: str
    sections: list[ManagementSummarySection]
    narrative: str | None
    disclaimer_text: str


class InvestigateRequest(BaseModel):
    insight_id: int | None = None
    well_id: int | None = None
    equipment_id: int | None = None


class PossibleCauseRead(BaseModel):
    description: str
    evidence_type: EvidenceType


class InvestigationResponse(BaseModel):
    event: str
    impact_summary: str
    primary_contributor: str | None
    possible_causes: list[PossibleCauseRead]
    ai_assessment: str
    confidence_level: ConfidenceLevel
    recommended_investigation: str
    sources: list[SourceReferenceRead]
    answered_by: Literal["deterministic", "ai"]
    disclaimer_text: str
