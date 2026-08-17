import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.equipment import DowntimeEvent
from app.models.field import Facility, Field, Well
from app.models.production import (
    PressureRecord,
    ProductionRecord,
    ProductionTarget,
    TemperatureRecord,
)
from app.models.user import User
from app.schemas.production import (
    ActualVsTargetPoint,
    ActualVsTargetResponse,
    ByScopeResponse,
    ProductionKpis,
    ProductionIssuesResponse,
    ProductionListResponse,
    ProductionRecordCreate,
    ProductionRecordRead,
    ProductionRecordUpdate,
    ProductionTargetCreate,
    ProductionTargetRead,
    ProductionTargetUpdate,
    ScopeBar,
    TrendResponse,
    WellIssueSummary,
)
from app.services.production_calculations import compute_boe, compute_gor, compute_water_cut_pct
from app.services.production_validation import has_invalid, validate_production_row
from app.services.system_settings import get_boe_gas_factor

router = APIRouter(prefix="/production", tags=["production"])

SORTABLE_FIELDS = {
    "record_date": ProductionRecord.record_date,
    "well_id": Well.well_id,
    "oil_bopd": ProductionRecord.oil_bopd,
    "gas_mscfd": ProductionRecord.gas_mscfd,
    "water_bwpd": ProductionRecord.water_bwpd,
}


# ----- Shared helpers -----


def _build_production_query(
    db: Session,
    *,
    search: str | None,
    well_id: int | None,
    field_id: int | None,
    facility_id: int | None,
    date_from: date | None,
    date_to: date | None,
):
    query = (
        db.query(ProductionRecord)
        .join(Well, ProductionRecord.well_id == Well.id)
        .join(Facility, Well.facility_id == Facility.id)
        .join(Field, Facility.field_id == Field.id)
        .options(joinedload(ProductionRecord.well).joinedload(Well.facility).joinedload(Facility.field))
    )
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Well.well_id.ilike(like), Well.name.ilike(like)))
    if well_id:
        query = query.filter(ProductionRecord.well_id == well_id)
    if field_id:
        query = query.filter(Facility.field_id == field_id)
    if facility_id:
        query = query.filter(Well.facility_id == facility_id)
    if date_from:
        query = query.filter(ProductionRecord.record_date >= date_from)
    if date_to:
        query = query.filter(ProductionRecord.record_date <= date_to)
    return query


def _compute_downtime_hours(events: list[DowntimeEvent], well_id: int, record_date: date) -> float:
    window_start = datetime.combine(record_date, time.min, tzinfo=timezone.utc)
    window_end = window_start + timedelta(days=1)
    now = datetime.now(timezone.utc)
    total = 0.0
    for event in events:
        if event.well_id != well_id:
            continue
        event_end = event.end_time or now
        start = max(event.start_time, window_start)
        end = min(event_end, window_end)
        if end > start:
            total += (end - start).total_seconds() / 3600
    return round(total, 2)


def _downtime_hours_for(db: Session, well_id: int, record_date: date) -> float:
    window_start = datetime.combine(record_date, time.min, tzinfo=timezone.utc)
    window_end = window_start + timedelta(days=1)
    events = (
        db.query(DowntimeEvent)
        .filter(
            DowntimeEvent.well_id == well_id,
            DowntimeEvent.start_time < window_end,
            or_(DowntimeEvent.end_time.is_(None), DowntimeEvent.end_time > window_start),
        )
        .all()
    )
    return _compute_downtime_hours(events, well_id, record_date)


def _build_record_read(
    *,
    production: ProductionRecord,
    pressure: PressureRecord | None,
    temperature: TemperatureRecord | None,
    well: Well,
    boe_gas_factor: float,
    downtime_hours: float = 0.0,
    warnings: list[str] | None = None,
) -> ProductionRecordRead:
    return ProductionRecordRead(
        id=production.id,
        record_date=production.record_date,
        well_id=well.id,
        well_code=well.well_id,
        well_name=well.name,
        facility_id=well.facility.id,
        facility_name=well.facility.name,
        field_id=well.facility.field.id,
        field_name=well.facility.field.name,
        oil_bopd=production.oil_bopd,
        gas_mscfd=production.gas_mscfd,
        water_bwpd=production.water_bwpd,
        water_cut_pct=production.water_cut_pct,
        gor=production.gor,
        boe=compute_boe(production.oil_bopd, production.gas_mscfd, boe_gas_factor),
        choke_size=production.choke_size,
        wellhead_pressure=pressure.wellhead_pressure if pressure else None,
        tubing_pressure=pressure.tubing_pressure if pressure else None,
        casing_pressure=pressure.casing_pressure if pressure else None,
        flowline_pressure=pressure.flowline_pressure if pressure else None,
        wellhead_temperature=temperature.wellhead_temperature if temperature else None,
        downtime_hours=downtime_hours,
        warnings=warnings,
    )


