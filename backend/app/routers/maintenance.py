from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.equipment import Equipment, MaintenanceRecord
from app.models.field import Facility, Well
from app.models.user import User
from app.routers.equipment import _resolve_scope
from app.schemas.maintenance import (
    EquipmentRequiringMaintenanceItem,
    MaintenanceByScopeResponse,
    MaintenanceCostTrendPoint,
    MaintenanceCostTrendResponse,
    MaintenanceCreate,
    MaintenanceDashboardResponse,
    MaintenanceEntry,
    MaintenanceListResponse,
    MaintenanceScheduleItem,
    MaintenanceScheduleResponse,
    MaintenanceScopeBar,
    MaintenanceStatusCounts,
    MaintenanceUpdate,
)
from app.services.equipment_health import recompute_equipment_health
from app.services.system_settings import get_maintenance_schedule_lookahead_days

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

STATUS_KEYS = ["scheduled", "open", "in_progress", "waiting_for_parts", "completed", "cancelled", "overdue"]
TERMINAL_STATUSES = ("completed", "cancelled")
DELETE_ALLOWED_STATUSES = ("scheduled", "open")
HEALTH_RELEVANT_FIELDS = {"status", "maintenance_type", "start_date", "equipment_id"}
COST_COMPONENT_FIELDS = ("labor_cost", "parts_cost", "contractor_cost", "other_cost")

SORTABLE_FIELDS = {
    "work_order_number": MaintenanceRecord.work_order_number,
    "maintenance_type": MaintenanceRecord.maintenance_type,
    "priority": MaintenanceRecord.priority,
    "status": MaintenanceRecord.status,
    "start_date": MaintenanceRecord.start_date,
    "planned_completion_date": MaintenanceRecord.planned_completion_date,
    "cost": MaintenanceRecord.cost,
}


# ----- Shared helpers -----


def _maintenance_query(db: Session):
    return db.query(MaintenanceRecord).options(
        joinedload(MaintenanceRecord.equipment).joinedload(Equipment.well).joinedload(Well.facility).joinedload(
            Facility.field
        ),
        joinedload(MaintenanceRecord.equipment).joinedload(Equipment.facility).joinedload(Facility.field),
        joinedload(MaintenanceRecord.technician),
    )


def _compute_cost(record: MaintenanceRecord) -> float | None:
    components = [getattr(record, f) for f in COST_COMPONENT_FIELDS]
    if all(c is None for c in components):
        return None
    return round(sum(c or 0 for c in components), 2)


