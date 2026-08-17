from datetime import date

from app.services.whatif_calculations import (
    BaselineMetrics,
    ScenarioAssumptions,
    build_comparison,
    compute_scenario_metrics,
    run_sensitivity,
    validate_assumptions,
)


def _baseline(**overrides) -> BaselineMetrics:
    defaults = dict(
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        period_days=31,
        oil_bbl=3100.0,
        gas_mscf=6200.0,
        boe=4133.33,
        oil_price=80.0,
        oil_price_currency="USD",
        gas_price=3.5,
        gas_price_currency="USD",
        revenue_dict={"USD": 3100.0 * 80.0 + 6200.0 * 3.5},
        oil_revenue_dict={"USD": 3100.0 * 80.0},
        gas_revenue_dict={"USD": 6200.0 * 3.5},
        operating_cost_dict={"USD": 50000.0},
        energy_cost_dict={"USD": 20000.0},
        other_cost_dict={"USD": 30000.0},
        maintenance_cost_dict={"USD": 10000.0},
        total_cost_dict={"USD": 60000.0},
        lost_oil_bbl=100.0,
        lost_gas_mscf=50.0,
        production_loss_revenue_dict={"USD": 100.0 * 80.0},
        downtime_hours=100.0,
        margin_dict={"USD": (3100.0 * 80.0 + 6200.0 * 3.5) - 60000.0},
    )
    defaults.update(overrides)
    return BaselineMetrics(**defaults)


# ----- Formula correctness -----


def test_production_change_pct_scales_oil_and_gas_linearly():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(production_change_pct=10), boe_gas_factor=6000)
    assert scenario.oil_bbl == round(3100.0 * 1.10, 2)
    assert scenario.gas_mscf == round(6200.0 * 1.10, 2)


def test_scenario_revenue_equals_scenario_production_times_commodity_price():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(production_change_pct=20), boe_gas_factor=6000)
    expected = round(scenario.oil_bbl * 80.0, 2) + round(scenario.gas_mscf * 3.5, 2)
    assert scenario.revenue_dict["USD"] == round(expected, 2)


def test_scenario_operating_cost_equals_baseline_times_one_plus_cost_change():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(operating_cost_change_pct=-15), boe_gas_factor=6000)
    assert scenario.operating_cost_dict["USD"] == round(50000.0 * 0.85, 2)


def test_scenario_production_loss_equals_baseline_times_one_minus_reduction():
    baseline = _baseline()
    scenario = compute_scenario_metrics(
        baseline, ScenarioAssumptions(production_loss_reduction_pct=25), boe_gas_factor=6000
    )
    assert scenario.lost_oil_bbl == round(100.0 * 0.75, 1)
    assert scenario.lost_gas_mscf == round(50.0 * 0.75, 1)


def test_scenario_operating_margin_equals_scenario_revenue_minus_scenario_cost():
    baseline = _baseline()
    scenario = compute_scenario_metrics(
        baseline, ScenarioAssumptions(production_change_pct=10, operating_cost_change_pct=5), boe_gas_factor=6000
    )
    assert scenario.margin_dict["USD"] == round(scenario.revenue_dict["USD"] - scenario.total_cost_dict["USD"], 2)


def test_no_assumptions_means_scenario_equals_baseline():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(), boe_gas_factor=6000)
    assert scenario.oil_bbl == baseline.oil_bbl
    assert scenario.gas_mscf == baseline.gas_mscf
    assert scenario.total_cost_dict == baseline.total_cost_dict
    assert scenario.lost_oil_bbl == baseline.lost_oil_bbl
    assert scenario.downtime_hours == baseline.downtime_hours
    assert scenario.revenue_dict == baseline.revenue_dict
    assert scenario.margin_dict == baseline.margin_dict


