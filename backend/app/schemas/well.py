from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class FieldSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class FacilitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    facility_type: str | None = None
    field: FieldSummary


class FacilityRead(BaseModel):
    id: int
    name: str
    facility_type: str | None = None
    field_id: int
    field_name: str


class WellBase(BaseModel):
    well_id: str
    name: str
    well_type: str | None = None
    status: str = "active"
    artificial_lift_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    completion_date: date | None = None
    completion_type: str | None = None
    total_depth_ft: float | None = None


class WellCreate(WellBase):
    facility_id: int


class WellUpdate(BaseModel):
    well_id: str | None = None
    name: str | None = None
    well_type: str | None = None
    status: str | None = None
    artificial_lift_type: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    completion_date: date | None = None
    completion_type: str | None = None
    total_depth_ft: float | None = None
    facility_id: int | None = None


class WellRead(WellBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    facility_id: int
    facility: FacilitySummary
    created_at: datetime
    updated_at: datetime


class WellListResponse(BaseModel):
    items: list[WellRead]
    total: int
    page: int
    page_size: int


class ProductionRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_date: date
    oil_bopd: float
    gas_mscfd: float
    water_bwpd: float
    water_cut_pct: float | None = None
    gor: float | None = None
    choke_size: float | None = None


class PressureRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_date: date
    wellhead_pressure: float | None = None
    tubing_pressure: float | None = None
    casing_pressure: float | None = None
    flowline_pressure: float | None = None


class DowntimeEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    start_time: datetime
    end_time: datetime | None = None
    reason: str | None = None


class DowntimeSummary(BaseModel):
    event_count: int
    total_hours: float


class DowntimeListResponse(BaseModel):
    events: list[DowntimeEventRead]
    summary: DowntimeSummary


class MaintenanceRecordRead(BaseModel):
    id: int
    maintenance_type: str
    status: str
    description: str | None = None
    start_date: date | None = None
    completion_date: date | None = None
    cost: float | None = None
    equipment_tag: str
    equipment_type: str


class MaintenanceSummary(BaseModel):
    record_count: int
    total_cost: float
    total_downtime_hours: float = 0.0


class MaintenanceListResponse(BaseModel):
    records: list[MaintenanceRecordRead]
    summary: MaintenanceSummary
