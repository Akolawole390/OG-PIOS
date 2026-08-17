from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EquipmentStatus = Literal[
    "operating", "standby", "maintenance", "failed", "decommissioned", "unknown"
]


class EquipmentBase(BaseModel):
    equipment_tag: str
    name: str
    equipment_type: str
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    installation_date: date | None = None
    commissioning_date: date | None = None
    description: str | None = None
    status: EquipmentStatus = "unknown"
    operating_hours: float | None = None
    next_maintenance_due: date | None = None


class EquipmentCreate(EquipmentBase):
    facility_id: int | None = None
    well_id: int | None = None


class EquipmentUpdate(BaseModel):
    equipment_tag: str | None = None
    name: str | None = None
    equipment_type: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    installation_date: date | None = None
    commissioning_date: date | None = None
    description: str | None = None
    status: EquipmentStatus | None = None
    operating_hours: float | None = None
    next_maintenance_due: date | None = None
    facility_id: int | None = None
    well_id: int | None = None


class EquipmentRead(EquipmentBase):
    # status is deliberately widened to `str` (not the strict EquipmentStatus Literal used for
    # writes) so a read never fails to serialize because of a legacy/unexpected stored value —
    # validation belongs at the write boundary (EquipmentCreate/EquipmentUpdate), not on read.
    status: str

    id: int
    facility_id: int | None = None
    well_id: int | None = None
    field_id: int | None = None
    field_name: str | None = None
    facility_name: str | None = None
    well_code: str | None = None
    health_score: float | None = None
    health_band: str | None = None
    last_maintenance_date: date | None = None
    created_at: datetime
    updated_at: datetime


class EquipmentListResponse(BaseModel):
    items: list[EquipmentRead]
    total: int
    page: int
    page_size: int


# ----- Health -----


class EquipmentHealthFactor(BaseModel):
    factor: str
    deduction: float
    detail: str


class EquipmentHealthRead(BaseModel):
    equipment_id: int
    score: float
    band: str
    starting_score: float
    factors: list[EquipmentHealthFactor]
    disclaimer_text: str
    computed_at: datetime


# ----- Readings -----


class EquipmentReadingCreate(BaseModel):
    reading_at: datetime
    parameter: str
    value: float
    unit: str | None = None


class EquipmentReadingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reading_at: datetime
    parameter: str
    value: float
    unit: str | None = None


class EquipmentReadingListResponse(BaseModel):
    items: list[EquipmentReadingRead]
    total: int


# ----- Dashboard / aggregates -----


class EquipmentStatusCounts(BaseModel):
    total: int
    operating: int
    standby: int
    maintenance: int
    failed: int
    decommissioned: int
    unknown: int
    attention_count: int


class EquipmentHealthDistributionBucket(BaseModel):
    band: str
    count: int


class EquipmentHealthDistribution(BaseModel):
    buckets: list[EquipmentHealthDistributionBucket]
    unscored_count: int


class EquipmentDashboardResponse(BaseModel):
    status_counts: EquipmentStatusCounts
    health_distribution: EquipmentHealthDistribution


class EquipmentScopeBar(BaseModel):
    key: str
    label: str
    count: int
    avg_health_score: float | None = None


class EquipmentByScopeResponse(BaseModel):
    group_by: str
    bars: list[EquipmentScopeBar]


class EquipmentInvestigationItem(BaseModel):
    id: int
    equipment_tag: str
    name: str
    equipment_type: str
    status: str
    health_score: float | None = None
    health_band: str | None = None
    detail: str


class EquipmentIssuesResponse(BaseModel):
    items: list[EquipmentInvestigationItem]