def _build_maintenance_entry(record: MaintenanceRecord) -> MaintenanceEntry:
    field_id, field_name, facility_id, facility_name, well_id, well_code = _resolve_scope(record.equipment)
    return MaintenanceEntry(
        id=record.id,
        work_order_number=record.work_order_number,
        equipment_id=record.equipment_id,
        equipment_tag=record.equipment.equipment_tag,
        equipment_name=record.equipment.name or record.equipment.equipment_tag,
        equipment_type=record.equipment.equipment_type,
        field_id=field_id,
        field_name=field_name,
        facility_id=facility_id,
        facility_name=facility_name,
        well_id=well_id,
        well_code=well_code,
        maintenance_type=record.maintenance_type,
        priority=record.priority,
        status=record.status,
        description=record.description,
        planned_start_date=record.planned_start_date,
        planned_completion_date=record.planned_completion_date,
        start_date=record.start_date,
        completion_date=record.completion_date,
        technician_id=record.technician_id,
        technician_name=record.technician.full_name if record.technician else None,
        labor_cost=record.labor_cost,
        parts_cost=record.parts_cost,
        contractor_cost=record.contractor_cost,
        other_cost=record.other_cost,
        cost=record.cost,
        downtime_hours=record.downtime_hours,
        failure_cause=record.failure_cause,
        corrective_action=record.corrective_action,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _get_maintenance_or_404(db: Session, id: int) -> MaintenanceRecord:
    record = _maintenance_query(db).filter(MaintenanceRecord.id == id).first()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance record not found")
    return record


# ----- List / create -----


@router.get("", response_model=MaintenanceListResponse)
def list_maintenance(
    search: str | None = None,
    equipment_id: int | None = None,
    well_id: int | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    status_filter: str | None = Query(None, alias="status"),
    priority: str | None = None,
    maintenance_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "start_date",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceListResponse:
    query = _maintenance_query(db)

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                MaintenanceRecord.description.ilike(like),
                MaintenanceRecord.work_order_number.ilike(like),
                MaintenanceRecord.equipment.has(Equipment.equipment_tag.ilike(like)),
                MaintenanceRecord.equipment.has(Equipment.name.ilike(like)),
            )
        )
    if equipment_id:
        query = query.filter(MaintenanceRecord.equipment_id == equipment_id)
    if well_id:
        query = query.filter(MaintenanceRecord.equipment.has(Equipment.well_id == well_id))
    if facility_id:
        query = query.filter(
            MaintenanceRecord.equipment.has(
                or_(Equipment.facility_id == facility_id, Equipment.well.has(Well.facility_id == facility_id))
            )
        )
    if field_id:
        query = query.filter(
            MaintenanceRecord.equipment.has(
                or_(
                    Equipment.facility.has(Facility.field_id == field_id),
                    Equipment.well.has(Well.facility.has(Facility.field_id == field_id)),
                )
            )
        )
    if status_filter:
        query = query.filter(MaintenanceRecord.status == status_filter)
    if priority:
        query = query.filter(MaintenanceRecord.priority == priority)
    if maintenance_type:
        query = query.filter(MaintenanceRecord.maintenance_type == maintenance_type)
    if date_from:
        query = query.filter(MaintenanceRecord.start_date >= date_from)
    if date_to:
        query = query.filter(MaintenanceRecord.start_date <= date_to)

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, MaintenanceRecord.start_date)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [_build_maintenance_entry(r) for r in records]

    return MaintenanceListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=MaintenanceEntry, status_code=status.HTTP_201_CREATED)