def _hydrate_records(db: Session, records: list[ProductionRecord]) -> list[ProductionRecordRead]:
    if not records:
        return []

    well_ids = {r.well_id for r in records}
    dates = {r.record_date for r in records}
    boe_gas_factor = get_boe_gas_factor(db)

    pressures = {
        (p.well_id, p.record_date): p
        for p in db.query(PressureRecord).filter(
            PressureRecord.well_id.in_(well_ids), PressureRecord.record_date.in_(dates)
        )
    }
    temperatures = {
        (t.well_id, t.record_date): t
        for t in db.query(TemperatureRecord).filter(
            TemperatureRecord.well_id.in_(well_ids), TemperatureRecord.record_date.in_(dates)
        )
    }

    min_date, max_date = min(dates), max(dates)
    window_start = datetime.combine(min_date, time.min, tzinfo=timezone.utc)
    window_end = datetime.combine(max_date, time.min, tzinfo=timezone.utc) + timedelta(days=1)
    downtime_events = (
        db.query(DowntimeEvent)
        .filter(
            DowntimeEvent.well_id.in_(well_ids),
            DowntimeEvent.start_time < window_end,
            or_(DowntimeEvent.end_time.is_(None), DowntimeEvent.end_time > window_start),
        )
        .all()
    )

    items = []
    for record in records:
        key = (record.well_id, record.record_date)
        well_events = [e for e in downtime_events if e.well_id == record.well_id]
        downtime_hours = _compute_downtime_hours(well_events, record.well_id, record.record_date)
        items.append(
            _build_record_read(
                production=record,
                pressure=pressures.get(key),
                temperature=temperatures.get(key),
                well=record.well,
                boe_gas_factor=boe_gas_factor,
                downtime_hours=downtime_hours,
            )
        )
    return items


def _get_production_or_404(db: Session, id: int) -> ProductionRecord:
    production = (
        db.query(ProductionRecord)
        .options(joinedload(ProductionRecord.well).joinedload(Well.facility).joinedload(Facility.field))
        .filter(ProductionRecord.id == id)
        .first()
    )
    if production is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production record not found")
    return production


def _resolve_target(db: Session, well_id: int, on_date: date) -> ProductionTarget | None:
    return (
        db.query(ProductionTarget)
        .filter(ProductionTarget.well_id == well_id, ProductionTarget.effective_date <= on_date)
        .order_by(ProductionTarget.effective_date.desc())
        .first()
    )


def _target_read(target: ProductionTarget, well: Well) -> ProductionTargetRead:
    return ProductionTargetRead(
        id=target.id,
        well_id=target.well_id,
        well_code=well.well_id,
        well_name=well.name,
        effective_date=target.effective_date,
        oil_target_bopd=target.oil_target_bopd,
        gas_target_mscfd=target.gas_target_mscfd,
        water_target_bwpd=target.water_target_bwpd,
    )


# ----- List / create (must come before the /{id} routes below) -----


@router.get("", response_model=ProductionListResponse)
def list_production(
    search: str | None = None,
    well_id: int | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "record_date",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionListResponse:
    query = _build_production_query(
        db, search=search, well_id=well_id, field_id=field_id, facility_id=facility_id,
        date_from=date_from, date_to=date_to,
    )

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, ProductionRecord.record_date)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    items = _hydrate_records(db, records)

    return ProductionListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ProductionRecordRead, status_code=status.HTTP_201_CREATED)
