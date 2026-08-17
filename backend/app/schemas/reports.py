from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

# Exactly 4 report types — see services/report_calculations.py's REPORT_TYPES for the
# authoritative section list per type.
ReportType = Literal["daily_operations", "weekly_production", "monthly_management", "what_if_scenario"]


class ReportFilters(BaseModel):
    """The full section-4 filter set. Every field optional; absence means "no restriction" for
    that dimension. `commodity` narrows which commodity is emphasized in trend/chart sections
    (BOE/combined figures always reflect both, since BOE is definitionally a combined unit)."""

    date_from: date | None = None
    date_to: date | None = None
    field_id: int | None = None
    facility_id: int | None = None
    well_id: int | None = None
    equipment_id: int | None = None
    commodity: str | None = None
    maintenance_type: str | None = None
    alert_severity: str | None = None
    production_loss_category: str | None = None
    # What-If Scenario Report only — selects the one saved Scenario to embed.
    scenario_id: int | None = None


class ReportTypeInfo(BaseModel):
    id: str
    label: str
    sections: list[str]


class ReportTypesResponse(BaseModel):
    types: list[ReportTypeInfo]


class ReportCreate(BaseModel):
    report_type: ReportType
    name: str
    description: str | None = None
    filters: ReportFilters
    sections: list[str] | None = None
    narrative: bool = False


class ReportUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    filters: ReportFilters | None = None
    sections: list[str] | None = None


class ReportListItem(BaseModel):
    id: int
    report_type: str
    name: str
    description: str | None
    created_by_id: int
    created_by_name: str | None
    period_start: datetime | None
    period_end: datetime | None
    calculation_version: str
    status: str
    last_generated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    has_results: bool


class ReportRead(ReportListItem):
    filters: dict
    sections: list[str]
    # Per Decision 3: a plain JSON dict, not ~30 fully-typed nested schema classes — each of the
    # 4 report types has a structurally different section set, and every section already embeds
    # an upstream-typed schema's own model_dump(mode="json"). See lib/api.ts (frontend) for the
    # hand-written TypeScript shape each report_type actually produces.
    results: dict | None
    disclaimer_text: str


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    total: int
    page: int
    page_size: int


class PreviewRequest(BaseModel):
    report_type: ReportType
    filters: ReportFilters
    sections: list[str] | None = None
    narrative: bool = False


class PreviewResponse(BaseModel):
    report_type: str
    calculation_version: str
    results: dict


ExportFormat = Literal["csv", "pdf"]
