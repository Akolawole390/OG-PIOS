"""Pure, deterministic calculations for the What-If Simulator.

No DB/ORM/FastAPI imports — every function here takes plain values (or the dataclasses defined
in this file) and returns plain values, so the math is directly unit-testable
(backend/tests/test_whatif_calculations.py) and never touched by an LLM. Mirrors the shape of
services/economics_calculations.py and services/production_loss_calculations.py; reuses
estimate_revenue()/estimate_operating_margin()/compute_per_unit() from the former and
compute_boe() from services/production_calculations.py directly rather than re-deriving them.

Documented formulas (verbatim from the module spec, also mirrored in docs/data-model.md):
    Scenario Production      = Baseline Production x (1 + Production Change %)
    Scenario Revenue         = Scenario Production x Commodity Price
    Scenario Operating Cost  = Baseline Operating Cost x (1 + Cost Change %)
    Scenario Production Loss = Baseline Production Loss x (1 - Loss Reduction %)
    Scenario Operating Margin = Scenario Revenue - Scenario Operating Costs

Two figures are deliberately kept SEPARATE from the scenario production number above, never
folded in (folding either in would double-count the same barrels under two different levers):
  - Estimated Potential Production Recovery FROM DOWNTIME REDUCTION
        = recovered_downtime_hours x (baseline_oil_bbl / (period_days x 24))
  - Estimated Potential Production Recovery FROM PRODUCTION-LOSS REDUCTION
        = baseline_lost_oil_bbl - scenario_lost_oil_bbl  (and the gas equivalent)

Every *_change_pct / *_reduction_pct is optional; absent means "no change" for that lever.
`downtime_change_pct` is the ONE downtime lever (the brief's separate "maintenance downtime
reduction %" is not separately representable — ProductionLoss.downtime_hours doesn't split by
cause — a documented scope simplification, not a fabricated breakdown). If
`energy_cost_change_pct` is supplied, it is applied to the energy slice of operating cost and
`operating_cost_change_pct` to the rest, so the two levers never both touch the same dollars; if
only `operating_cost_change_pct` is supplied, the whole baseline operating cost is adjusted once.

Currency handling matches cost_revenue.py exactly: every money figure here is a
`dict[currency, amount]`, never blended across currencies. Margin is only computed for
currencies present on both sides (via `_margin_by_currency`-equivalent logic); an unmatched cost
currency sets `margin_currency_mismatch=True` rather than silently excluding real cost.

Every figure produced here is a decision-support estimate for engineering/management review,
never a guaranteed outcome or an instruction to change equipment/production/SCADA settings — see
the standing AI/analytics-output guardrail in root CLAUDE.md, which explicitly names the
What-If Simulator.
"""

from dataclasses import dataclass, field
from datetime import date

from app.services.economics_calculations import (
    compute_per_unit,
    estimate_operating_margin,
    estimate_revenue,
)
from app.services.production_calculations import compute_boe

CALCULATION_VERSION = "1.0"

WHATIF_DISCLAIMER = (
    "Deterministic, rule-based estimate computed from recorded production, cost, and "
    "commodity-price data plus the assumptions entered. A planning/decision-support figure, "
    "not a forecast or guaranteed outcome, and not an instruction to change any equipment, "
    "production parameter, or SCADA/DCS setting. Requires engineering/management review before "
    "acting on it."
)

# Every *_change_pct / *_reduction_pct field, mapped to its hard (mathematically-impossible)
# bound as (lower, upper) — None means "no bound on that side". These all multiply a baseline by
# (1 + pct/100) except production_loss_reduction_pct, which uses (1 - pct/100); that is why its
# hard bound sits on the opposite side. Going past a bound would imply negative production, cost,
# downtime, or production loss — literally impossible, not merely unusual.
CHANGE_PCT_HARD_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "production_change_pct": (-100.0, None),
    "downtime_change_pct": (-100.0, None),
    "production_loss_reduction_pct": (None, 100.0),
    "operating_cost_change_pct": (-100.0, None),
    "energy_cost_change_pct": (-100.0, None),
    "maintenance_cost_change_pct": (-100.0, None),
    "oil_price_change_pct": (-100.0, None),
    "gas_price_change_pct": (-100.0, None),
}

