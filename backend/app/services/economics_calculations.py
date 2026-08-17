"""Rule-based, transparent revenue and unit-economics estimation for the Cost & Revenue module.

Pure functions (plain values in, no DB/ORM/FastAPI imports) so the math is directly
unit-testable (backend/tests/test_economics_calculations.py) and reusable from both the API
(backend/app/routers/cost_revenue.py) and the synthetic data seeder — mirrors the shape of
services/production_loss_calculations.py and services/equipment_health.py.

IMPORTANT: every figure this module produces is a decision-support estimate for management/
analyst review, not an audited accounting result. See ECONOMICS_DISCLAIMER — it must accompany
every value shown to a user, per this project's standing AI/analytics-output guardrail (root
CLAUDE.md).

Documented methodology (also mirrored in docs/data-model.md verbatim, per the module spec):
    Revenue = Production x Commodity Price
    Estimated Operating Margin = Estimated Revenue - Operating Costs
    Cost per barrel = Operating Cost / Production
    Production Loss Financial Impact = Estimated Lost Production x Commodity Price
        (computed and owned by the Production Loss module — see
        services/production_loss_calculations.py — never recomputed here, to avoid double
        counting; this module only reads ProductionLoss.estimated_revenue_impact).

Currency handling: this file has no notion of currency at all — every function operates on
plain numbers. It is the CALLER's responsibility (backend/app/routers/cost_revenue.py) to only
subtract/combine two amounts that are already known to share a currency. Revenue is never
converted between currencies, and no exchange rate is invented anywhere in this codebase.
"""

ECONOMICS_DISCLAIMER = (
    "Rule-based estimate computed from recorded production, cost, and commodity-price data; "
    "a management/analyst decision-support figure, not an audited accounting result. "
    "Requires financial review before acting on it."
)


def estimate_revenue(
    oil_bopd: float | None,
    gas_mscfd: float | None,
    oil_price_per_bbl: float | None,
    gas_price_per_mscf: float | None,
) -> tuple[float | None, float | None, float | None]:
    """Returns (oil_revenue, gas_revenue, total_revenue). Each commodity's revenue is None
    unless both its volume and its resolved price are known — never guessed from partial
    data. total_revenue is None only when neither commodity resolved."""
    oil_revenue = None
    if oil_bopd is not None and oil_price_per_bbl is not None:
        oil_revenue = round(oil_bopd * oil_price_per_bbl, 2)

    gas_revenue = None
    if gas_mscfd is not None and gas_price_per_mscf is not None:
        gas_revenue = round(gas_mscfd * gas_price_per_mscf, 2)

    if oil_revenue is None and gas_revenue is None:
        return oil_revenue, gas_revenue, None

    total_revenue = round((oil_revenue or 0.0) + (gas_revenue or 0.0), 2)
    return oil_revenue, gas_revenue, total_revenue


def estimate_operating_margin(revenue: float | None, cost: float | None) -> float | None:
    """Estimated Operating Margin = Estimated Revenue - Operating Costs. The caller must only
    pass amounts already confirmed to share one currency — this function itself has no
    currency awareness and performs a plain subtraction."""
    if revenue is None or cost is None:
        return None
    return round(revenue - cost, 2)


def compute_per_unit(amount: float | None, volume: float | None) -> float | None:
    """Safe division for any "X per barrel"/"X per BOE" figure. None if the amount or volume
    is unknown, or the volume is zero/negative (division would be meaningless, not just
    undefined) — never a fabricated or infinite result."""
    if amount is None or volume is None or volume <= 0:
        return None
    return round(amount / volume, 4)
