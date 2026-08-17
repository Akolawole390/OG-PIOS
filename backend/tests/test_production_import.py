from datetime import date

from app.models.production import PressureRecord, ProductionRecord, TemperatureRecord

CSV_HEADER = (
    "well_id,record_date,oil_bopd,gas_mscfd,water_bwpd,choke_size,"
    "wellhead_pressure,tubing_pressure,casing_pressure,flowline_pressure,wellhead_temperature"
)


def _csv_bytes(rows: list[str]) -> bytes:
    return "\n".join([CSV_HEADER, *rows]).encode("utf-8")


def test_preview_classifies_valid_warning_duplicate_invalid_rows(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="I-001")
    headers = auth_headers("Administrator")

    client.post("/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}, headers=headers)

    rows = [
        "I-001,2026-06-02,300,150,50,40,1500,1700,900,1200,180",
        "I-001,2026-06-03,60000,150,50,40,1500,1700,900,1200,180",
        "I-001,2026-06-01,300,150,50,40,1500,1700,900,1200,180",
        "BOGUS-WELL,2026-06-04,300,150,50,,,,,,",
    ]
    files = {"file": ("import.csv", _csv_bytes(rows), "text/csv")}
    response = client.post("/production/import/preview", files=files, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 4
    assert body["valid_count"] == 1
    assert body["warning_count"] == 1
    assert body["duplicate_count"] == 1
    assert body["invalid_count"] == 1

    statuses = {row["well_id"] + (row["record_date"] or ""): row["status"] for row in body["rows"]}
    assert statuses["I-0012026-06-02"] == "valid"
    assert statuses["I-0012026-06-03"] == "warning"
    assert statuses["I-0012026-06-01"] == "duplicate"
    assert statuses["BOGUS-WELL2026-06-04"] == "invalid"


def test_preview_detects_in_file_duplicates(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="I-005")
    headers = auth_headers("Administrator")

    rows = [
        "I-005,2026-06-01,100,50,10,40,1500,1700,900,1200,180",
        "I-005,2026-06-01,200,50,10,40,1500,1700,900,1200,180",
    ]
    files = {"file": ("import.csv", _csv_bytes(rows), "text/csv")}
    response = client.post("/production/import/preview", files=files, headers=headers)
    body = response.json()
    assert body["rows"][0]["status"] == "valid"
    assert body["rows"][1]["status"] == "duplicate"


def test_preview_requires_write_role(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="I-002")
    headers = auth_headers("Viewer")
    files = {"file": ("import.csv", _csv_bytes(["I-002,2026-06-01,100,,,,,,,,"]), "text/csv")}
    response = client.post("/production/import/preview", files=files, headers=headers)
    assert response.status_code == 403


def test_confirm_creates_updates_skips_and_rejects(client, make_field_facility_well, auth_headers, db_session):
    _, _, well = make_field_facility_well(well_id="I-003")
    headers = auth_headers("Administrator")

    client.post("/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}, headers=headers)

    payload = {
        "rows": [
            {"row_number": 2, "well_id": "I-003", "record_date": "2026-06-02", "oil_bopd": 300, "action": "create"},
            {"row_number": 3, "well_id": "I-003", "record_date": "2026-06-01", "oil_bopd": 999, "action": "overwrite"},
            {"row_number": 4, "well_id": "I-003", "record_date": "2026-06-03", "oil_bopd": 50, "action": "skip"},
            {"row_number": 5, "well_id": "I-003", "record_date": "2026-06-04", "oil_bopd": -10, "action": "create"},
        ]
    }
    response = client.post("/production/import/confirm", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert body["updated"] == 1
    assert body["skipped"] == 1
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["row_number"] == 5

    overwritten = (
        db_session.query(ProductionRecord)
        .filter(ProductionRecord.well_id == well.id, ProductionRecord.record_date == date(2026, 6, 1))
        .first()
    )
    assert overwritten.oil_bopd == 999

    created = (
        db_session.query(ProductionRecord)
        .filter(ProductionRecord.well_id == well.id, ProductionRecord.record_date == date(2026, 6, 3))
        .first()
    )
    assert created is None  # skipped, never persisted


def test_confirm_create_action_on_existing_duplicate_is_rejected(client, make_field_facility_well, auth_headers):
    _, _, well = make_field_facility_well(well_id="I-004")
    headers = auth_headers("Administrator")
    client.post("/production", json={"well_id": well.id, "record_date": "2026-06-01", "oil_bopd": 100}, headers=headers)

    payload = {
        "rows": [
            {"row_number": 2, "well_id": "I-004", "record_date": "2026-06-01", "oil_bopd": 200, "action": "create"},
        ]
    }
    response = client.post("/production/import/confirm", json=payload, headers=headers)
    body = response.json()
    assert body["created"] == 0
    assert len(body["rejected"]) == 1


def test_confirm_requires_write_role(client, auth_headers):
    headers = auth_headers("Viewer")
    response = client.post("/production/import/confirm", json={"rows": []}, headers=headers)
    assert response.status_code == 403


def test_confirm_batches_existence_checks_but_still_detects_within_batch_duplicates(
    client, make_field_facility_well, auth_headers, db_session
):
    """Regression test for the N+1 -> batched-existence-check refactor: the batched lookup
    dicts are updated as new records are created mid-loop, so a second row in the *same*
    confirm payload targeting a well/date a prior row in the same payload just created is
    still correctly detected as a duplicate — not silently created twice."""
    _, _, well = make_field_facility_well(well_id="I-006")
    headers = auth_headers("Administrator")

    payload = {
        "rows": [
            {"row_number": 2, "well_id": "I-006", "record_date": "2026-06-05", "oil_bopd": 100, "action": "create"},
            {"row_number": 3, "well_id": "I-006", "record_date": "2026-06-05", "oil_bopd": 200, "action": "create"},
        ]
    }
    response = client.post("/production/import/confirm", json=payload, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["created"] == 1
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["row_number"] == 3

    records = (
        db_session.query(ProductionRecord)
        .filter(ProductionRecord.well_id == well.id, ProductionRecord.record_date == date(2026, 6, 5))
        .all()
    )
    assert len(records) == 1
    assert records[0].oil_bopd == 100


def test_confirm_creates_pressure_and_temperature_records(client, make_field_facility_well, auth_headers, db_session):
    """Exercises the batched pressure/temperature existence-check pre-fetch, not just
    ProductionRecord — confirms all three tables are still populated correctly."""
    _, _, well = make_field_facility_well(well_id="I-007")
    headers = auth_headers("Administrator")

    payload = {
        "rows": [
            {
                "row_number": 2, "well_id": "I-007", "record_date": "2026-06-06", "oil_bopd": 100,
                "wellhead_pressure": 1500, "tubing_pressure": 1700, "wellhead_temperature": 180,
                "action": "create",
            },
        ]
    }
    response = client.post("/production/import/confirm", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["created"] == 1

    pressure = (
        db_session.query(PressureRecord)
        .filter(PressureRecord.well_id == well.id, PressureRecord.record_date == date(2026, 6, 6))
        .first()
    )
    assert pressure is not None and pressure.wellhead_pressure == 1500

    temperature = (
        db_session.query(TemperatureRecord)
        .filter(TemperatureRecord.well_id == well.id, TemperatureRecord.record_date == date(2026, 6, 6))
        .first()
    )
    assert temperature is not None and temperature.wellhead_temperature == 180
