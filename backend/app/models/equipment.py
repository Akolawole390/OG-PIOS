from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Equipment(Base, TimestampMixin):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    installation_date: Mapped[date | None] = mapped_column(Date)
    commissioning_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="operational", nullable=False, index=True)
    operating_hours: Mapped[float | None] = mapped_column(Float)
    next_maintenance_due: Mapped[date | None] = mapped_column(Date)
    health_score: Mapped[float | None] = mapped_column(Float)
    maintenance_frequency_days: Mapped[int | None] = mapped_column(Integer)

    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"), index=True)

    facility: Mapped["Facility | None"] = relationship()
    well: Mapped["Well | None"] = relationship()

    readings: Mapped[list["EquipmentReading"]] = relationship(back_populates="equipment")
    maintenance_records: Mapped[list["MaintenanceRecord"]] = relationship(
        back_populates="equipment"
    )


class EquipmentReading(Base, TimestampMixin):
    __tablename__ = "equipment_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    reading_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    parameter: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))

    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False, index=True)
    equipment: Mapped["Equipment"] = relationship(back_populates="readings")


class MaintenanceRecord(Base, TimestampMixin):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_order_number: Mapped[str | None] = mapped_column(String(20), unique=True)
    maintenance_type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))

    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_completion_date: Mapped[date | None] = mapped_column(Date)
    # start_date/completion_date are the ACTUAL dates work began/finished — this semantics
    # predates this module and is relied on by app/services/equipment_health.py's
    # maintenance-history factor and app/routers/equipment.py's last-maintenance-date lookup;
    # do not repurpose them as "planned" dates.
    start_date: Mapped[date | None] = mapped_column(Date)
    completion_date: Mapped[date | None] = mapped_column(Date)

    # labor_cost/parts_cost/contractor_cost/other_cost are the only cost inputs; `cost` is
    # always server-recomputed as their sum (None if all four are None) — see
    # app/routers/maintenance.py's create/update handlers.
    labor_cost: Mapped[float | None] = mapped_column(Float)
    parts_cost: Mapped[float | None] = mapped_column(Float)
    contractor_cost: Mapped[float | None] = mapped_column(Float)
    other_cost: Mapped[float | None] = mapped_column(Float)
    cost: Mapped[float | None] = mapped_column(Float)

    # Work-order-level downtime estimate — deliberately separate from the equipment health
    # score's downtime factor, which is sourced from DowntimeEvent instead (see
    # app/services/equipment_health.py).
    downtime_hours: Mapped[float | None] = mapped_column(Float)

    failure_cause: Mapped[str | None] = mapped_column(String(500))
    corrective_action: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False, index=True)
    equipment: Mapped["Equipment"] = relationship(back_populates="maintenance_records")

    technician_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    technician: Mapped["User | None"] = relationship()


class DowntimeEvent(Base, TimestampMixin):
    __tablename__ = "downtime_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