PRICE_OVERRIDE_FIELDS = ("oil_price_override", "gas_price_override")


def _combine_money(*dicts: dict[str, float]) -> dict[str, float]:
    combined: dict[str, float] = {}
    for d in dicts:
        for currency, amount in d.items():
            combined[currency] = combined.get(currency, 0.0) + amount
    return combined


def _scale_money(amounts: dict[str, float], factor: float) -> dict[str, float]:
    return {currency: round(amount * factor, 2) for currency, amount in amounts.items()}


def _margin_by_currency(revenue: dict[str, float], cost: dict[str, float]) -> tuple[dict[str, float], bool]:
    matched = set(revenue.keys()) & set(cost.keys())
    unmatched_cost_currencies = set(cost.keys()) - set(revenue.keys())
    mismatch = bool(unmatched_cost_currencies)
    margins = {c: estimate_operating_margin(revenue[c], cost[c]) for c in matched}
    return {c: v for c, v in margins.items() if v is not None}, mismatch


@dataclass
class BaselineMetrics:
    """Computed once, live, from existing OG-PIOS data — never invented. `data_sufficient=False`
    means the caller must show `missing_data_note` instead of any figure derived from it."""

    period_start: date
    period_end: date
    period_days: int

    oil_bbl: float = 0.0
    gas_mscf: float = 0.0
    boe: float = 0.0

    oil_price: float | None = None
    oil_price_currency: str | None = None
    gas_price: float | None = None
    gas_price_currency: str | None = None

    revenue_dict: dict[str, float] = field(default_factory=dict)
    # Oil-only / gas-only slices of revenue_dict, priced day-by-day against real commodity-price
    # history (see cost_revenue.py's _revenue_dicts_for_records) — kept separate from the
    # combined revenue_dict so compute_scenario_metrics can derive a true realized-average price
    # per commodity (see _effective_baseline_unit_price) instead of conflating oil and gas
    # revenue when they share a currency.
    oil_revenue_dict: dict[str, float] = field(default_factory=dict)
    gas_revenue_dict: dict[str, float] = field(default_factory=dict)
    operating_cost_dict: dict[str, float] = field(default_factory=dict)
    energy_cost_dict: dict[str, float] = field(default_factory=dict)
    other_cost_dict: dict[str, float] = field(default_factory=dict)
    maintenance_cost_dict: dict[str, float] = field(default_factory=dict)
    total_cost_dict: dict[str, float] = field(default_factory=dict)

    lost_oil_bbl: float = 0.0
    lost_gas_mscf: float = 0.0
    production_loss_revenue_dict: dict[str, float] = field(default_factory=dict)
    downtime_hours: float = 0.0

    margin_dict: dict[str, float] = field(default_factory=dict)
    margin_currency_mismatch: bool = False

    data_sufficient: bool = True
    missing_data_note: str | None = None


@dataclass
class ScenarioAssumptions:
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

    def as_dict(self) -> dict[str, float]:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "ScenarioAssumptions":
        known = {f: data.get(f) for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)


@dataclass
class ScenarioMetrics:
    oil_bbl: float = 0.0
    gas_mscf: float = 0.0
    boe: float = 0.0

    oil_price: float | None = None
    oil_price_currency: str | None = None
    gas_price: float | None = None
    gas_price_currency: str | None = None

    revenue_dict: dict[str, float] = field(default_factory=dict)
    operating_cost_dict: dict[str, float] = field(default_factory=dict)
    maintenance_cost_dict: dict[str, float] = field(default_factory=dict)
    total_cost_dict: dict[str, float] = field(default_factory=dict)

    lost_oil_bbl: float = 0.0
    lost_gas_mscf: float = 0.0
    production_loss_revenue_dict: dict[str, float] = field(default_factory=dict)
    downtime_hours: float = 0.0

    margin_dict: dict[str, float] = field(default_factory=dict)
    margin_currency_mismatch: bool = False

    # Reported separately, never folded into oil_bbl/gas_mscf above — see module docstring.
    recovered_downtime_hours: float = 0.0
    recovered_production_bbl: float = 0.0
    potential_loss_reduction_oil_bbl: float = 0.0
    potential_loss_reduction_gas_mscf: float = 0.0
    potential_loss_reduction_revenue_dict: dict[str, float] = field(default_factory=dict)
    potential_cost_saving_dict: dict[str, float] = field(default_factory=dict)


