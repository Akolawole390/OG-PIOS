from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Field(Base, TimestampMixin):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))

    facilities: Mapped[list["Facility"]] = relationship(back_populates="field")


class Facility(Base, TimestampMixin):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[str | None] = mapped_column(String(100))

    field_id: Mapped[int] = mapped_column(ForeignKey("fields.id"), nullable=False)
    field: Mapped["Field"] = relationship(back_populates="facilities")

    wells: Mapped[list["Well"]] = relationship(back_populates="facility")


class Well(Base, TimestampMixin):
    __tablename__ = "wells"

    id: Mapped[int] = mapped_column(primary_key=True)
    well_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    well_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    artificial_lift_type: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    facility: Mapped["Facility"] = relationship(back_populates="wells")

    production_records: Mapped[list["ProductionRecord"]] = relationship(back_populates="well")
    pressure_records: Mapped[list["PressureRecord"]] = relationship(back_populates="well")
    temperature_records: Mapped[list["TemperatureRecord"]] = relationship(back_populates="well")