def test_no_assumptions_scenario_matches_baseline_revenue_even_when_price_changed_mid_period():
    """Regression coverage for a real bug found during pilot-demo validation: baseline.revenue_dict
    is priced day-by-day against real commodity-price history (cost_revenue.py's
    _revenue_dicts_for_records), so it does NOT generally equal oil_bbl x the single spot price on
    the period's last day whenever the commodity price changed mid-period. Before the fix, a
    zero-assumption ("nothing changed") scenario silently disagreed with its own baseline by
    exactly that spot-vs-realized-average gap — e.g. a well priced at $75.78/bbl for most of a
    31-day window then $69.79/bbl on the final day showed an ~$82k unexplained "impact" from
    running What-If with no assumptions at all. oil_revenue_dict/gas_revenue_dict now carry the
    true realized revenue per commodity so compute_scenario_metrics can derive the correct
    volume-weighted price basis instead of the raw end-of-period spot price."""
    baseline = _baseline(
        oil_bbl=200.0,
        gas_mscf=0.0,
        oil_price=60.0,  # spot price on the period's last day
        oil_price_currency="USD",
        gas_price=None,
        gas_price_currency=None,
        # Realized: 100 bbl priced at $70 + 100 bbl priced at $60 = $13,000, i.e. an average of
        # $65/bbl -- deliberately NOT equal to oil_bbl (200) x the $60 spot price ($12,000).
        revenue_dict={"USD": 13000.0},
        oil_revenue_dict={"USD": 13000.0},
        gas_revenue_dict={},
        production_loss_revenue_dict={},
        margin_dict={"USD": 13000.0 - 60000.0},
    )
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(), boe_gas_factor=6000)
    assert scenario.revenue_dict == baseline.revenue_dict
    assert scenario.oil_price == 65.0


# ----- Downtime: recovery reported separately, never double-counted -----


def test_downtime_reduction_worked_example_100h_20pct_reduction_gives_80h_scenario_20h_recovered():
    baseline = _baseline(downtime_hours=100.0)
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(downtime_change_pct=-20), boe_gas_factor=6000)
    assert scenario.downtime_hours == 80.0
    assert scenario.recovered_downtime_hours == 20.0


def test_recovered_production_from_downtime_never_folded_into_scenario_oil_bbl():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(downtime_change_pct=-50), boe_gas_factor=6000)
    # production_change_pct was never supplied, so oil_bbl must equal the untouched baseline —
    # any leakage from the downtime lever into production would break this.
    assert scenario.oil_bbl == baseline.oil_bbl
    assert scenario.recovered_production_bbl > 0


def test_recovered_production_formula_matches_hourly_rate_times_recovered_hours():
    baseline = _baseline(oil_bbl=3100.0, period_days=31, downtime_hours=100.0)
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(downtime_change_pct=-20), boe_gas_factor=6000)
    hourly_rate = 3100.0 / (31 * 24)
    assert scenario.recovered_production_bbl == round(20.0 * hourly_rate, 2)


# ----- Production loss: potential reduction reported separately -----


def test_potential_loss_reduction_never_folded_into_scenario_oil_bbl():
    baseline = _baseline()
    scenario = compute_scenario_metrics(
        baseline, ScenarioAssumptions(production_loss_reduction_pct=50), boe_gas_factor=6000
    )
    assert scenario.oil_bbl == baseline.oil_bbl
    assert scenario.potential_loss_reduction_oil_bbl == round(100.0 - 50.0, 1)


# ----- Energy cost lever never double-applies operating_cost_change_pct -----


def test_energy_cost_lever_scales_only_energy_slice_not_the_whole_operating_cost():
    baseline = _baseline(energy_cost_dict={"USD": 20000.0}, other_cost_dict={"USD": 30000.0}, operating_cost_dict={"USD": 50000.0})
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(energy_cost_change_pct=-50), boe_gas_factor=6000)
    # energy halves to 10000, "other" untouched at 30000 (operating_cost_change_pct absent) => 40000
    assert scenario.operating_cost_dict["USD"] == 40000.0


