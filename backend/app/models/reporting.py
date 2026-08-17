from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Report(Base, TimestampMixin):
    """A saved Reports-module report — like `Scenario` (What-If Simulator), `results` is a
    **frozen snapshot** computed at save/regenerate time, not recomputed on every read. This
    table existed since the initial scaffold (`report_type`/`period_start`/`period_end`/
    `file_path`/`generated_by_id`, zero rows ever written) — the same "modeled but never
    populated" situation `Alert`/`AIRecommendation`/`OperatingCost`/`ProductionLoss` were in
    before their modules extended them in place; this module does the same rather than adding a
    new table. `file_path` stays unused/nullable — exports are generated on demand from `results`,
    never written to disk.
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)

    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # {field_id, facility_id, well_id, equipment_id, commodity, maintenance_type, alert_severity,
    # production_loss_category, scenario_id} — all optional. See
    # services/report_calculations.py for the authoritative shape.
    filters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Selected section keys for this report_type; empty/absent means "all default sections."
    sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Frozen snapshot of the computed report. Null until the first generate/regenerate.
    results: Mapped[dict | None] = mapped_column(JSON)
    calculation_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    file_path: Mapped[str | None] = mapped_column(String(500))
    generated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    generated_by: Mapped["User"] = relationship()


class AuditLog(Base, TimestampMixin):
    """Enterprise-style audit trail — existed since the initial scaffold (`action`,
    `entity_type`, `entity_id`, `details`, `user_id`), zero rows ever written anywhere (grepped
    to confirm). The same "modeled but never populated" situation `Alert`/`AIRecommendation`/
    `OperatingCost`/`ProductionLoss`/`Report` were all in before their modules populated them —
    the Administration module does the same here. Written only via
    `services/audit.py::record_audit_event()`, never directly, and never for passwords, API
    keys, or other secrets.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(100), index=True)
    entity_id: Mapped[int | None] = mapped_column()
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    # Structured, non-secret extra context (e.g. {"from_role": "Analyst", "to_role": "Management"}
    # for a role change) — named metadata_json, not metadata, since SQLAlchemy's declarative
    # base reserves the plain `metadata` attribute name for its own use.
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User | None"] = relationship()
