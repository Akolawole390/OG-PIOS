from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

DEFAULT_AI_DISCLAIMER = (
    "AI-generated estimate requiring engineering review; not a guaranteed conclusion."
)


class Alert(Base, TimestampMixin):
    """Centralized Alert & Event Intelligence record. Originally a minimal, never-populated
    table (see the Alerts module's docs/data-model.md section) — extended in place rather than
    duplicated, per this project's "don't duplicate existing models" convention. Populating this
    table for the first time also activates equipment_health.py's previously-dormant
    `alarm_frequency` scoring factor (it already queried `Alert.equipment_id`/`triggered_at`,
    but nothing ever wrote a row) — an intentional, self-limiting reuse of an existing signal,
    not a new coupling: `triggered_at` never moves after creation, so an alert ages out of that
    factor's 30-day window regardless of how long it stays open.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)

    alert_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"), index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    maintenance_record_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_records.id"))
    production_loss_id: Mapped[int | None] = mapped_column(ForeignKey("production_losses.id"))

    threshold_value: Mapped[float | None] = mapped_column(Float)
    current_value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))

    # Deduplication key, e.g. "production_below_target:well:42" — see
    # services/alert_rules.py. Indexed (not unique) since resolved/dismissed history for the
    # same key legitimately persists across multiple rows over time.
    dedup_key: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    well: Mapped["Well | None"] = relationship()
    field: Mapped["Field | None"] = relationship()
    facility: Mapped["Facility | None"] = relationship()
    equipment: Mapped["Equipment | None"] = relationship()
    maintenance_record: Mapped["MaintenanceRecord | None"] = relationship()
    production_loss: Mapped["ProductionLoss | None"] = relationship()
    acknowledged_by: Mapped["User | None"] = relationship(foreign_keys=[acknowledged_by_id])
    resolved_by: Mapped["User | None"] = relationship(foreign_keys=[resolved_by_id])
    history: Mapped[list["AlertStatusHistory"]] = relationship(
        back_populates="alert", order_by="AlertStatusHistory.changed_at.desc()"
    )


class AlertStatusHistory(Base):
    """One row per actual Alert state transition (including creation) or note addition — never
    written on a mere rule-run "reaffirm" of an already-open alert (that only bumps
    Alert.occurrence_count/last_detected_at/current_value). Provides the audit trail the
    generic, unused AuditLog model (models/reporting.py) doesn't fit: AuditLog has no per-row
    from/to state or timestamp-per-transition shape, so a dedicated table was added instead of
    force-fitting it.
    """

    __tablename__ = "alert_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    alert: Mapped["Alert"] = relationship(back_populates="history")
    changed_by: Mapped["User | None"] = relationship()


class AIPrediction(Base, TimestampMixin):
    """Genuine forecasting/ML predictions — deliberately left dormant by the AI Insights module
    too, same as it was left dormant by every prior module. AI Insights is an evidence-based
    analysis engine over already-recorded history, not a predictive/forecasting system; nothing
    in that module writes here. Reserved for a future, explicitly-scoped forecasting module.
    """

    __tablename__ = "ai_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_type: Mapped[str] = mapped_column(String(100), nullable=False)
    parameter: Mapped[str] = mapped_column(String(100), nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    model_name: Mapped[str | None] = mapped_column(String(100))

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))


class AIRecommendation(Base, TimestampMixin):
    """Centralized AI Insight record ("Insight" in API/docs; table name kept as originally
    scaffolded, same "keep the DB name, rename in the API" precedent as Alert/`state`). Existed
    since the initial schema with only observation/evidence/possible_contributors/
    recommended_investigation/potential_impact/confidence and zero rows ever written — the same
    "modeled but never populated" situation ProductionLoss/OperatingCost/Alert were in before
    their own modules extended them in place.

    `evidence`/`possible_contributors` (free text) are replaced by the `AIInsightEvidence` child
    table below so fact-vs-hypothesis separation (observed fact / calculated metric /
    correlation / possible contributor) is a data guarantee, not a prose convention a UI has to
    parse. The numeric `confidence` float is replaced by `confidence_level` (high/medium/low,
    computed from evidence-category count) — never a fabricated statistical score. The
    `ai_prediction_id` FK inherited from the original scaffolding is dropped: nothing in this
    module ever writes an AIPrediction row (see its own docstring), so keeping a permanently-null
    FK to a permanently-empty table would be exactly the kind of dead scaffolding this project's
    "don't duplicate/keep unused" convention is meant to eliminate.
    """

    __tablename__ = "ai_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)

    insight_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)
    generated_by: Mapped[str] = mapped_column(String(20), default="rule_based", nullable=False)
    ai_provider: Mapped[str | None] = mapped_column(String(50))
    ai_model: Mapped[str | None] = mapped_column(String(100))

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_investigation: Mapped[str | None] = mapped_column(Text)
    data_quality_note: Mapped[str | None] = mapped_column(Text)
    # Populated only by the opt-in POST /ai-insights/{id}/interpret action (never by
    # run_insight_engine, which is always 100% deterministic) — an AI-authored paragraph
    # phrasing this insight's already-computed summary/evidence, never inventing new figures.
    ai_interpretation: Mapped[str | None] = mapped_column(Text)

    confidence_level: Mapped[str] = mapped_column(String(10), nullable=False)

    estimated_production_impact_value: Mapped[float | None] = mapped_column(Float)
    estimated_production_impact_unit: Mapped[str | None] = mapped_column(String(20))
    estimated_production_impact_note: Mapped[str | None] = mapped_column(Text)
    estimated_financial_impact_value: Mapped[float | None] = mapped_column(Float)
    estimated_financial_impact_currency: Mapped[str | None] = mapped_column(String(10))
    estimated_financial_impact_note: Mapped[str | None] = mapped_column(Text)

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"), index=True)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    maintenance_record_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_records.id"))
    production_loss_id: Mapped[int | None] = mapped_column(ForeignKey("production_losses.id"))
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))

    # Deduplication key, e.g. "production_decline:well:42" — see services/insight_engine.py.
    # Matched only against non-dismissed (new/reviewed) rows on regeneration; unlike Alert there
    # is no auto-dismiss branch — an insight remains valid historical commentary even after its
    # triggering condition clears, so dismissal stays a 100% manual action.
    dedup_key: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    disclaimer_text: Mapped[str] = mapped_column(
        Text, nullable=False, default=DEFAULT_AI_DISCLAIMER
    )

    well: Mapped["Well | None"] = relationship()
    field: Mapped["Field | None"] = relationship()
    facility: Mapped["Facility | None"] = relationship()
    equipment: Mapped["Equipment | None"] = relationship()
    maintenance_record: Mapped["MaintenanceRecord | None"] = relationship()
    production_loss: Mapped["ProductionLoss | None"] = relationship()
    alert: Mapped["Alert | None"] = relationship()
    evidence: Mapped[list["AIInsightEvidence"]] = relationship(
        back_populates="insight", order_by="AIInsightEvidence.id"
    )
    feedback: Mapped[list["AIInsightFeedback"]] = relationship(
        back_populates="insight", order_by="AIInsightFeedback.submitted_at.desc()"
    )


class AIInsightEvidence(Base):
    """One row per fact/metric/correlation/contributor backing an Insight — the data-level
    mechanism for the fact-vs-hypothesis UI separation (see AIRecommendation's docstring). This
    is deliberately a different, citation-oriented shape from AuditLog.entity_type/entity_id
    (models/reporting.py): an audit-log row records *who did what*; this records *what fact
    backs this claim, and where to verify it* — not a missed reuse of that convention.
    """

    __tablename__ = "ai_insight_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    insight_id: Mapped[int] = mapped_column(ForeignKey("ai_recommendations.id"), nullable=False, index=True)

    # observed_fact / calculated_metric / correlation / possible_contributor
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # well / production_record / equipment / maintenance_record / production_loss / alert /
    # operating_cost / computed (the last for aggregate evidence with no single source row, e.g.
    # "3-month average decline rate" — source_id stays null in that case).
    source_type: Mapped[str | None] = mapped_column(String(30))
    source_id: Mapped[int | None] = mapped_column(Integer)
    source_label: Mapped[str | None] = mapped_column(String(200))

    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(20))

    insight: Mapped["AIRecommendation"] = relationship(back_populates="evidence")


class AIInsightFeedback(Base):
    """User feedback on an Insight's usefulness/correctness — storage only, per the module's
    explicit scope: never used to auto-train or auto-tune anything.
    """

    __tablename__ = "ai_insight_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    insight_id: Mapped[int] = mapped_column(ForeignKey("ai_recommendations.id"), nullable=False, index=True)

    # useful / not_useful / incorrect / needs_review
    feedback: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    submitted_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    insight: Mapped["AIRecommendation"] = relationship(back_populates="feedback")
    submitted_by: Mapped["User"] = relationship()
