from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.economics import CommodityPrice, ProductionLoss
from app.models.equipment import DowntimeEvent, Equipment, MaintenanceRecord
from app.models.field import Facility, Well
from app.models.production import ProductionRecord
from app.models.user import User
from app.routers.equipment import _resolve_scope
from app.routers.production import _resolve_target
from app.schemas.production_loss import (
    ProductionLossByScopeResponse,
    ProductionLossCategoryCount,
    ProductionLossCreate,
    ProductionLossDashboardResponse,
    ProductionLossEntry,
    ProductionLossListResponse,
    ProductionLossScopeBar,
    ProductionLossTrendPoint,
    ProductionLossTrendResponse,
    ProductionLossUpdate,
)
from app.services.production_loss_calculations import (
    PRODUCTION_LOSS_DISCLAIMER,
    estimate_revenue_impact,
    estimate_volume_loss,
)

router = APIRouter(prefix="/production-loss", tags=["production-loss"])

SORTABLE_FIELDS = {
    "loss_date": ProductionLoss.loss_date,
    "estimated_bopd_lost": ProductionLoss.estimated_bopd_lost,
    "estimated_mscf_lost": ProductionLoss.estimated_mscf_lost,
    "estimated_revenue_impact": ProductionLoss.estimated_revenue_impact,
    "downtime_hours": ProductionLoss.downtime_hours,
}

RECOMPUTE_TRIGGER_FIELDS = {"well_id", "loss_date", "downtime_event_id", "maintenance_record_id"}
COMPUTED_FIELDS = ("estimated_bopd_lost", "estimated_mscf_lost", "estimated_revenue_impact", "currency", "downtime_hours")


# ----- Shared helpers -----


def _loss_query(db: Session):
    return db.query(ProductionLoss).options(
        joinedload(ProductionLoss.well).joinedload(Well.facility).joinedload(Facility.field),
        joinedload(ProductionLoss.equipment).joinedload(Equipment.well).joinedload(Well.facility).joinedload(
            Facility.field
        ),
        joinedload(ProductionLoss.equipment).joinedload(Equipment.facility).joinedload(Facility.field),
        joinedload(ProductionLoss.downtime_event),
        joinedload(ProductionLoss.maintenance_record),
    )


def _resolve_loss_scope(loss: ProductionLoss) -> tuple[int | None, str | None, int | None, str | None]:
    """Returns (field_id, field_name, facility_id, facility_name) — well-first, falling back
    to the linked equipment's own scope resolution when there's no direct well link."""
    if loss.well_id and loss.well:
        facility = loss.well.facility
        field = facility.field
        return field.id, field.name, facility.id, facility.name
    if loss.equipment_id and loss.equipment:
        field_id, field_name, facility_id, facility_name, _, _ = _resolve_scope(loss.equipment)
        return field_id, field_name, facility_id, facility_name
    return None, None, None, None


def _resolve_commodity_price(db: Session, commodity: str, on_date: date) -> CommodityPrice | None:
    return (
        db.query(CommodityPrice)
        .filter(CommodityPrice.commodity == commodity, CommodityPrice.effective_date <= on_date)
        .order_by(CommodityPrice.effective_date.desc())
        .first()
    )


