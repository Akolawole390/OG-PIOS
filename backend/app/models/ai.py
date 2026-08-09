from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

DEFAULT_AI_DISCLAIMER = (
    "AI-generated estimate requiring engineering review; not a guaranteed conclusion."
)


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="new", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))


class AIPrediction(Base, TimestampMixin):
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
    __tablename__ = "ai_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    possible_contributors: Mapped[str | None] = mapped_column(Text)
    recommended_investigation: Mapped[str | None] = mapped_column(Text)
    potential_impact: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    disclaimer_text: Mapped[str] = mapped_column(
        Text, nullable=False, default=DEFAULT_AI_DISCLAIMER
    )

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    ai_prediction_id: Mapped[int | None] = mapped_column(ForeignKey("ai_predictions.id"))