@dataclass
class GuardrailFlag:
    field: str
    message: str
    severity: str  # "error" | "warning"


@dataclass
class ComparisonRow:
    metric: str
    baseline: float
    scenario: float
    difference: float
    pct_change: float | None
    currency: str | None
    direction: str  # "positive" | "negative" | "neutral"


@dataclass
class SensitivityPoint:
    variable_value: float
    recovered_production_bbl: float
    recovered_downtime_hours: float
    revenue_impact_dict: dict[str, float]
    margin_impact_dict: dict[str, float]


def validate_assumptions(
    assumptions: ScenarioAssumptions, reasonable_bound_pct: float
) -> list[GuardrailFlag]:
    """Two-tier guardrail check (never a silent rejection):
    - severity="error" flags are mathematically impossible inputs — the router turns any of
      these into a 422, per Decision 3.
    - severity="warning" flags are merely unusual-but-valid inputs (magnitude beyond
      `reasonable_bound_pct`) — still computed and returned, never dropped.
    """
    flags: list[GuardrailFlag] = []
    data = assumptions.as_dict()

    for name, (lower, upper) in CHANGE_PCT_HARD_BOUNDS.items():
        value = data.get(name)
        if value is None:
            continue
        if (lower is not None and value < lower) or (upper is not None and value > upper):
            bound_desc = f"below {lower}" if lower is not None and value < lower else f"above {upper}"
            flags.append(
                GuardrailFlag(
                    field=name,
                    message=f"{name} of {value} is {bound_desc}%, which is mathematically impossible.",
                    severity="error",
                )
            )
            continue
        if abs(value) > reasonable_bound_pct:
            flags.append(
                GuardrailFlag(
                    field=name,
                    message="Scenario is outside configured operating assumptions.",
                    severity="warning",
                )
            )

    for name in PRICE_OVERRIDE_FIELDS:
        value = data.get(name)
        if value is not None and value <= 0:
            flags.append(
                GuardrailFlag(
                    field=name,
                    message=f"{name} must be a positive price.",
                    severity="error",
                )
            )

    return flags


def _effective_price(
    baseline_price: float | None, override: float | None, change_pct: float | None
) -> float | None:
    if override is not None:
        return override
    if baseline_price is None:
        return None
    if change_pct is not None:
        return round(baseline_price * (1 + change_pct / 100), 4)
    return baseline_price


def _effective_baseline_unit_price(
    revenue_dict: dict[str, float], currency: str | None, volume: float, spot_price: float | None
) -> float | None:
    """The price basis scenario math starts from: the true volume-weighted price that actually
    produced this commodity's slice of baseline revenue (priced day-by-day against real
    commodity-price history), NOT the raw spot price on the period's last day — those two can
    diverge whenever the commodity price changed mid-period, which would otherwise make even a
    zero-assumption "scenario" silently disagree with its own baseline. Falls back to the spot
    price when there's no volume/currency to derive a realized average from."""
    if volume and currency and currency in revenue_dict:
        return revenue_dict[currency] / volume
    return spot_price


