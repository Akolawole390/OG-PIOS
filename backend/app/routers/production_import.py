import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_role
from app.models.field import Well
from app.models.production import PressureRecord, ProductionRecord, TemperatureRecord
from app.models.user import User
from app.schemas.production import (
    ImportConfirmRequest,
    ImportConfirmResponse,
    ImportPreviewResponse,
    ImportRejectedRow,
    ImportRowResult,
)
from app.services.csv_import import parse_csv_rows
from app.services.production_calculations import compute_gor, compute_water_cut_pct
from app.services.production_validation import validate_production_row

router = APIRouter(prefix="/production/import", tags=["production-import"])

logger = logging.getLogger(__name__)


def _parse_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if value is None or value.strip() == "":
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


@router.post("/preview", response_model=ImportPreviewResponse)
def preview_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ImportPreviewResponse:
    """Parses + validates + classifies every row. Persists nothing."""
    raw_bytes = file.file.read()
    raw_rows = parse_csv_rows(raw_bytes)

    wells_by_code = {w.well_id: w for w in db.query(Well).all()}
    existing_keys = {
        (well_id, record_date): id_
        for well_id, record_date, id_ in db.query(
            ProductionRecord.well_id, ProductionRecord.record_date, ProductionRecord.id
        )
    }

    seen_in_file: set[tuple[str, str]] = set()
    results: list[ImportRowResult] = []

    for index, raw in enumerate(raw_rows, start=2):  # row 1 is the header
        well_code = (raw.get("well_id") or "").strip()
        record_date_str = (raw.get("record_date") or "").strip()
        messages: list[str] = []
        row_status = "valid"

        well = wells_by_code.get(well_code)
        if not well_code:
            messages.append("Missing well_id.")
            row_status = "invalid"
        elif well is None:
            messages.append(f"Unrecognized well_id '{well_code}'.")
            row_status = "invalid"

        record_date = _parse_date(record_date_str)
        if not record_date_str:
            messages.append("Missing record_date.")
            row_status = "invalid"
        elif record_date is None:
            messages.append("record_date must be in YYYY-MM-DD format.")
            row_status = "invalid"

        oil_bopd = _parse_float(raw.get("oil_bopd")) or 0.0
        gas_mscfd = _parse_float(raw.get("gas_mscfd")) or 0.0
        water_bwpd = _parse_float(raw.get("water_bwpd")) or 0.0
        choke_size = _parse_float(raw.get("choke_size"))
        wellhead_pressure = _parse_float(raw.get("wellhead_pressure"))
        tubing_pressure = _parse_float(raw.get("tubing_pressure"))
        casing_pressure = _parse_float(raw.get("casing_pressure"))
        flowline_pressure = _parse_float(raw.get("flowline_pressure"))
        wellhead_temperature = _parse_float(raw.get("wellhead_temperature"))

        parsed = {
            "well_id": well_code,
            "record_date": record_date_str,
            "oil_bopd": oil_bopd,
            "gas_mscfd": gas_mscfd,
            "water_bwpd": water_bwpd,
            "choke_size": choke_size,
            "wellhead_pressure": wellhead_pressure,
            "tubing_pressure": tubing_pressure,
            "casing_pressure": casing_pressure,
            "flowline_pressure": flowline_pressure,
            "wellhead_temperature": wellhead_temperature,
        }

        existing_record_id: int | None = None
        if row_status != "invalid":
            issues = validate_production_row(
                oil_bopd=oil_bopd, gas_mscfd=gas_mscfd, water_bwpd=water_bwpd,
                wellhead_pressure=wellhead_pressure, tubing_pressure=tubing_pressure,
                casing_pressure=casing_pressure, flowline_pressure=flowline_pressure,
                wellhead_temperature=wellhead_temperature, choke_size=choke_size,
            )
            invalid_messages = [i.message for i in issues if i.severity == "invalid"]
            warning_messages = [i.message for i in issues if i.severity == "warning"]

            if invalid_messages:
                row_status = "invalid"
                messages.extend(invalid_messages)
            else:
                file_key = (well_code, record_date_str)
                db_key = (well.id, record_date) if well and record_date else None
                if file_key in seen_in_file:
                    row_status = "duplicate"
                    messages.append("Duplicate well_id/record_date within this file.")
                elif db_key and db_key in existing_keys:
                    row_status = "duplicate"
                    existing_record_id = existing_keys[db_key]
                    messages.append("A record already exists for this well and date.")
                elif warning_messages:
                    row_status = "warning"
                    messages.extend(warning_messages)

        seen_in_file.add((well_code, record_date_str))

        results.append(
            ImportRowResult(
                row_number=index, status=row_status, well_id=well_code,
                record_date=record_date_str or None, parsed=parsed, messages=messages,
                existing_record_id=existing_record_id,
            )
        )

    return ImportPreviewResponse(
        total_rows=len(results),
        valid_count=sum(1 for r in results if r.status == "valid"),
        warning_count=sum(1 for r in results if r.status == "warning"),
        duplicate_count=sum(1 for r in results if r.status == "duplicate"),
        invalid_count=sum(1 for r in results if r.status == "invalid"),
        rows=results,
    )


