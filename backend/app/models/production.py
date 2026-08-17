from datetime import date

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin


class ProductionRecord(Base, TimestampMixin):
    __tablename__ = "production_records"
    __table_args__ = (UniqueConstraint("well_id", "record_date", name="uq_production_records_well_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    oil_bopd: Mapped[float] = mapped_column(Float, default=0)
    gas_mscfd: Mapped[float] = mapped_column(Float, default=0)
    water_bwpd: Mapped[float] = mapped_column(Float, default=0)
    water_cut_pct: Mapped[float | None] = mapped_column(Float)
    gor: Mapped[float | None] = mapped_column(Float)
    choke_size: Mapped[float | None] = mapped_column(Float)

    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False)
    well: Mapped["Well"] = relationship(back_populates="production_records")


class PressureRecord(Base, TimestampMixin):
    __tablename__ = "pressure_records"
    __table_args__ = (UniqueConstraint("well_id", "record_date", name="uq_pressure_records_well_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    wellhead_pressure: Mapped[float | None] = mapped_column(Float)
    tubing_pressure: Mapped[float | None] = mapped_column(Float)
    casing_pressure: Mapped[float | None] = mapped_column(Float)
    flowline_pressure: Mapped[float | None] = mapped_column(Float)

    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False)
    well: Mapped["Well"] = relationship(back_populates="pressure_records")


class TemperatureRecord(Base, TimestampMixin):
    __tablename__ = "temperature_records"
    __table_args__ = (UniqueConstraint("well_id", "record_date", name="uq_temperature_records_well_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    record_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    wellhead_temperature: Mapped[float | None] = mapped_column(Float)

    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False)
    well: Mapped["Well"] = relationship(back_populates="temperature_records")


class ProductionTarget(Base, TimestampMixin):
    __tablename__ = "production_targets"
    __table_args__ = (UniqueConstraint("well_id", "effective_date", name="uq_production_targets_well_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    oil_target_bopd: Mapped[float | None] = mapped_column(Float)
    gas_target_mscfd: Mapped[float | None] = mapped_column(Float)
    water_target_bwpd: Mapped[float | None] = mapped_column(Float)

    well_id: Mapped[int] = mapped_column(ForeignKey("wells.id"), nullable=False)
    well: Mapped["Well"] = relationship()
