from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Scenario(Base, TimestampMixin):
    """A saved What-If Simulator scenario — a user's hypothesis-testing artifact, never a
    record of real operational activity. `assumptions`/`results` use `sqlalchemy.JSON`
    (portable, not Postgres-only `JSONB`, matching this project's stated schema-portability
    convention for building against SQLite in tests) — this is the first model to actually use
    that column type, for exactly the structured-but-non-relational data it's meant for.

    `results` is a **frozen snapshot** computed at save/run time, not recomputed on every read —
    the literal reading of "store the assumptions and calculation version used... important for
    reproducibility." A saved scenario shows exactly what was seen when it was saved; `POST
    /what-if/scenarios/{id}/rerun` recomputes against current data on demand, deliberately not
    on every GET.
    """

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    baseline_date_from: Mapped[date] = mapped_column(Date, nullable=False)
    baseline_date_to: Mapped[date] = mapped_column(Date, nullable=False)
    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"))
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))

    # {production_change_pct, downtime_change_pct, production_loss_reduction_pct,
    # operating_cost_change_pct, energy_cost_change_pct, maintenance_cost_change_pct,
    # oil_price_override, oil_price_change_pct, gas_price_override, gas_price_change_pct} — all
    # keys optional, absent means "no change." See services/whatif_calculations.py for the
    # authoritative shape and every formula that consumes it.
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Frozen snapshot: {baseline: {...}, scenario: {...}, comparison: [...], guardrail_flags:
    # [...]}. Null until the first run.
    results: Mapped[dict | None] = mapped_column(JSON)
    calculation_version: Mapped[str] = mapped_column(String(20), nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped["User"] = relationship()
    field: Mapped["Field | None"] = relationship()
    facility: Mapped["Facility | None"] = relationship()
    well: Mapped["Well | None"] = relationship()
    equipment: Mapped["Equipment | None"] = relationship()
