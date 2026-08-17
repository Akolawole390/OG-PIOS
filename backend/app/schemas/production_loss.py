from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

# Closed vocabulary — the spec has no "allow more in future" language for this field (unlike
# Maintenance's maintenance_type), so it's a strict Literal at the write boundary.
ProductionLossCategory = Literal[
    "equipment_failure",
    "scheduled_maintenance",
    "reservoir",
    "weather",
    "operational",
    "market_curtailment",
    "other",
]


class ProductionLossBase(BaseModel):
    loss_date: date
    category: ProductionLossCategory | None = None
    cause: str | None = None
    downtime_hours: float | None = None
    well_id: int | None = None
    equipment_id: int | None = None
    downtime_event_id: int | None = None
    maintenance_record_id: int | None = None
    # Manual overrides — normally left unset so the server auto-derives them from resolved
    # ProductionTarget/ProductionRecord/CommodityPrice data; supplying a value here takes
    # precedence (e.g. a historical backfill entry predating target data).
    estimated_bopd_lost: float | None = None
    estimated_mscf_lost: float | None = None
    estimated_revenue_impact: float | None = None
    currency: str | None = None


class ProductionLossCreate(ProductionLossBase):
    pass


class ProductionLossUpdate(BaseModel):
    loss_date: date | None = None
    category: ProductionLossCategory | None = None
    cause: str | None = None
    downtime_hours: float | None = None
    well_id: int | None = None
    equipment_id: int | None = None
    downtime_event_id: int | None = None
    maintenance_record_id: int | None = None
    estimated_bopd_lost: float | None = None
    estimated_mscf_lost: float | None = None
    estimated_revenue_impact: float | None = None
    currency: str | None = None


class ProductionLossEntry(BaseModel):
    id: int
    loss_date: date
    category: str | None = None
    cause: str | None = None
    downtime_hours: float | None = None

    well_id: int | None = None
    well_code: str | None = None
    equipment_id: int | None = None
    equipment_tag: str | None = None
    equipment_name: str | None = None
    field_id: int | None = None
    field_name: str | None = None
    facility_id: int | None = None
    facility_name: str | None = None
    downtime_event_id: int | None = None
    maintenance_record_id: int | None = None
    work_order_number: str | None = None

    estimated_bopd_lost: float | None = None
    estimated_mscf_lost: float | None = None
    estimated_revenue_impact: float | None = None
    currency: str | None = None
    # Resolved, not stored — transparency on what price(s) actually drove the revenue figure.
    oil_price_per_bbl: float | None = None
    gas_price_per_mscf: float | None = None

    disclaimer_text: str
    created_at: datetime
    updated_at: datetime


class ProductionLossListResponse(BaseModel):
    items: list[ProductionLossEntry]
    total: int
    page: int
    page_size: int


# ----- Dashboard / aggregates -----


class ProductionLossCategoryCount(BaseModel):
    category: str
    count: int


class ProductionLossDashboardResponse(BaseModel):
    event_count: int
    total_oil_bopd_lost: float
    total_gas_mscfd_lost: float
    total_revenue_impact: float
    avg_downtime_hours: float
    by_category: list[ProductionLossCategoryCount]
    disclaimer_text: str


class ProductionLossScopeBar(BaseModel):
    key: str
    label: str
    count: int
    total_oil_bopd_lost: float
    total_gas_mscfd_lost: float
    total_revenue_impact: float


class ProductionLossByScopeResponse(BaseModel):
    group_by: str
    bars: list[ProductionLossScopeBar]


class ProductionLossTrendPoint(BaseModel):
    month: str
    total_oil_bopd_lost: float
    total_gas_mscfd_lost: float
    total_revenue_impact: float
    event_count: int


class ProductionLossTrendResponse(BaseModel):
    points: list[ProductionLossTrendPoint]