def compute_scenario_metrics(
    baseline: BaselineMetrics, assumptions: ScenarioAssumptions, boe_gas_factor: float
) -> ScenarioMetrics:
    """Every formula from the module spec's section 4, applied once each — no adjustment is
    ever applied twice (see the energy-cost-vs-operating-cost handling below). `boe_gas_factor`
    must be the same factor used to compute `baseline.boe` (system_settings.get_boe_gas_factor),
    so BOE stays consistent between baseline and scenario."""
    production_factor = 1 + (assumptions.production_change_pct or 0) / 100
    oil_bbl = round(baseline.oil_bbl * production_factor, 2)
    gas_mscf = round(baseline.gas_mscf * production_factor, 2)
    boe = compute_boe(oil_bbl, gas_mscf, boe_gas_factor)

    oil_price_basis = _effective_baseline_unit_price(
        baseline.oil_revenue_dict, baseline.oil_price_currency, baseline.oil_bbl, baseline.oil_price
    )
    gas_price_basis = _effective_baseline_unit_price(
        baseline.gas_revenue_dict, baseline.gas_price_currency, baseline.gas_mscf, baseline.gas_price
    )
    oil_price = _effective_price(
        oil_price_basis, assumptions.oil_price_override, assumptions.oil_price_change_pct
    )
    gas_price = _effective_price(
        gas_price_basis, assumptions.gas_price_override, assumptions.gas_price_change_pct
    )

    oil_revenue_dict: dict[str, float] = {}
    if oil_price is not None and baseline.oil_price_currency:
        oil_revenue_dict[baseline.oil_price_currency] = round(oil_bbl * oil_price, 2)
    gas_revenue_dict: dict[str, float] = {}
    if gas_price is not None and baseline.gas_price_currency:
        gas_revenue_dict[baseline.gas_price_currency] = round(gas_mscf * gas_price, 2)
    revenue_dict = _combine_money(oil_revenue_dict, gas_revenue_dict)

    # Cost: energy gets its own lever without double-applying operating_cost_change_pct
    # (Decision 6) — if energy_cost_change_pct is supplied, the energy slice and the rest of
    # operating cost are scaled independently; otherwise the whole operating cost is scaled once.
    if assumptions.energy_cost_change_pct is not None:
        energy_factor = 1 + assumptions.energy_cost_change_pct / 100
        other_factor = 1 + (assumptions.operating_cost_change_pct or 0) / 100
        operating_cost_dict = _combine_money(
            _scale_money(baseline.energy_cost_dict, energy_factor),
            _scale_money(baseline.other_cost_dict, other_factor),
        )
    else:
        operating_factor = 1 + (assumptions.operating_cost_change_pct or 0) / 100
        operating_cost_dict = _scale_money(baseline.operating_cost_dict, operating_factor)

    maintenance_factor = 1 + (assumptions.maintenance_cost_change_pct or 0) / 100
    maintenance_cost_dict = _scale_money(baseline.maintenance_cost_dict, maintenance_factor)

    total_cost_dict = _combine_money(operating_cost_dict, maintenance_cost_dict)
    potential_cost_saving_dict = {
        c: round(baseline.total_cost_dict.get(c, 0.0) - total_cost_dict.get(c, 0.0), 2)
        for c in set(baseline.total_cost_dict) | set(total_cost_dict)
    }

    # Production loss: Scenario Production Loss = Baseline Production Loss x (1 - Reduction %)
    loss_factor = 1 - (assumptions.production_loss_reduction_pct or 0) / 100
    lost_oil_bbl = round(baseline.lost_oil_bbl * loss_factor, 1)
    lost_gas_mscf = round(baseline.lost_gas_mscf * loss_factor, 1)
    production_loss_revenue_dict = _scale_money(baseline.production_loss_revenue_dict, loss_factor)

    potential_loss_reduction_oil_bbl = round(baseline.lost_oil_bbl - lost_oil_bbl, 1)
    potential_loss_reduction_gas_mscf = round(baseline.lost_gas_mscf - lost_gas_mscf, 1)
    potential_loss_reduction_revenue_dict: dict[str, float] = {}
    if oil_price is not None and baseline.oil_price_currency and potential_loss_reduction_oil_bbl:
        potential_loss_reduction_revenue_dict[baseline.oil_price_currency] = (
            potential_loss_reduction_revenue_dict.get(baseline.oil_price_currency, 0.0)
            + round(potential_loss_reduction_oil_bbl * oil_price, 2)
        )
    if gas_price is not None and baseline.gas_price_currency and potential_loss_reduction_gas_mscf:
        potential_loss_reduction_revenue_dict[baseline.gas_price_currency] = (
            potential_loss_reduction_revenue_dict.get(baseline.gas_price_currency, 0.0)
            + round(potential_loss_reduction_gas_mscf * gas_price, 2)
        )

    # Downtime: one lever (Decision 4). Recovered hours/production are reported separately from
    # oil_bbl/gas_mscf above, never folded in (Decision 5) — avoids double-counting the same
    # barrels against the production_change_pct lever.
    downtime_factor = 1 + (assumptions.downtime_change_pct or 0) / 100
    scenario_downtime_hours = round(baseline.downtime_hours * downtime_factor, 2)
    recovered_downtime_hours = round(baseline.downtime_hours - scenario_downtime_hours, 2)
    hourly_oil_rate = baseline.oil_bbl / (baseline.period_days * 24) if baseline.period_days > 0 else 0.0
    recovered_production_bbl = round(recovered_downtime_hours * hourly_oil_rate, 2)

    margin_dict, margin_currency_mismatch = _margin_by_currency(revenue_dict, total_cost_dict)

    return ScenarioMetrics(
        oil_bbl=oil_bbl,
        gas_mscf=gas_mscf,
        boe=boe,
        oil_price=oil_price,
        oil_price_currency=baseline.oil_price_currency,
        gas_price=gas_price,
        gas_price_currency=baseline.gas_price_currency,
        revenue_dict=revenue_dict,
        operating_cost_dict=operating_cost_dict,
        maintenance_cost_dict=maintenance_cost_dict,
        total_cost_dict=total_cost_dict,
        lost_oil_bbl=lost_oil_bbl,
        lost_gas_mscf=lost_gas_mscf,
        production_loss_revenue_dict=production_loss_revenue_dict,
        downtime_hours=scenario_downtime_hours,
        margin_dict=margin_dict,
        margin_currency_mismatch=margin_currency_mismatch,
        recovered_downtime_hours=recovered_downtime_hours,
        recovered_production_bbl=recovered_production_bbl,
        potential_loss_reduction_oil_bbl=potential_loss_reduction_oil_bbl,
        potential_loss_reduction_gas_mscf=potential_loss_reduction_gas_mscf,
        potential_loss_reduction_revenue_dict=potential_loss_reduction_revenue_dict,
        potential_cost_saving_dict=potential_cost_saving_dict,
    )