def create_production_record(
    payload: ProductionRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ProductionRecordRead:
    well = (
        db.query(Well)
        .options(joinedload(Well.facility).joinedload(Facility.field))
        .filter(Well.id == payload.well_id)
        .first()
    )
    if well is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")

    existing = (
        db.query(ProductionRecord)
        .filter(ProductionRecord.well_id == payload.well_id, ProductionRecord.record_date == payload.record_date)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A production record already exists for this well and date.",
        )

    issues = validate_production_row(
        oil_bopd=payload.oil_bopd,
        gas_mscfd=payload.gas_mscfd,
        water_bwpd=payload.water_bwpd,
        wellhead_pressure=payload.wellhead_pressure,
        tubing_pressure=payload.tubing_pressure,
        casing_pressure=payload.casing_pressure,
        flowline_pressure=payload.flowline_pressure,
        wellhead_temperature=payload.wellhead_temperature,
        choke_size=payload.choke_size,
    )
    if has_invalid(issues):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"field": i.field, "message": i.message} for i in issues if i.severity == "invalid"],
        )

    production = ProductionRecord(
        well_id=payload.well_id,
        record_date=payload.record_date,
        oil_bopd=payload.oil_bopd,
        gas_mscfd=payload.gas_mscfd,
        water_bwpd=payload.water_bwpd,
        water_cut_pct=compute_water_cut_pct(payload.oil_bopd, payload.water_bwpd),
        gor=compute_gor(payload.oil_bopd, payload.gas_mscfd),
        choke_size=payload.choke_size,
    )
    db.add(production)

    pressure = None
    if any(
        v is not None
        for v in (payload.wellhead_pressure, payload.tubing_pressure, payload.casing_pressure, payload.flowline_pressure)
    ):
        pressure = PressureRecord(
            well_id=payload.well_id,
            record_date=payload.record_date,
            wellhead_pressure=payload.wellhead_pressure,
            tubing_pressure=payload.tubing_pressure,
            casing_pressure=payload.casing_pressure,
            flowline_pressure=payload.flowline_pressure,
        )
        db.add(pressure)

    temperature = None
    if payload.wellhead_temperature is not None:
        temperature = TemperatureRecord(
            well_id=payload.well_id, record_date=payload.record_date, wellhead_temperature=payload.wellhead_temperature
        )
        db.add(temperature)

    db.commit()
    db.refresh(production)

    boe_gas_factor = get_boe_gas_factor(db)
    warnings = [i.message for i in issues if i.severity == "warning"] or None

    return _build_record_read(
        production=production, pressure=pressure, temperature=temperature, well=well,
        boe_gas_factor=boe_gas_factor, downtime_hours=_downtime_hours_for(db, well.id, payload.record_date),
        warnings=warnings,
    )


# ----- Fixed sub-paths (must be registered before /{id}) -----


