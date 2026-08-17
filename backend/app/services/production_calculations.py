"""Pure production-metric formulas. No DB/FastAPI imports — reused by both the manual
create/update API path and CSV import, and unit-tested in isolation.
"""


def compute_water_cut_pct(oil_bopd: float, water_bwpd: float) -> float | None:
    denominator = oil_bopd + water_bwpd
    if denominator <= 0:
        return None
    return round(water_bwpd / denominator * 100, 2)


def compute_gor(oil_bopd: float, gas_mscfd: float) -> float | None:
    """Gas-oil ratio in scf/bbl."""
    if oil_bopd <= 0:
        return None
    return round(gas_mscfd * 1000 / oil_bopd, 2)


def compute_boe(oil_bopd: float, gas_mscfd: float, boe_gas_factor: float) -> float:
    """Barrels of oil equivalent: oil plus gas converted via the configurable factor
    (standard cubic feet of gas per barrel-of-oil-equivalent)."""
    return round(oil_bopd + (gas_mscfd * 1000 / boe_gas_factor), 2)
