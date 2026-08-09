from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class ProductionLoss(Base, TimestampMixin):
    __tablename__ = "production_losses"

    id: Mapped[int] = mapped_column(primary_key=True)
    loss_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    estimated_bopd_lost: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_revenue_impact: Mapped[float | None] = mapped_column(Float)
    cause: Mapped[str | None] = mapped_column(String(255))

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
    downtime_event_id: Mapped[int | None] = mapped_column(ForeignKey("downtime_events.id"))


class OperatingCost(Base, TimestampMixin):
    __tablename__ = "operating_costs"

    id: Mapped[int] = mapped_column(primary_key=True)
    cost_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)

    field_id: Mapped[int | None] = mapped_column(ForeignKey("fields.id"))
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))


class CommodityPrice(Base, TimestampMixin):
    __tablename__ = "commodity_prices"

    id: Mapped[int] = mapped_column(primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    commodity: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
