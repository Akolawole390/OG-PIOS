from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Fixed 5-level severity scale per the Alerts module spec — a strict Literal on write, matching
# every other closed-vocabulary field in this codebase (e.g. MaintenanceRecord.priority).
AlertSeverity = Literal["critical", "high", "medium", "low", "informational"]

# The 5 domain groupings from the module spec's "ALERT TYPES" section.
AlertCategory = Literal["production", "equipment", "maintenance", "production_loss", "economics"]

# DB column stays named `state` (minimal diff from the pre-existing Alert model); API/docs call
# it "status" throughout, matching the module spec's own wording.
AlertStatus = Literal["new", "acknowledged", "investigating", "resolved", "dismissed"]


class AlertEntry(BaseModel):
    id: int
    alert_type: str
    category: AlertCategory
    source_module: str
    severity: str
    status: str
    title: str
    description: str
    recommended_action: str | None
    notes: str | None

    well_id: int | None
    well_code: str | None
    field_id: int | None
    field_name: str | None
    facility_id: int | None
    facility_name: str | None
    equipment_id: int | None
    equipment_tag: str | None
    maintenance_record_id: int | None
    maintenance_work_order_number: str | None
    production_loss_id: int | None

    threshold_value: float | None
    current_value: float | None
    unit: str | None

    dedup_key: str
    occurrence_count: int

    triggered_at: datetime
    last_detected_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    acknowledged_by_name: str | None
    resolved_by_name: str | None

    created_at: datetime
    updated_at: datetime

    disclaimer_text: str


class AlertListResponse(BaseModel):
    items: list[AlertEntry]
    total: int
    page: int
    page_size: int


class AlertCreate(BaseModel):
    category: AlertCategory
    alert_type: str
    severity: AlertSeverity
    title: str
    description: str
    recommended_action: str | None = None
    notes: str | None = None
    well_id: int | None = None
    field_id: int | None = None
    facility_id: int | None = None
    equipment_id: int | None = None
    maintenance_record_id: int | None = None
    production_loss_id: int | None = None
    threshold_value: float | None = None
    current_value: float | None = None
    unit: str | None = None


class AlertUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: AlertSeverity | None = None
    recommended_action: str | None = None
    notes: str | None = None


class AlertStatusChangeRequest(BaseModel):
    note: str | None = None


class AlertHistoryEntry(BaseModel):
    id: int
    from_state: str | None
    to_state: str
    note: str | None
    changed_by_name: str | None
    changed_at: datetime


class AlertHistoryResponse(BaseModel):
    items: list[AlertHistoryEntry]


class SeverityCounts(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    informational: int = 0


class StatusCounts(BaseModel):
    new: int = 0
    acknowledged: int = 0
    investigating: int = 0
    resolved: int = 0
    dismissed: int = 0


class CategoryCount(BaseModel):
    category: str
    count: int


class ScopeCount(BaseModel):
    key: str
    label: str
    count: int


class AlertSummaryResponse(BaseModel):
    total: int
    open_count: int
    by_severity: SeverityCounts
    by_status: StatusCounts
    by_category: list[CategoryCount]
    by_field: list[ScopeCount]
    by_equipment: list[ScopeCount]
    recent: list[AlertEntry]
    disclaimer_text: str


class AlertRunCategoryResult(BaseModel):
    created: int
    updated: int


class AlertRunResponse(BaseModel):
    created: int
    updated: int
    auto_resolved: int
    by_category: dict[str, AlertRunCategoryResult]
    disclaimer_text: str
