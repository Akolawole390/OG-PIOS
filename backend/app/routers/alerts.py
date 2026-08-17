from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from uuid import uuid4

from app.core.database import get_db
from app.deps import get_current_user, require_role
from app.models.ai import Alert, AlertStatusHistory
from app.models.equipment import Equipment, MaintenanceRecord
from app.models.field import Facility, Field, Well
from app.models.user import User
from app.schemas.alerts import (
    AlertCreate,
    AlertEntry,
    AlertHistoryEntry,
    AlertHistoryResponse,
    AlertListResponse,
    AlertRunCategoryResult,
    AlertRunResponse,
    AlertStatusChangeRequest,
    AlertSummaryResponse,
    AlertUpdate,
    CategoryCount,
    ScopeCount,
    SeverityCounts,
    StatusCounts,
)
from app.services.alert_rules import ALERT_DISCLAIMER, run_alert_rules

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Any authenticated user except Viewer — these are operational actions (acknowledge/
# investigate/resolve/dismiss/notes), not a single domain's write privilege. Viewer is
# read-only everywhere else in the app; this simply extends that existing line.
NON_VIEWER_ROLES = (
    "Administrator",
    "Production Operator",
    "Production Engineer",
    "Maintenance Engineer",
    "Management",
    "Analyst",
)

SORTABLE_FIELDS = {
    "triggered_at": Alert.triggered_at,
    "last_detected_at": Alert.last_detected_at,
    "severity": Alert.severity,
    "status": Alert.state,
    "title": Alert.title,
    "category": Alert.category,
}

OPEN_STATES = ("new", "acknowledged", "investigating")


def _alert_query(db: Session):
    return db.query(Alert).options(
        joinedload(Alert.well),
        joinedload(Alert.field),
        joinedload(Alert.facility),
        joinedload(Alert.equipment),
        joinedload(Alert.maintenance_record),
        joinedload(Alert.acknowledged_by),
        joinedload(Alert.resolved_by),
    )


def _build_entry(alert: Alert) -> AlertEntry:
    return AlertEntry(
        id=alert.id,
        alert_type=alert.alert_type,
        category=alert.category,
        source_module=alert.source_module,
        severity=alert.severity,
        status=alert.state,
        title=alert.title,
        description=alert.description,
        recommended_action=alert.recommended_action,
        notes=alert.notes,
        well_id=alert.well_id,
        well_code=alert.well.well_id if alert.well else None,
        field_id=alert.field_id,
        field_name=alert.field.name if alert.field else None,
        facility_id=alert.facility_id,
        facility_name=alert.facility.name if alert.facility else None,
        equipment_id=alert.equipment_id,
        equipment_tag=alert.equipment.equipment_tag if alert.equipment else None,
        maintenance_record_id=alert.maintenance_record_id,
        maintenance_work_order_number=(
            alert.maintenance_record.work_order_number if alert.maintenance_record else None
        ),
        production_loss_id=alert.production_loss_id,
        threshold_value=alert.threshold_value,
        current_value=alert.current_value,
        unit=alert.unit,
        dedup_key=alert.dedup_key,
        occurrence_count=alert.occurrence_count,
        triggered_at=alert.triggered_at,
        last_detected_at=alert.last_detected_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        acknowledged_by_name=alert.acknowledged_by.full_name if alert.acknowledged_by else None,
        resolved_by_name=alert.resolved_by.full_name if alert.resolved_by else None,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        disclaimer_text=ALERT_DISCLAIMER,
    )


def _get_alert_or_404(db: Session, id: int) -> Alert:
    alert = _alert_query(db).filter(Alert.id == id).first()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


def _transition(db: Session, alert: Alert, to_state: str, current_user: User, note: str | None) -> Alert:
    now = datetime.now(timezone.utc)
    from_state = alert.state
    alert.state = to_state
    if to_state == "acknowledged":
        alert.acknowledged_at = now
        alert.acknowledged_by_id = current_user.id
    elif to_state == "resolved":
        alert.resolved_at = now
        alert.resolved_by_id = current_user.id
    if note:
        alert.notes = note
    db.add(
        AlertStatusHistory(
            alert_id=alert.id,
            from_state=from_state,
            to_state=to_state,
            note=note,
            changed_by_id=current_user.id,
            changed_at=now,
        )
    )
    db.commit()
    return _get_alert_or_404(db, alert.id)


# ----- List / create (must come before the /{id} routes below) -----


@router.get("", response_model=AlertListResponse)
def list_alerts(
    search: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    field_id: int | None = None,
    facility_id: int | None = None,
    well_id: int | None = None,
    equipment_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "triggered_at",
    order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertListResponse:
    query = _alert_query(db)

    if search:
        like = f"%{search}%"
        query = query.filter((Alert.title.ilike(like)) | (Alert.description.ilike(like)))
    if severity:
        query = query.filter(Alert.severity == severity)
    if category:
        query = query.filter(Alert.category == category)
    if status_filter:
        query = query.filter(Alert.state == status_filter)
    if field_id:
        query = query.filter(Alert.field_id == field_id)
    if facility_id:
        query = query.filter(Alert.facility_id == facility_id)
    if well_id:
        query = query.filter(Alert.well_id == well_id)
    if equipment_id:
        query = query.filter(Alert.equipment_id == equipment_id)
    if date_from:
        query = query.filter(Alert.triggered_at >= date_from)
    if date_to:
        # date_to is a calendar date (no time-of-day); triggered_at is a timestamp, so an
        # inclusive "<=" comparison against midnight would silently exclude every event later
        # that same day (e.g. date_to=today would drop today's own alerts). Compare against the
        # start of the following day instead, so the whole of date_to is included.
        query = query.filter(Alert.triggered_at < date_to + timedelta(days=1))

    total = query.count()

    sort_column = SORTABLE_FIELDS.get(sort, Alert.triggered_at)
    sort_column = sort_column.desc() if order == "desc" else sort_column.asc()
    query = query.order_by(sort_column)

    records = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [_build_entry(a) for a in records]

    return AlertListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=AlertEntry, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Management")),
) -> AlertEntry:
    for model, field_id in (
        (Field, payload.field_id),
        (Facility, payload.facility_id),
        (Well, payload.well_id),
        (Equipment, payload.equipment_id),
    ):
        if field_id is not None and db.get(model, field_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{model.__name__} not found"
            )
    if payload.maintenance_record_id is not None and db.get(MaintenanceRecord, payload.maintenance_record_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maintenance record not found")

    now = datetime.now(timezone.utc)
    # dedup_key is namespaced "manual:{uuid}" so the rule engine's dedup lookup and
    # auto-resolve sweep never touch a manually created alert.
    alert = Alert(
        alert_type=payload.alert_type,
        category=payload.category,
        source_module="manual",
        severity=payload.severity,
        state="new",
        title=payload.title,
        description=payload.description,
        recommended_action=payload.recommended_action,
        notes=payload.notes,
        well_id=payload.well_id,
        field_id=payload.field_id,
        facility_id=payload.facility_id,
        equipment_id=payload.equipment_id,
        maintenance_record_id=payload.maintenance_record_id,
        production_loss_id=payload.production_loss_id,
        threshold_value=payload.threshold_value,
        current_value=payload.current_value,
        unit=payload.unit,
        dedup_key=f"manual:{uuid4()}",
        occurrence_count=1,
        triggered_at=now,
        last_detected_at=now,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    db.add(AlertStatusHistory(alert_id=alert.id, from_state=None, to_state="new", changed_by_id=current_user.id, changed_at=now))
    db.commit()

    return _build_entry(_get_alert_or_404(db, alert.id))


@router.get("/summary", response_model=AlertSummaryResponse)
def get_alert_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertSummaryResponse:
    all_alerts = _alert_query(db).all()

    severity_counts = SeverityCounts()
    status_counts = StatusCounts()
    category_totals: dict[str, int] = {}
    field_totals: dict[str, str] = {}
    field_counts: dict[str, int] = {}
    equipment_totals: dict[str, str] = {}
    equipment_counts: dict[str, int] = {}
    open_count = 0

    for alert in all_alerts:
        if hasattr(severity_counts, alert.severity):
            setattr(severity_counts, alert.severity, getattr(severity_counts, alert.severity) + 1)
        if hasattr(status_counts, alert.state):
            setattr(status_counts, alert.state, getattr(status_counts, alert.state) + 1)
        if alert.state in OPEN_STATES:
            open_count += 1
        category_totals[alert.category] = category_totals.get(alert.category, 0) + 1
        if alert.field_id is not None:
            key = str(alert.field_id)
            field_totals[key] = alert.field.name if alert.field else key
            field_counts[key] = field_counts.get(key, 0) + 1
        if alert.equipment_id is not None:
            key = str(alert.equipment_id)
            equipment_totals[key] = alert.equipment.equipment_tag if alert.equipment else key
            equipment_counts[key] = equipment_counts.get(key, 0) + 1

    recent = sorted(all_alerts, key=lambda a: a.triggered_at, reverse=True)[:10]

    return AlertSummaryResponse(
        total=len(all_alerts),
        open_count=open_count,
        by_severity=severity_counts,
        by_status=status_counts,
        by_category=[CategoryCount(category=c, count=n) for c, n in sorted(category_totals.items())],
        by_field=[
            ScopeCount(key=k, label=field_totals[k], count=n)
            for k, n in sorted(field_counts.items(), key=lambda kv: -kv[1])
        ],
        by_equipment=[
            ScopeCount(key=k, label=equipment_totals[k], count=n)
            for k, n in sorted(equipment_counts.items(), key=lambda kv: -kv[1])[:10]
        ],
        recent=[_build_entry(a) for a in recent],
        disclaimer_text=ALERT_DISCLAIMER,
    )


@router.post("/run", response_model=AlertRunResponse)
def trigger_alert_run(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator")),
) -> AlertRunResponse:
    result = run_alert_rules(db)
    return AlertRunResponse(
        created=result.created,
        updated=result.updated,
        auto_resolved=result.auto_resolved,
        by_category={k: AlertRunCategoryResult(**v) for k, v in result.by_category.items()},
        disclaimer_text=result.disclaimer_text,
    )


# ----- Single-alert routes -----


@router.get("/{id}", response_model=AlertEntry)
def get_alert(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertEntry:
    return _build_entry(_get_alert_or_404(db, id))


@router.put("/{id}", response_model=AlertEntry)
def update_alert(
    id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("Administrator", "Management")),
) -> AlertEntry:
    alert = _get_alert_or_404(db, id)
    update_data = payload.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        setattr(alert, field_name, value)
    db.commit()
    db.refresh(alert)
    return _build_entry(_get_alert_or_404(db, id))


@router.get("/{id}/history", response_model=AlertHistoryResponse)
def get_alert_history(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertHistoryResponse:
    _get_alert_or_404(db, id)
    rows = (
        db.query(AlertStatusHistory)
        .options(joinedload(AlertStatusHistory.changed_by))
        .filter(AlertStatusHistory.alert_id == id)
        .order_by(AlertStatusHistory.changed_at.desc())
        .all()
    )
    items = [
        AlertHistoryEntry(
            id=r.id,
            from_state=r.from_state,
            to_state=r.to_state,
            note=r.note,
            changed_by_name=r.changed_by.full_name if r.changed_by else None,
            changed_at=r.changed_at,
        )
        for r in rows
    ]
    return AlertHistoryResponse(items=items)


@router.put("/{id}/acknowledge", response_model=AlertEntry)
def acknowledge_alert(
    id: int,
    payload: AlertStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> AlertEntry:
    alert = _get_alert_or_404(db, id)
    alert = _transition(db, alert, "acknowledged", current_user, payload.note)
    return _build_entry(alert)


@router.put("/{id}/investigate", response_model=AlertEntry)
def investigate_alert(
    id: int,
    payload: AlertStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> AlertEntry:
    alert = _get_alert_or_404(db, id)
    alert = _transition(db, alert, "investigating", current_user, payload.note)
    return _build_entry(alert)


@router.put("/{id}/resolve", response_model=AlertEntry)
def resolve_alert(
    id: int,
    payload: AlertStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> AlertEntry:
    alert = _get_alert_or_404(db, id)
    alert = _transition(db, alert, "resolved", current_user, payload.note)
    return _build_entry(alert)


@router.put("/{id}/dismiss", response_model=AlertEntry)
def dismiss_alert(
    id: int,
    payload: AlertStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> AlertEntry:
    alert = _get_alert_or_404(db, id)
    alert = _transition(db, alert, "dismissed", current_user, payload.note)
    return _build_entry(alert)


@router.post("/{id}/notes", response_model=AlertEntry)
def add_alert_note(
    id: int,
    payload: AlertStatusChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*NON_VIEWER_ROLES)),
) -> AlertEntry:
    if not payload.note:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="note is required")
    alert = _get_alert_or_404(db, id)
    now = datetime.now(timezone.utc)
    alert.notes = payload.note
    db.add(
        AlertStatusHistory(
            alert_id=alert.id,
            from_state=alert.state,
            to_state=alert.state,
            note=payload.note,
            changed_by_id=current_user.id,
            changed_at=now,
        )
    )
    db.commit()
    db.refresh(alert)
    return _build_entry(_get_alert_or_404(db, id))
