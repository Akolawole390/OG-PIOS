from app.services.production_loss_calculations import estimate_revenue_impact, estimate_volume_loss


def test_estimate_volume_loss_clamps_at_zero_when_actual_exceeds_expected():
    oil_lost, gas_lost = estimate_volume_loss(500, 600, 300, 250)
    assert oil_lost == 0.0
    assert gas_lost == 50.0


def test_estimate_volume_loss_basic_shortfall():
    oil_lost, gas_lost = estimate_volume_loss(500, 400, 300, 200)
    assert oil_lost == 100.0
    assert gas_lost == 100.0


def test_estimate_volume_loss_none_when_expected_missing():
    oil_lost, gas_lost = estimate_volume_loss(None, 400, None, 200)
    assert oil_lost is None
    assert gas_lost is None


def test_estimate_volume_loss_none_when_actual_missing():
    oil_lost, gas_lost = estimate_volume_loss(500, None, 300, None)
    assert oil_lost is None
    assert gas_lost is None


def test_estimate_volume_loss_independent_per_commodity():
    # Oil data present, gas data missing — oil still computes.
    oil_lost, gas_lost = estimate_volume_loss(500, 400, None, None)
    assert oil_lost == 100.0
    assert gas_lost is None


def test_estimate_revenue_impact_both_commodities():
    impact = estimate_revenue_impact(100.0, 50.0, oil_price_per_bbl=70.0, gas_price_per_mscf=3.0)
    assert impact == 100.0 * 70.0 + 50.0 * 3.0


def test_estimate_revenue_impact_oil_only_when_gas_price_missing():
    impact = estimate_revenue_impact(100.0, 50.0, oil_price_per_bbl=70.0, gas_price_per_mscf=None)
    assert impact == 7000.0


def test_estimate_revenue_impact_none_when_no_volume_and_price_pair():
    assert estimate_revenue_impact(None, None, 70.0, 3.0) is None
    assert estimate_revenue_impact(100.0, 50.0, None, None) is None


def test_estimate_revenue_impact_zero_volume_still_counts_if_price_known():
    impact = estimate_revenue_impact(0.0, 0.0, oil_price_per_bbl=70.0, gas_price_per_mscf=3.0)
    assert impact == 0.0