def _compute_derived_fields(
    db: Session,
    loss: ProductionLoss,
    downtime_event: DowntimeEvent | None,
    maintenance_record: MaintenanceRecord | None,
) -> None:
    """Fills in whatever of downtime_hours/estimated_bopd_lost/estimated_mscf_lost/
    estimated_revenue_impact/currency are still None, using real recorded data — never
    overwrites a value the caller already set (manual override wins). See
    services/production_loss_calculations.py for the disclaimer and documented method."""
    if loss.downtime_hours is None:
        if downtime_event is not None and downtime_event.end_time is not None:
            loss.downtime_hours = round(
                (downtime_event.end_time - downtime_event.start_time).total_seconds() / 3600, 2
            )
        elif maintenance_record is not None and maintenance_record.downtime_hours is not None:
            loss.downtime_hours = maintenance_record.downtime_hours

    expected_oil = expected_gas = actual_oil = actual_gas = None
    if loss.well_id is not None:
        target = _resolve_target(db, loss.well_id, loss.loss_date)
        if target is not None:
            expected_oil = target.oil_target_bopd
            expected_gas = target.gas_target_mscfd
        record = (
            db.query(ProductionRecord)
            .filter(ProductionRecord.well_id == loss.well_id, ProductionRecord.record_date == loss.loss_date)
            .first()
        )
        if record is not None:
            actual_oil = record.oil_bopd
            actual_gas = record.gas_mscfd

    auto_oil_lost, auto_gas_lost = estimate_volume_loss(expected_oil, actual_oil, expected_gas, actual_gas)
    if loss.estimated_bopd_lost is None:
        loss.estimated_bopd_lost = auto_oil_lost
    if loss.estimated_mscf_lost is None:
        loss.estimated_mscf_lost = auto_gas_lost

    oil_price_row = _resolve_commodity_price(db, "oil", loss.loss_date)
    gas_price_row = _resolve_commodity_price(db, "gas", loss.loss_date)
    oil_price = oil_price_row.price if oil_price_row else None
    gas_price = gas_price_row.price if gas_price_row else None

    if loss.estimated_revenue_impact is None:
        loss.estimated_revenue_impact = estimate_revenue_impact(
            loss.estimated_bopd_lost, loss.estimated_mscf_lost, oil_price, gas_price
        )
    if loss.currency is None and loss.estimated_revenue_impact is not None:
        loss.currency = (oil_price_row.currency if oil_price_row else None) or (
            gas_price_row.currency if gas_price_row else None
        )


def _build_entry(db: Session, loss: ProductionLoss) -> ProductionLossEntry:
    field_id, field_name, facility_id, facility_name = _resolve_loss_scope(loss)
    oil_price_row = _resolve_commodity_price(db, "oil", loss.loss_date)
    gas_price_row = _resolve_commodity_price(db, "gas", loss.loss_date)

    return ProductionLossEntry(
        id=loss.id,
        loss_date=loss.loss_date,
        category=loss.category,
        cause=loss.cause,
        downtime_hours=loss.downtime_hours,
        well_id=loss.well_id,
        well_code=loss.well.well_id if loss.well else None,
        equipment_id=loss.equipment_id,
        equipment_tag=loss.equipment.equipment_tag if loss.equipment else None,
        equipment_name=(loss.equipment.name or loss.equipment.equipment_tag) if loss.equipment else None,
        field_id=field_id,
        field_name=field_name,
        facility_id=facility_id,
        facility_name=facility_name,
        downtime_event_id=loss.downtime_event_id,
        maintenance_record_id=loss.maintenance_record_id,
        work_order_number=loss.maintenance_record.work_order_number if loss.maintenance_record else None,
        estimated_bopd_lost=loss.estimated_bopd_lost,
        estimated_mscf_lost=loss.estimated_mscf_lost,
        estimated_revenue_impact=loss.estimated_revenue_impact,
        currency=loss.currency,
        oil_price_per_bbl=oil_price_row.price if oil_price_row else None,
        gas_price_per_mscf=gas_price_row.price if gas_price_row else None,
        disclaimer_text=PRODUCTION_LOSS_DISCLAIMER,
        created_at=loss.created_at,
        updated_at=loss.updated_at,
    )


def _get_loss_or_404(db: Session, id: int) -> ProductionLoss:
    loss = _loss_query(db).filter(ProductionLoss.id == id).first()
    if loss is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production loss record not found")
    return loss


# ----- List / create -----


