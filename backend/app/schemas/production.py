from datetime import date
from typing import Literal

from pydantic import BaseModel

# ----- Composite production record -----


class ProductionRecordCreate(BaseModel):
    well_id: int
    record_date: date
    oil_bopd: float = 0
    gas_mscfd: float = 0
    water_bwpd: float = 0
    choke_size: float | None = None
    wellhead_pressure: float | None = None
    tubing_pressure: float | None = None
    casing_pressure: float | None = None
    flowline_pressure: float | None = None
    wellhead_temperature: float | None = None


class ProductionRecordUpdate(BaseModel):
    # well_id / record_date are intentionally immutable: moving a record risks colliding
    # with the (well_id, record_date) unique constraint or orphaning sibling pressure/
    # temperature rows. Move a record by deleting and recreating it instead.
    oil_bopd: float | None = None
    gas_mscfd: float | None = None
    water_bwpd: float | None = None
    choke_size: float | None = None
    wellhead_pressure: float | None = None
    tubing_pressure: float | None = None
    casing_pressure: float | None = None
    flowline_pressure: float | None = None
    wellhead_temperature: float | None = None


class ProductionRecordRead(BaseModel):
    id: int
    record_date: date
    well_id: int
    well_code: str
    well_name: str
    facility_id: int
    facility_name: str
    field_id: int
    field_name: str
    oil_bopd: float
    gas_mscfd: float
    water_bwpd: float
    water_cut_pct: float | None = None
    gor: float | None = None
    boe: float
    choke_size: float | None = None
    wellhead_pressure: float | None = None
    tubing_pressure: float | None = None
    casing_pressure: float | None = None
    flowline_pressure: float | None = None
    wellhead_temperature: float | None = None
    downtime_hours: float = 0
    warnings: list[str] | None = None


class ProductionListResponse(BaseModel):
    items: list[ProductionRecordRead]
    total: int
    page: int
    page_size: int


# ----- Production targets -----


class ProductionTargetCreate(BaseModel):
    well_id: int
    effective_date: date
    oil_target_bopd: float | None = None
    gas_target_mscfd: float | None = None
    water_target_bwpd: float | None = None


class ProductionTargetUpdate(BaseModel):
    effective_date: date | None = None
    oil_target_bopd: float | None = None
    gas_target_mscfd: float | None = None
    water_target_bwpd: float | None = None


class ProductionTargetRead(BaseModel):
    id: int
    well_id: int
    well_code: str
    well_name: str
    effective_date: date
    oil_target_bopd: float | None = None
    gas_target_mscfd: float | None = None
    water_target_bwpd: float | None = None


# ----- KPIs -----


class ProductionKpis(BaseModel):
    total_oil_bbl: float
    total_gas_mscf: float
    total_water_bbl: float
    avg_daily_oil_bopd: float
    avg_daily_gas_mscfd: float
    avg_daily_water_bwpd: float
    avg_water_cut_pct: float | None = None
    avg_gor: float | None = None
    boe: float
    boe_gas_factor: float
    producing_wells_count: int
    target_oil_bopd: float | None = None
    target_variance_pct: float | None = None
    reference_date: date | None = None
    days_in_range: int


# ----- Trends / scope charts -----


class TrendResponse(BaseModel):
    metric: str
    points: list[dict[str, float | str | None]]


class ScopeBar(BaseModel):
    key: str
    label: str
    oil_bopd: float
    gas_mscfd: float
    water_bwpd: float
    boe: float


class ByScopeResponse(BaseModel):
    group_by: str
    bars: list[ScopeBar]


class ActualVsTargetPoint(BaseModel):
    record_date: date
    actual_oil_bopd: float
    target_oil_bopd: float | None = None


class ActualVsTargetResponse(BaseModel):
    points: list[ActualVsTargetPoint]


# ----- Active production issues -----


class WellIssueSummary(BaseModel):
    well_id: int
    well_code: str
    well_name: str
    detail: str


class ProductionIssuesResponse(BaseModel):
    reference_date: date | None = None
    down_wells: list[WellIssueSummary]
    zero_production_wells: list[WellIssueSummary]


# ----- CSV import -----

ImportRowStatus = Literal["valid", "warning", "duplicate", "invalid"]
ImportRowAction = Literal["create", "overwrite", "skip"]


class ImportRowResult(BaseModel):
    row_number: int
    status: ImportRowStatus
    well_id: str
    record_date: str | None
    parsed: dict[str, float | str | None]
    messages: list[str]
    existing_record_id: int | None = None


class ImportPreviewResponse(BaseModel):
    total_rows: int
    valid_count: int
    warning_count: int
    duplicate_count: int
    invalid_count: int
    rows: list[ImportRowResult]


class ImportConfirmRow(BaseModel):
    row_number: int
    well_id: str
    record_date: str
    oil_bopd: float = 0
    gas_mscfd: float = 0
    water_bwpd: float = 0
    choke_size: float | None = None
    wellhead_pressure: float | None = None
    tubing_pressure: float | None = None
    casing_pressure: float | None = None
    flowline_pressure: float | None = None
    wellhead_temperature: float | None = None
    action: ImportRowAction = "create"


class ImportConfirmRequest(BaseModel):
    rows: list[ImportConfirmRow]


class ImportRejectedRow(BaseModel):
    row_number: int
    well_id: str
    record_date: str
    messages: list[str]


class ImportConfirmResponse(BaseModel):
    created: int
    updated: int
    skipped: int
    rejected: list[ImportRejectedRow]
