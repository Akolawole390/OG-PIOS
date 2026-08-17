from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.equipment import DowntimeEvent, Equipment, EquipmentReading, MaintenanceRecord
from app.models.field import Facility, Well
from app.models.user import User
from app.schemas.equipment import (
    EquipmentByScopeResponse,
    EquipmentCreate,
    EquipmentDashboardResponse,
    EquipmentHealthDistribution,
    EquipmentHealthDistributionBucket,
    EquipmentHealthFactor,
    EquipmentHealthRead,
    EquipmentInvestigationItem,
    EquipmentIssuesResponse,
    EquipmentListResponse,
    EquipmentRead,
    EquipmentReadingCreate,
    EquipmentReadingListResponse,
    EquipmentReadingRead,
    EquipmentScopeBar,
    EquipmentStatusCounts,
    EquipmentUpdate,
)
from app.schemas.maintenance import ReliabilityMetricsRead
from app.schemas.well import (
    DowntimeListResponse,
    DowntimeSummary,
    MaintenanceListResponse,
    MaintenanceRecordRead,
    MaintenanceSummary,
)
from app.services.equipment_health import band_for, recompute_equipment_health
from app.services.reliability_metrics import DowntimeInterval, compute_reliability

router = APIRouter(prefix="/equipment", tags=["equipment"])

STATUS_KEYS = ["operating", "standby", "maintenance", "failed", "decommissioned", "unknown"]
BAND_ORDER = ["Excellent", "Good", "Monitor", "Maintenance Required", "Critical"]

SORTABLE_FIELDS = {
    "equipment_tag": Equipment.equipment_tag,
    "name": Equipment.name,
    "equipment_type": Equipment.equipment_type,
    "status": Equipment.status,
    "health_score": Equipment.health_score,
    "installation_date": Equipment.installation_date,
}


# ----- Shared helpers -----


def _equipment_query(db: Session):
    return db.query(Equipment).options(
        joinedload(Equipment.well).joinedload(Well.facility).joinedload(Facility.field),
        joinedload(Equipment.facility).joinedload(Facility.field),
    )


def _resolve_scope(
    equipment: Equipment,
) -> tuple[int | None, str | None, int | None, str | None, int | None, str | None]:
    """Returns (field_id, field_name, facility_id, facility_name, well_id, well_code)."""
    if equipment.well_id and equipment.well:
        well = equipment.well
        facility = well.facility
        field = facility.field
        return field.id, field.name, facility.id, facility.name, well.id, well.well_id
    if equipment.facility_id and equipment.facility:
        facility = equipment.facility
        field = facility.field
        return field.id, field.name, facility.id, facility.name, None, None
    return None, None, None, None, None, None


def _build_equipment_read(equipment: Equipment, last_maintenance_date: date | None) -> EquipmentRead:
    field_id, field_name, facility_id, facility_name, well_id, well_code = _resolve_scope(equipment)
    return EquipmentRead(
        id=equipment.id,
        equipment_tag=equipment.equipment_tag,
        name=equipment.name or equipment.equipment_tag,
        equipment_type=equipment.equipment_type,
        manufacturer=equipment.manufacturer,
        model=equipment.model,
        serial_number=equipment.serial_number,
        installation_date=equipment.installation_date,
        commissioning_date=equipment.commissioning_date,
        description=equipment.description,
        status=equipment.status,
        operating_hours=equipment.operating_hours,
        next_maintenance_due=equipment.next_maintenance_due,
        facility_id=equipment.facility_id,
        well_id=equipment.well_id,
        field_id=field_id,
        field_name=field_name,
        facility_name=facility_name,
        well_code=well_code,
        health_score=equipment.health_score,
        health_band=band_for(equipment.health_score) if equipment.health_score is not None else None,
        last_maintenance_date=last_maintenance_date,
        created_at=equipment.created_at,
        updated_at=equipment.updated_at,
    )


def _last_maintenance_dates(db: Session, equipment_ids: list[int]) -> dict[int, date]:
    if not equipment_ids:
        return {}
    rows = (
        db.query(MaintenanceRecord.equipment_id, func.max(MaintenanceRecord.completion_date))
        .filter(
            MaintenanceRecord.equipment_id.in_(equipment_ids),
            MaintenanceRecord.completion_date.isnot(None),
        )
        .group_by(MaintenanceRecord.equipment_id)
        .all()
    )
    return {equipment_id: max_date for equipment_id, max_date in rows}