def _row(
    metric: str,
    baseline: float,
    scenario: float,
    *,
    currency: str | None = None,
    higher_is_better: bool = True,
) -> ComparisonRow:
    difference = round(scenario - baseline, 4)
    pct_change = round(difference / baseline * 100, 2) if baseline else None
    if difference == 0:
        direction = "neutral"
    elif (difference > 0) == higher_is_better:
        direction = "positive"
    else:
        direction = "negative"
    return ComparisonRow(
        metric=metric,
        baseline=round(baseline, 4),
        scenario=round(scenario, 4),
        difference=difference,
        pct_change=pct_change,
        currency=currency,
        direction=direction,
    )


def build_comparison(baseline: BaselineMetrics, scenario: ScenarioMetrics) -> list[ComparisonRow]:
    """Metric | Baseline | Scenario | Difference | % Change, per the module spec's section 8."""
    rows = [
        _row("Oil Production (bbl)", baseline.oil_bbl, scenario.oil_bbl),
        _row("Gas Production (mscf)", baseline.gas_mscf, scenario.gas_mscf),
        _row("BOE", baseline.boe, scenario.boe),
        _row(
            "Production Loss — Oil (bbl)",
            baseline.lost_oil_bbl,
            scenario.lost_oil_bbl,
            higher_is_better=False,
        ),
        _row(
            "Production Loss — Gas (mscf)",
            baseline.lost_gas_mscf,
            scenario.lost_gas_mscf,
            higher_is_better=False,
        ),
        _row(
            "Downtime (hours)",
            baseline.downtime_hours,
            scenario.downtime_hours,
            higher_is_better=False,
        ),
    ]

    currencies = (
        set(baseline.revenue_dict)
        | set(scenario.revenue_dict)
        | set(baseline.total_cost_dict)
        | set(scenario.total_cost_dict)
        | set(baseline.maintenance_cost_dict)
        | set(scenario.maintenance_cost_dict)
        | set(baseline.margin_dict)
        | set(scenario.margin_dict)
    )
    for currency in sorted(currencies):
        rows.append(
            _row(
                f"Revenue ({currency})",
                baseline.revenue_dict.get(currency, 0.0),
                scenario.revenue_dict.get(currency, 0.0),
                currency=currency,
            )
        )
        rows.append(
            _row(
                f"Operating Cost ({currency})",
                baseline.total_cost_dict.get(currency, 0.0),
                scenario.total_cost_dict.get(currency, 0.0),
                currency=currency,
                higher_is_better=False,
            )
        )
        rows.append(
            _row(
                f"Maintenance Cost ({currency})",
                baseline.maintenance_cost_dict.get(currency, 0.0),
                scenario.maintenance_cost_dict.get(currency, 0.0),
                currency=currency,
                higher_is_better=False,
            )
        )
        baseline_cpb = compute_per_unit(baseline.total_cost_dict.get(currency), baseline.oil_bbl)
        scenario_cpb = compute_per_unit(scenario.total_cost_dict.get(currency), scenario.oil_bbl)
        if baseline_cpb is not None and scenario_cpb is not None:
            rows.append(
                _row(
                    f"Cost per Barrel ({currency})",
                    baseline_cpb,
                    scenario_cpb,
                    currency=currency,
                    higher_is_better=False,
                )
            )
        if currency in baseline.margin_dict or currency in scenario.margin_dict:
            rows.append(
                _row(
                    f"Estimated Operating Margin ({currency})",
                    baseline.margin_dict.get(currency, 0.0),
                    scenario.margin_dict.get(currency, 0.0),
                    currency=currency,
                )
            )

    return rows