def test_energy_and_operating_cost_levers_combine_without_double_applying():
    baseline = _baseline(energy_cost_dict={"USD": 20000.0}, other_cost_dict={"USD": 30000.0}, operating_cost_dict={"USD": 50000.0})
    scenario = compute_scenario_metrics(
        baseline,
        ScenarioAssumptions(energy_cost_change_pct=-50, operating_cost_change_pct=10),
        boe_gas_factor=6000,
    )
    # energy: 20000 * 0.5 = 10000; other: 30000 * 1.10 = 33000; total = 43000 (never 50000*1.10
    # AND separately adjusted energy, which would double-apply the operating_cost_change_pct
    # lever to the energy dollars too)
    assert scenario.operating_cost_dict["USD"] == 43000.0


def test_operating_cost_alone_scales_full_baseline_once_when_energy_lever_absent():
    baseline = _baseline(energy_cost_dict={"USD": 20000.0}, other_cost_dict={"USD": 30000.0}, operating_cost_dict={"USD": 50000.0})
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(operating_cost_change_pct=10), boe_gas_factor=6000)
    assert scenario.operating_cost_dict["USD"] == 55000.0


# ----- Currency mismatch: margin never blended/fabricated -----


def test_margin_never_blended_across_mismatched_currencies():
    # Scenario revenue is always recomputed fresh from oil_bbl/gas_mscf x oil_price/gas_price
    # (both USD, per the default fixture) — never copied from baseline.revenue_dict. Cost is
    # entirely NGN here, so no currency matches revenue at all.
    baseline = _baseline(
        operating_cost_dict={"NGN": 5_000_000.0},
        energy_cost_dict={},
        other_cost_dict={"NGN": 5_000_000.0},
        maintenance_cost_dict={},
        total_cost_dict={"NGN": 5_000_000.0},
    )
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(), boe_gas_factor=6000)
    assert scenario.revenue_dict == {"USD": 269700.0}
    assert scenario.margin_dict == {}
    assert scenario.margin_currency_mismatch is True


def test_margin_computed_for_matched_currency_even_with_partial_mismatch():
    baseline = _baseline(
        operating_cost_dict={"USD": 40000.0, "NGN": 5_000_000.0},
        energy_cost_dict={},
        other_cost_dict={"USD": 40000.0, "NGN": 5_000_000.0},
        maintenance_cost_dict={},
    )
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(), boe_gas_factor=6000)
    assert scenario.margin_dict == {"USD": 229700.0}
    assert scenario.margin_currency_mismatch is True


# ----- Guardrails: two-tier (hard error vs soft warning), never a silent rejection -----


def test_hard_reject_production_change_below_negative_100():
    flags = validate_assumptions(ScenarioAssumptions(production_change_pct=-150), reasonable_bound_pct=50)
    assert any(f.severity == "error" and f.field == "production_change_pct" for f in flags)


def test_hard_reject_production_loss_reduction_above_100():
    flags = validate_assumptions(ScenarioAssumptions(production_loss_reduction_pct=150), reasonable_bound_pct=50)
    assert any(f.severity == "error" and f.field == "production_loss_reduction_pct" for f in flags)


def test_hard_reject_non_positive_price_override():
    flags = validate_assumptions(ScenarioAssumptions(oil_price_override=0), reasonable_bound_pct=50)
    assert any(f.severity == "error" and f.field == "oil_price_override" for f in flags)
    flags = validate_assumptions(ScenarioAssumptions(oil_price_override=-10), reasonable_bound_pct=50)
    assert any(f.severity == "error" and f.field == "oil_price_override" for f in flags)


def test_soft_warn_never_silently_rejects_unusual_but_valid_input():
    flags = validate_assumptions(ScenarioAssumptions(production_change_pct=-80), reasonable_bound_pct=50)
    assert flags == [
        f for f in flags if f.severity == "warning"
    ]  # only warnings, never an error, for a valid (if unusual) input
    assert len(flags) == 1
    assert "outside configured operating assumptions" in flags[0].message


