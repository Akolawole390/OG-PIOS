from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class ProductionLoss(Base, TimestampMixin):
    __tablename__ = "production_losses"

    id: Mapped[int] = mapped_column(primary_key=True)
    loss_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # estimated_bopd_lost/estimated_mscf_lost/estimated_revenue_impact are server-computed
    # (max(expected - actual, 0) from ProductionTarget vs ProductionRecord, priced via
    # CommodityPrice) when a well_id/loss_date resolve real data — see
    # app/services/production_loss_calculations.py and app/routers/production_loss.py. A
    # caller may also supply any of the three directly (e.g. a historical backfill entry),
    # in which case the supplied value is respected instead of being auto-derived. Never
    # independently fabricated when neither path applies — stays None.
    estimated_bopd_lost: Mapped[float | None] = mapped_column(Float)
    estimated_mscf_lost: Mapped[float | None] = mapped_column(Float)
    estimated_revenue_impact: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(10))

    category: Mapped[str | None] = mapped_column(String(50))
    cause: Mapped[str | None] = mapped_column(String(255))
    downtime_hours: Mapped[float | None] = mapped_column(Float)

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), index=True)
    downtime_event_id: Mapped[int | None] = mapped_column(ForeignKey("downtime_events.id"))
    maintenance_record_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_records.id"))

    well: Mapped["Well | None"] = relationship()
    equipment: Mapped["Equipment | None"] = relationship()
    downtime_event: Mapped["DowntimeEvent | None"] = relationship()
    maintenance_record: Mapped["MaintenanceRecord | None"] = relationship()


class OperatingCost(Base, TimestampMixin):
    __tablename__ = "operating_costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    cost_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

    description: Mapped[str | None] = mapped_column(String(500))
    cost_period: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"), index=True)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"), index=True)

    field: Mapped["Field | None"] = relationship()
    facility: Mapped["Facility | None"] = relationship()
    well: Mapped["Well | None"] = relationship()
    equipment: Mapped["Equipment | None"] = relationship()


class CommodityPrice(Base, TimestampMixin):
    __tablename__ = "commodity_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    commodity: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