def run_sensitivity(
    baseline: BaselineMetrics,
    base_assumptions: ScenarioAssumptions,
    variable_key: str,
    values: list[float],
    boe_gas_factor: float,
) -> list[SensitivityPoint]:
    """Sweeps one assumption field across `values`, reusing compute_scenario_metrics() once per
    point — no separate math, just repeated application of the same deterministic formulas."""
    if variable_key not in ScenarioAssumptions.__dataclass_fields__:
        raise ValueError(f"Unknown sensitivity variable: {variable_key}")

    points: list[SensitivityPoint] = []
    for value in values:
        swept = ScenarioAssumptions(**{**base_assumptions.as_dict(), variable_key: value})
        scenario = compute_scenario_metrics(baseline, swept, boe_gas_factor)
        revenue_impact = {
            c: round(scenario.revenue_dict.get(c, 0.0) - baseline.revenue_dict.get(c, 0.0), 2)
            for c in set(baseline.revenue_dict) | set(scenario.revenue_dict)
        }
        margin_impact = {
            c: round(scenario.margin_dict.get(c, 0.0) - baseline.margin_dict.get(c, 0.0), 2)
            for c in set(baseline.margin_dict) | set(scenario.margin_dict)
        }
        points.append(
            SensitivityPoint(
                variable_value=value,
                recovered_production_bbl=scenario.recovered_production_bbl,
                recovered_downtime_hours=scenario.recovered_downtime_hours,
                revenue_impact_dict=revenue_impact,
                margin_impact_dict=margin_impact,
            )
        )
    return points
