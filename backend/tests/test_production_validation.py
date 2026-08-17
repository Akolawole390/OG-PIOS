from app.services.production_validation import has_invalid, validate_production_row


def _base_kwargs(**overrides):
    kwargs = dict(
        oil_bopd=500,
        gas_mscfd=300,
        water_bwpd=50,
        wellhead_pressure=1500,
        tubing_pressure=1700,
        casing_pressure=900,
        flowline_pressure=1200,
        wellhead_temperature=180,
        choke_size=40,
    )
    kwargs.update(overrides)
    return kwargs


def test_normal_row_has_no_issues():
    issues = validate_production_row(**_base_kwargs())
    assert issues == []


def test_negative_oil_is_invalid():
    issues = validate_production_row(**_base_kwargs(oil_bopd=-10))
    assert has_invalid(issues)
    assert any(i.field == "oil_bopd" and i.severity == "invalid" for i in issues)


def test_negative_pressure_is_invalid():
    issues = validate_production_row(**_base_kwargs(wellhead_pressure=-5))
    assert has_invalid(issues)


def test_extreme_temperature_is_invalid():
    issues = validate_production_row(**_base_kwargs(wellhead_temperature=1000))
    assert has_invalid(issues)


def test_unusually_high_oil_is_warning_not_invalid():
    issues = validate_production_row(**_base_kwargs(oil_bopd=60000))
    assert not has_invalid(issues)
    assert any(i.field == "oil_bopd" and i.severity == "warning" for i in issues)


def test_high_water_cut_produces_warning():
    issues = validate_production_row(**_base_kwargs(oil_bopd=10, water_bwpd=990))
    assert not has_invalid(issues)
    assert any(i.field == "water_cut_pct" for i in issues)


def test_missing_pressure_and_temperature_is_warning():
    issues = validate_production_row(
        **_base_kwargs(
            wellhead_pressure=None,
            tubing_pressure=None,
            casing_pressure=None,
            flowline_pressure=None,
            wellhead_temperature=None,
        )
    )
    assert not has_invalid(issues)
    assert any(i.field == "pressure_temperature" for i in issues)