def create_maintenance(
    payload: MaintenanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Maintenance Engineer")),
) -> MaintenanceEntry:
    equipment = db.get(Equipment, payload.equipment_id)
    if equipment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    if payload.technician_id is not None and db.get(User, payload.technician_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")

    record = MaintenanceRecord(**payload.model_dump())
    record.cost = _compute_cost(record)
    db.add(record)
    db.flush()  # assign record.id before generating the work order number
    record.work_order_number = f"WO-{record.id:06d}"
    db.commit()
    db.refresh(record)

    recompute_equipment_health(db, equipment)
    db.commit()

    return _build_maintenance_entry(_get_maintenance_or_404(db, record.id))


# ----- Fixed sub-paths (must be registered before /{id}) -----


@router.get("/dashboard", response_model=MaintenanceDashboardResponse)
def get_maintenance_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceDashboardResponse:
    records = db.query(MaintenanceRecord).all()
    today = date.today()

    counts = {key: 0 for key in STATUS_KEYS}
    for record in records:
        counts[record.status if record.status in counts else "scheduled"] += 1

    emergency_count = sum(1 for r in records if r.maintenance_type == "emergency")
    computed_overdue_count = sum(
        1
        for r in records
        if r.status not in TERMINAL_STATUSES
        and r.planned_completion_date is not None
        and r.planned_completion_date < today
    )
    total_cost = round(sum(r.cost or 0 for r in records), 2)
    total_downtime_hours = round(sum(r.downtime_hours or 0 for r in records), 2)

    lookahead_days = get_maintenance_schedule_lookahead_days(db)
    horizon = today + timedelta(days=lookahead_days)
    due_equipment = (
        db.query(Equipment)
        .filter(Equipment.next_maintenance_due.isnot(None), Equipment.next_maintenance_due <= horizon)
        .order_by(Equipment.next_maintenance_due.asc())
        .limit(10)
        .all()
    )
    equipment_requiring_maintenance = [
        EquipmentRequiringMaintenanceItem(
            equipment_id=e.id,
            equipment_tag=e.equipment_tag,
            equipment_name=e.name or e.equipment_tag,
            next_maintenance_due=e.next_maintenance_due,
            days_from_today=(e.next_maintenance_due - today).days,
        )
        for e in due_equipment
    ]

    return MaintenanceDashboardResponse(
        status_counts=MaintenanceStatusCounts(
            total=len(records),
            emergency_count=emergency_count,
            computed_overdue_count=computed_overdue_count,
            **counts,
        ),
        total_cost=total_cost,
        total_downtime_hours=total_downtime_hours,
        equipment_requiring_maintenance=equipment_requiring_maintenance,
    )


@router.get("/by-scope", response_model=MaintenanceByScopeResponse)
def get_maintenance_by_scope(
    group_by: str = Query("type", pattern="^(type|equipment|field|well)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceByScopeResponse:
    records = _maintenance_query(db).all()

    groups: dict[str, dict] = {}
    for record in records:
        if group_by == "type":
            key = label = record.maintenance_type
        elif group_by == "equipment":
            key, label = str(record.equipment_id), record.equipment.equipment_tag
        elif group_by == "well":
            _, _, _, _, well_id, well_code = _resolve_scope(record.equipment)
            if well_id is None:
                continue
            key, label = str(well_id), well_code
        else:
            field_id, field_name, _, _, _, _ = _resolve_scope(record.equipment)
            if field_id is None:
                continue
            key, label = str(field_id), field_name

        bucket = groups.setdefault(key, {"label": label, "count": 0, "total_cost": 0.0, "total_downtime_hours": 0.0})
        bucket["count"] += 1
        bucket["total_cost"] += record.cost or 0
        bucket["total_downtime_hours"] += record.downtime_hours or 0

    bars = [
        MaintenanceScopeBar(
            key=key,
            label=b["label"],
            count=b["count"],
            total_cost=round(b["total_cost"], 2),
            total_downtime_hours=round(b["total_downtime_hours"], 2),
        )
        for key, b in groups.items()
    ]
    bars.sort(key=lambda b: b.count, reverse=True)
    return MaintenanceByScopeResponse(group_by=group_by, bars=bars)


@router.get("/cost-trend", response_model=MaintenanceCostTrendResponse)
def get_maintenance_cost_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceCostTrendResponse:
    records = db.query(MaintenanceRecord).all()

    buckets: dict[str, dict] = {}
    for record in records:
        anchor = record.start_date or record.planned_start_date
        if anchor is None:
            continue
        month_key = anchor.strftime("%Y-%m")
        bucket = buckets.setdefault(month_key, {"total_cost": 0.0, "record_count": 0})
        bucket["total_cost"] += record.cost or 0
        bucket["record_count"] += 1

    points = [
        MaintenanceCostTrendPoint(month=month, total_cost=round(b["total_cost"], 2), record_count=b["record_count"])
        for month, b in sorted(buckets.items())
    ]
    return MaintenanceCostTrendResponse(points=points)


@router.get("/schedule", response_model=MaintenanceScheduleResponse)
def get_maintenance_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceScheduleResponse:
    """Rule-based scheduling view — not automatic status mutation. Combines two independent
    signals: open work orders with a planned completion date, and equipment-level
    next_maintenance_due (which doesn't require an open work order to exist)."""
    today = date.today()
    lookahead_days = get_maintenance_schedule_lookahead_days(db)

    overdue: list[MaintenanceScheduleItem] = []
    due_today: list[MaintenanceScheduleItem] = []
    upcoming: list[MaintenanceScheduleItem] = []

    def _bucket_for(days_from_today: int) -> list[MaintenanceScheduleItem] | None:
        if days_from_today < 0:
            return overdue
        if days_from_today == 0:
            return due_today
        if days_from_today <= lookahead_days:
            return upcoming
        return None

    active_records = (
        _maintenance_query(db)
        .filter(
            MaintenanceRecord.status.notin_(TERMINAL_STATUSES),
            MaintenanceRecord.planned_completion_date.isnot(None),
        )
        .all()
    )
    for record in active_records:
        days_from_today = (record.planned_completion_date - today).days
        bucket = _bucket_for(days_from_today)
        if bucket is None:
            continue
        bucket.append(
            MaintenanceScheduleItem(
                source="work_order",
                id=record.id,
                label=f"{record.work_order_number or record.id} — {record.equipment.equipment_tag}",
                equipment_id=record.equipment_id,
                equipment_tag=record.equipment.equipment_tag,
                due_date=record.planned_completion_date,
                status=record.status,
                priority=record.priority,
                days_from_today=days_from_today,
            )
        )

    due_equipment = db.query(Equipment).filter(Equipment.next_maintenance_due.isnot(None)).all()
    for equipment in due_equipment:
        days_from_today = (equipment.next_maintenance_due - today).days
        bucket = _bucket_for(days_from_today)
        if bucket is None:
            continue
        bucket.append(
            MaintenanceScheduleItem(
                source="equipment",
                id=equipment.id,
                label=f"{equipment.equipment_tag} — {equipment.name or equipment.equipment_tag}",
                equipment_id=equipment.id,
                equipment_tag=equipment.equipment_tag,
                due_date=equipment.next_maintenance_due,
                status=None,
                priority=None,
                days_from_today=days_from_today,
            )
        )

    overdue.sort(key=lambda i: i.days_from_today)
    due_today.sort(key=lambda i: i.equipment_tag)
    upcoming.sort(key=lambda i: i.days_from_today)

    return MaintenanceScheduleResponse(
        reference_date=today,
        lookahead_days=lookahead_days,
        overdue=overdue,
        due_today=due_today,
        upcoming=upcoming,
    )


# ----- Single-record routes -----


@router.get("/{id}", response_model=MaintenanceEntry)
def get_maintenance(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceEntry:
    return _build_maintenance_entry(_get_maintenance_or_404(db, id))


@router.put("/{id}", response_model=MaintenanceEntry)
def update_maintenance(
    id: int,
    payload: MaintenanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Maintenance Engineer")),
) -> MaintenanceEntry:
    record = _get_maintenance_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)

    if "equipment_id" in update_data and db.get(Equipment, update_data["equipment_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")
    if update_data.get("technician_id") is not None and db.get(User, update_data["technician_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Technician not found")

    old_equipment_id = record.equipment_id
    needs_recompute = bool(HEALTH_RELEVANT_FIELDS & update_data.keys())

    for field_name, value in update_data.items():
        setattr(record, field_name, value)

    if any(f in update_data for f in COST_COMPONENT_FIELDS):
        record.cost = _compute_cost(record)

    db.commit()
    db.refresh(record)

    if needs_recompute:
        equipment = db.get(Equipment, record.equipment_id)
        if equipment is not None:
            recompute_equipment_health(db, equipment)
        if old_equipment_id != record.equipment_id:
            old_equipment = db.get(Equipment, old_equipment_id)
            if old_equipment is not None:
                recompute_equipment_health(db, old_equipment)
        db.commit()

    return _build_maintenance_entry(_get_maintenance_or_404(db, id))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_maintenance(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Maintenance Engineer")),
) -> None:
    record = _get_maintenance_or_404(db, id)

    has_recorded_actuals = (
        record.status not in DELETE_ALLOWED_STATUSES or record.cost is not None or record.downtime_hours is not None
    )
    if has_recorded_actuals:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a maintenance record with recorded status/cost/downtime — "
            "set status to 'cancelled' instead to preserve the audit trail.",
        )

    equipment_id = record.equipment_id
    db.delete(record)
    db.commit()

    equipment = db.get(Equipment, equipment_id)
    if equipment is not None:
        recompute_equipment_health(db, equipment)
        db.commit()
