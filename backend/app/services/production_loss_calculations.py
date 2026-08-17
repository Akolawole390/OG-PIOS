"""Rule-based, transparent production-loss volume and revenue-impact estimation.

Pure functions (plain values in, no DB/ORM/FastAPI imports) so the math is directly
unit-testable (backend/tests/test_production_loss_calculations.py) and reusable from both the
API (backend/app/routers/production_loss.py) and the synthetic data seeder
(backend/app/db/seed_wells.py) — the seed script's linked loss records must derive their
numbers by calling these functions on real underlying data, never an independently faked
figure, mirroring the precedent set by equipment_health.py and reliability_metrics.py.

IMPORTANT: this is a decision-support estimate, not a certified financial or engineering
figure. See PRODUCTION_LOSS_DISCLAIMER — it must accompany every value shown to a user, per
this project's standing AI/analytics-output guardrail (root CLAUDE.md).

Method: "expected vs. actual" — expected production comes from the existing ProductionTarget
resolution rule (most recent target with effective_date <= the date in question, per well;
see app/routers/production.py's _resolve_target, reused directly rather than duplicated),
actual comes from the existing ProductionRecord for that well/date. Lost volume is
max(expected - actual, 0) per commodity — never negative (overproduction is not modeled as a
negative loss). Revenue impact sums whichever commodity has both a lost volume and a resolved
CommodityPrice; a commodity with no resolvable price is simply excluded from the total rather
than guessed at.
"""

PRODUCTION_LOSS_DISCLAIMER = (
    "Rule-based estimate computed from recorded production/target data and commodity prices; "
    "not a certified financial figure or root-cause determination. Requires engineering and "
    "financial review before acting on it."
)


def estimate_volume_loss(
    expected_oil_bopd: float | None,
    actual_oil_bopd: float | None,
    expected_gas_mscfd: float | None,
    actual_gas_mscfd: float | None,
) -> tuple[float | None, float | None]:
    """Returns (oil_bopd_lost, gas_mscfd_lost). Each is None unless both its expected and
    actual values are known — never guesses a loss from partial data."""
    oil_lost = None
    if expected_oil_bopd is not None and actual_oil_bopd is not None:
        oil_lost = round(max(expected_oil_bopd - actual_oil_bopd, 0.0), 2)

    gas_lost = None
    if expected_gas_mscfd is not None and actual_gas_mscfd is not None:
        gas_lost = round(max(expected_gas_mscfd - actual_gas_mscfd, 0.0), 2)

    return oil_lost, gas_lost


def estimate_revenue_impact(
    oil_bopd_lost: float | None,
    gas_mscfd_lost: float | None,
    oil_price_per_bbl: float | None,
    gas_price_per_mscf: float | None,
) -> float | None:
    """Sums whichever commodity has both a lost volume and a resolved price. None if neither
    commodity has both — never a fabricated total from missing inputs."""
    total = 0.0
    counted = False

    if oil_bopd_lost is not None and oil_price_per_bbl is not None:
        total += oil_bopd_lost * oil_price_per_bbl
        counted = True

    if gas_mscfd_lost is not None and gas_price_per_mscf is not None:
        total += gas_mscfd_lost * gas_price_per_mscf
        counted = True

    return round(total, 2) if counted else None
