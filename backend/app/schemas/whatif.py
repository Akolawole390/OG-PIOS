from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.economics import MoneyByCurrency

# ----- Shared building blocks -----


class BaselineConfigSchema(BaseModel):
    date_from: date
    date_to: date
    field_id: int | None = None
    facility_id: int | None = None
    well_id: int | None = None
    equipment_id: int | None = None


class ScenarioAssumptionsSchema(BaseModel):
    """Every field optional — absent means "no change" for that lever. Mirrors
    services/whatif_calculations.ScenarioAssumptions field-for-field; see that module's
    docstring for the exact formula each field feeds. Hard/soft guardrail checking happens in
    the router via validate_assumptions(), not here, so a merely-unusual value is never silently
    rejected at the schema layer."""

    production_change_pct: float | None = None
    downtime_change_pct: float | None = None
    production_loss_reduction_pct: float | None = None
    operating_cost_change_pct: float | None = None
    energy_cost_change_pct: float | None = None
    maintenance_cost_change_pct: float | None = None
    oil_price_override: float | None = None
    oil_price_change_pct: float | None = None
    gas_price_override: float | None = None
    gas_price_change_pct: float | None = None


class GuardrailFlagRead(BaseModel):
    field: str
    message: str
    severity: Literal["error", "warning"]


class BaselineMetricsRead(BaseModel):
    period_start: date
    period_end: date
    period_days: int

    oil_bbl: float
    gas_mscf: float
    boe: float

    oil_price: float | None
    oil_price_currency: str | None
    gas_price: float | None
    gas_price_currency: str | None

    revenue: list[MoneyByCurrency]
    operating_cost: list[MoneyByCurrency]
    maintenance_cost: list[MoneyByCurrency]
    total_cost: list[MoneyByCurrency]

    lost_oil_bbl: float
    lost_gas_mscf: float
    production_loss_revenue: list[MoneyByCurrency]
    downtime_hours: float

    margin: list[MoneyByCurrency]
    margin_currency_mismatch: bool

    data_sufficient: bool
    missing_data_note: str | None


class ScenarioMetricsRead(BaseModel):
    oil_bbl: float
    gas_mscf: float
    boe: float

    oil_price: float | None
    oil_price_currency: str | None
    gas_price: float | None
    gas_price_currency: str | None

    revenue: list[MoneyByCurrency]
    operating_cost: list[MoneyByCurrency]
    maintenance_cost: list[MoneyByCurrency]
    total_cost: list[MoneyByCurrency]

    lost_oil_bbl: float
    lost_gas_mscf: float
    production_loss_revenue: list[MoneyByCurrency]
    downtime_hours: float

    margin: list[MoneyByCurrency]
    margin_currency_mismatch: bool

    # Always labeled "potential"/"estimated" — never a guaranteed outcome, kept separate from
    # oil_bbl/gas_mscf above so nothing is double-counted. See whatif_calculations.py docstring.
    recovered_downtime_hours: float
    recovered_production_bbl: float
    potential_loss_reduction_oil_bbl: float
    potential_loss_reduction_gas_mscf: float
    potential_loss_reduction_revenue: list[MoneyByCurrency]
    potential_cost_saving: list[MoneyByCurrency]


class ComparisonRowRead(BaseModel):
    metric: str
    baseline: float
    scenario: float
    difference: float
    pct_change: float | None
    currency: str | None
    direction: Literal["positive", "negative", "neutral"]


class ScenarioResultsRead(BaseModel):
    baseline: BaselineMetricsRead
    scenario: ScenarioMetricsRead
    comparison: list[ComparisonRowRead]
    guardrail_flags: list[GuardrailFlagRead]


# ----- Scenario CRUD -----


class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None
    baseline: BaselineConfigSchema
    assumptions: ScenarioAssumptionsSchema


class ScenarioUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    baseline: BaselineConfigSchema | None = None
    assumptions: ScenarioAssumptionsSchema | None = None


class ScenarioListItem(BaseModel):
    id: int
    name: str
    description: str | None
    created_by_id: int
    created_by_name: str | None

    baseline_date_from: date
    baseline_date_to: date
    field_id: int | None
    field_name: str | None
    facility_id: int | None
    facility_name: str | None
    well_id: int | None
    well_code: str | None
    equipment_id: int | None
    equipment_tag: str | None

    calculation_version: str
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
    has_results: bool


class ScenarioRead(ScenarioListItem):
    assumptions: ScenarioAssumptionsSchema
    results: ScenarioResultsRead | None
    disclaimer_text: str


class ScenarioListResponse(BaseModel):
    items: list[ScenarioListItem]
    total: int
    page: int
    page_size: int


# ----- Preview / Compare / Sensitivity / Interpret -----


class PreviewRequest(BaseModel):
    baseline: BaselineConfigSchema
    assumptions: ScenarioAssumptionsSchema


class PreviewResponse(BaseModel):
    results: ScenarioResultsRead
    calculation_version: str
    disclaimer_text: str


class CompareRequest(BaseModel):
    scenario_ids: list[int]
    narrative: bool = False


class ScenarioCompareEntry(BaseModel):
    id: int
    name: str
    results: ScenarioResultsRead | None


class CompareResponse(BaseModel):
    scenarios: list[ScenarioCompareEntry]
    ai_narrative: str | None = None
    disclaimer_text: str


class SensitivityRequest(BaseModel):
    baseline: BaselineConfigSchema
    base_assumptions: ScenarioAssumptionsSchema
    variable: str
    values: list[float]


class SensitivityPointRead(BaseModel):
    variable_value: float
    recovered_production_bbl: float
    recovered_downtime_hours: float
    revenue_impact: list[MoneyByCurrency]
    margin_impact: list[MoneyByCurrency]


class SensitivityResponse(BaseModel):
    baseline: BaselineMetricsRead
    variable: str
    points: list[SensitivityPointRead]
    disclaimer_text: str


class InterpretResponse(BaseModel):
    scenario_id: int
    interpretation: str
    provider: str
    model: str | None
    disclaimer_text: str