@router.get("", response_model=ProductionLossListResponse)
def list_production_loss(
    search: str | None = None,
    well_id: int | None = None,
    equipment_id: int | None = None,
    field_id: int | None = None,
    facility_id: int | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "loss_date",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionLossListResponse:
    query = _loss_query(db)

    if search:
        like = f"%{search}%"
        query = query.filter(ProductionLoss.cause.ilike(like))
    if well_id:
        query = query.filter(ProductionLoss.well_id == well_id)
    if equipment_id:
        query = query.filter(ProductionLoss.equipment_id == equipment_id)
    if facility_id:
        query = query.filter(
            or_(
                ProductionLoss.well.has(Well.facility_id == facility_id),
                ProductionLoss.equipment.has(
                    or_(Equipment.facility_id == facility_id, Equipment.well.has(Well.facility_id == facility_id))
                ),
            )
        )
    if field_id:
        query = query.filter(
            or_(
                ProductionLoss.well.has(Well.facility.has(Facility.field_id == field_id)),
                ProductionLoss.equipment.has(
                    or_(
                        Equipment.facility.has(Facility.field_id == field_id),
                        Equipment.well.has(Well.facility.has(Facility.field_id == field_id)),
                    )
                ),
            )
        )
    if category:
        query = query.filter(ProductionLoss.category == category)
    if date_from:
        query = query.filter(ProductionLoss.loss_date >= date_from)
    if date_to:
        query = query.filter(ProductionLoss.loss_date <= date_to)

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, ProductionLoss.loss_date)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [_build_entry(db, r) for r in records]

    return ProductionLossListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=ProductionLossEntry, status_code=status.HTTP_201_CREATED)
