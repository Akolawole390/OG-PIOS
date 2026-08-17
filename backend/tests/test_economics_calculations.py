from app.services.economics_calculations import compute_per_unit, estimate_operating_margin, estimate_revenue


def test_estimate_revenue_both_commodities():
    oil_rev, gas_rev, total = estimate_revenue(500.0, 300.0, oil_price_per_bbl=70.0, gas_price_per_mscf=3.0)
    assert oil_rev == 35000.0
    assert gas_rev == 900.0
    assert total == 35900.0


def test_estimate_revenue_oil_only_when_gas_price_missing():
    oil_rev, gas_rev, total = estimate_revenue(500.0, 300.0, oil_price_per_bbl=70.0, gas_price_per_mscf=None)
    assert oil_rev == 35000.0
    assert gas_rev is None
    assert total == 35000.0


def test_estimate_revenue_none_when_no_data_resolves():
    oil_rev, gas_rev, total = estimate_revenue(None, None, oil_price_per_bbl=70.0, gas_price_per_mscf=3.0)
    assert oil_rev is None
    assert gas_rev is None
    assert total is None


def test_estimate_revenue_zero_volume_still_counts_if_price_known():
    oil_rev, gas_rev, total = estimate_revenue(0.0, 0.0, oil_price_per_bbl=70.0, gas_price_per_mscf=3.0)
    assert oil_rev == 0.0
    assert gas_rev == 0.0
    assert total == 0.0


def test_estimate_operating_margin_basic():
    assert estimate_operating_margin(10000.0, 6000.0) == 4000.0


def test_estimate_operating_margin_negative_when_cost_exceeds_revenue():
    assert estimate_operating_margin(4000.0, 6000.0) == -2000.0


def test_estimate_operating_margin_none_when_either_side_missing():
    assert estimate_operating_margin(None, 6000.0) is None
    assert estimate_operating_margin(10000.0, None) is None
    assert estimate_operating_margin(None, None) is None


def test_compute_per_unit_basic_division():
    assert compute_per_unit(1000.0, 200.0) == 5.0


def test_compute_per_unit_none_when_volume_zero_or_negative():
    assert compute_per_unit(1000.0, 0.0) is None
    assert compute_per_unit(1000.0, -5.0) is None


def test_compute_per_unit_none_when_either_input_missing():
    assert compute_per_unit(None, 200.0) is None
    assert compute_per_unit(1000.0, None) is None
