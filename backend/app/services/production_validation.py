"""Shared validation tiers for production records — used by both the manual create/update
API path (backend/app/routers/production.py) and CSV import
(backend/app/routers/production_import.py), so the rules only live in one place.

Pure (plain values in, no DB/ORM/FastAPI) so it's directly unit-testable and reusable from a
non-request context (e.g. a future Excel importer).

Per product requirement: use warnings where appropriate instead of rejecting data
unnecessarily. INVALID rows must never be persisted; WARNING rows are still saved/imported
with the warning surfaced to the user.
"""

from dataclasses import dataclass
from typing import Literal

from app.services.production_calculations import compute_water_cut_pct

Severity = Literal["invalid", "warning"]


@dataclass
class ValidationIssue:
    field: str
    severity: Severity
    message: str


def validate_production_row(
    *,
    oil_bopd: float,
    gas_mscfd: float,
    water_bwpd: float,
    wellhead_pressure: float | None = None,
    tubing_pressure: float | None = None,
    casing_pressure: float | None = None,
    flowline_pressure: float | None = None,
    wellhead_temperature: float | None = None,
    choke_size: float | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if oil_bopd < 0:
        issues.append(ValidationIssue("oil_bopd", "invalid", "Oil production cannot be negative."))
    elif oil_bopd > 50000:
        issues.append(ValidationIssue("oil_bopd", "warning", "Oil rate is unusually high — please verify."))

    if gas_mscfd < 0:
        issues.append(ValidationIssue("gas_mscfd", "invalid", "Gas production cannot be negative."))
    elif gas_mscfd > 100000:
        issues.append(ValidationIssue("gas_mscfd", "warning", "Gas rate is unusually high — please verify."))

    if water_bwpd < 0:
        issues.append(ValidationIssue("water_bwpd", "invalid", "Water production cannot be negative."))
    elif water_bwpd > 100000:
        issues.append(ValidationIssue("water_bwpd", "warning", "Water rate is unusually high — please verify."))

    pressures = {
        "wellhead_pressure": wellhead_pressure,
        "tubing_pressure": tubing_pressure,
        "casing_pressure": casing_pressure,
        "flowline_pressure": flowline_pressure,
    }
    for field_name, value in pressures.items():
        if value is None:
            continue
        if value < 0:
            issues.append(ValidationIssue(field_name, "invalid", "Pressure readings cannot be negative."))
        elif value > 10000:
            issues.append(ValidationIssue(field_name, "warning", "Pressure reading is unusually high — please verify."))

    if wellhead_temperature is not None:
        if wellhead_temperature < -50 or wellhead_temperature > 400:
            issues.append(
                ValidationIssue(
                    "wellhead_temperature", "invalid", "Temperature is outside a physically plausible range."
                )
            )
        elif wellhead_temperature < 32 or wellhead_temperature > 350:
            issues.append(
                ValidationIssue("wellhead_temperature", "warning", "Temperature reading is unusual — please verify.")
            )

    if choke_size is not None and (choke_size < 0 or choke_size > 100):
        issues.append(ValidationIssue("choke_size", "warning", "Choke size is outside the typical 0-100 range."))

    water_cut = compute_water_cut_pct(oil_bopd, water_bwpd)
    if water_cut is not None and water_cut > 98:
        issues.append(ValidationIssue("water_cut_pct", "warning", "Computed water cut is unusually high (>98%)."))

    if all(value is None for value in (*pressures.values(), wellhead_temperature)):
        issues.append(
            ValidationIssue(
                "pressure_temperature", "warning", "No pressure or temperature readings supplied for this record."
            )
        )

    return issues


def has_invalid(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "invalid" for issue in issues)