def _hydrate_equipment_list(db: Session, records: list[Equipment]) -> list[EquipmentRead]:
    if not records:
        return []
    last_maint_by_id = _last_maintenance_dates(db, [e.id for e in records])
    return [_build_equipment_read(e, last_maint_by_id.get(e.id)) for e in records]


def _get_equipment_or_404(db: Session, id: int) -> Equipment:
    equipment = _equipment_query(db).filter(Equipment.id == id).first()
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    return equipment


# ----- List / create -----


@router.get("", response_model=EquipmentListResponse)
def list_equipment(
    search: str | None = None,
    equipment_type: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    sort: str = "equipment_tag",
    order: str = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentListResponse:
    query = _equipment_query(db)

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Equipment.equipment_tag.ilike(like), Equipment.name.ilike(like)))
    if equipment_type:
        query = query.filter(Equipment.equipment_type == equipment_type)
    if status_filter:
        query = query.filter(Equipment.status == status_filter)
    if well_id:
        query = query.filter(Equipment.well_id == well_id)
    if facility_id:
        query = query.filter(
            or_(Equipment.facility_id == facility_id, Equipment.well.has(Well.facility_id == facility_id))
        )
    if field_id:
        query = query.filter(
            or_(
                Equipment.facility.has(Facility.field_id == field_id),
                Equipment.well.has(Well.facility.has(Facility.field_id == field_id)),
            )
        )

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, Equipment.equipment_tag)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    items = _hydrate_equipment_list(db, records)

    return EquipmentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=EquipmentRead, status_code=status.HTTP_201_CREATED)