@router.post("/confirm", response_model=ImportConfirmResponse)
def confirm_import(
    payload: ImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ImportConfirmResponse:
    """Re-validates and re-checks duplicates from scratch for every row — never trusts
    whatever status the client's preview claimed."""
    wells_by_code = {w.well_id: w for w in db.query(Well).all()}

    # Batched once across every row in the payload — replaces what was previously up to 3
    # separate per-row existence-check queries (ProductionRecord/PressureRecord/
    # TemperatureRecord) inside the loop below with 3 queries total. Superset-fetches by
    # (well_id in involved wells) x (date in involved dates) rather than the exact pair set —
    # harmless (a few extra rows transferred, never fewer), and still one round trip instead
    # of one per row.
    candidate_well_ids: set[int] = set()
    candidate_dates: set[date] = set()
    for row in payload.rows:
        if row.action == "skip":
            continue
        well = wells_by_code.get(row.well_id)
        record_date = _parse_date(row.record_date)
        if well is not None and record_date is not None:
            candidate_well_ids.add(well.id)
            candidate_dates.add(record_date)

    existing_production_by_key: dict[tuple[int, date], ProductionRecord] = {}
    existing_pressure_by_key: dict[tuple[int, date], PressureRecord] = {}
    existing_temperature_by_key: dict[tuple[int, date], TemperatureRecord] = {}
    if candidate_well_ids and candidate_dates:
        for r in (
            db.query(ProductionRecord)
            .filter(ProductionRecord.well_id.in_(candidate_well_ids), ProductionRecord.record_date.in_(candidate_dates))
            .all()
        ):
            existing_production_by_key[(r.well_id, r.record_date)] = r
        for r in (
            db.query(PressureRecord)
            .filter(PressureRecord.well_id.in_(candidate_well_ids), PressureRecord.record_date.in_(candidate_dates))
            .all()
        ):
            existing_pressure_by_key[(r.well_id, r.record_date)] = r
        for r in (
            db.query(TemperatureRecord)
            .filter(TemperatureRecord.well_id.in_(candidate_well_ids), TemperatureRecord.record_date.in_(candidate_dates))
            .all()
        ):
            existing_temperature_by_key[(r.well_id, r.record_date)] = r

    created = 0
    updated = 0
    skipped = 0
    rejected: list[ImportRejectedRow] = []

    for row in payload.rows:
        if row.action == "skip":
            skipped += 1
            continue

        well = wells_by_code.get(row.well_id)
        record_date = _parse_date(row.record_date)
        row_messages: list[str] = []

        if well is None:
            row_messages.append(f"Unrecognized well_id '{row.well_id}'.")
        if record_date is None:
            row_messages.append("record_date must be in YYYY-MM-DD format.")

        if not row_messages:
            issues = validate_production_row(
                oil_bopd=row.oil_bopd, gas_mscfd=row.gas_mscfd, water_bwpd=row.water_bwpd,
                wellhead_pressure=row.wellhead_pressure, tubing_pressure=row.tubing_pressure,
                casing_pressure=row.casing_pressure, flowline_pressure=row.flowline_pressure,
                wellhead_temperature=row.wellhead_temperature, choke_size=row.choke_size,
            )
            row_messages.extend(i.message for i in issues if i.severity == "invalid")

        if row_messages:
            rejected.append(
                ImportRejectedRow(row_number=row.row_number, well_id=row.well_id, record_date=row.record_date, messages=row_messages)
            )
            continue

        existing = existing_production_by_key.get((well.id, record_date))

        if existing is not None and row.action != "overwrite":
            rejected.append(
                ImportRejectedRow(
                    row_number=row.row_number, well_id=row.well_id, record_date=row.record_date,
                    messages=["Record already exists; choose overwrite or skip."],
                )
            )
            continue

        water_cut_pct = compute_water_cut_pct(row.oil_bopd, row.water_bwpd)
        gor = compute_gor(row.oil_bopd, row.gas_mscfd)
        is_update = existing is not None

        try:
            with db.begin_nested():
                if existing is not None:
                    production = existing
                    production.oil_bopd = row.oil_bopd
                    production.gas_mscfd = row.gas_mscfd
                    production.water_bwpd = row.water_bwpd
                    production.water_cut_pct = water_cut_pct
                    production.gor = gor
                    production.choke_size = row.choke_size
                else:
                    production = ProductionRecord(
                        well_id=well.id, record_date=record_date,
                        oil_bopd=row.oil_bopd, gas_mscfd=row.gas_mscfd, water_bwpd=row.water_bwpd,
                        water_cut_pct=water_cut_pct, gor=gor, choke_size=row.choke_size,
                    )
                    db.add(production)
                    existing_production_by_key[(well.id, record_date)] = production

                if any(
                    v is not None
                    for v in (row.wellhead_pressure, row.tubing_pressure, row.casing_pressure, row.flowline_pressure)
                ):
                    pressure = existing_pressure_by_key.get((well.id, record_date))
                    if pressure is None:
                        pressure = PressureRecord(well_id=well.id, record_date=record_date)
                        db.add(pressure)
                        existing_pressure_by_key[(well.id, record_date)] = pressure
                    pressure.wellhead_pressure = row.wellhead_pressure
                    pressure.tubing_pressure = row.tubing_pressure
                    pressure.casing_pressure = row.casing_pressure
                    pressure.flowline_pressure = row.flowline_pressure

                if row.wellhead_temperature is not None:
                    temperature = existing_temperature_by_key.get((well.id, record_date))
                    if temperature is None:
                        temperature = TemperatureRecord(well_id=well.id, record_date=record_date)
                        db.add(temperature)
                        existing_temperature_by_key[(well.id, record_date)] = temperature
                    temperature.wellhead_temperature = row.wellhead_temperature

                db.flush()

            if is_update:
                updated += 1
            else:
                created += 1
        except Exception:  # pragma: no cover - defensive, catches DB-level failures per row
            # Never surface a raw DB/exception string to the client — it can reveal constraint
            # names or internal structure. Log the real error server-side, reject with a
            # generic message instead.
            logger.exception("CSV import row %s failed to write", row.row_number)
            rejected.append(
                ImportRejectedRow(
                    row_number=row.row_number, well_id=row.well_id, record_date=row.record_date,
                    messages=["This row could not be saved due to an unexpected error."],
                )
            )

    db.commit()
    return ImportConfirmResponse(created=created, updated=updated, skipped=skipped, rejected=rejected)