def create_production_loss(
    payload: ProductionLossCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ProductionLossEntry:
    if payload.well_id is not None and db.get(Well, payload.well_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")
    if payload.equipment_id is not None and db.get(Equipment, payload.equipment_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")

    downtime_event = None
    if payload.downtime_event_id is not None:
        downtime_event = db.get(DowntimeEvent, payload.downtime_event_id)
        if downtime_event is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Downtime event not found")

    maintenance_record = None
    if payload.maintenance_record_id is not None:
        maintenance_record = db.get(MaintenanceRecord, payload.maintenance_record_id)
        if maintenance_record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance record not found")

    loss = ProductionLoss(**payload.model_dump())
    _compute_derived_fields(db, loss, downtime_event, maintenance_record)
    db.add(loss)
    db.commit()
    db.refresh(loss)

    return _build_entry(db, _get_loss_or_404(db, loss.id))


# ----- Fixed sub-paths (must be registered before /{id}) -----


@router.get("/dashboard", response_model=ProductionLossDashboardResponse)
def get_production_loss_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionLossDashboardResponse:
    losses = db.query(ProductionLoss).all()

    downtime_values = [loss.downtime_hours for loss in losses if loss.downtime_hours is not None]

    category_counts: dict[str, int] = {}
    for loss in losses:
        key = loss.category or "uncategorized"
        category_counts[key] = category_counts.get(key, 0) + 1
    by_category = [
        ProductionLossCategoryCount(category=k, count=v)
        for k, v in sorted(category_counts.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return ProductionLossDashboardResponse(
        event_count=len(losses),
        total_oil_bopd_lost=round(sum(loss.estimated_bopd_lost or 0 for loss in losses), 2),
        total_gas_mscfd_lost=round(sum(loss.estimated_mscf_lost or 0 for loss in losses), 2),
        total_revenue_impact=round(sum(loss.estimated_revenue_impact or 0 for loss in losses), 2),
        avg_downtime_hours=round(sum(downtime_values) / len(downtime_values), 2) if downtime_values else 0.0,
        by_category=by_category,
        disclaimer_text=PRODUCTION_LOSS_DISCLAIMER,
    )


@router.get("/by-scope", response_model=ProductionLossByScopeResponse)
def get_production_loss_by_scope(
    group_by: str = Query("category", pattern="^(category|well|equipment|field)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionLossByScopeResponse:
    losses = _loss_query(db).all()

    groups: dict[str, dict] = {}
    for loss in losses:
        if group_by == "category":
            key = label = loss.category or "uncategorized"
        elif group_by == "well":
            if not loss.well_id or not loss.well:
                continue
            key, label = str(loss.well_id), loss.well.well_id
        elif group_by == "equipment":
            if not loss.equipment_id or not loss.equipment:
                continue
            key, label = str(loss.equipment_id), loss.equipment.equipment_tag
        else:
            field_id, field_name, _, _ = _resolve_loss_scope(loss)
            if field_id is None:
                continue
            key, label = str(field_id), field_name

        bucket = groups.setdefault(key, {"label": label, "count": 0, "oil": 0.0, "gas": 0.0, "revenue": 0.0})
        bucket["count"] += 1
        bucket["oil"] += loss.estimated_bopd_lost or 0
        bucket["gas"] += loss.estimated_mscf_lost or 0
        bucket["revenue"] += loss.estimated_revenue_impact or 0

    bars = [
        ProductionLossScopeBar(
            key=key,
            label=b["label"],
            count=b["count"],
            total_oil_bopd_lost=round(b["oil"], 2),
            total_gas_mscfd_lost=round(b["gas"], 2),
            total_revenue_impact=round(b["revenue"], 2),
        )
        for key, b in groups.items()
    ]
    bars.sort(key=lambda b: b.total_revenue_impact, reverse=True)
    return ProductionLossByScopeResponse(group_by=group_by, bars=bars)


@router.get("/trend", response_model=ProductionLossTrendResponse)
def get_production_loss_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionLossTrendResponse:
    losses = db.query(ProductionLoss).all()

    buckets: dict[str, dict] = {}
    for loss in losses:
        month_key = loss.loss_date.strftime("%Y-%m")
        bucket = buckets.setdefault(month_key, {"oil": 0.0, "gas": 0.0, "revenue": 0.0, "count": 0})
        bucket["oil"] += loss.estimated_bopd_lost or 0
        bucket["gas"] += loss.estimated_mscf_lost or 0
        bucket["revenue"] += loss.estimated_revenue_impact or 0
        bucket["count"] += 1

    points = [
        ProductionLossTrendPoint(
            month=month,
            total_oil_bopd_lost=round(b["oil"], 2),
            total_gas_mscfd_lost=round(b["gas"], 2),
            total_revenue_impact=round(b["revenue"], 2),
            event_count=b["count"],
        )
        for month, b in sorted(buckets.items())
    ]
    return ProductionLossTrendResponse(points=points)


# ----- Single-record routes -----


@router.get("/{id}", response_model=ProductionLossEntry)
def get_production_loss(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionLossEntry:
    return _build_entry(db, _get_loss_or_404(db, id))


@router.put("/{id}", response_model=ProductionLossEntry)
def update_production_loss(
    id: int,
    payload: ProductionLossUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> ProductionLossEntry:
    loss = _get_loss_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)

    if update_data.get("well_id") is not None and db.get(Well, update_data["well_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Well not found")
    if update_data.get("equipment_id") is not None and db.get(Equipment, update_data["equipment_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Equipment not found")

    downtime_event = None
    if update_data.get("downtime_event_id") is not None:
        downtime_event = db.get(DowntimeEvent, update_data["downtime_event_id"])
        if downtime_event is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Downtime event not found")

    maintenance_record = None
    if update_data.get("maintenance_record_id") is not None:
        maintenance_record = db.get(MaintenanceRecord, update_data["maintenance_record_id"])
        if maintenance_record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance record not found")

    needs_recompute = bool(RECOMPUTE_TRIGGER_FIELDS & update_data.keys())
    manually_set_this_request = {f for f in COMPUTED_FIELDS if f in update_data}

    for field_name, value in update_data.items():
        setattr(loss, field_name, value)

    if needs_recompute:
        # Reset any computed field not explicitly overridden in this same request, so a
        # changed well/date/link produces a genuine re-derivation instead of keeping a stale
        # cached number from before the change.
        for field_name in COMPUTED_FIELDS:
            if field_name not in manually_set_this_request:
                setattr(loss, field_name, None)

        if downtime_event is None and loss.downtime_event_id:
            downtime_event = db.get(DowntimeEvent, loss.downtime_event_id)
        if maintenance_record is None and loss.maintenance_record_id:
            maintenance_record = db.get(MaintenanceRecord, loss.maintenance_record_id)
        _compute_derived_fields(db, loss, downtime_event, maintenance_record)

    db.commit()
    db.refresh(loss)

    return _build_entry(db, _get_loss_or_404(db, id))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_production_loss(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Production Engineer")),
) -> None:
    loss = _get_loss_or_404(db, id)

    if loss.downtime_event_id is not None or loss.maintenance_record_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a production loss record linked to a downtime event or "
            "maintenance record — edit it instead to preserve the audit trail.",
        )

    db.delete(loss)
    db.commit()
