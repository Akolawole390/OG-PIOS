from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

# maintenance_type is deliberately open (plain str, not a Literal) — the spec explicitly says
# "allow the system to support additional types in the future," unlike status/priority below.
# Canonical suggestions surfaced in the frontend's <datalist>, mirroring Equipment.equipment_type:
MAINTENANCE_TYPE_SUGGESTIONS = [
    "preventive",
    "corrective",
    "emergency",
    "predictive",
    "inspection",
    "calibration",
    "routine",
]

MaintenancePriority = Literal["critical", "high", "medium", "low"]
MaintenanceStatus = Literal[
    "scheduled", "open", "in_progress", "waiting_for_parts", "completed", "cancelled", "overdue"
]


class MaintenanceBase(BaseModel):
    maintenance_type: str
    priority: MaintenancePriority = "medium"
    status: MaintenanceStatus = "scheduled"
    description: str | None = None
    planned_start_date: date | None = None
    planned_completion_date: date | None = None
    start_date: date | None = None
    completion_date: date | None = None
    technician_id: int | None = None
    labor_cost: float | None = None
    parts_cost: float | None = None
    contractor_cost: float | None = None
    other_cost: float | None = None
    downtime_hours: float | None = None
    failure_cause: str | None = None
    corrective_action: str | None = None
    notes: str | None = None


class MaintenanceCreate(MaintenanceBase):
    equipment_id: int


class MaintenanceUpdate(BaseModel):
    equipment_id: int | None = None
    maintenance_type: str | None = None
    priority: MaintenancePriority | None = None
    status: MaintenanceStatus | None = None
    description: str | None = None
    planned_start_date: date | None = None
    planned_completion_date: date | None = None
    start_date: date | None = None
    completion_date: date | None = None
    technician_id: int | None = None
    labor_cost: float | None = None
    parts_cost: float | None = None
    contractor_cost: float | None = None
    other_cost: float | None = None
    downtime_hours: float | None = None
    failure_cause: str | None = None
    corrective_action: str | None = None
    notes: str | None = None


class MaintenanceEntry(MaintenanceBase):
    # status is deliberately widened to `str` on read (not the strict MaintenanceStatus
    # Literal used for writes) — validation belongs at the write boundary, matching
    # EquipmentRead's identical reasoning.
    status: str

    id: int
    work_order_number: str | None = None
    equipment_id: int
    equipment_tag: str
    equipment_name: str
    equipment_type: str
    field_id: int | None = None
    field_name: str | None = None
    facility_id: int | None = None
    facility_name: str | None = None
    well_id: int | None = None
    well_code: str | None = None
    technician_name: str | None = None
    cost: float | None = None
    created_at: datetime
    updated_at: datetime


class MaintenanceListResponse(BaseModel):
    items: list[MaintenanceEntry]
    total: int
    page: int
    page_size: int


# ----- Dashboard / aggregates -----


class MaintenanceStatusCounts(BaseModel):
    total: int
    scheduled: int
    open: int
    in_progress: int
    waiting_for_parts: int
    completed: int
    cancelled: int
    overdue: int
    emergency_count: int
    computed_overdue_count: int


class EquipmentRequiringMaintenanceItem(BaseModel):
    equipment_id: int
    equipment_tag: str
    equipment_name: str
    next_maintenance_due: date
    days_from_today: int


class MaintenanceDashboardResponse(BaseModel):
    status_counts: MaintenanceStatusCounts
    total_cost: float
    total_downtime_hours: float
    equipment_requiring_maintenance: list[EquipmentRequiringMaintenanceItem]


class MaintenanceScopeBar(BaseModel):
    key: str
    label: str
    count: int
    total_cost: float
    total_downtime_hours: float


class MaintenanceByScopeResponse(BaseModel):
    group_by: str
    bars: list[MaintenanceScopeBar]


class MaintenanceCostTrendPoint(BaseModel):
    month: str
    total_cost: float
    record_count: int


class MaintenanceCostTrendResponse(BaseModel):
    points: list[MaintenanceCostTrendPoint]


class MaintenanceScheduleItem(BaseModel):
    source: Literal["work_order", "equipment"]
    id: int
    label: str
    equipment_id: int
    equipment_tag: str
    due_date: date
    status: str | None = None
    priority: str | None = None
    days_from_today: int


class MaintenanceScheduleResponse(BaseModel):
    reference_date: date
    lookahead_days: int
    overdue: list[MaintenanceScheduleItem]
    due_today: list[MaintenanceScheduleItem]
    upcoming: list[MaintenanceScheduleItem]


# ----- Reliability (equipment-scoped, exposed via /equipment/{id}/reliability) -----


class ReliabilityMetricsRead(BaseModel):
    equipment_id: int
    mtbf_hours: float | None = None
    mtbf_data_sufficient: bool
    mttr_hours: float | None = None
    mttr_data_sufficient: bool
    availability_pct: float | None = None
    failure_count: int
    failure_count_annualized: float | None = None
    observation_period_hours: float
    disclaimer_text: str
    assumptions: list[str]
    computed_at: datetime