def test_within_bound_assumption_produces_no_flags():
    flags = validate_assumptions(ScenarioAssumptions(production_change_pct=10, operating_cost_change_pct=-5), reasonable_bound_pct=50)
    assert flags == []


def test_no_assumptions_produces_no_flags():
    assert validate_assumptions(ScenarioAssumptions(), reasonable_bound_pct=50) == []


# ----- Comparison table -----


def test_comparison_direction_flags_cost_increase_as_negative():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(operating_cost_change_pct=20), boe_gas_factor=6000)
    rows = build_comparison(baseline, scenario)
    cost_row = next(r for r in rows if r.metric == "Operating Cost (USD)")
    assert cost_row.direction == "negative"  # cost went up -> bad


def test_comparison_direction_flags_revenue_increase_as_positive():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(production_change_pct=10), boe_gas_factor=6000)
    rows = build_comparison(baseline, scenario)
    revenue_row = next(r for r in rows if r.metric == "Revenue (USD)")
    assert revenue_row.direction == "positive"


def test_comparison_direction_flags_production_loss_decrease_as_positive():
    baseline = _baseline()
    scenario = compute_scenario_metrics(
        baseline, ScenarioAssumptions(production_loss_reduction_pct=30), boe_gas_factor=6000
    )
    rows = build_comparison(baseline, scenario)
    loss_row = next(r for r in rows if r.metric == "Production Loss — Oil (bbl)")
    assert loss_row.direction == "positive"  # less loss -> good


def test_comparison_row_is_neutral_and_pct_change_zero_when_unchanged():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(), boe_gas_factor=6000)
    rows = build_comparison(baseline, scenario)
    oil_row = next(r for r in rows if r.metric == "Oil Production (bbl)")
    assert oil_row.direction == "neutral"
    assert oil_row.pct_change == 0.0


# ----- Sensitivity analysis -----


def test_sensitivity_sweep_returns_one_point_per_value():
    baseline = _baseline()
    points = run_sensitivity(
        baseline, ScenarioAssumptions(), "downtime_change_pct", [0, -10, -20, -30, -40, -50], boe_gas_factor=6000
    )
    assert len(points) == 6
    assert [p.variable_value for p in points] == [0, -10, -20, -30, -40, -50]


def test_sensitivity_recovered_production_increases_monotonically_with_downtime_reduction():
    baseline = _baseline()
    points = run_sensitivity(
        baseline, ScenarioAssumptions(), "downtime_change_pct", [0, -10, -20, -30], boe_gas_factor=6000
    )
    values = [p.recovered_production_bbl for p in points]
    assert values == sorted(values)


def test_sensitivity_unknown_variable_raises():
    baseline = _baseline()
    try:
        run_sensitivity(baseline, ScenarioAssumptions(), "not_a_real_field", [0, 1], boe_gas_factor=6000)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ----- Boundary conditions -----


def test_full_100_pct_production_loss_reduction_zeroes_out_loss():
    baseline = _baseline()
    scenario = compute_scenario_metrics(
        baseline, ScenarioAssumptions(production_loss_reduction_pct=100), boe_gas_factor=6000
    )
    assert scenario.lost_oil_bbl == 0.0
    assert scenario.lost_gas_mscf == 0.0


def test_full_negative_100_pct_operating_cost_change_zeroes_out_cost():
    baseline = _baseline()
    scenario = compute_scenario_metrics(baseline, ScenarioAssumptions(operating_cost_change_pct=-100), boe_gas_factor=6000)
    assert scenario.operating_cost_dict["USD"] == 0.0


def test_price_override_takes_precedence_over_price_change_pct():
    baseline = _baseline()
    scenario = compute_scenario_metrics(
        baseline, ScenarioAssumptions(oil_price_override=999.0, oil_price_change_pct=10), boe_gas_factor=6000
    )
    assert scenario.oil_price == 999.0
