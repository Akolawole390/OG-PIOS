"""CSV parsing for the production-data import workflow.

Deliberately format-agnostic seam: this module returns a plain
`list[dict[str, str]]` (header -> raw string value) — the validation/classification layer in
backend/app/routers/production_import.py operates on that shape without knowing it came from
CSV. A future `parse_xlsx_rows()` (openpyxl) could return the same shape and slot in without
changing anything downstream. No Excel dependency is added now.
"""

import csv
import io

EXPECTED_COLUMNS = [
    "well_id",
    "record_date",
    "oil_bopd",
    "gas_mscfd",
    "water_bwpd",
    "choke_size",
    "wellhead_pressure",
    "tubing_pressure",
    "casing_pressure",
    "flowline_pressure",
    "wellhead_temperature",
]


def parse_csv_rows(raw_bytes: bytes) -> list[dict[str, str]]:
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]
