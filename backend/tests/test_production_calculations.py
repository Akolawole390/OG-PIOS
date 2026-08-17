from app.services.production_calculations import compute_boe, compute_gor, compute_water_cut_pct


def test_water_cut_pct_normal_case():
    assert compute_water_cut_pct(oil_bopd=800, water_bwpd=200) == 20.0


def test_water_cut_pct_zero_denominator():
    assert compute_water_cut_pct(oil_bopd=0, water_bwpd=0) is None


def test_water_cut_pct_all_water():
    assert compute_water_cut_pct(oil_bopd=0, water_bwpd=100) == 100.0


def test_gor_normal_case():
    # 500 mscf/d * 1000 / 1000 bopd = 500 scf/bbl
    assert compute_gor(oil_bopd=1000, gas_mscfd=500) == 500.0


def test_gor_zero_oil_returns_none():
    assert compute_gor(oil_bopd=0, gas_mscfd=500) is None


def test_boe_oil_only():
    assert compute_boe(oil_bopd=1000, gas_mscfd=0, boe_gas_factor=6000) == 1000.0


def test_boe_includes_gas_conversion():
    # 6000 mscf/d * 1000 / 6000 factor = 1000 boe/d from gas alone
    assert compute_boe(oil_bopd=500, gas_mscfd=6000, boe_gas_factor=6000) == 1500.0


def test_boe_respects_custom_factor():
    low_factor = compute_boe(oil_bopd=0, gas_mscfd=1000, boe_gas_factor=1000)
    high_factor = compute_boe(oil_bopd=0, gas_mscfd=1000, boe_gas_factor=10000)
    assert low_factor > high_factor
