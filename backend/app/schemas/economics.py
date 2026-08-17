from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# Fixed 2-currency scope per the spec ("Support: USD, NGN") — not an "allow more" vocabulary,
# unlike category below, so this is a strict Literal rather than free text.
Currency = Literal["USD", "NGN"]

# category stays a free string (open vocabulary, "allow future expansion" per the spec) — this
# is the canonical suggestion list surfaced via the frontend's <datalist>, mirroring
# Maintenance's maintenance_type / Equipment's equipment_type open-vocabulary pattern.
COST_CATEGORY_SUGGESTIONS = [
    "Production",
    "Maintenance",
    "Energy",
    "Chemicals",
    "Labour",
    "Contractor",
    "Logistics",
    "Utilities",
    "Facility",
    "Equipment",
    "Other",
]


class MoneyByCurrency(BaseModel):
    """The one shared building block every Cost & Revenue aggregate response uses — amounts
    are always grouped by currency, never blended, since no exchange rate is invented
    anywhere in this codebase (see services/economics_calculations.py)."""

    currency: str
    amount: float


class OperatingCostBase(BaseModel):
    cost_date: date
    category: str
    amount: float = Field(ge=0)
    currency: Currency = "USD"
    description: str | None = None
    cost_period: str | None = None
    source: str | None = None
    notes: str | None = None
    field_id: int | None = None
    facility_id: int | None = None
    well_id: int | None = None
    equipment_id: int | None = None


class OperatingCostCreate(OperatingCostBase):
    pass


class OperatingCostUpdate(BaseModel):
    cost_date: date | None = None
    category: str | None = None
    amount: float | None = Field(default=None, ge=0)
    currency: Currency | None = None
    description: str | None = None
    cost_period: str | None = None
    source: str | None = None
    notes: str | None = None
    field_id: int | None = None
    facility_id: int | None = None
    well_id: int | None = None
    equipment_id: int | None = None


class OperatingCostEntry(BaseModel):
    # currency is deliberately widened to `str` on read (not the strict Currency Literal used
    # for writes) — validation belongs at the write boundary, matching EquipmentRead's/
    # MaintenanceEntry's identical reasoning.
    currency: str

    id: int
    cost_date: date
    category: str
    amount: float
    description: str | None = None
    cost_period: str | None = None
    source: str | None = None
    notes: str | None = None
    field_id: int | None = None
    field_name: str | None = None
    facility_id: int | None = None
    facility_name: str | None = None
    well_id: int | None = None
    well_code: str | None = None
    equipment_id: int | None = None
    equipment_tag: str | None = None
    created_at: datetime
    updated_at: datetime


class OperatingCostListResponse(BaseModel):
    items: list[OperatingCostEntry]
    total: int
    page: int
    page_size: int


# ----- Cost & Revenue analytics -----


class ProductionTotals(BaseModel):
    oil_bbl: float
    gas_mscf: float
    boe: float


class RevenueSection(BaseModel):
    oil: list[MoneyByCurrency]
    gas: list[MoneyByCurrency]
    total: list[MoneyByCurrency]


class CostSection(BaseModel):
    operating: list[MoneyByCurrency]
    maintenance: list[MoneyByCurrency]
    energy: list[MoneyByCurrency]
    other: list[MoneyByCurrency]
    total: list[MoneyByCurrency]


class EconomicsSection(BaseModel):
    margin: list[MoneyByCurrency]
    cost_per_bbl: list[MoneyByCurrency]
    cost_per_boe: list[MoneyByCurrency]
    revenue_per_bbl: list[MoneyByCurrency]
    revenue_per_boe: list[MoneyByCurrency]
    currency_mismatch: bool


class ProductionLossSection(BaseModel):
    estimated_lost_oil_bbl: float
    estimated_lost_gas_mscf: float
    estimated_lost_revenue: list[MoneyByCurrency]
    downtime_hours: float


class CostRevenueDashboardResponse(BaseModel):
    period_start: date
    period_end: date
    production: ProductionTotals
    revenue: RevenueSection
    costs: CostSection
    economics: EconomicsSection
    production_loss: ProductionLossSection
    disclaimer_text: str


class UnitEconomicsResponse(BaseModel):
    period_start: date
    period_end: date
    production: ProductionTotals
    revenue: RevenueSection
    costs: CostSection
    economics: EconomicsSection
    disclaimer_text: str


class EconomicsScopeRow(BaseModel):
    scope: Literal["field", "well"]
    key: str
    label: str
    oil_bbl: float
    gas_mscf: float
    boe: float
    revenue: list[MoneyByCurrency]
    operating_cost: list[MoneyByCurrency]
    maintenance_cost: float
    production_loss_revenue: list[MoneyByCurrency]
    margin: list[MoneyByCurrency]
    cost_per_bbl: list[MoneyByCurrency]
    revenue_per_bbl: list[MoneyByCurrency]
    currency_mismatch: bool
    # Well-scope only — rule-based classification flags, never an automatic "uneconomic"
    # label. `review_note` carries "Requires further economic review" when data is thin.
    high_production: bool | None = None
    high_cost: bool | None = None
    low_margin: bool | None = None
    high_loss: bool | None = None
    review_note: str | None = None


class EconomicsByScopeResponse(BaseModel):
    scope: str
    rank_by: str
    rows: list[EconomicsScopeRow]
    disclaimer_text: str


class RevenueTrendPoint(BaseModel):
    month: str
    oil_revenue: list[MoneyByCurrency]
    gas_revenue: list[MoneyByCurrency]
    total_revenue: list[MoneyByCurrency]
    revenue_per_bbl: list[MoneyByCurrency]


class RevenueTrendResponse(BaseModel):
    points: list[RevenueTrendPoint]


class CostTrendPoint(BaseModel):
    month: str
    total_cost: list[MoneyByCurrency]
    cost_per_bbl: list[MoneyByCurrency]


class CostTrendResponse(BaseModel):
    points: list[CostTrendPoint]


class MarginTrendPoint(BaseModel):
    month: str
    margin: list[MoneyByCurrency]


class MarginTrendResponse(BaseModel):
    points: list[MarginTrendPoint]


class CostAlert(BaseModel):
    severity: Literal["info", "warning", "critical"]
    category: str
    scope_label: str
    message: str
    detail: str


class CostAlertsResponse(BaseModel):
    alerts: list[CostAlert]
    disclaimer_text: str
