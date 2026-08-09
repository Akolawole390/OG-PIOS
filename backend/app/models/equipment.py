from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Equipment(Base, TimestampMixin):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_tag: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    model: Mapped[str | None] = mapped_column(String(255))
    serial_number: Mapped[str | None] = mapped_column(String(255))
    installation_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="operational", nullable=False)
    health_score: Mapped[float | None] = mapped_column(Float)

    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))

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

    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    equipment: Mapped["Equipment"] = relationship(back_populates="readings")


class MaintenanceRecord(Base, TimestampMixin):
    __tablename__ = "maintenance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    maintenance_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    start_date: Mapped[date | None] = mapped_column(Date)
    completion_date: Mapped[date | None] = mapped_column(Date)
    cost: Mapped[float | None] = mapped_column(Float)

    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    equipment: Mapped["Equipment"] = relationship(back_populates="maintenance_records")

    technician_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class DowntimeEvent(Base, TimestampMixin):
    __tablename__ = "downtime_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))

    well_id: Mapped[int | None] = mapped_column(ForeignKey("wells.id"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id"))
