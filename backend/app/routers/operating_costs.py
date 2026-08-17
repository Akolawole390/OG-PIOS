from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.economics import OperatingCost
from app.models.equipment import Equipment
from app.models.field import Facility, Field, Well
from app.models.user import User
from app.routers.equipment import _resolve_scope
from app.schemas.economics import (
    OperatingCostCreate,
    OperatingCostEntry,
    OperatingCostListResponse,
    OperatingCostUpdate,
)

router = APIRouter(prefix="/operating-costs", tags=["operating-costs"])

SORTABLE_FIELDS = {
    "cost_date": OperatingCost.cost_date,
    "category": OperatingCost.category,
    "amount": OperatingCost.amount,
    "currency": OperatingCost.currency,
}


def _cost_query(db: Session):
    return db.query(OperatingCost).options(
        joinedload(OperatingCost.field),
        joinedload(OperatingCost.facility).joinedload(Facility.field),
        joinedload(OperatingCost.well).joinedload(Well.facility).joinedload(Facility.field),
        joinedload(OperatingCost.equipment).joinedload(Equipment.well).joinedload(Well.facility).joinedload(
            Facility.field
        ),
        joinedload(OperatingCost.equipment).joinedload(Equipment.facility).joinedload(Facility.field),
    )


def _resolve_cost_scope(cost: OperatingCost) -> tuple[int | None, str | None, int | None, str | None]:
    """Returns (field_id, field_name, facility_id, facility_name) — resolved via whichever of
    field/facility/well/equipment is set on the record, same fallback-through-the-hierarchy
    principle Equipment/Maintenance/Production Loss all apply to their own scope resolution
    (never store a field_id redundantly when it's derivable)."""
    if cost.field_id and cost.field:
        return cost.field.id, cost.field.name, cost.facility_id, (cost.facility.name if cost.facility else None)
    if cost.facility_id and cost.facility:
        field = cost.facility.field
        return field.id, field.name, cost.facility.id, cost.facility.name
    if cost.well_id and cost.well:
        facility = cost.well.facility
        return facility.field_id, facility.field.name, facility.id, facility.name
    if cost.equipment_id and cost.equipment:
        field_id, field_name, facility_id, facility_name, _, _ = _resolve_scope(cost.equipment)
        return field_id, field_name, facility_id, facility_name
    return None, None, None, None


def _build_entry(cost: OperatingCost) -> OperatingCostEntry:
    # field_id/facility_id/well_id/equipment_id stay as the RAW stored values (OperatingCost,
    # unlike Equipment, stores all four independently — an edit form must see exactly what's
    # set, not a resolved cascade, or resubmitting an unchanged well-only record could
    # silently write a facility_id that was never really there). Only the *_name display
    # fields resolve through the fallback hierarchy, so a cost linked only via well_id or
    # equipment_id still shows a human-readable field/facility name.
    _, field_name, _, facility_name = _resolve_cost_scope(cost)
    return OperatingCostEntry(
        id=cost.id,
        cost_date=cost.cost_date,
        category=cost.category,
        amount=cost.amount,
        currency=cost.currency,
        description=cost.description,
        cost_period=cost.cost_period,
        source=cost.source,
        notes=cost.notes,
        field_id=cost.field_id,
        field_name=field_name,
        facility_id=cost.facility_id,
        facility_name=facility_name,
        well_id=cost.well_id,
        well_code=cost.well.well_id if cost.well else None,
        equipment_id=cost.equipment_id,
        equipment_tag=cost.equipment.equipment_tag if cost.equipment else None,
        created_at=cost.created_at,
        updated_at=cost.updated_at,
    )


def _get_cost_or_404(db: Session, id: int) -> OperatingCost:
    cost = _cost_query(db).filter(OperatingCost.id == id).first()
    if cost is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operating cost record not found")
    return cost


def _validate_references(db: Session, payload) -> None:
    if payload.field_id is not None and db.get(Field, payload.field_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Field not found")
    if payload.facility_id is not None and db.get(Facility, payload.facility_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    if payload.well_id is not None and db.get(Well, payload.well_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")
    if payload.equipment_id is not None and db.get(Equipment, payload.equipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")


@router.get("", response_model=OperatingCostListResponse)
def list_operating_costs(
    search: str | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    equipment_id: int | None = None,
    category: str | None = None,
    currency: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "cost_date",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OperatingCostListResponse:
    query = _cost_query(db)

    if search:
        like = f"%{search}%"
        query = query.filter(OperatingCost.description.ilike(like))
    if field_id:
        query = query.filter(OperatingCost.field_id == field_id)
    if facility_id:
        query = query.filter(OperatingCost.facility_id == facility_id)
    if well_id:
        query = query.filter(OperatingCost.well_id == well_id)
    if equipment_id:
        query = query.filter(OperatingCost.equipment_id == equipment_id)
    if category:
        query = query.filter(OperatingCost.category == category)
    if currency:
        query = query.filter(OperatingCost.currency == currency)
    if date_from:
        query = query.filter(OperatingCost.cost_date >= date_from)
    if date_to:
        query = query.filter(OperatingCost.cost_date <= date_to)

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, OperatingCost.cost_date)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [_build_entry(r) for r in records]

    return OperatingCostListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=OperatingCostEntry, status_code=status.HTTP_201_CREATED)
def create_operating_cost(
    payload: OperatingCostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Management")),
) -> OperatingCostEntry:
    _validate_references(db, payload)

    cost = OperatingCost(**payload.model_dump())
    db.add(cost)
    db.commit()
    db.refresh(cost)

    return _build_entry(_get_cost_or_404(db, cost.id))


@router.get("/{id}", response_model=OperatingCostEntry)
def get_operating_cost(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OperatingCostEntry:
    return _build_entry(_get_cost_or_404(db, id))


@router.put("/{id}", response_model=OperatingCostEntry)
def update_operating_cost(
    id: int,
    payload: OperatingCostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Management")),
) -> OperatingCostEntry:
    cost = _get_cost_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)

    _validate_references(db, payload)

    for field_name, value in update_data.items():
        setattr(cost, field_name, value)

    db.commit()
    db.refresh(cost)

    return _build_entry(_get_cost_or_404(db, id))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_operating_cost(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Management")),
) -> None:
    cost = _get_cost_or_404(db, id)
    db.delete(cost)
    db.commit()
