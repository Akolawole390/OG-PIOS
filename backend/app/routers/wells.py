from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.equipment import DowntimeEvent, Equipment, MaintenanceRecord
from app.models.field import Facility, Field, Well
from app.models.production import PressureRecord, ProductionRecord
from app.models.user import User
from app.schemas.well import (
    DowntimeListResponse,
    DowntimeSummary,
    FacilityRead,
    MaintenanceListResponse,
    MaintenanceRecordRead,
    MaintenanceSummary,
    PressureRecordRead,
    ProductionRecordRead,
    WellCreate,
    WellListResponse,
    WellRead,
    WellUpdate,
)

router = APIRouter(prefix="/wells", tags=["wells"])
facilities_router = APIRouter(prefix="/facilities", tags=["facilities"])

SORTABLE_FIELDS = {
    "well_id": Well.well_id,
    "name": Well.name,
    "status": Well.status,
    "well_type": Well.well_type,
    "created_at": Well.created_at,
}


def _load_well(db: Session, id: int) -> Well | None:
    return (
        db.query(Well)
        .options(joinedload(Well.facility).joinedload(Facility.field))
        .filter(Well.id == id)
        .first()
    )


def _get_well_or_404(db: Session, id: int) -> Well:
    well = _load_well(db, id)
    if well is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")
    return well


@router.get("", response_model=WellListResponse)
def list_wells(
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    well_type: str | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    sort: str = "well_id",
    order: str = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WellListResponse:
    query = (
        db.query(Well)
        .join(Facility, Well.facility_id == Facility.id)
        .join(Field, Facility.field_id == Field.id)
        .options(joinedload(Well.facility).joinedload(Facility.field))
    )

    if search:
        like = f"%{search}%"
        query = query.filter(or_(Well.well_id.ilike(like), Well.name.ilike(like)))
    if status_filter:
        query = query.filter(Well.status == status_filter)
    if well_type:
        query = query.filter(Well.well_type == well_type)
    if field_id:
        query = query.filter(Facility.field_id == field_id)
    if facility_id:
        query = query.filter(Well.facility_id == facility_id)

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, Well.well_id)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return WellListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=WellRead, status_code=status.HTTP_201_CREATED)
def create_well(
    payload: WellCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> Well:
    facility = db.get(Facility, payload.facility_id)
    if facility is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")

    existing = db.query(Well).filter(Well.well_id == payload.well_id).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Well with well_id '{payload.well_id}' already exists",
        )

    well = Well(**payload.model_dump())
    db.add(well)
    db.commit()
    return _get_well_or_404(db, well.id)


@router.get("/{id}", response_model=WellRead)
def get_well(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Well:
    return _get_well_or_404(db, id)


@router.put("/{id}", response_model=WellRead)
def update_well(
    id: int,
    payload: WellUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> Well:
    well = _get_well_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)

    if "facility_id" in update_data:
        facility = db.get(Facility, update_data["facility_id"])
        if facility is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")

    new_well_id = update_data.get("well_id")
    if new_well_id and new_well_id != well.well_id:
        duplicate = db.query(Well).filter(Well.well_id == new_well_id).first()
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Well with well_id '{new_well_id}' already exists",
            )

    for field_name, value in update_data.items():
        setattr(well, field_name, value)

    db.commit()
    return _get_well_or_404(db, id)


@router.get("/{id}/production", response_model=list[ProductionRecordRead])
def get_well_production(
    id: int,
    days: int = Query(90, ge=1, le=730),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductionRecord]:
    _get_well_or_404(db, id)
    cutoff = date.today() - timedelta(days=days)
    return (
        db.query(ProductionRecord)
        .filter(ProductionRecord.well_id == id, ProductionRecord.record_date >= cutoff)
        .order_by(ProductionRecord.record_date)
        .all()
    )


@router.get("/{id}/pressure", response_model=list[PressureRecordRead])
def get_well_pressure(
    id: int,
    days: int = Query(90, ge=1, le=730),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PressureRecord]:
    _get_well_or_404(db, id)
    cutoff = date.today() - timedelta(days=days)
    return (
        db.query(PressureRecord)
        .filter(PressureRecord.well_id == id, PressureRecord.record_date >= cutoff)
        .order_by(PressureRecord.record_date)
        .all()
    )


@router.get("/{id}/downtime", response_model=DowntimeListResponse)
def get_well_downtime(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DowntimeListResponse:
    _get_well_or_404(db, id)
    events = (
        db.query(DowntimeEvent)
        .filter(DowntimeEvent.well_id == id)
        .order_by(DowntimeEvent.start_time.desc())
        .all()
    )
    total_hours = sum(
        (event.end_time - event.start_time).total_seconds() / 3600
        for event in events
        if event.end_time is not None
    )
    summary = DowntimeSummary(event_count=len(events), total_hours=round(total_hours, 2))
    return DowntimeListResponse(events=events, summary=summary)


@router.get("/{id}/maintenance", response_model=MaintenanceListResponse)
def get_well_maintenance(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MaintenanceListResponse:
    _get_well_or_404(db, id)
    records = (
        db.query(MaintenanceRecord)
        .join(Equipment, MaintenanceRecord.equipment_id == Equipment.id)
        .filter(Equipment.well_id == id)
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
            equipment_tag=record.equipment.equipment_tag,
            equipment_type=record.equipment.equipment_type,
        )
        for record in records
    ]
    total_cost = sum(record.cost or 0 for record in records)
    total_downtime_hours = sum(record.downtime_hours or 0 for record in records)
    summary = MaintenanceSummary(
        record_count=len(records),
        total_cost=round(total_cost, 2),
        total_downtime_hours=round(total_downtime_hours, 2),
    )
    return MaintenanceListResponse(records=items, summary=summary)


@facilities_router.get("", response_model=list[FacilityRead])
def list_facilities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FacilityRead]:
    facilities = (
        db.query(Facility).options(joinedload(Facility.field)).order_by(Facility.name).all()
    )
    return [
        FacilityRead(
            id=facility.id,
            name=facility.name,
            facility_type=facility.facility_type,
            field_id=facility.field_id,
            field_name=facility.field.name,
        )
        for facility in facilities
    ]