def create_equipment(
    payload: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Maintenance Engineer")),
) -> EquipmentRead:
    if payload.facility_id is not None and db.get(Facility, payload.facility_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    if payload.well_id is not None and db.get(Well, payload.well_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")

    existing = db.query(Equipment).filter(Equipment.equipment_tag == payload.equipment_tag).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Equipment with tag '{payload.equipment_tag}' already exists",
        )

    equipment = Equipment(**payload.model_dump())
    db.add(equipment)
    db.commit()
    db.refresh(equipment)

    recompute_equipment_health(db, equipment)
    db.commit()

    return _build_equipment_read(_get_equipment_or_404(db, equipment.id), None)


# ----- Fixed sub-paths (must be registered before /{id}) -----


@router.get("/dashboard", response_model=EquipmentDashboardResponse)
def get_equipment_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentDashboardResponse:
    all_equipment = db.query(Equipment).all()

    counts = {key: 0 for key in STATUS_KEYS}
    for equipment in all_equipment:
        counts[equipment.status if equipment.status in counts else "unknown"] += 1

    attention_count = sum(
        1
        for equipment in all_equipment
        if equipment.status in ("failed", "maintenance")
        or (equipment.health_score is not None and equipment.health_score < 50)
    )

    band_counts = {band: 0 for band in BAND_ORDER}
    unscored = 0
    for equipment in all_equipment:
        if equipment.health_score is None:
            unscored += 1
        else:
            band_counts[band_for(equipment.health_score)] += 1

    return EquipmentDashboardResponse(
        status_counts=EquipmentStatusCounts(total=len(all_equipment), attention_count=attention_count, **counts),
        health_distribution=EquipmentHealthDistribution(
            buckets=[EquipmentHealthDistributionBucket(band=b, count=c) for b, c in band_counts.items()],
            unscored_count=unscored,
        ),
    )


@router.get("/by-scope", response_model=EquipmentByScopeResponse)
def get_equipment_by_scope(
    group_by: str = Query("type", pattern="^(type|field|facility)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentByScopeResponse:
    equipment_list = _equipment_query(db).all()

    groups: dict[str, dict] = {}
    for equipment in equipment_list:
        if group_by == "type":
            key = label = equipment.equipment_type
        else:
            field_id, field_name, facility_id, facility_name, _, _ = _resolve_scope(equipment)
            if group_by == "field":
                if field_id is None:
                    continue
                key, label = str(field_id), field_name
            else:
                if facility_id is None:
                    continue
                key, label = str(facility_id), facility_name

        bucket = groups.setdefault(key, {"label": label, "count": 0, "health_sum": 0.0, "health_count": 0})
        bucket["count"] += 1
        if equipment.health_score is not None:
            bucket["health_sum"] += equipment.health_score
            bucket["health_count"] += 1

    bars = [
        EquipmentScopeBar(
            key=key,
            label=bucket["label"],
            count=bucket["count"],
            avg_health_score=round(bucket["health_sum"] / bucket["health_count"], 1)
            if bucket["health_count"]
            else None,
        )
        for key, bucket in groups.items()
    ]
    bars.sort(key=lambda b: b.count, reverse=True)
    return EquipmentByScopeResponse(group_by=group_by, bars=bars)


@router.get("/issues", response_model=EquipmentIssuesResponse)
def get_equipment_issues(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentIssuesResponse:
    equipment_list = db.query(Equipment).all()

    def sort_key(equipment: Equipment):
        is_failed = 0 if equipment.status == "failed" else 1
        score = equipment.health_score if equipment.health_score is not None else 100.0
        return (is_failed, score)

    items: list[EquipmentInvestigationItem] = []
    for equipment in sorted(equipment_list, key=sort_key):
        flagged = equipment.status == "failed" or (
            equipment.health_score is not None and equipment.health_score < 75
        )
        if not flagged:
            continue
        detail = (
            "Status is Failed."
            if equipment.status == "failed"
            else f"Health score {equipment.health_score} ({band_for(equipment.health_score)})."
        )
        items.append(
            EquipmentInvestigationItem(
                id=equipment.id,
                equipment_tag=equipment.equipment_tag,
                name=equipment.name or equipment.equipment_tag,
                equipment_type=equipment.equipment_type,
                status=equipment.status,
                health_score=equipment.health_score,
                health_band=band_for(equipment.health_score) if equipment.health_score is not None else None,
                detail=detail,
            )
        )
        if len(items) >= limit:
            break

    return EquipmentIssuesResponse(items=items)


# ----- Single-equipment routes -----


@router.get("/{id}", response_model=EquipmentRead)
def get_equipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentRead:
    equipment = _get_equipment_or_404(db, id)
    last_maint = _last_maintenance_dates(db, [id]).get(id)
    return _build_equipment_read(equipment, last_maint)


@router.put("/{id}", response_model=EquipmentRead)
def update_equipment(
    id: int,
    payload: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Maintenance Engineer")),
) -> EquipmentRead:
    equipment = _get_equipment_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)

    if update_data.get("facility_id") is not None and db.get(Facility, update_data["facility_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    if update_data.get("well_id") is not None and db.get(Well, update_data["well_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")

    new_tag = update_data.get("equipment_tag")
    if new_tag and new_tag != equipment.equipment_tag:
        duplicate = db.query(Equipment).filter(Equipment.equipment_tag == new_tag).first()
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Equipment with tag '{new_tag}' already exists",
            )

    needs_recompute = bool({"status", "operating_hours"} & update_data.keys())

    for field_name, value in update_data.items():
        setattr(equipment, field_name, value)

    db.commit()
    db.refresh(equipment)

    if needs_recompute:
        recompute_equipment_health(db, equipment)
        db.commit()

    equipment = _get_equipment_or_404(db, id)
    last_maint = _last_maintenance_dates(db, [id]).get(id)
    return _build_equipment_read(equipment, last_maint)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Maintenance Engineer")),
) -> None:
    equipment = _get_equipment_or_404(db, id)

    has_history = (
        db.query(MaintenanceRecord).filter(MaintenanceRecord.equipment_id == id).first() is not None
        or db.query(EquipmentReading).filter(EquipmentReading.equipment_id == id).first() is not None
        or db.query(DowntimeEvent).filter(DowntimeEvent.equipment_id == id).first() is not None
    )
    if has_history:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete equipment with existing readings, maintenance, or downtime "
            "history — decommission it instead.",
        )

    db.delete(equipment)
    db.commit()


@router.get("/{id}/health", response_model=EquipmentHealthRead)
def get_equipment_health(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentHealthRead:
    equipment = _get_equipment_or_404(db, id)
    result = recompute_equipment_health(db, equipment)
    db.commit()

    return EquipmentHealthRead(
        equipment_id=id,
        score=result.score,
        band=result.band,
        starting_score=result.starting_score,
        factors=[
            EquipmentHealthFactor(factor=f.factor, deduction=f.deduction, detail=f.detail)
            for f in result.factors
        ],
        disclaimer_text=result.disclaimer_text,
        computed_at=result.computed_at,
    )


@router.get("/{id}/readings", response_model=EquipmentReadingListResponse)
def list_equipment_readings(
    id: int,
    parameter: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentReadingListResponse:
    _get_equipment_or_404(db, id)
    query = db.query(EquipmentReading).filter(EquipmentReading.equipment_id == id)
    if parameter:
        query = query.filter(EquipmentReading.parameter == parameter)
    if date_from:
        query = query.filter(EquipmentReading.reading_at >= date_from)
    if date_to:
        # date_to is a calendar date; reading_at is a timestamp, so compare against the start of
        # the following day rather than midnight of date_to itself, or same-day readings taken
        # after midnight would be silently excluded (e.g. date_to=today).
        query = query.filter(EquipmentReading.reading_at < date_to + timedelta(days=1))

    total = query.count()
    items = (
        query.order_by(EquipmentReading.reading_at).offset((page - 1) * page_size).limit(page_size).all()
    )
    return EquipmentReadingListResponse(
        items=[EquipmentReadingRead.model_validate(r) for r in items], total=total
    )


@router.post("/{id}/readings", response_model=EquipmentReadingRead, status_code=status.HTTP_201_CREATED)
def create_equipment_reading(
    id: int,
    payload: EquipmentReadingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Maintenance Engineer")),
) -> EquipmentReading:
    equipment = _get_equipment_or_404(db, id)
    reading = EquipmentReading(
        equipment_id=id,
        reading_at=payload.reading_at,
        parameter=payload.parameter,
        value=payload.value,
        unit=payload.unit,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    if payload.parameter in ("temperature", "vibration", "current", "flow"):
        recompute_equipment_health(db, equipment)
        db.commit()

    return reading


@router.get("/{id}/maintenance", response_model=MaintenanceListResponse)
def get_equipment_maintenance(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceListResponse:
    equipment = _get_equipment_or_404(db, id)
    records = (
        db.query(MaintenanceRecord)
        .filter(MaintenanceRecord.equipment_id == id)
        .order_by(MaintenanceRecord.start_date.desc())
        .all()
    )
    items = [
        MaintenanceRecordRead(
            id=record.id,
            maintenance_type=record.maintenance_type,
            status=record.status,
            description=record.description,
            start_date=record.start_date,
            completion_date=record.completion_date,
            cost=record.cost,
            equipment_tag=equipment.equipment_tag,
            equipment_type=equipment.equipment_type,
        )
        for record in records
    ]
    total_cost = sum(record.cost or 0 for record in records)
    total_downtime_hours = sum(record.downtime_hours or 0 for record in records)
    return MaintenanceListResponse(
        records=items,
        summary=MaintenanceSummary(
            record_count=len(records),
            total_cost=round(total_cost, 2),
            total_downtime_hours=round(total_downtime_hours, 2),
        ),
    )


@router.get("/{id}/downtime", response_model=DowntimeListResponse)
def get_equipment_downtime(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DowntimeListResponse:
    _get_equipment_or_404(db, id)
    events = (
        db.query(DowntimeEvent)
        .filter(DowntimeEvent.equipment_id == id)
        .order_by(DowntimeEvent.start_time.desc())
        .all()
    )
    total_hours = sum(
        (event.end_time - event.start_time).total_seconds() / 3600
        for event in events
        if event.end_time is not None
    )
    return DowntimeListResponse(
        events=events, summary=DowntimeSummary(event_count=len(events), total_hours=round(total_hours, 2))
    )


@router.get("/{id}/reliability", response_model=ReliabilityMetricsRead)
def get_equipment_reliability(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReliabilityMetricsRead:
    """Foundation-level MTBF/MTTR/availability/failure-frequency, sourced from this
    equipment's DowntimeEvent history — see services/reliability_metrics.py for the
    documented assumptions and disclaimer."""
    equipment = _get_equipment_or_404(db, id)

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=365)
    if equipment.installation_date is not None:
        installed_at = datetime.combine(equipment.installation_date, datetime.min.time(), tzinfo=timezone.utc)
        window_start = max(window_start, installed_at)
    observation_period_hours = max((now - window_start).total_seconds() / 3600, 0.0)

    events = (
        db.query(DowntimeEvent)
        .filter(DowntimeEvent.equipment_id == id, DowntimeEvent.start_time >= window_start)
        .all()
    )
    intervals = [DowntimeInterval(start=e.start_time, end=e.end_time) for e in events]

    result = compute_reliability(intervals, observation_period_hours, now=now)

    return ReliabilityMetricsRead(
        equipment_id=id,
        mtbf_hours=result.mtbf_hours,
        mtbf_data_sufficient=result.mtbf_data_sufficient,
        mttr_hours=result.mttr_hours,
        mttr_data_sufficient=result.mttr_data_sufficient,
        availability_pct=result.availability_pct,
        failure_count=result.failure_count,
        failure_count_annualized=result.failure_count_annualized,
        observation_period_hours=round(result.observation_period_hours, 1),
        disclaimer_text=result.disclaimer_text,
        assumptions=result.assumptions,
        computed_at=result.computed_at,
    )