@router.get("/export")
def export_production_csv(
    search: str | None = None,
    well_id: int | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    query = _build_production_query(
        db, search=search, well_id=well_id, field_id=field_id, facility_id=facility_id,
        date_from=date_from, date_to=date_to,
    )
    records = query.order_by(ProductionRecord.record_date).all()
    items = _hydrate_records(db, records)

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "record_date", "well_id", "well_name", "field_name", "facility_name",
                "oil_bopd", "gas_mscfd", "water_bwpd", "water_cut_pct", "gor", "boe",
                "wellhead_pressure", "tubing_pressure", "casing_pressure", "flowline_pressure",
                "wellhead_temperature", "choke_size", "downtime_hours",
            ]
        )
        yield buffer.getvalue()
        for item in items:
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow(
                [
                    item.record_date, item.well_code, item.well_name, item.field_name, item.facility_name,
                    item.oil_bopd, item.gas_mscfd, item.water_bwpd, item.water_cut_pct, item.gor, item.boe,
                    item.wellhead_pressure, item.tubing_pressure, item.casing_pressure, item.flowline_pressure,
                    item.wellhead_temperature, item.choke_size, item.downtime_hours,
                ]
            )
            yield buffer.getvalue()

    return StreamingResponse(
        generate(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=production_export.csv"},
    )


@router.get("/kpis", response_model=ProductionKpis)
def get_production_kpis(
    well_id: int | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionKpis:
    records = _build_production_query(
        db, search=None, well_id=well_id, field_id=field_id, facility_id=facility_id,
        date_from=date_from, date_to=date_to,
    ).all()

    boe_gas_factor = get_boe_gas_factor(db)

    if not records:
        return ProductionKpis(
            total_oil_bbl=0, total_gas_mscf=0, total_water_bbl=0,
            avg_daily_oil_bopd=0, avg_daily_gas_mscfd=0, avg_daily_water_bwpd=0,
            avg_water_cut_pct=None, avg_gor=None, boe=0, boe_gas_factor=boe_gas_factor,
            producing_wells_count=0, target_oil_bopd=None, target_variance_pct=None,
            reference_date=None, days_in_range=0,
        )

    total_oil = sum(r.oil_bopd for r in records)
    total_gas = sum(r.gas_mscfd for r in records)
    total_water = sum(r.water_bwpd for r in records)
    distinct_dates = {r.record_date for r in records}
    days = len(distinct_dates)
    reference_date = max(distinct_dates)

    avg_water_cut = (
        round(total_water / (total_oil + total_water) * 100, 2) if (total_oil + total_water) > 0 else None
    )
    avg_gor = round(total_gas * 1000 / total_oil, 2) if total_oil > 0 else None

    reference_records = [r for r in records if r.record_date == reference_date]
    producing_well_ids = {r.well_id for r in reference_records if r.oil_bopd > 0 or r.gas_mscfd > 0}
    producing_wells_count = 0
    if producing_well_ids:
        producing_wells_count = (
            db.query(Well.id).filter(Well.id.in_(producing_well_ids), Well.status == "active").count()
        )

    target_oil_sum = 0.0
    actual_oil_for_targeted = 0.0
    any_target = False
    for r in reference_records:
        target = _resolve_target(db, r.well_id, reference_date)
        if target is not None and target.oil_target_bopd is not None:
            any_target = True
            target_oil_sum += target.oil_target_bopd
            actual_oil_for_targeted += r.oil_bopd

    target_oil_bopd = round(target_oil_sum, 2) if any_target and target_oil_sum > 0 else None
    target_variance_pct = (
        round((actual_oil_for_targeted - target_oil_sum) / target_oil_sum * 100, 2)
        if any_target and target_oil_sum > 0
        else None
    )

    return ProductionKpis(
        total_oil_bbl=round(total_oil, 2),
        total_gas_mscf=round(total_gas, 2),
        total_water_bbl=round(total_water, 2),
        avg_daily_oil_bopd=round(total_oil / days, 2),
        avg_daily_gas_mscfd=round(total_gas / days, 2),
        avg_daily_water_bwpd=round(total_water / days, 2),
        avg_water_cut_pct=avg_water_cut,
        avg_gor=avg_gor,
        boe=compute_boe(total_oil, total_gas, boe_gas_factor),
        boe_gas_factor=boe_gas_factor,
        producing_wells_count=producing_wells_count,
        target_oil_bopd=target_oil_bopd,
        target_variance_pct=target_variance_pct,
        reference_date=reference_date,
        days_in_range=days,
    )


@router.get("/trends", response_model=TrendResponse)
def get_production_trends(
    metric: str = Query("oil_gas_water", pattern="^(oil_gas_water|water_cut|gor|pressure)$"),
    well_id: int | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrendResponse:
    records = _build_production_query(
        db, search=None, well_id=well_id, field_id=field_id, facility_id=facility_id,
        date_from=date_from, date_to=date_to,
    ).order_by(ProductionRecord.record_date).all()

    if metric == "pressure":
        well_ids = {r.well_id for r in records}
        dates = sorted({r.record_date for r in records})
        pressures = (
            db.query(PressureRecord)
            .filter(PressureRecord.well_id.in_(well_ids), PressureRecord.record_date.in_(dates))
            .all()
            if well_ids
            else []
        )
        by_date: dict[date, list[PressureRecord]] = {}
        for p in pressures:
            by_date.setdefault(p.record_date, []).append(p)

        points = []
        for d in dates:
            rows = by_date.get(d, [])
            if not rows:
                continue
            points.append(
                {
                    "record_date": d.isoformat(),
                    "wellhead_pressure": round(sum(r.wellhead_pressure or 0 for r in rows) / len(rows), 1),
                    "tubing_pressure": round(sum(r.tubing_pressure or 0 for r in rows) / len(rows), 1),
                    "casing_pressure": round(sum(r.casing_pressure or 0 for r in rows) / len(rows), 1),
                    "flowline_pressure": round(sum(r.flowline_pressure or 0 for r in rows) / len(rows), 1),
                }
            )
        return TrendResponse(metric=metric, points=points)

    by_date: dict[date, list[ProductionRecord]] = {}
    for r in records:
        by_date.setdefault(r.record_date, []).append(r)

    points = []
    for d in sorted(by_date.keys()):
        rows = by_date[d]
        oil = sum(r.oil_bopd for r in rows)
        gas = sum(r.gas_mscfd for r in rows)
        water = sum(r.water_bwpd for r in rows)
        if metric == "oil_gas_water":
            points.append(
                {"record_date": d.isoformat(), "oil_bopd": round(oil, 1), "gas_mscfd": round(gas, 2), "water_bwpd": round(water, 1)}
            )
        elif metric == "water_cut":
            points.append({"record_date": d.isoformat(), "water_cut_pct": compute_water_cut_pct(oil, water)})
        elif metric == "gor":
            points.append({"record_date": d.isoformat(), "gor": compute_gor(oil, gas)})

    return TrendResponse(metric=metric, points=points)


@router.get("/by-scope", response_model=ByScopeResponse)
def get_production_by_scope(
    group_by: str = Query("well", pattern="^(well|field|facility)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ByScopeResponse:
    records = _build_production_query(
        db, search=None, well_id=None, field_id=None, facility_id=None, date_from=date_from, date_to=date_to,
    ).all()

    boe_gas_factor = get_boe_gas_factor(db)
    groups: dict[str, dict] = {}
    for r in records:
        well = r.well
        if group_by == "well":
            key, label = str(well.id), well.well_id
        elif group_by == "field":
            key, label = str(well.facility.field.id), well.facility.field.name
        else:
            key, label = str(well.facility.id), well.facility.name

        bucket = groups.setdefault(key, {"label": label, "oil_bopd": 0.0, "gas_mscfd": 0.0, "water_bwpd": 0.0})
        bucket["oil_bopd"] += r.oil_bopd
        bucket["gas_mscfd"] += r.gas_mscfd
        bucket["water_bwpd"] += r.water_bwpd

    bars = [
        ScopeBar(
            key=key,
            label=bucket["label"],
            oil_bopd=round(bucket["oil_bopd"], 1),
            gas_mscfd=round(bucket["gas_mscfd"], 2),
            water_bwpd=round(bucket["water_bwpd"], 1),
            boe=compute_boe(bucket["oil_bopd"], bucket["gas_mscfd"], boe_gas_factor),
        )
        for key, bucket in groups.items()
    ]
    bars.sort(key=lambda b: b.oil_bopd, reverse=(order == "desc"))
    return ByScopeResponse(group_by=group_by, bars=bars[:limit])


@router.get("/actual-vs-target", response_model=ActualVsTargetResponse)
def get_actual_vs_target(
    well_id: int | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ActualVsTargetResponse:
    records = _build_production_query(
        db, search=None, well_id=well_id, field_id=field_id, facility_id=facility_id,
        date_from=date_from, date_to=date_to,
    ).order_by(ProductionRecord.record_date).all()

    well_ids = {r.well_id for r in records}
    targets = (
        db.query(ProductionTarget)
        .filter(ProductionTarget.well_id.in_(well_ids))
        .order_by(ProductionTarget.well_id, ProductionTarget.effective_date)
        .all()
        if well_ids
        else []
    )
    targets_by_well: dict[int, list[ProductionTarget]] = {}
    for t in targets:
        targets_by_well.setdefault(t.well_id, []).append(t)

    def resolve(target_well_id: int, on_date: date) -> ProductionTarget | None:
        candidates = [t for t in targets_by_well.get(target_well_id, []) if t.effective_date <= on_date]
        return candidates[-1] if candidates else None

    by_date: dict[date, list[ProductionRecord]] = {}
    for r in records:
        by_date.setdefault(r.record_date, []).append(r)

    points = []
    for d in sorted(by_date.keys()):
        rows = by_date[d]
        actual_oil = sum(r.oil_bopd for r in rows)
        target_sum = 0.0
        has_target = False
        for r in rows:
            target = resolve(r.well_id, d)
            if target is not None and target.oil_target_bopd is not None:
                target_sum += target.oil_target_bopd
                has_target = True
        points.append(
            ActualVsTargetPoint(
                record_date=d, actual_oil_bopd=round(actual_oil, 1),
                target_oil_bopd=round(target_sum, 1) if has_target else None,
            )
        )
    return ActualVsTargetResponse(points=points)


@router.get("/issues", response_model=ProductionIssuesResponse)
def get_production_issues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionIssuesResponse:
    reference_date = db.query(func.max(ProductionRecord.record_date)).scalar()

    down_events = (
        db.query(DowntimeEvent)
        .filter(DowntimeEvent.end_time.is_(None), DowntimeEvent.well_id.isnot(None))
        .all()
    )
    down_well_ids = {e.well_id for e in down_events if e.well_id is not None}
    down_wells = []
    if down_well_ids:
        for w in db.query(Well).filter(Well.id.in_(down_well_ids)):
            down_wells.append(
                WellIssueSummary(well_id=w.id, well_code=w.well_id, well_name=w.name, detail="Currently down (open downtime event)")
            )

    zero_production_wells = []
    if reference_date is not None:
        zero_records = (
            db.query(ProductionRecord)
            .join(Well, ProductionRecord.well_id == Well.id)
            .options(joinedload(ProductionRecord.well))
            .filter(
                ProductionRecord.record_date == reference_date,
                Well.status == "active",
                ProductionRecord.oil_bopd == 0,
                ProductionRecord.gas_mscfd == 0,
            )
            .all()
        )
        for r in zero_records:
            zero_production_wells.append(
                WellIssueSummary(
                    well_id=r.well_id, well_code=r.well.well_id, well_name=r.well.name,
                    detail=f"Zero production on {reference_date}",
                )
            )

    return ProductionIssuesResponse(
        reference_date=reference_date, down_wells=down_wells, zero_production_wells=zero_production_wells
    )


# ----- Production targets -----


@router.get("/targets", response_model=list[ProductionTargetRead])
def list_production_targets(
    well_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductionTargetRead]:
    query = db.query(ProductionTarget).options(joinedload(ProductionTarget.well))
    if well_id:
        query = query.filter(ProductionTarget.well_id == well_id)
    targets = query.order_by(ProductionTarget.well_id, ProductionTarget.effective_date.desc()).all()
    return [_target_read(t, t.well) for t in targets]


@router.post("/targets", response_model=ProductionTargetRead, status_code=status.HTTP_201_CREATED)
def create_production_target(
    payload: ProductionTargetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ProductionTargetRead:
    well = db.query(Well).filter(Well.id == payload.well_id).first()
    if well is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")

    existing = (
        db.query(ProductionTarget)
        .filter(ProductionTarget.well_id == payload.well_id, ProductionTarget.effective_date == payload.effective_date)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A target already exists for this well and effective date."
        )

    target = ProductionTarget(**payload.model_dump())
    db.add(target)
    db.commit()
    db.refresh(target)
    return _target_read(target, well)


@router.put("/targets/{id}", response_model=ProductionTargetRead)
def update_production_target(
    id: int,
    payload: ProductionTargetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ProductionTargetRead:
    target = (
        db.query(ProductionTarget).options(joinedload(ProductionTarget.well)).filter(ProductionTarget.id == id).first()
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field_name, value)
    db.commit()
    db.refresh(target)
    return _target_read(target, target.well)


@router.delete("/targets/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_production_target(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> None:
    target = db.query(ProductionTarget).filter(ProductionTarget.id == id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    db.delete(target)
    db.commit()


# ----- Single-record routes (must come after the fixed sub-paths above) -----


@router.get("/{id}", response_model=ProductionRecordRead)
def get_production_record(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionRecordRead:
    production = _get_production_or_404(db, id)
    pressure = (
        db.query(PressureRecord)
        .filter(PressureRecord.well_id == production.well_id, PressureRecord.record_date == production.record_date)
        .first()
    )
    temperature = (
        db.query(TemperatureRecord)
        .filter(TemperatureRecord.well_id == production.well_id, TemperatureRecord.record_date == production.record_date)
        .first()
    )
    boe_gas_factor = get_boe_gas_factor(db)
    return _build_record_read(
        production=production, pressure=pressure, temperature=temperature, well=production.well,
        boe_gas_factor=boe_gas_factor,
        downtime_hours=_downtime_hours_for(db, production.well_id, production.record_date),
    )


@router.put("/{id}", response_model=ProductionRecordRead)
def update_production_record(
    id: int,
    payload: ProductionRecordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ProductionRecordRead:
    production = _get_production_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)

    merged_oil = update_data.get("oil_bopd", production.oil_bopd)
    merged_gas = update_data.get("gas_mscfd", production.gas_mscfd)
    merged_water = update_data.get("water_bwpd", production.water_bwpd)
    merged_choke = update_data.get("choke_size", production.choke_size)

    pressure = (
        db.query(PressureRecord)
        .filter(PressureRecord.well_id == production.well_id, PressureRecord.record_date == production.record_date)
        .first()
    )
    temperature = (
        db.query(TemperatureRecord)
        .filter(TemperatureRecord.well_id == production.well_id, TemperatureRecord.record_date == production.record_date)
        .first()
    )

    wellhead_pressure = update_data.get("wellhead_pressure", pressure.wellhead_pressure if pressure else None)
    tubing_pressure = update_data.get("tubing_pressure", pressure.tubing_pressure if pressure else None)
    casing_pressure = update_data.get("casing_pressure", pressure.casing_pressure if pressure else None)
    flowline_pressure = update_data.get("flowline_pressure", pressure.flowline_pressure if pressure else None)
    wellhead_temperature = update_data.get(
        "wellhead_temperature", temperature.wellhead_temperature if temperature else None
    )

    issues = validate_production_row(
        oil_bopd=merged_oil, gas_mscfd=merged_gas, water_bwpd=merged_water,
        wellhead_pressure=wellhead_pressure, tubing_pressure=tubing_pressure,
        casing_pressure=casing_pressure, flowline_pressure=flowline_pressure,
        wellhead_temperature=wellhead_temperature, choke_size=merged_choke,
    )
    if has_invalid(issues):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[{"field": i.field, "message": i.message} for i in issues if i.severity == "invalid"],
        )

    production.oil_bopd = merged_oil
    production.gas_mscfd = merged_gas
    production.water_bwpd = merged_water
    production.choke_size = merged_choke
    production.water_cut_pct = compute_water_cut_pct(merged_oil, merged_water)
    production.gor = compute_gor(merged_oil, merged_gas)

    if any(v is not None for v in (wellhead_pressure, tubing_pressure, casing_pressure, flowline_pressure)):
        if pressure is None:
            pressure = PressureRecord(well_id=production.well_id, record_date=production.record_date)
            db.add(pressure)
        pressure.wellhead_pressure = wellhead_pressure
        pressure.tubing_pressure = tubing_pressure
        pressure.casing_pressure = casing_pressure
        pressure.flowline_pressure = flowline_pressure

    if wellhead_temperature is not None:
        if temperature is None:
            temperature = TemperatureRecord(well_id=production.well_id, record_date=production.record_date)
            db.add(temperature)
        temperature.wellhead_temperature = wellhead_temperature

    db.commit()
    db.refresh(production)

    boe_gas_factor = get_boe_gas_factor(db)
    warnings = [i.message for i in issues if i.severity == "warning"] or None
    return _build_record_read(
        production=production, pressure=pressure, temperature=temperature, well=production.well,
        boe_gas_factor=boe_gas_factor,
        downtime_hours=_downtime_hours_for(db, production.well_id, production.record_date),
        warnings=warnings,
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_production_record(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> None:
    production = _get_production_or_404(db, id)
    db.query(PressureRecord).filter(
        PressureRecord.well_id == production.well_id, PressureRecord.record_date == production.record_date
    ).delete()
    db.query(TemperatureRecord).filter(
        TemperatureRecord.well_id == production.well_id, TemperatureRecord.record_date == production.record_date
    ).delete()
    db.delete(production)
    db.commit()
